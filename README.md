# Blurt-AI
Blurt-AI turns voice notes into organized and reviewable records.

## Snapshots
<img src="frontend/assets/image-1.png" alt="Homepage" width="720" />

## Architecture

```mermaid
flowchart LR
  user([User]) -->|record / upload| FE[Next.js frontend]
  FE -->|/api proxy| API[FastAPI API]
  API -->|store audio| R2[(Cloudflare R2)]
  API -->|enqueue jobs| DB[(PostgreSQL<br/>data + job queue)]

  DB <-->|claim jobs| AW[audio-worker<br/>normalize · transcribe]
  DB <-->|claim jobs| LW[llm-worker<br/>split · route · extract · summarize]

  AW -->|fetch audio| R2
  AW -->|speech-to-text| STT[Whisper<br/>mlx on-device / Groq]
  LW -->|chat completion| LLM[OpenAI-compatible LLM<br/>Ollama / hosted]
```

## Tech Stack

### Frontend: TypeScript, Next.js, Tailwind CSS
### Backend : Python, FastAPI, SQLAlchemy, JWT
### Database: PostgreSQL
### Infra: Docker, Kubernetes, CI/CD, Cloudflare R2
### Eval & AI: Speech-to-text (OpenAI Whisper), LLM (OpenAI)
