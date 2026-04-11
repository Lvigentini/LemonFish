# LemonFish — LLM Budget & Multi-Provider Planning

## Token Consumption Model

There is **no token tracking** in the codebase currently. All estimates below are derived from measuring the actual prompt templates.

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
| Groq | llama-4-scout-17b | 500K | 1,000 |
| Groq | qwen3-32b | 500K | 1,000 |
| Groq | llama-3.3-70b | 100K | 1,000 |
| Google | gemini-2.5-flash | ~1M+ | ~1,500 |
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

## Proposed: Multi-Provider Token Allocator

### Design

Before simulation starts, the allocator:

1. **Probes** each configured provider with a minimal API call to check availability and measure response time
2. **Queries** rate limits (where APIs expose this, e.g., Groq returns `x-ratelimit-remaining` headers)
3. **Estimates** total token budget needed using the formula above (based on N agents, R rounds)
4. **Allocates** agents to providers proportionally:
   - Providers with higher daily token budgets get more agents
   - Providers with lower latency get priority for high-activity agents
   - Ollama gets agents if API budgets are insufficient
5. **Assigns** each agent a provider+model at simulation start (locked for duration)
6. **Monitors** during simulation:
   - Tracks consumed tokens per provider (read `response.usage` from API responses)
   - If a provider hits rate limits, its agents skip turns (never reassign to different model)
   - Logs per-provider consumption for post-simulation analysis

### Configuration

```env
# Multi-provider setup (comma-separated)
LLM_PROVIDERS=groq,google,ollama
LLM_GROQ_API_KEY=gsk_...
LLM_GROQ_BASE_URL=https://api.groq.com/openai/v1
LLM_GROQ_MODELS=llama-3.1-8b-instant,llama-4-scout-17b-16e-instruct
LLM_GROQ_DAILY_TOKEN_BUDGET=1000000
LLM_GOOGLE_API_KEY=AIza...
LLM_GOOGLE_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_GOOGLE_MODELS=gemini-2.5-flash
LLM_GOOGLE_DAILY_TOKEN_BUDGET=1000000
LLM_OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
LLM_OLLAMA_MODELS=gemma2:9b,mistral:7b
LLM_OLLAMA_DAILY_TOKEN_BUDGET=999999999
```

### Allocation Algorithm

```
For each simulation:
  1. total_needed = estimate_tokens(N, R, D, S)
  2. For each provider:
       available = min(daily_budget - consumed_today, remaining_rate_limit)
  3. Sort providers by available tokens (descending)
  4. Assign agents round-robin across providers, weighted by available budget
  5. Store assignment in agent profile (agent.provider, agent.model)
  6. Lock assignments for simulation duration
```

### Implementation Priority

1. **First**: Add token tracking to LLMClient (read `response.usage`)
2. **Second**: Add pre-simulation token estimation (the formula)
3. **Third**: Multi-provider config and agent assignment
4. **Fourth**: Runtime monitoring and skip-turn logic

---

## Open Questions

- Should the estimation be shown to the user before starting? ("This simulation will use approximately 3.7M tokens across 3 providers. Estimated time: 45 minutes. Proceed?")
- Should there be a "dry run" mode that estimates cost without running?
- How to handle providers that don't return usage data in responses?
- Should we cache and reuse profile generation across runs with the same seed documents?
- Rate limit headers vary by provider — need per-provider parsing logic
