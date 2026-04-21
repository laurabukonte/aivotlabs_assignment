"""
In-memory session manager.

Each chat session maintains:
  - Full message history (for the LLM context window)
  - A step-by-step log with timestamps (for observability)
  - Booking draft state

Sessions are automatically cleaned up after the configured timeout.
"""

import time
from datetime import datetime
from typing import Any

from app.config import SESSION_TIMEOUT_SECONDS


class Session:
    """Represents a single user conversation."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.messages: list[dict] = []          # OpenAI-format messages
        self.booking_draft: dict = {}
        self.state = "greeting"                 # greeting → in_progress → booked
        self.created_at = datetime.now().isoformat()
        self.last_activity = time.time()
        self.log: list[dict] = []               # timestamped step log

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.last_activity) > SESSION_TIMEOUT_SECONDS

    def add_message(
        self,
        role: str,
        content: str | None,
        *,
        tool_calls: list[Any] | None = None,
        tool_call_id: str | None = None,
    ):
        message = {"role": role, "content": content}
        if tool_calls:
            message["tool_calls"] = [_serialize_tool_call(tool_call) for tool_call in tool_calls]
        if tool_call_id:
            message["tool_call_id"] = tool_call_id

        self.messages.append(message)
        self.last_activity = time.time()
        self.log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "event": "message",
                "role": role,
                "content": content or "",
            }
        )

    def add_tool_event(self, tool_name: str, args: dict, result: str):
        self.last_activity = time.time()
        self.log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "event": "tool_call",
                "tool": tool_name,
                "args": args,
                "result": result,
            }
        )

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "state": self.state,
            "booking_draft": self.booking_draft,
            "messages": self.messages,
            "created_at": self.created_at,
            "log": self.log,
        }


class SessionManager:
    """Thread-safe in-memory session store with automatic expiry."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, session_id: str) -> Session:
        self._cleanup_expired()
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id)
        session = self._sessions[session_id]
        session.last_activity = time.time()
        return session

    def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[str]:
        return list(self._sessions.keys())

    def _cleanup_expired(self):
        now = time.time()
        expired = [
            sid
            for sid, s in self._sessions.items()
            if now - s.last_activity > SESSION_TIMEOUT_SECONDS
        ]
        for sid in expired:
            del self._sessions[sid]


def _serialize_tool_call(tool_call: Any) -> dict:
    """Convert SDK tool call objects into plain dicts for message history."""
    if isinstance(tool_call, dict):
        return tool_call

    if hasattr(tool_call, "model_dump"):
        return tool_call.model_dump(exclude_none=True)

    function = getattr(tool_call, "function", None)
    function_payload = None
    if function is not None:
        if isinstance(function, dict):
            function_payload = function
        elif hasattr(function, "model_dump"):
            function_payload = function.model_dump(exclude_none=True)
        else:
            function_payload = {
                "name": getattr(function, "name", None),
                "arguments": getattr(function, "arguments", None),
            }

    payload = {
        "id": getattr(tool_call, "id", None),
        "type": getattr(tool_call, "type", "function"),
        "function": function_payload,
    }
    return {key: value for key, value in payload.items() if value is not None}
