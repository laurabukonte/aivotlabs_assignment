"""
LLM service - handles all interactions with the language model.

Responsibilities:
  - LLM client initialization
  - Tool execution dispatch
  - Iterative tool-call loop (including raw-text fallback)
  - Conversation turn management

Prompts and tool definitions live in app/prompts.py
"""

import json
import logging
import re

from openai import BadRequestError, OpenAI

from app.config import LLM_API_KEY, LLM_BASE_URL, LLM_MAX_TOOL_ROUNDS, LLM_MODEL
from app.prompts import SYSTEM_PROMPT, TOOLS
from app.services.booking import BookingService
from app.services.session import Session

logger = logging.getLogger("agent")


# LLM Service
class LLMService:
    """Manages LLM client and the multi-turn tool-calling conversation loop."""

    def __init__(self, booking_service: BookingService):
        self._client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY, default_headers={"HTTP-Referer": "https://aistudio.google.com/"} )
        self._booking = booking_service


    # ---------------------------------------------------------------------------
    # Main Conversation Logic
    # ---------------------------------------------------------------------------

    def get_reply(self, session: Session, user_message: str) -> str:
        """
        Process one user message and return the assistant reply.

        This method orchestrates the conversation turn, including:
        1. Sending the user message to the LLM.
        2. Handling structured tool calls in a loop.
        3. Falling back to raw-text tool call parsing if needed.
        4. Recovering from specific API errors.
        """
        sid = session.session_id[:8]
        logger.info("[%s] USER: %s", sid, user_message)
        session.add_message("user", user_message)

        # Initial request to the LLM
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + session.messages
        assistant_msg, recovered_reply = self._request_completion(session, messages, sid)

        if recovered_reply:
            return self._finalize_reply(session, sid, recovered_reply)

        # Main loop for tool calls
        reply = self._process_tool_calls(session, assistant_msg, sid)

        return self._finalize_reply(session, sid, reply)

    def _process_tool_calls(self, session: Session, assistant_msg, sid: str) -> str:
        """Handle the iterative tool-calling process."""
        rounds = 0
        while rounds < LLM_MAX_TOOL_ROUNDS:
            # First, try to process structured tool calls if they exist
            if assistant_msg.tool_calls:
                assistant_msg = self._process_structured_tool_calls(session, assistant_msg, sid)
                if assistant_msg is None:  # Recovery happened
                    return session.messages[-1].get("content", "")
                rounds += 1
                continue

            # If no structured calls, check for raw-text calls in the content
            reply_content = assistant_msg.content or ""
            raw_calls = _parse_raw_tool_calls(reply_content)
            if raw_calls:
                return self._process_raw_text_tool_calls(session, reply_content, raw_calls, sid)

            # If no more tool calls of any kind, break the loop
            return reply_content

        # If max rounds are exceeded, return the last content
        return assistant_msg.content or ""

    def _finalize_reply(self, session: Session, sid: str, reply: str) -> str:
        """Add the final reply to the session and log it."""
        session.add_message("assistant", reply)
        if session.state == "greeting":
            session.state = "in_progress"
        logger.info("[%s] AGENT: %s", sid, reply)
        return reply

    # ---------------------------------------------------------------------------
    # Tool Execution
    # ---------------------------------------------------------------------------

    def _execute_tool(self, session: Session, fn_name: str, fn_args: dict) -> str:
        """Dispatch to the appropriate tool implementation."""
        # Defensive checks for fn_args
        if fn_args is None:
            fn_args = {}
        if not isinstance(fn_args, dict):
            logger.error("fn_args is not a dict: %s (type: %s)", fn_args, type(fn_args))
            fn_args = {}

        if fn_name == "check_availability":
            return self._booking.check_availability(fn_args.get("appointment_type"))

        if fn_name == "book_appointment":
            return self._execute_book_appointment(fn_args)

        return f"Unknown function: {fn_name}"

    def _execute_book_appointment(self, fn_args: dict) -> str:
        """Handle the logic for the 'book_appointment' tool."""
        patient_name = (fn_args.get("patient_name") or "").strip()
        if not patient_name:
            return _ERR_NAME_MISSING
        if not _looks_like_full_name(patient_name):
            return _ERR_NAME_PARTIAL

        slot_id = (fn_args.get("slot_id") or "").strip()
        if not slot_id:
            return _ERR_SLOT_MISSING

        if not _is_true(fn_args.get("slot_confirmed", False)):
            return _ERR_NOT_CONFIRMED

        return self._booking.book_appointment(
            patient_name=patient_name,
            appointment_type=fn_args.get("appointment_type", ""),
            slot_id=slot_id,
        )

    # ---------------------------------------------------------------------------
    # API Interaction & Message Handling
    # ---------------------------------------------------------------------------

    def _request_completion(self, session: Session, messages: list[dict], sid: str):
        """Send a completion request to the LLM, with error recovery."""
        try:
            response = self._client.chat.completions.create(
                model=LLM_MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
            )
            return response.choices[0].message, None
        except BadRequestError as exc:
            recovered_reply = self._recover_from_failed_generation(session, sid, exc)
            if recovered_reply is not None:
                return None, recovered_reply
            raise

    def _process_structured_tool_calls(self, session: Session, assistant_msg, sid: str):
        """Process a list of structured tool calls from the LLM."""
        session.add_message("assistant", assistant_msg.content, tool_calls=assistant_msg.tool_calls)

        for tc in assistant_msg.tool_calls:
            fn_name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments) if tc.function.arguments else {}
            except (json.JSONDecodeError, TypeError) as e:
                logger.error("[%s] Failed to parse tool arguments: %s - Error: %s", sid, tc.function.arguments, e)
                fn_args = {}

            logger.info("[%s] TOOL CALL: %s(%s)", sid, fn_name, fn_args)
            result = self._execute_tool(session, fn_name, fn_args)
            logger.info("[%s] TOOL RESULT: %s", sid, result)

            session.add_tool_event(fn_name, fn_args, result)
            if fn_name == "book_appointment" and "vahvistettu" in result.lower():
                session.state = "booked"
            session.add_message("tool", result, tool_call_id=tc.id)

        # After processing, get the next message from the LLM
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + session.messages
        next_assistant_msg, recovered_reply = self._request_completion(session, messages, sid)
        if recovered_reply is not None:
            session.add_message("assistant", recovered_reply)
            return None  # Indicate recovery happened
        return next_assistant_msg

    # ---------------------------------------------------------------------------
    # Workaround/Recovery Helpers
    # ---------------------------------------------------------------------------

    def _process_raw_text_tool_calls(
        self, session: Session, reply: str, raw_calls: list, sid: str
    ) -> str:
        """Handle Llama-style raw-text function calls embedded in the reply."""
        cleaned_reply = _RAW_TOOL_RE.sub("", reply).strip()
        if cleaned_reply:
            session.add_message("assistant", cleaned_reply)

        for fn_name, fn_args in raw_calls:
            logger.info("[%s] RAW TOOL: %s(%s)", sid, fn_name, fn_args)
            result = self._execute_tool(session, fn_name, fn_args)
            logger.info("[%s] RAW TOOL RESULT: %s", sid, result)

            session.add_tool_event(fn_name, fn_args, result)
            if fn_name == "book_appointment" and "vahvistettu" in result.lower():
                session.state = "booked"
            session.add_message("user", f"[Järjestelmä: {fn_name} tulos: {result}]")

        # After processing raw calls, get the next message from the LLM
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + session.messages
        assistant_msg, recovered_reply = self._request_completion(session, messages, sid)
        if recovered_reply is not None:
            return recovered_reply

        return assistant_msg.content or ""

    def _recover_from_failed_generation(self, session: Session, sid: str, exc: BadRequestError) -> str | None:
        """Attempt to recover from a 400 error due to malformed tool call text."""
        failed_generation = _extract_failed_generation(exc)
        logger.warning("[%s] Tool use failed, attempting recovery. Error: %s", sid, str(exc))

        if not failed_generation:
            logger.error("[%s] Could not extract failed_generation from error.", sid)
            return None
        logger.warning("[%s] Extracted failed_generation: %s", sid, failed_generation)

        raw_calls = _parse_raw_tool_calls(failed_generation)
        if not raw_calls:
            logger.error("[%s] No raw tool calls found in failed_generation.", sid)
            return None

        logger.warning("[%s] Recovering, found %d raw tool calls.", sid, len(raw_calls))
        return self._process_raw_text_tool_calls(session, failed_generation, raw_calls, sid)


# ===========================================================================
# Regex for Llama-style raw text tool calls (this is workaround for Groq's current limitations in structured tool call parsing)
# ===========================================================================

# Supports variants like:
#   <function=check_availability>{"appointment_type":"Hammaslääkäriaika"}</function>
#   <function=check_availability={"appointment_type":"Hammaslääkäriaika"}></function>
_RAW_TOOL_RE = re.compile(
    r"<function=(\w+)(?:\s+(\{[^<]*?\})\s*>?|>\s*(\{[^<]*?\})\s*|[=:](\{[^<]*?\})\s*>?\s*|(\{[^<]*?\})\s*>?\s*)</function>",
    re.DOTALL,
)

_FAILED_GENERATION_RE = re.compile(r"['\"]failed_generation['\"]:\s*['\"](.*?)['\"]")

# ===========================================================================
# Tool result error messages (in Finnish — returned to the LLM as tool output)
# ===========================================================================
_ERR_NAME_MISSING   = "Virhe: patient_name puuttuu. Kysy potilaan koko nimi ennen varauksen tekemistä."
_ERR_NAME_PARTIAL   = "Virhe: Potilaan etu- ja sukunimi vaaditaan. Pyydä myös sukunimi."
_ERR_SLOT_MISSING   = "Virhe: Aikatunnus puuttuu. Kysy potilaalta valittu aika."
_ERR_NOT_CONFIRMED  = "Virhe: Aikaa ei ole vahvistettu. Varmista ensin, että aika on oikein."


# ===========================================================================
# Standalone Helper Functions
# ===========================================================================

def _parse_raw_tool_calls(text: str) -> list[tuple[str, dict]]:
    """Extract (fn_name, fn_args) from Llama-style raw text function calls."""
    results = []
    # Primary regex for standard cases
    for match in _RAW_TOOL_RE.finditer(text):
        fn_name = match.group(1)
        try:
            fn_args_str = match.group(2) or match.group(3) or match.group(4) or match.group(5)
            if fn_args_str:
                fn_args = json.loads(fn_args_str)
                results.append((fn_name, fn_args))
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse JSON from raw tool call: %s - Error: %s", fn_args_str, e)

    # Fallback for more permissive parsing if primary fails
    if not results:
        fallback_pattern = re.compile(
            r"<function=(\w+)(?:[>=:]|\s+)?\s*(\{.*?\})\s*>?\s*</function>",
            re.DOTALL,
        )
        for match in fallback_pattern.finditer(text):
            fn_name = match.group(1)
            try:
                fn_args = json.loads(match.group(2))
                results.append((fn_name, fn_args))
            except json.JSONDecodeError:
                pass  # Ignore errors in fallback
    return results


def _extract_failed_generation(exc: BadRequestError) -> str | None:
    """Extract the raw 'failed_generation' text from a provider 400 error."""
    sources = [
        lambda: exc.body.get("error", {}).get("failed_generation"),
        lambda: exc.response.json().get("error", {}).get("failed_generation"),
        lambda: _FAILED_GENERATION_RE.search(str(exc)).group(1).encode("utf-8").decode("unicode_escape")
    ]
    for source in sources:
        try:
            failed_text = source()
            if isinstance(failed_text, str) and failed_text.strip():
                return failed_text
        except (AttributeError, KeyError, IndexError, json.JSONDecodeError, TypeError):
            continue
    return None


def _looks_like_full_name(value: str) -> bool:
    """Check if a string looks like it contains at least a first and last name."""
    return len([p for p in (value or "").strip().split() if p]) >= 2


def _is_true(value) -> bool:
    """Check for truthiness in various forms."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "kyllä", "joo"}
    return value == 1

