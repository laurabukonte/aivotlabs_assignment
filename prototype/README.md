# Dental Clinic Appointment Agent – Prototype 

A very basic and minimal, Finnish-speaking chat  agent **Anna** that books dental clinic appointments. The agent guides patients through selecting an appointment type, choosing a slot, providing their name, confirming, and completing the booking, all in Finnish.

Built with FastAPI and an OpenAI-compatible LLM backend (default: Groq / Llama 3.3 70B) using structured function calling.

---

## What the Prototype Does

The agent acts as a receptionist for a fictional dental clinic. A patient opens a chat window and converses naturally in Finnish. Anna:

1. Greets the patient and asks how she can help
2. Identifies the appointment type (dentist, hygienist, or occupational health)
3. Calls `check_availability` to look up free slots
4. Presents the available options and lets the patient choose
5. Collects the patient's full name (first + last)
6. Asks for explicit confirmation before booking
7. Calls `book_appointment` and confirms the booking

Bookings are persisted to a local JSON file (`bookings_log.json`). Sessions expire after inactivity (configurable) and are managed in memory.

---

## Requirements

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- A Groq API key (free tier at [console.groq.com](https://console.groq.com)) — or any OpenAI-compatible provider

---

## Setup

```bash
cd prototype

# 1. Install dependencies
uv sync

# 2. Configure environment
cp .env.example .env      # or create .env manually
# Edit .env and set LLM_API_KEY

# 3. Start the server
uv run python -m app.main
```

Open **http://localhost:8000** and chat in Finnish.

---

## Environment Variables

`LLM_API_KEY` API key for the LLM provider (required) 
`LLM_BASE_URL`  =`https://api.groq.com/openai/v1`  OpenAI-compatible endpoint
`LLM_MODEL` = `llama-3.3-70b-versatile`  Model name 
`LLM_MAX_TOOL_ROUNDS` = `5`  Max tool-call iterations per turn 
`SESSION_TIMEOUT` = `400`  Session expiry in seconds 

**Example `.env` for Groq:**
```dotenv
LLM_API_KEY=gsk_...
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
```

**Example `.env` for Gemini:**
```dotenv
LLM_API_KEY=AIza...
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL=gemini-2.0-flash
```

---

## Example Conversation

```
USER:  Moi!
ANNA:  Hei! Olen Anna Hammashoitolasta. Kuinka voin auttaa sinua tänään?
USER:  Hammaslääkäriaika
ANNA:  Vapaat ajat: 21.04 klo 09:00 (slot-1), 21.04 klo 14:00 (slot-2). Kumpi sopii?
USER:  slot-1
ANNA:  Saanko nimenne varausta varten?
USER:  Laura Virtanen
ANNA:  Varaus vahvistettu! Laura Virtanen, Hammaslääkäriaika 21.04.2026 klo 09:00.
```

---

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Web UI |
| `POST` | `/chat` | Chat (`{message, session_id?}`) |
| `GET` | `/slots` | Appointment slots |
| `GET` | `/bookings` | Confirmed bookings |
| `GET` | `/sessions/{id}` | Session transcript & log |
| `POST` | `/reset-slots` | Reset slots to available ( helper) |
| `GET` | `/health` | Health check |

---

## Tests

```bash
uv run pytest tests/ -v          # unit tests (no API key needed)
```

---

## Project Structure

```
app/
├── main.py              # App factory, middleware, static mount
├── config.py            # All settings (env vars, paths, timeouts)
├── routes.py            # API endpoint handlers
├── prompts.py           # System prompt & tool definitions
├── services/
│   ├── booking.py       # Slot availability & booking persistence
│   ├── session.py       # In-memory session manager with expiry
│   └── llm.py           # LLM client, tool dispatch, conversation loop
├── static/
│   ├── style.css        # Styles
│   └── app.js           # Client-side logic & timeout handling
├── templates/
│   └── index.html       # HTML shell
└── data/
    └── slots.json       # Appointment slot data
tests/
├── test_booking.py      # BookingService & SessionManager unit tests
└── test_llm.py          # Raw tool-call parser & recovery helpers
```

---

## Design Focus & Compromises

### What was prioritised

In this prototype I focus on the LLM integration, the booking flow and the promt design and tool calling. A raw-text tool-call parser handles models that emit `<function=...>` (Groq does it) text instead of structured calls, with a separate recovery path for API `400` errors.
I try to make a solid base for the project by creating clear project structure - separating prompts, llm logic, booking and session logic.
LLM model can be changed just by changing the env variables.


### Compromises made

 **Input and Output**  - plain text, instead of audio and related tech
 **Persistence**  - JSON files instead of a database. Simple and inspectable for a prototype; not suitable for production or concurrent writes, real system would use postgresql
 **Sessions**  -  In-memory only, lost on restart. Sufficient for single-server demo; a real system would use Redis
 **Authentication** - No patient identity or access control
 **Slots** -  Static fixture file (`slots.json`) - No real calendar integration; slots are reset manually via `/reset-slots` 
