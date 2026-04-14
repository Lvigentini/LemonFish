# LLM Providers Reference

> **Last verified:** 2026-04-11
> **Maintained by:** the `/llm-provider-tracker` skill (`.claude/skills/llm-provider-tracker/SKILL.md`)
> **Update cadence:** weekly — run `/llm-provider-tracker audit` to refresh this file and open a PR with changes

This document is the canonical reference for every LLM provider currently supported by LemonFish (via the `setup.sh` wizard or as a custom provider). It is intentionally kept in sync with `setup.sh` and `backend/app/config.py` — if anything here drifts from those files, the audit skill will flag it.

Every price below is followed by the source URL it was fetched from.

---

## Summary Table

| Provider | Base URL | Free tier? | JSON mode | Cheapest model | Cheapest input/M |
|----------|----------|-----------|-----------|---------------|------------------|
| OpenRouter | `https://openrouter.ai/api/v1` | Yes (`:free` models) | Varies | gemma-4-31b-it:free | $0 |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | Yes (generous) | Yes | gemini-2.5-flash-lite | $0.10 |
| OpenAI | `https://api.openai.com/v1` | No | Yes | gpt-5-nano | $0.05 |
| DeepSeek | `https://api.deepseek.com/v1` | No | Yes | deepseek-chat (cache hit) | $0.028 |
| Anthropic | `https://api.anthropic.com/v1/` | No | Limited | claude-haiku-4-5 | $1.00 |
| Grok (xAI) | `https://api.x.ai/v1` | No | Limited | grok-4-1-fast | $0.20 |
| Alibaba Qwen | `https://dashscope.aliyuncs.com/compatible-mode/v1` | Limited | Yes | qwen-flash | $0.05 |
| Kimi/Moonshot | `https://api.moonshot.cn/v1` | Limited | Yes | moonshot-v1-8k | ¥2.00 (~$0.28) |
| Groq | `https://api.groq.com/openai/v1` | Yes (renewable) | Yes | llama-3.1-8b-instant | $0.05 |
| Ollama (local) | `http://localhost:11434/v1` | Free (local) | Yes | any | $0 |

---

## 1. OpenRouter

| Field | Value |
|-------|-------|
| Base URL | `https://openrouter.ai/api/v1` |
| API keys | https://openrouter.ai/keys |
| Models page | https://openrouter.ai/models |
| JSON mode | Varies by upstream model |
| Free tier | Yes — multiple models with `:free` suffix |
| Default in `setup.sh` | `google/gemma-4-31b-it:free` |

**Fallback chain configured in `setup.sh`:**
```
meta-llama/llama-3.3-70b-instruct:free
nousresearch/hermes-3-llama-3.1-405b:free
nvidia/nemotron-3-super-120b-a12b:free
openrouter/free
```

**Verified free models:**

| Model | Context | Pricing | Source |
|-------|---------|---------|--------|
| google/gemma-4-31b-it:free | 262,144 | $0 in / $0 out | https://openrouter.ai/google/gemma-4-31b-it:free (2026-04-11) |

**Notes:**
- Free model rate limits are dynamic and undocumented (~20-200 RPD per model)
- The OpenRouter `/models` page is JS-rendered — individual model pages must be fetched directly to verify pricing
- Paid models pass through upstream pricing with a small markup

---

## 2. Google Gemini (AI Studio)

| Field | Value |
|-------|-------|
| Base URL | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| API keys | https://aistudio.google.com/apikey |
| Pricing page | https://ai.google.dev/pricing |
| JSON mode | Yes (full `response_format` support) |
| Free tier | Yes — generous |
| Default in `setup.sh` | `gemini-2.5-flash` |

**Pricing — verified 2026-04-11 from https://ai.google.dev/pricing**

| Model | Free tier | Paid input/M | Paid output/M |
|-------|-----------|--------------|---------------|
| gemini-3.1-flash-lite-preview | Free | $0.25 | $1.50 |
| gemini-3-flash-preview | Free | $0.50 | $3.00 |
| gemini-2.5-flash | Free | $0.30 | $2.50 |
| gemini-2.5-flash-lite | Free | $0.10 | $0.40 |
| gemini-2.5-pro | Paid only | $1.25 (≤200k) / $2.50 (>200k) | $10.00 / $15.00 |
| gemini-3.1-pro-preview | Paid only | $2.00 / $4.00 | $12.00 / $18.00 |

**Notes:**
- Best free tier for sustained usage
- `gemini-2.5-flash-lite` is now the cheapest paid Gemini option
- New 3.x preview models suggest 2.5 family may be deprecated soon

---

## 3. OpenAI

| Field | Value |
|-------|-------|
| Base URL | `https://api.openai.com/v1` |
| API keys | https://platform.openai.com/api-keys |
| Pricing page | https://developers.openai.com/api/docs/pricing |
| JSON mode | Yes (full `response_format` support) |
| Free tier | No (prepaid credits) |
| Default in `setup.sh` | `gpt-4o-mini` |

**Pricing — verified 2026-04-11 from https://developers.openai.com/api/docs/pricing and https://pricepertoken.com/pricing-page/provider/openai**

| Model | Input/M | Cached input/M | Output/M |
|-------|---------|----------------|----------|
| gpt-5-nano | $0.05 | — | $0.40 |
| gpt-4.1-nano | $0.10 | — | $0.40 |
| gpt-4o-mini | $0.15 | — | $0.60 |
| gpt-5.4-nano | $0.20 | $0.02 | $1.25 |
| gpt-5-mini | $0.25 | — | $2.00 |
| gpt-4.1-mini | $0.40 | — | $1.60 |
| o3-mini | $0.55 | — | $2.20 |
| gpt-5.4-mini | $0.75 | $0.075 | $4.50 |
| o4-mini | $1.10 | — | $4.40 |
| gpt-4.1 | $2.00 | — | $8.00 |
| gpt-4o | $2.50 | — | $10.00 |
| gpt-5.4 | $2.50 | $0.25 | $15.00 |

**Notes:**
- `setup.sh` default `gpt-4o-mini` is still available but is now mid-tier in price
- `gpt-5-nano` ($0.05/$0.40) is currently the cheapest OpenAI model
- OpenAI's pricing page blocks scraping — must use `developers.openai.com` mirror or third-party trackers

---

## 4. DeepSeek

| Field | Value |
|-------|-------|
| Base URL | `https://api.deepseek.com/v1` |
| API keys | https://platform.deepseek.com/api_keys |
| Pricing page | https://api-docs.deepseek.com/quick_start/pricing |
| JSON mode | Yes |
| Free tier | No (very cheap prepaid) |
| Default in `setup.sh` | `deepseek-chat` |

**Pricing — verified 2026-04-11 from https://api-docs.deepseek.com/quick_start/pricing**

| Model | Input/M (cache miss) | Input/M (cache hit) | Output/M |
|-------|---------------------|---------------------|----------|
| deepseek-chat (V3.2) | $0.28 | $0.028 | $0.42 |
| deepseek-reasoner (R1) | $0.28 | $0.028 | $0.42 |

**Notes:**
- Both models now share identical pricing (changed September 2025)
- Cache hits are 10× cheaper — great for repeated prompts
- One of the cheapest paid options for GPT-4-class quality

---

## 5. Anthropic Claude

| Field | Value |
|-------|-------|
| Base URL | `https://api.anthropic.com/v1/` |
| API keys | https://console.anthropic.com/settings/keys |
| Models page | https://platform.claude.com/docs/en/docs/about-claude/models |
| JSON mode | **Limited** — does not support `response_format: {"type": "json_object"}` via OpenAI SDK |
| Free tier | No |
| Default in `setup.sh` | `claude-sonnet-4-20250514` ⚠️ **legacy — should be updated** |

**Pricing — verified 2026-04-11 from https://platform.claude.com/docs/en/docs/about-claude/models**

Current models:

| Model | Model ID | Input/M | Output/M | Context |
|-------|----------|---------|----------|---------|
| Claude Opus 4.6 | `claude-opus-4-6` | $5.00 | $25.00 | 1M |
| Claude Sonnet 4.6 | `claude-sonnet-4-6` | $3.00 | $15.00 | 1M |
| Claude Haiku 4.5 | `claude-haiku-4-5-20251001` | $1.00 | $5.00 | 200k |

Legacy (still available):

| Model | Model ID | Input/M | Output/M |
|-------|----------|---------|----------|
| Claude Sonnet 4.5 | `claude-sonnet-4-5` | $3.00 | $15.00 |
| Claude Sonnet 4 | `claude-sonnet-4-0` | $3.00 | $15.00 |
| Claude Opus 4 | `claude-opus-4-0` | $15.00 | $75.00 |
| Claude Haiku 3 | `claude-3-haiku-20240307` | $0.25 | $1.25 |

**⚠️ Deprecation:** Claude Haiku 3 retires 2026-04-19.

**LemonFish-specific notes:**
- LemonFish's `chat_json()` strips markdown code fences as a workaround for the missing `response_format` support
- Complex JSON schemas may produce inconsistent output — Claude is risky for ontology generation
- Highest-quality reasoning but expensive for simulation-heavy workloads

---

## 6. Grok (xAI)

| Field | Value |
|-------|-------|
| Base URL | `https://api.x.ai/v1` |
| API keys | https://console.x.ai |
| Pricing page | https://docs.x.ai/docs/models |
| JSON mode | Limited |
| Free tier | No |
| Default in `setup.sh` | `grok-3-mini` ⚠️ **may be deprecated** |

**Pricing — verified 2026-04-11 from https://docs.x.ai/docs/models**

| Model | Input/M | Cached input/M | Output/M |
|-------|---------|----------------|----------|
| grok-4-1-fast (reasoning) | $0.20 | $0.05 | $0.50 |
| grok-4-1-fast (non-reasoning) | $0.20 | $0.05 | $0.50 |
| grok-4.20-0309 (reasoning) | $2.00 | $0.20 | $6.00 |
| grok-4.20-0309 (non-reasoning) | $2.00 | $0.20 | $6.00 |
| grok-4.20-multi-agent-0309 | $2.00 | $0.20 | $6.00 |

**Notes:**
- `grok-3-mini` was not visible in the current docs page — verify availability
- `grok-4-1-fast-non-reasoning` is the recommended budget option

---

## 7. Alibaba DashScope / Qwen

| Field | Value |
|-------|-------|
| Base URL | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| API keys | https://bailian.console.aliyun.com/ |
| Pricing page | https://www.alibabacloud.com/help/en/model-studio/getting-started/models |
| JSON mode | Yes |
| Free tier | Limited (trial credits) |
| Default in `setup.sh` | `qwen-plus` |

**Pricing — verified 2026-04-11 from https://www.alibabacloud.com/help/en/model-studio/getting-started/models (international region)**

| Model | Input/M | Output/M | Notes |
|-------|---------|----------|-------|
| qwen-flash | $0.05–$0.25 | $0.40–$2.00 | Tiered by request size |
| qwen-plus | $0.115–$1.20 | $0.287–$3.60 | Tiered by request size |
| qwen-max | $0.359–$3.00 | $1.434–$15.00 | Tiered by request size |

**⚠️ Deprecated:** `qwen-turbo` — replaced by `qwen-flash`.

**Notes:**
- Pricing varies significantly by region (International, Global, US, Mainland China, Hong Kong, EU)
- Tiered pricing means larger requests get cheaper per-token rates
- Best choice for Chinese-language simulations

---

## 8. Kimi / Moonshot

| Field | Value |
|-------|-------|
| Base URL | `https://api.moonshot.cn/v1` |
| API keys | https://platform.kimi.com/console/api-keys |
| Pricing pages | https://platform.kimi.com/docs/pricing/chat-v1 and /chat-k2 |
| JSON mode | Yes |
| Free tier | Limited |
| Default in `setup.sh` | `moonshot-v1-8k` |

**⚠️ Domain change:** `platform.moonshot.cn` now redirects to `platform.kimi.com`.

**Pricing — verified 2026-04-11**

Moonshot V1 (legacy) — from https://platform.kimi.com/docs/pricing/chat-v1:

| Model | Input/M (¥) | Output/M (¥) |
|-------|-------------|--------------|
| moonshot-v1-8k | ¥2.00 | ¥10.00 |
| moonshot-v1-32k | ¥5.00 | ¥20.00 |
| moonshot-v1-128k | ¥10.00 | ¥30.00 |

Kimi K2 (current) — from https://platform.kimi.com/docs/pricing/chat-k2:

| Model | Input/M (¥) | Cache hit/M (¥) | Output/M (¥) |
|-------|-------------|-----------------|--------------|
| kimi-k2-0905-preview | ¥4.00 | ¥1.00 | ¥16.00 |
| kimi-k2-0711-preview | ¥4.00 | ¥1.00 | ¥16.00 |
| kimi-k2-thinking | ¥4.00 | ¥1.00 | ¥16.00 |
| kimi-k2-turbo-preview | ¥8.00 | ¥1.00 | ¥58.00 |
| kimi-k2-thinking-turbo | ¥8.00 | ¥1.00 | ¥58.00 |

**Notes:**
- Approximate USD: ¥1 ≈ $0.14 (rate varies)
- K2 family is the current default for Chinese-language workloads

---

## 9. Groq (not yet in setup wizard)

| Field | Value |
|-------|-------|
| Base URL | `https://api.groq.com/openai/v1` |
| API keys | https://console.groq.com/keys |
| Pricing page | https://groq.com/pricing |
| Rate limits page | https://console.groq.com/docs/rate-limits |
| JSON mode | Yes |
| Free tier | Yes — documented daily limits per model |
| In `setup.sh`? | **No** — must be added via custom provider (option 9) |

**Pricing — verified 2026-04-11 from https://groq.com/pricing**

| Model | Input/M | Output/M |
|-------|---------|----------|
| llama-3.1-8b-instant | $0.05 | $0.08 |
| gpt-oss-20b | $0.075 | $0.30 |
| llama-4-scout-17b-16e | $0.11 | $0.34 |
| gpt-oss-120b | $0.15 | $0.60 |
| qwen3-32b | $0.29 | $0.59 |
| llama-3.3-70b-versatile | $0.59 | $0.79 |

**Free tier limits — verified 2026-04-11 from https://console.groq.com/docs/rate-limits**

| Model | RPM | RPD | TPM | TPD |
|-------|-----|-----|-----|-----|
| llama-3.1-8b-instant | 30 | 14,400 | 6K | 500K |
| llama-3.3-70b-versatile | 30 | 1,000 | 12K | 100K |
| llama-4-scout-17b-16e | 30 | 1,000 | 30K | 500K |
| qwen3-32b | 60 | 1,000 | 6K | 500K |
| moonshotai/kimi-k2-instruct | 60 | 1,000 | 10K | 300K |
| openai/gpt-oss-120b | 30 | 1,000 | 8K | 200K |
| openai/gpt-oss-20b | 30 | 1,000 | 8K | 200K |

**Notes:**
- 50% discount on cached input tokens
- Total free daily budget across all models: ~2.5M tokens
- LPU hardware = very fast inference (often >500 tok/s)
- **Strong candidate for adding to `setup.sh` wizard**

---

## 10. Ollama (local)

| Field | Value |
|-------|-------|
| Base URL (host) | `http://localhost:11434/v1` |
| Base URL (Docker) | `http://host.docker.internal:11434/v1` |
| Setup | https://ollama.com/download |
| Model library | https://ollama.com/library |
| JSON mode | Yes |
| Free tier | Unlimited (local hardware) |
| In `setup.sh`? | **No** — must be added via custom provider (option 9) |

**Recommended models for LemonFish (CPU-friendly):**

| Model | Size | RAM needed | Quality | Speed (CPU) |
|-------|------|-----------|---------|-------------|
| llama3.2:3b | 2GB | 4GB | Low-medium | Fast |
| mistral:7b | 4GB | 6GB | Good | Medium |
| llama3.3:latest (8B) | 5GB | 8GB | Good | Medium |
| gemma2:9b | 5GB | 8GB | Good | Medium |
| qwen2.5:14b | 8GB | 12GB | Good | Slow |

**Notes:**
- CPU-only is ~10× slower than API calls (~20s per agent action vs ~2s)
- Models below 7B produce incoherent personas — avoid
- Best used to **supplement** API budget, not replace it

### Wiring Ollama into the multi-provider pool

Ollama speaks OpenAI-compatible JSON, so it plugs directly into `LLM_PROVIDERS`. Use the plural `LLM_OLLAMA_MODELS` env var to declare multiple local models — the pool will sub-allocate agents across them the same way it does for catalogue-backed providers like OpenRouter.

```env
LLM_PROVIDERS=gemini,openrouter,ollama

LLM_OLLAMA_API_KEY=ollama              # placeholder, never sent to a network
LLM_OLLAMA_BASE_URL=http://localhost:11434/v1
LLM_OLLAMA_MODELS=qwen3:4b,llama3.2:3b
# Or for single-model:
# LLM_OLLAMA_MODEL=qwen3:4b
```

The pool loader requires `LLM_OLLAMA_API_KEY` to be non-empty (any string works), `LLM_OLLAMA_BASE_URL` to resolve to your Ollama daemon, and either the plural `LLM_OLLAMA_MODELS` or singular `LLM_OLLAMA_MODEL` to declare at least one model. Inside Docker replace `localhost` with `host.docker.internal` (macOS/Windows) or the host LAN IP (Linux).

### Availability check (LLM settings screen)

The read-only **`/settings/llm`** screen in the frontend includes an Ollama panel that runs a cheap availability probe against every pool entry whose base URL points at an Ollama daemon. Unlike the generic provider probe (which costs a real chat completion), this hits `GET http://<daemon>/api/tags` with a 2-second timeout, returning:

- **running** — whether the daemon answered
- **installed_models** — models Ollama actually has pulled
- **configured_models** — what `LLM_OLLAMA_MODELS` currently lists
- **missing** — configured models that are *not* yet pulled, with a `ollama pull <model>` hint

The same screen exposes a **Reload .env** button so adding/removing Ollama models doesn't require restarting the Flask backend — the pool is rebuilt from the refreshed environment on the next request.

The raw endpoint is `GET /api/simulation/providers/ollama/status` if you want to script it.

---

## Cost Estimator

Token formula (from `docs/llm_budget_planning.md`):

```
Total Tokens ≈ 1,160 × R × N + 2,700 × N + 41,400 × S + D/2 + 18,400
```

Where: **N** = agents, **R** = rounds, **S** = report sections (2-5), **D** = document chars

### Minimal sim — 20 agents, 10 rounds, 3 sections (~370K tokens)

| Provider | Model | Estimated cost |
|----------|-------|---------------|
| OpenRouter | gemma-4-31b-it:free | $0 |
| Gemini | gemini-2.5-flash (free tier) | $0 |
| Groq | llama-3.1-8b-instant (free tier) | $0 |
| OpenAI | gpt-5-nano | ~$0.07 |
| OpenAI | gpt-4.1-nano | ~$0.10 |
| DeepSeek | deepseek-chat | ~$0.12 |
| OpenAI | gpt-4o-mini | ~$0.13 |
| Anthropic | claude-haiku-4-5 | ~$1.48 |
| Anthropic | claude-sonnet-4-6 | ~$4.44 |

### Full simulation — 40 agents, 72 rounds, 4 sections (~3.7M tokens)

| Provider | Model | Estimated cost |
|----------|-------|---------------|
| OpenAI | gpt-5-nano | ~$0.70 |
| DeepSeek | deepseek-chat | ~$1.20 |
| OpenAI | gpt-4o-mini | ~$1.30 |
| Anthropic | claude-haiku-4-5 | ~$14.80 |
| Anthropic | claude-sonnet-4-6 | ~$44.40 |
