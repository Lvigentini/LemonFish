# MiroFish — Local Setup (Docker)

Multi-agent AI prediction/simulation engine. Runs thousands of LLM-backed agents
on simulated social platforms (Twitter/Reddit) to forecast outcomes.

Original repo: https://github.com/666ghj/MiroFish

## Prerequisites

- **Docker Desktop** with at least 4GB RAM allocated (8GB+ recommended for large simulations)
- An **OpenAI SDK-compatible LLM API key** (OpenAI, DashScope, etc.)
- A **Zep Cloud API key** (free tier: https://app.getzep.com/)

## Setup

### 1. Configure API keys

Edit `.env` in this directory:

```env
LLM_API_KEY=sk-...            # your LLM provider key
LLM_BASE_URL=https://...      # provider endpoint (OpenAI: https://api.openai.com/v1)
LLM_MODEL_NAME=gpt-4o         # or qwen-plus, etc.

ZEP_API_KEY=z_...              # from https://app.getzep.com/
```

**Optional — local Ollama in the provider pool:**

```env
LLM_PROVIDERS=ollama           # or append to an existing list
LLM_OLLAMA_API_KEY=ollama      # placeholder, ignored by Ollama
LLM_OLLAMA_BASE_URL=http://host.docker.internal:11434/v1   # or http://localhost:11434/v1 on host
LLM_OLLAMA_MODELS=qwen3:4b,llama3.2:3b
```

Visit **http://localhost:3000/settings/llm** after startup to see which providers are configured, probe availability, and verify that every configured Ollama model has been pulled locally. The screen also has a **Reload .env** button so you can edit the file and pick up changes without restarting the backend container.

### 2. Start

```bash
docker compose up -d
```

### 3. Access

- **Frontend UI**: http://localhost:3000
- **Backend API**: http://localhost:5001

### 4. Stop

```bash
docker compose down
```

## Resource Notes

- The Docker container itself is lightweight (~300-500MB RAM at idle)
- Heavy resource consumption comes from **LLM API calls**, not local compute
- Each simulation round triggers many parallel LLM requests — start with <40 rounds
- Token costs can add up quickly with large agent populations
- Uploaded seed materials are persisted in `./backend/uploads/` (mounted volume)

## Common LLM Provider Configs

| Provider | `LLM_BASE_URL` | `LLM_MODEL_NAME` |
|----------|----------------|-------------------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` / `gpt-4o-mini` |
| Alibaba DashScope | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Any OpenAI-compatible | your endpoint | your model |

## Why Docker?

This project depends on `camel-oasis` which requires:
- Python 3.10-3.11 (hard upper bound at <3.12)
- PyTorch with platform-specific wheels (no macOS x86_64 support in recent versions)

Docker sidesteps both constraints by running on Linux x86_64 inside the container.

## Notable Forks

| Fork | What it changes |
|------|-----------------|
| [nikmcfly/MiroFish-Offline](https://github.com/nikmcfly/MiroFish-Offline) | Fully offline — Neo4j + Ollama, no cloud APIs |
| [amadad/mirofish](https://github.com/amadad/mirofish) | CLI-only, Claude/Codex integration, JSON output |
