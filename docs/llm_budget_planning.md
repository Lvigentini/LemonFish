# LemonFish — LLM Budget & Multi-Provider Planning

> **Note:** Provider pricing, rate limits, and model availability change frequently. For the canonical, verified-weekly provider catalogue, see [`docs/llm_providers.md`](./llm_providers.md), maintained by the `/llm-provider-tracker` skill. If anything in this document contradicts `llm_providers.md`, the provider doc wins.

## Token Consumption Model

The estimates below are derived from measuring the actual prompt templates across all five pipeline steps. Live token tracking is wired through every step — the `TokenTracker` service records `response.usage` on every LLM call and persists per-simulation tallies to `backend/uploads/token_usage/{simulation_id}.json`. The pre-flight modal in the UI uses these formulas to predict cost before a user clicks Start; post-simulation the actual vs estimated breakdown is visible via `GET /api/simulation/token-usage/<simulation_id>`.

### Per-Step Breakdown

| Step | LLM Calls | Tokens per call | Total tokens | Notes |
|------|-----------|-----------------|-------------|-------|
| 1. Ontology | 1 | 5K-28K | 2,800 + D/2 | D = document chars, max 50K |
| 2. Profiles | N | ~2,700 | N * 2,700 | N = entity/agent count |
| 3. Config | 2 + ceil(N/15) | ~3,500-5,200 | 10,300 + ceil(N/15) * 3,580 | Batched agent configs |
| 4. Simulation | R * A_avg | ~2,900 | R * 0.4 * N * 2,900 | **Dominates everything** |
| 5. Report | 5-25 (ReACT) | variable | 2,300 + S * 41,400 + 3,000 | S = sections (2-5) |

### Formula

```
Total Tokens ~ 1,160 * R * N  +  2,700 * N  +  41,400 * S  +  D/2  +  18,400
```

Where: N = agents, R = rounds, D = document chars, S = report sections

### Example Scenarios

| Scenario | Agents | Rounds | Tokens | Approx. LLM calls |
|----------|--------|--------|--------|-------------------|
| Minimal (max_rounds=10) | 20 | 10 | ~370K | ~110 |
| Default | 40 | 72 | ~3.7M | ~1,200 |
| Large | 80 | 72 | ~7.2M | ~2,400 |
| Full uncapped | 80 | 144 | ~14M | ~4,800 |

The simulation step (Step 4) accounts for ~90% of total consumption.

---

## Free Provider Inventory

### Tier 1: Reliable daily free budgets (documented, renewable)

| Provider | Base URL | Daily free tokens | RPM | RPD | JSON mode | Signup |
|----------|----------|-------------------|-----|-----|-----------|--------|
| **Groq** | `api.groq.com/openai/v1` | ~2.5M (across models) | 30-60 | 1,000-14,400 | Yes | No CC |
| **Google AI Studio** | `generativelanguage.googleapis.com/v1beta/openai/` | ~1M+ TPM on Gemini Flash | 15-30 | ~1,500 | Yes | No CC |
| **SambaNova** | `api.sambanova.ai/v1` | ~1M (200K × 5 models) | 20 | 20 per model | Likely | No CC |

### Tier 2: Rate-limited free models

| Provider | Base URL | Limits | JSON mode | Notes |
|----------|----------|--------|-----------|-------|
| **OpenRouter** | `openrouter.ai/api/v1` | ~20-200 RPD (free models) | Varies | Limits are dynamic, undocumented |
| **HuggingFace** | `router.huggingface.co/v1` | $0.10/month (~1-5M tokens) | Yes (via providers) | Routes to Groq/SambaNova/etc |

### Tier 3: One-time credits (not renewable)

| Provider | Base URL | Credits | JSON mode |
|----------|----------|---------|-----------|
| **Together AI** | `api.together.xyz/v1` | ~$5 signup | Yes |
| **Fireworks AI** | `api.fireworks.ai/inference/v1` | ~$1 signup | Yes |
| **SambaNova** | (same) | $5 for 30 days | Likely |

### Tier 4: Undocumented/limited

| Provider | Base URL | Notes |
|----------|----------|-------|
| **Cerebras** | `api.cerebras.ai/v1` | Free tier exists, limits unknown |
| **Mistral** | `api.mistral.ai/v1` | Experiment tier, limits unknown |
| **Cohere** | `api.cohere.ai/compatibility/v1` | 1,000 calls/month |

### Local: Ollama

| Provider | Base URL | Limits | JSON mode | Notes |
|----------|----------|--------|-----------|-------|
| **Ollama** | `http://host.docker.internal:11434/v1` | Unlimited (local hardware) | Yes | CPU-only is slow but works. See section below. |

---

## Combined Daily Token Budget (Tier 1 only)

Using only the reliable renewable providers:

| Provider | Model | Daily tokens | RPD |
|----------|-------|-------------|-----|
| Groq | llama-3.1-8b-instant | 500K | 14,400 |
| Groq | qwen3-32b | 500K | 1,000 |
| Groq | kimi-k2-instruct | 300K | 1,000 |
| Groq | gpt-oss-120b | 200K | 1,000 |
| Groq | gpt-oss-20b | 200K | 1,000 |
| Groq | llama-3.3-70b-versatile | 100K | 1,000 |
| Google | gemini-2.5-flash-lite | ~1M+ | ~1,500 |
| Google | gemini-3-flash-preview | ~1M+ | ~1,500 |
| SambaNova | deepseek-v3.1 | 200K | 20 |
| SambaNova | llama-3.3-70b | 200K | 20 |
| **Total** | | **~3M+/day** | |

A "Default" simulation (40 agents, 72 rounds) needs ~3.7M tokens — just above the daily free budget. Strategies:
- Run over 2 days
- Use `max_rounds=40` (halves token use)
- Reduce agent count to 30
- Supplement with Ollama for some agents

A "Minimal" simulation (20 agents, 10 rounds, ~370K tokens) fits comfortably within a single day's free budget from Groq alone.

---

## Ollama (Local Models)

### Does it work with LemonFish?

**Yes.** Ollama exposes an OpenAI-compatible API at `http://localhost:11434/v1`. From inside Docker, use `http://host.docker.internal:11434/v1`.

### CPU-only performance

Without GPU, expect:
- **7B models** (llama3.2, gemma2:2b, phi-3-mini): 5-15 tokens/sec. Usable for individual calls, painful for simulation.
- **13B-14B models** (llama3.2:13b, qwen2.5:14b): 2-8 tokens/sec. Slow but functional.
- **32B+ models**: <2 tokens/sec on CPU. Not practical for simulation.

### Impact on simulation timing

A typical agent action call is ~200 output tokens.
- At 10 tok/s (7B CPU): 20 seconds per agent per round
- 20 agents × 10 rounds = 200 calls × 20s = **~67 minutes** for a minimal sim
- Compare to API calls: 200 calls × 2s = **~7 minutes**

**CPU Ollama is ~10x slower** but has unlimited tokens. Acceptable for:
- Profile generation (N calls, parallelisable with API calls)
- Low-frequency agents (agents assigned to Ollama could be the "lurkers" with fewer actions)
- Supplementing API budget rather than replacing it

### Persona quality on small models

Small local models (7B-14B) may not follow complex persona instructions as faithfully as 70B+ API models. This is actually desirable for the multi-model diversity goal — different quality/style of role-play adds realistic variation. But models below 7B tend to produce incoherent responses and should be avoided.

### Recommended Ollama models for LemonFish

| Model | Size | RAM needed | Quality | Speed (CPU) |
|-------|------|-----------|---------|-------------|
| llama3.2:3b | 2GB | 4GB | Low-medium | Fast |
| gemma2:9b | 5GB | 8GB | Medium | Medium |
| qwen2.5:14b | 8GB | 12GB | Good | Slow |
| llama3.3:latest (8B) | 5GB | 8GB | Good | Medium |
| mistral:7b | 4GB | 6GB | Good | Medium |

---

## Multi-Provider Token Allocator

The allocator is implemented across `backend/app/services/provider_pool.py`, `agent_model_assignment.py`, and `backend/scripts/oasis_model_patch.py`. Here's how it works end-to-end:

### Pre-flight (simulation setup)

1. **Probe** — `ProviderPool.probe_all()` pings each configured provider with a 5-token sample call and records reachability, latency, and whether the `response.usage` field is returned.
2. **Estimate** — `token_estimator.estimate()` runs the formula above against the planned N agents / R rounds / D document chars and produces a per-step breakdown plus cost projections across six pricing tiers. This is what the pre-flight modal in the UI shows.
3. **Allocate** — `ProviderPool.allocate_agents(agent_ids, seed, only_reachable)` uniformly-at-random assigns each agent to a provider. The assignment is seeded (`LLM_MULTI_PROVIDER_SEED`) for reproducibility.
4. **Persist** — the allocation is written to `agent_model_assignments.json` in the simulation directory.

### Runtime (during simulation)

5. **Subprocess routing** — the OASIS simulation subprocess picks up `MIROFISH_AGENT_MODEL_ASSIGNMENTS` from its environment. `oasis_model_patch.py` monkey-patches `generate_reddit_agent_graph` / `generate_twitter_agent_graph` so each `SocialAgent` is constructed with its own `BaseModelBackend` instance rather than a shared one. No upstream OASIS fork required.
6. **Token tracking** — `TokenTracker` persists per-simulation, per-step, per-model consumption. From inside the subprocess, `token_instrumentation.py` monkey-patches the openai SDK to record usage against the same file the parent Flask process writes to.
7. **Agents are locked to their assigned provider** — if that provider hits rate limits mid-simulation, the agent skips its turn rather than swapping model. This preserves positional integrity: an agent's "voice" never changes mid-run.

### Configuration

```env
LLM_PROVIDERS=groq,google,ollama

LLM_GROQ_API_KEY=gsk_...
LLM_GROQ_BASE_URL=https://api.groq.com/openai/v1
LLM_GROQ_MODEL=llama-3.1-8b-instant
LLM_GROQ_DAILY_TOKEN_BUDGET=1000000

LLM_GOOGLE_API_KEY=AIza...
LLM_GOOGLE_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_GOOGLE_MODEL=gemini-3-flash-preview
LLM_GOOGLE_DAILY_TOKEN_BUDGET=1000000

LLM_OLLAMA_API_KEY=ollama
LLM_OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
LLM_OLLAMA_MODEL=llama3.2
LLM_OLLAMA_DAILY_TOKEN_BUDGET=999999999

# Reproducibility (optional)
LLM_MULTI_PROVIDER_SEED=42
```

### Daily budget tracking

`GET /api/simulation/budget/daily` aggregates 24-hour consumption across all simulations and compares it to each provider's `DAILY_TOKEN_BUDGET`. Response includes per-endpoint `total_tokens`, `remaining`, `percent_used`, and a warnings list for providers at or above 80% usage.

### Cost warnings

The pre-flight modal displays tiered warnings based on the estimated token cost:

- **Medium warning** when DeepSeek equivalent cost > $2
- **High warning** when Claude Sonnet equivalent cost > $5
- **Danger warning** when total tokens > 10M

Users see these before clicking Start and can back off to a smaller scenario or switch providers.

---

## API surface

| Endpoint | Purpose |
|----------|---------|
| `POST /api/simulation/estimate` | Pre-flight token and cost estimate for a planned simulation |
| `GET /api/simulation/token-usage/<simulation_id>` | Actual usage per step for a running or completed simulation |
| `GET /api/simulation/providers/pool` | Configured multi-provider pool |
| `POST /api/simulation/providers/probe` | Live probe of every provider |
| `POST /api/simulation/providers/allocate` | Preview an agent-to-provider allocation (seeded or random) |
| `GET /api/simulation/providers/capabilities` | Cached capability detection results (JSON mode support, etc.) |
| `GET /api/simulation/assignment/<simulation_id>` | Agent-to-provider assignment for a running simulation (API keys redacted) |
| `GET /api/simulation/budget/daily` | 24-hour consumption vs per-provider daily budgets |
