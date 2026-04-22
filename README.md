# AI Voice Agent – Project Overview

This repository contains a healthcare appointment booking voice-agent system design and description.


## Folder and File Overview

### Root folder
- `README.md` — this high-level project overview.
- `ARCHITECTURE.pdf` — architecture design document (system-level plan).
- `LauraBukonte_AivotLabs_VoiceAgentDesign.pdf` — design submission / supporting material.
- `Screen Recording ... .mov` — demo recording.
- `prototype/` — runnable FastAPI prototype - description in the prototype/README.md


## Architecture Focus (Main Pillars)

### 1 Security
Primary design target was handling healthcare-related data safely.

- **Isolated LLM**: the LLM is treated as an external reasoning component; booking and patient validation remains on the server side. Personal data never reaches LLM  (nor logs)
- **Data residency option (EU)**: architecture targets EU deployment regions to support GDPR-aligned data location requirements. (Azure)
- **Zero-retention capable providers**: provider choice favors APIs that support zero-retention modes where available.
- **Anonymisation layer**: transcripts can be redacted or pseudonymised before analytics/storage.
- **Least-privilege service design**: clear separation between telephony, agent logic, booking data, and observability.

### 2 Low Latency
Low response time is critical for natural voice interaction.

- **Streaming-first pipeline** (STT/LLM/TTS) reduces turn time versus batch processing.
- **Fast inference providers** reduce model delay. (Azure is relatively fast, Groq is reported faster but Azure is more secure)
- **Short prompt + structured tool calls** lowers token usage and round trips.
- **In-memory session state** avoids slow storage access in  calls. (Redis)

### 3 Scalability
The architecture is designed to scale from prototype to production.

- **Vapi-ready voice orchestration** simplifies scaling concurrent call handling.
- **Kubernetes-native deployment path** enables horizontal scaling, rolling updates, and fault isolation.
- **Stateless API pods + external state stores** supports independent scaling of compute and data layers.
- **Modular services** allow targeted scaling (telephony, LLM agent etc) by bottleneck.
