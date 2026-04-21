# Dental Clinic Appointment Agent – Prototype

Finnish-speaking appointment booking agent **Anna**, powered by FastAPI + Groq (Llama 3.3 70B) with LLM function calling.


## Requirements

Groq API key.

## Quick Start

```bash
cd prototype
uv sync                        # install dependencies
uv run python -m app.main       # start server on :8000
```

Open **http://localhost:8000** and chat in Finnish.

## Environment Variables

 `LMM_API_KEY` - Groq API key (required) 
 `BASE_URL` -  `https://api.groq.com/openai/v1`  LLM endpoint (OpenAI-compatible) 
 `LLM_MODEL` - `llama-3.3-70b-versatile` 


## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Web UI |
| `POST` | `/chat` | Chat (`{message, session_id?}`) |
| `GET` | `/slots` | Appointment slots |
| `GET` | `/bookings` | Confirmed bookings |
| `GET` | `/sessions/{id}` | Session transcript & log |
| `POST` | `/reset-slots` | Reset slots ( helper) |
| `GET` | `/health` | Health check |

## Conversation Flow

```
USER:  Moi!
ANNA:  Hei! Olen Anna Hammashoitolasta. Minkälaisen ajan haluaisitte varata?
USER:  Hammaslääkäriaika
ANNA:  Vapaat ajat: 21.04 klo 09:00 (slot-1), 21.04 klo 14:00 (slot-2). Kumpi sopii?
USER:  slot-1
ANNA:  Saanko nimenne varausta varten?
USER:  Laura Virtanen
ANNA:  Varaus vahvistettu! Laura Virtanen, Hammaslääkäriaika 21.04.2026 klo 09:00.
```

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
└── test_booking.py      # unit tests (BookingService, SessionManager, LMM)
```

## Tests

```bash
uv run pytest tests/test_booking.py -v          # unit tests (no API key needed)
```

## Key Design Decisions

| Decision | Rationale |
|---|---|
| In-memory sessions | Sufficient for single-server prototype |
| JSON file storage | Simple, inspectable, no external dependencies |
| Server-side name validation | LLM cannot book without patient name, enforced in code |
| Session timeout (10 min) | Client-side warning banner + server-side expiry |
| Raw tool-call parser | Catches Llama's occasional `<function=...>` text output |
| App factory pattern | Clean separation: config → services → routes → app |
| Separated prompts | Easy prompt/tool editing in `prompts.py` without touching LLM logic |
| Separated CSS/JS | Clean HTML template, reusable static assets |
