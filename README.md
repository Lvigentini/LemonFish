<div align="center">

<img src="./frontend/public/MiroFish_lemonLogo.jpeg" alt="MiroFish [LemonFish]" width="240"/>

# MiroFish <sub>[LemonFish]</sub>

**Multi-agent prediction engine** — a hardened fork of [MiroFish](https://github.com/666ghj/MiroFish) with research-backed agent personalities, multi-provider LLM routing, a slim Docker image, and first-class free-tier support.

[![GitHub Stars](https://img.shields.io/github/stars/Lvigentini/LemonFish?style=flat-square&color=DAA520)](https://github.com/Lvigentini/LemonFish/stargazers)
[![GitHub Release](https://img.shields.io/github/v/release/Lvigentini/LemonFish?style=flat-square&color=DAA520)](https://github.com/Lvigentini/LemonFish/releases)
[![License](https://img.shields.io/badge/License-AGPL--3.0-blue?style=flat-square)](LICENSE)

[Detailed Guide](./docs/DETAILED_GUIDE.md) · [Architecture](./docs/ARCHITECTURE.md) · [Personality Frameworks](./docs/personality_frameworks.md) · [Provider Catalogue](./docs/llm_providers.md)

</div>

---

## What it does

Describe what you want to predict. LemonFish builds a simulated social world of AI agents with distinct personalities, runs them on simulated Twitter + Reddit, and delivers a structured prediction report.

You start in one of two ways:

```
┌─ Upload documents ─┐                                                     ┌─ Prediction ─┐
│  PDF / MD / TXT    │ ──┐                                                 │   report     │
│  CSV stakeholders  │   │                                                 │              │
└────────────────────┘   │                                                 │ + per-agent  │
                         ├─► Knowledge ─► Agent ──► Social ──► Report ─────┤   interviews │
┌─ OR research ──────┐   │   graph       personas   simulation   agent     │              │
│  Describe the      │ ──┘   (Zep)       (Big Five  (Twitter +             │ + distribu-  │
│  prediction goal   │                    + org      Reddit)               │   tion maps  │
│  AI gathers data   │                    arche-                           │              │
└────────────────────┘                    types)                           └──────────────┘
```

See the [Detailed Guide](./docs/DETAILED_GUIDE.md) for a full walkthrough.

---

## Quick start

```bash
git clone https://github.com/Lvigentini/LemonFish.git lemonfish
cd lemonfish
./setup.sh
```

The interactive wizard walks you through:

1. **Pick an LLM provider** — 11 supported out of the box (OpenRouter, Gemini, Groq, OpenAI, DeepSeek, Anthropic Claude, Grok, Qwen, Kimi, Ollama, or custom)
2. **Paste your API key** — or use Ollama locally with no key at all
3. **Add a [Zep Cloud](https://app.getzep.com/) key** for the knowledge graph (free tier is enough)
4. **Build and launch** — slim Docker image, typically ~2–3 GB

Open **http://localhost:3000** when done.

### Without Docker

```bash
npm run setup:all   # installs frontend (npm) + backend (uv) deps
npm run dev         # runs Flask :5001 + Vite :3000 concurrently
```

---

## Why this fork

| | Original MiroFish | This fork |
|---|---|---|
| **Docker image** | ~14 GB (CUDA + full Debian) | ~**2–3 GB** (multi-stage slim, CPU-only torch, nginx) |
| **LLM failure mode** | Single call → hard crash | Exponential backoff + fallback model chain |
| **Provider choice** | DashScope / Qwen only | 11 OpenAI-compatible providers + custom endpoints |
| **Free-tier support** | None | Multi-provider pool with daily-budget tracking |
| **Pipeline setup** | Manual `.env` editing | Interactive wizard, per-step model routing |
| **Agent personality** | MBTI (pseudoscientific, Reddit-only, one sentence) | **Big Five for people, 8 archetypes for institutions** |
| **Input source** | Documents only | Documents **or** research-from-prompt (Phase 8) |
| **Cancellation** | None | Full task cancel with batch-boundary checkpoints |
| **Cost visibility** | None | Pre-flight token estimation with 6-tier cost bands |
| **Language** | Chinese only | **7 languages** (en, zh, es, de, fr, pt, it) |
| **Remote access** | localhost only | Network-accessible by default |

---

## Research-backed agent personalities

Agents aren't just bios — they have structured personality profiles grounded in empirical research:

**Individuals** use the **Big Five / Five Factor Model**, the dominant trait taxonomy in academic personality psychology:

- `openness` · `conscientiousness` · `extraversion` · `agreeableness` · `neuroticism` (each 0–100)
- Derived from the source material (an expert in a contested field scores high conscientiousness, low agreeableness; a community organiser scores high extraversion, high agreeableness)
- Rendered into the agent's system prompt as natural-language descriptions, so both Twitter and Reddit agents see their own personality

**Institutions** use a pragmatic 8-archetype taxonomy plus 5 behavioural trait scores:

| Archetype | Voice |
|-----------|-------|
| `authoritative` | Government bodies, regulators, central banks — formal, cautious, slow |
| `technocratic` | Expert bodies, standards orgs — evidence-based, measured |
| `advocacy` | NGOs, campaigns, unions — passionate, confrontational |
| `commercial` | Companies, brands — polished, customer-focused, deflective |
| `community` | Local groups, clubs — personal, colloquial, responsive |
| `media` | News outlets — editorial, headline-driven |
| `academic` | Universities, research institutes — nuanced, hedged |
| `populist` | Movements, insurgent political actors — emotional, simplified |

Behavioural traits: `formality` · `risk_tolerance` · `transparency` · `responsiveness` · `ideological_intensity` (each 0–100).

See [`docs/personality_frameworks.md`](./docs/personality_frameworks.md) for the full rationale, including why we replaced MBTI and what the academic citations are.

---

## Multi-provider LLM pool

You can spread LLM calls across multiple providers to stretch free-tier budgets. Agents are randomly allocated at simulation start and locked to their provider for the whole run (no mid-run identity swaps).

```env
LLM_PROVIDERS=groq,google,openrouter,ollama

LLM_GROQ_API_KEY=gsk_...
LLM_GROQ_BASE_URL=https://api.groq.com/openai/v1
LLM_GROQ_MODEL=llama-3.1-8b-instant
LLM_GROQ_DAILY_TOKEN_BUDGET=500000

LLM_GOOGLE_API_KEY=AIza...
LLM_GOOGLE_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_GOOGLE_MODEL=gemini-3-flash-preview
LLM_GOOGLE_DAILY_TOKEN_BUDGET=1000000
```

**Per-step model routing** lets you send the expensive, reasoning-heavy steps (ontology, report) to a strong model while the 90%-of-tokens simulation step hits a free-tier fast model. See [`.env.example`](./.env.example) Section 3 for all 5 step overrides.

**Capability detection** auto-probes each provider once and caches whether it supports JSON mode. Providers without native `response_format` (Anthropic, some Grok models) are silently served via prompt-based JSON extraction.

**Daily budget aggregation** at `GET /api/simulation/budget/daily` shows how much you've spent across all simulations in the last 24h against your per-provider caps.

For the canonical, weekly-verified provider catalogue see [`docs/llm_providers.md`](./docs/llm_providers.md).

---

## Resilience

Every LLM call is protected by:

- **Retry with exponential backoff** (2s → 4s → 8s) on 429, 5xx, timeout, connection errors
- **Automatic fallback model chain** — when the primary model is exhausted, swing through a configured list
- **Per-batch graph building** — if batch 47 of 100 fails, batches 1–46 are preserved in Zep
- **Full task cancellation** with batch-boundary checkpoints; partial progress kept
- **Retry from failed/cancelled state** — no need to restart a project from scratch
- **Orphan project cleanup** on ontology failure so the history list stays clean

All tunable via `.env`:

```env
LLM_MAX_RETRIES=3
LLM_RETRY_BASE_DELAY=2.0
LLM_FALLBACK_MODELS=model1:free,model2:free,model3:free
```

---

## Phase 8 — Research from prompt

Instead of uploading curated documents, describe what you want to predict and AI research agents gather source material via web search. The compiled document feeds the existing pipeline unchanged.

Four runners are available:

- **`api`** — always on. Uses your configured LLM + [ddgs](https://pypi.org/project/ddgs/) for DuckDuckGo search. Ships in the slim Docker image.
- **`claude`** — shells out to Claude Code CLI using `~/.claude` OAuth
- **`codex`** — shells out to OpenAI Codex CLI using `~/.codex` credentials
- **`kimi`** — shells out to Moonshot Kimi CLI

Enable with `RESEARCH_ENABLED=true` in `.env`. For Docker CLI runners, launch with the research overlay:

```bash
docker compose -f docker-compose.slim.yml -f docker-compose.research.yml up -d
```

See [`docs/research_module.md`](./docs/research_module.md) for the full guide.

---

## Documentation

All reference docs live in [`docs/`](./docs/):

| Doc | For whom |
|-----|----------|
| [`DETAILED_GUIDE.md`](./docs/DETAILED_GUIDE.md) | Users — pipeline walkthrough, configuration reference |
| [`ARCHITECTURE.md`](./docs/ARCHITECTURE.md) | Developers — full technical deep-dive |
| [`personality_frameworks.md`](./docs/personality_frameworks.md) | Anyone — Big Five + org archetypes rationale with academic citations |
| [`oasis_dev.md`](./docs/oasis_dev.md) | Contributors — OASIS engine internals, extension points |
| [`llm_providers.md`](./docs/llm_providers.md) | Operators — verified provider catalogue, updated weekly |
| [`llm_budget_planning.md`](./docs/llm_budget_planning.md) | Operators — token consumption formulas, cost model |
| [`document_and_ontology_guide.md`](./docs/document_and_ontology_guide.md) | Users — seed document quality guide |
| [`research_module.md`](./docs/research_module.md) | Users — Phase 8 research-from-prompt user guide |

The full environment variable reference is in [`.env.example`](./.env.example) — every one of the 50+ env vars the backend reads is documented and organised into numbered sections.

---

## Credits

MiroFish [LemonFish] is a fork of **[MiroFish](https://github.com/666ghj/MiroFish)** by BaiFu (666ghj), which received strategic support and incubation from Shanda Group.

The simulation engine is powered by **[OASIS](https://github.com/camel-ai/oasis)** (Open Agent Social Interaction Simulations) from the CAMEL-AI team.

## License

AGPL-3.0 — same as the original MiroFish project.
