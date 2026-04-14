# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MiroFish (LemonFish fork) is a multi-agent prediction and social simulation engine. It ingests domain documents, builds knowledge graphs via Zep Cloud, generates AI agent personas, simulates social dynamics on Twitter/Reddit using OASIS, and produces predictive forecast reports with agent interviews.

## Runtime

**This project runs in Docker in normal operation.** Always assume the Docker runtime when diagnosing, advising on URLs, or deciding how to pick up config changes. The `npm run dev` path below is contributor-mode only.

```bash
# Day-to-day (Docker, slim image)
docker compose -f docker-compose.slim.yml up -d          # start
docker compose -f docker-compose.slim.yml restart        # pick up .env / code changes
docker compose -f docker-compose.slim.yml logs -f        # tail logs
docker compose -f docker-compose.slim.yml down           # stop

# Contributor-mode (host, no container)
npm run setup:all          # install frontend (npm) + backend (uv) deps
npm run dev                # Frontend :3000 + Backend :5001 concurrently
npm run frontend           # Vite dev server on :3000 (proxies /api to :5001)
npm run backend            # Flask dev server on :5001 (via uv run python run.py)
npm run build              # Vite production build of frontend

# Interactive wizard — generates .env + builds the Docker image
./setup.sh
```

Backend uses **uv** as the Python package manager (`backend/pyproject.toml`). Run backend commands with `cd backend && uv run <command>` in contributor mode, or `docker compose exec mirofish uv run <command>` under Docker.

### Docker specifics

- **Compose file:** `docker-compose.slim.yml` (single `mirofish` service, slim image, ~2-3GB).
- **Bind mounts:** `./backend/uploads:/app/backend/uploads` (sim state readable from both sides) and `./.env:/app/.env:ro` (so the "Reload .env" feature in the LLM settings screen can re-read the file without a container restart).
- **.env loading:** compose `env_file: .env` injects variables at container start. The file is also bind-mounted so runtime reload works. Edits without reload → restart container to pick up.
- **Networking to the host** (e.g. local Ollama): use `http://host.docker.internal:11434/v1`, never `localhost`. `host.docker.internal` is auto on macOS/Windows Docker Desktop and added via `extra_hosts` for Linux.
- **Host-port access:** frontend `localhost:3000`, backend `localhost:5001` (both published by compose).
- **PIDs** in `backend/uploads/simulations/*/run_state.json` are container-local, not host PIDs.

## Architecture

**Two-process monorepo:** Vue 3 frontend + Flask backend communicating via REST API. Vite proxies `/api/*` to Flask in dev; nginx does the same in Docker.

### Backend (Python 3.11+ / Flask)

- **Entry point:** `backend/run.py` — validates config, creates Flask app
- **App factory:** `backend/app/__init__.py` — registers blueprints, CORS, middleware
- **Config:** `backend/app/config.py` — reads from `.env` (LLM, Zep, simulation settings)
- **3 API blueprints** in `backend/app/api/`:
  - `graph.py` — `/api/graph/*` (ontology generation, project CRUD)
  - `simulation.py` — `/api/simulation/*` (entity reading, profile gen, sim start/stop)
  - `report.py` — `/api/report/*` (report generation, agent chat/interviews)
- **Services** in `backend/app/services/` — all business logic (~13 files). Key ones:
  - `simulation_runner.py` — spawns OASIS as subprocess for isolation
  - `simulation_ipc.py` — filesystem-based JSON IPC between processes
  - `report_agent.py` — ReACT-loop agent with tool calls (graph search, interviews, analysis)
- **LLM client** (`backend/app/utils/llm_client.py`): OpenAI SDK wrapper with exponential backoff retry and fallback model chain
- **Retry utilities** (`backend/app/utils/retry.py`): `@retry_with_backoff` decorator, `RetryableAPIClient`

### Frontend (Vue 3 / Vite)

- **Views** in `frontend/src/views/` — 7 views mapping to the 5-step pipeline + home
- **Components** in `frontend/src/components/` — Step1-5 components, GraphPanel, LanguageSwitcher
- **API clients** in `frontend/src/api/` — Axios wrappers for graph, simulation, report endpoints
- **i18n** via vue-i18n; translations in `locales/*.json` (zh, en, es + 4 more)

### 5-Step Pipeline

1. **Ontology Generation** — upload docs, LLM extracts entity types and relationships
2. **Knowledge Graph Building** — Zep Cloud ingests text, builds graph
3. **Agent Persona Generation** — LLM creates bios/MBTI/demographics from graph entities
4. **Simulation** — OASIS subprocess runs agents posting/commenting per round (~90% of token cost)
5. **Report & Interaction** — ReACT agent generates forecast report; user can chat with agents

### State & Storage

All state is filesystem-based JSON/JSONL (no database):
- Projects: `uploads/projects/{project_id}/`
- Simulations: `uploads/simulations/{sim_id}/`
- Reports: `uploads/reports/{report_id}/`

### External Dependencies

- **Zep Cloud** — knowledge graph storage and retrieval (requires `ZEP_API_KEY`)
- **Any OpenAI-compatible LLM API** — configured via `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL_NAME`
- **OASIS / camel-ai** — simulation engine (Python packages)

## i18n

- **Backend:** Thread-local `t('key.path')` function in `backend/app/utils/locale.py`; detects locale from `Accept-Language` header; falls back to Chinese (zh)
- **Frontend:** vue-i18n with dynamic locale loading from `locales/` directory
- **Language registry:** `locales/languages.json` includes per-language LLM instruction prompts
- When adding UI text, use `t()` keys on both frontend and backend — never hardcode user-facing strings

## Environment

Required in `.env` (see `.env.example`):
- `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL_NAME` — LLM provider config
- `ZEP_API_KEY` — Zep Cloud API key

Optional: `LLM_BOOST_*` (separate accelerated LLM), `LLM_MAX_RETRIES`, `LLM_RETRY_BASE_DELAY`, `LLM_FALLBACK_MODELS`, `OASIS_DEFAULT_MAX_ROUNDS`

## CI/CD

GitHub Actions (`.github/workflows/docker-image.yml`): tag push or manual dispatch builds multi-platform Docker image (amd64 + arm64) to `ghcr.io/Lvigentini/mirofish`.
