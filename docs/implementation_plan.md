# LemonFish — Consolidated Implementation Plan

> **Status legend:** ✅ done · 🚧 in progress · 📋 planned · 💡 idea

This document consolidates every change and proposal discussed during development. It is organised in rough priority order with dependencies called out. Each item links back to the detailed design doc where one exists.

---

## Phase 0 — Already Shipped (v0.2.0)

These are the changes live on `main` as of v0.2.0.

| Feature | Status | Commit | Notes |
|---------|--------|--------|-------|
| Fork to `Lvigentini/LemonFish` with upstream link | ✅ | initial | Credit retained to 666ghj/MiroFish |
| Docker build-from-source compose | ✅ | `fa78d6c` | `docker-compose.yml` switched from pre-built image |
| Frontend relative-URL fix for remote network access | ✅ | `fa78d6c` | Vite proxy handles `/api/*` |
| LLM retry with exponential backoff | ✅ | `a685e03` | 429, 500-504, timeouts, connection errors |
| Fallback model chain | ✅ | `a685e03` | `LLM_FALLBACK_MODELS` comma-separated list |
| Graph builder per-batch retry | ✅ | `a685e03` | Partial progress preserved on batch failure |
| i18n backend string extraction | ✅ | `fcb5d73` | 24-key `backend` section added to all locale files |
| Spanish translation | ✅ | `fcb5d73` | `es.json` complete |
| German, French, Portuguese, Italian translations | ✅ | `fd58842` | Complete, 18 sections each |
| Default locale changed to English | ✅ | `fd58842` | Backend and frontend |
| LemonFish rebrand + new logo | ✅ | `519b534` | `MiroFish_lemonLogo.jpeg` + nav text |
| Slim Docker image (2GB vs 14GB) | ✅ | `519b534` | Multi-stage, CPU-only torch, nginx reverse proxy |
| Setup wizard (`setup.sh`) | ✅ | `519b534` | 8 provider options, creates `.env`, launches Docker |
| Architecture deep-dive doc | ✅ | `cb92b6e` | [docs/ARCHITECTURE.md](./ARCHITECTURE.md) |
| LLM budget planning doc | ✅ | `a5bc5c3` | Token consumption formulas |
| Document & ontology guide | ✅ | `4625cb8` | Quality tiers, enrichment strategies |
| Per-step LLM override (ontology only) | ✅ | `19ced62` | `LLM_ONTOLOGY_*` env vars, bypasses 50K truncation |
| Gemini 3 Flash wired for ontology | ✅ | `19ced62` | `gemini-3-flash-preview` |
| Padel document enrichment | ✅ | local | Global news, Aussie news, 9 stakeholder profiles, opposition |
| Version pill from `package.json` | ✅ | `276b251` | Vite `__APP_VERSION__` define, visible in UI |
| `llm_providers.md` canonical catalogue | ✅ | user | Weekly audit cadence via `/llm-provider-tracker` skill |

---

## Phase 1 — Provider Catalogue Sync (v0.3.0 target) ✅ SHIPPED

**Goal:** Bring `setup.sh` and in-code defaults in line with the current verified provider catalogue in [`docs/llm_providers.md`](./llm_providers.md).

**Why first:** Every subsequent feature (multi-model personas, budget allocator, step-specific overrides) depends on having accurate, current provider info. Doing this as its own phase prevents the larger features from absorbing the drift cleanup.

### Tasks

| # | Task | File | Status |
|---|------|------|--------|
| 1.1 | Update Anthropic default to `claude-sonnet-4-6` | `setup.sh` | ✅ |
| 1.2 | Update Grok default to `grok-4-1-fast-non-reasoning` | `setup.sh` | ✅ |
| 1.3 | OpenAI default: `gpt-5-nano` | `setup.sh` | ✅ |
| 1.4 | Add Groq as first-class wizard option | `setup.sh` | ✅ |
| 1.5 | Add Ollama as first-class wizard option (skips API key prompt) | `setup.sh` | ✅ |
| 1.6 | Update DeepSeek pricing in docs | `docs/llm_budget_planning.md` | ✅ |
| 1.7 | Replace stale Groq models with current lineup | `docs/llm_budget_planning.md` | ✅ |
| 1.8 | Update default Gemini model to `gemini-3-flash-preview` | `setup.sh` | ✅ |
| 1.9 | Replace stale OpenRouter `gemma-4-31b-it:free` with `llama-3.3-70b-instruct:free` default | `setup.sh` | ✅ |
| 1.10 | Rewrite `.env.example` in English with current provider examples | `.env.example` | ✅ |
| 1.11 | Update Qwen default to `qwen-flash` (cheapest tier) | `setup.sh` | ✅ |

### Acceptance

- Running `./setup.sh` produces a working `.env` for every provider offered
- `docs/llm_budget_planning.md` numbers match `docs/llm_providers.md`
- `/llm-provider-tracker audit` reports zero drift against `setup.sh`

---

## Phase 2 — Step-Specific Model Routing (v0.4.0 target)

**Goal:** Expand the existing `LLM_ONTOLOGY_*` mechanism to all 5 pipeline steps. Users can assign different providers/models to each step.

**Why:** Different steps have wildly different cost/quality profiles. Simulation is ~90% of tokens and must be cheap; ontology needs large context; report needs reasoning. A single model config is always a compromise.

### Design

Symmetrical env vars for all steps, all optional (fall back to primary `LLM_*` config):

```env
LLM_ONTOLOGY_*     (already exists — uses Gemini 3 Flash)
LLM_PROFILES_*     (new — cheap/fast JSON-capable, e.g. gpt-5-nano)
LLM_CONFIG_*       (new — small context, JSON mode)
LLM_SIMULATION_*   (new — free/near-free, e.g. Groq llama-3.1-8b)
LLM_REPORT_*       (new — reasoning-capable, e.g. Claude Sonnet, Gemini 2.5 Pro)
```

### Tasks

| # | Task | File | Priority |
|---|------|------|----------|
| 2.1 | Add `LLM_PROFILES_*` config vars and wire in `oasis_profile_generator.py` | `backend/app/config.py`, `backend/app/services/oasis_profile_generator.py` | High |
| 2.2 | Add `LLM_CONFIG_*` config vars and wire in `simulation_config_generator.py` | same pattern | Medium |
| 2.3 | Add `LLM_SIMULATION_*` config vars — requires passing model config to OASIS subprocess | `backend/scripts/run_parallel_simulation.py` | High (hardest) |
| 2.4 | Add `LLM_REPORT_*` config vars and wire in `report_agent.py` | `backend/app/services/report_agent.py` | Medium |
| 2.5 | Update wizard to ask "simple (one provider)" vs "advanced (per-step)" | `setup.sh` | Low |
| 2.6 | Document the override pattern | `docs/llm_providers.md` | Low |

### Risks

- OASIS subprocess model override (2.3) requires verifying that `camel.models.ModelFactory` honours dynamic base URLs. May need a patch.
- Config proliferation. Needs clear defaults so users don't have to set all 5.

### Acceptance

- A user can configure Gemini for ontology, Groq for simulation, and OpenAI for report — all in one run
- Tokens consumed per-step are logged separately
- Default behaviour (single `LLM_*` block) unchanged

---

## Phase 3 — Token Tracking & Budget Prediction (v0.5.0 target)

**Goal:** Before starting a simulation, show the user the estimated token cost. During the run, track actual consumption. This is the foundation for the budget allocator (Phase 4).

### Tasks

| # | Task | File | Priority |
|---|------|------|----------|
| 3.1 | Read `response.usage` in `LLMClient` and log per-step | `backend/app/utils/llm_client.py` | High |
| 3.2 | Persist per-simulation token tallies to `state.json` | `backend/app/services/simulation_manager.py` | High |
| 3.3 | Implement the formula from `llm_budget_planning.md` as a pre-flight estimator | `backend/app/services/token_estimator.py` (new) | High |
| 3.4 | Expose estimator via `/api/simulation/estimate` endpoint | `backend/app/api/simulation.py` | Medium |
| 3.5 | Frontend: show "This simulation will use ~X tokens (~Y minutes)" confirmation before starting | `frontend/src/views/MainView.vue` or modal | Medium |
| 3.6 | Post-simulation summary: actual vs estimated tokens by step | report view | Low |

### Acceptance

- Every simulation run produces a `tokens.json` with per-step actual token counts
- Users see the estimate before clicking Start
- Estimator accuracy: ±30% across 3 test simulations

---

## Phase 4 — Multi-Provider Token Budget Allocator (v0.6.0 target)

**Goal:** Automatically distribute agent LLM calls across multiple free-tier providers to stretch daily budgets. Depends on Phase 3 (tracking) and Phase 2 (per-step routing).

### Design

See [`docs/llm_budget_planning.md#proposed-multi-provider-token-allocator`](./llm_budget_planning.md) for the full design.

Key properties:
- **Random agent-to-provider assignment** (not role-based — see [new_features_planning.md](./new_features_planning.md))
- **Agent locks to assigned provider for the whole simulation** (no fallback = identity preserved)
- **Skip-turn on exhaustion** — if a provider is rate-limited, its agents go silent rather than route elsewhere
- **Runtime monitoring** — track consumption per provider; show live in UI

### Tasks

| # | Task | Priority |
|---|------|----------|
| 4.1 | Multi-provider config schema (`LLM_PROVIDERS=groq,google,ollama` plus per-provider blocks) | High |
| 4.2 | Pre-simulation probe: ping each provider, measure latency, read rate-limit headers | High |
| 4.3 | Allocator: map agents to providers proportional to available budget | High |
| 4.4 | Store assignment in agent profile JSON (reproducible via seed) | Medium |
| 4.5 | Per-provider rate limit tracking at runtime | High |
| 4.6 | Skip-turn logic in simulation loop when assigned provider unavailable | High |
| 4.7 | Live monitor UI (consumption per provider, per agent) | Low |
| 4.8 | Post-simulation report: which agents used which model, any skip events | Medium |

### Dependencies

- Phase 2 (step routing) — proves per-call provider selection works
- Phase 3 (token tracking) — needed to measure consumption

### Acceptance

- A simulation running on 3 providers (Groq + Google + Ollama) completes successfully
- Assignment is reproducible given a seed
- If Groq hits rate limit mid-sim, Groq-assigned agents skip; Google/Ollama agents continue
- Post-sim report shows per-provider token consumption

---

## Phase 5 — Provider Capability Detection (v0.7.0 target)

**Goal:** Automatically detect whether a provider supports features like `response_format` JSON mode, and fall back to prompt-based JSON extraction if not.

### Why

Currently `chat_json()` in `llm_client.py:126` always passes `response_format={"type": "json_object"}` and hopes for the best. Anthropic and Grok don't support this — the code relies on a markdown-fence-strip workaround that fails on edge cases.

### Tasks

| # | Task | Priority |
|---|------|----------|
| 5.1 | Capability probe at `LLMClient.__init__` (1 small test call) | Medium |
| 5.2 | Cache capability results per (base_url, model) | Medium |
| 5.3 | If `response_format` not supported, switch to "respond in JSON only" system prompt + stricter parser | Medium |
| 5.4 | Expose capabilities in logs and UI (badge: "JSON mode ✓" or "prompt-based JSON") | Low |

### Acceptance

- Using Anthropic for any step succeeds without JSON parse errors
- Using Grok for any step succeeds without JSON parse errors
- Zero behavioural change for providers that do support `response_format`

---

## Phase 6 — Multi-Model Persona Assignment (v0.8.0 target)

**Goal:** Randomly assign different LLMs to different agents to break monoculture artifacts in simulation output.

Full design: [`docs/new_features_planning.md#feature-multi-model-persona-assignment`](./new_features_planning.md).

**Blocker:** Depends on Phase 4 (multi-provider allocator) — that feature provides the infrastructure; this one provides the scientific rationale for using it. Without Phase 4, you can't randomly assign agents to models.

### Tasks

| # | Task | Priority |
|---|------|----------|
| 6.1 | `LLM_AGENT_MODELS` config (pool of models to draw from) | High |
| 6.2 | Assignment happens at Step 2 (profile generation) and is stored in profile JSON | High |
| 6.3 | Simulation runner respects per-agent model when calling OASIS | High |
| 6.4 | Seed-based reproducibility | Medium |
| 6.5 | Analysis tools: did agents on model X behave differently than agents on model Y? | Low (research) |

### Acceptance

- A 40-agent sim can be split across 4 different models (10 agents each)
- Re-running with the same seed produces identical model assignments
- Post-sim analysis shows model-correlated behaviour differences

---

## Phase 7 — Quality-of-Life Improvements (ongoing)

Backlog items that are self-contained and can be picked up anytime.

| # | Task | Source |
|---|------|--------|
| 7.1 | Document quality scoring before ontology generation (estimate ontology richness from entity density) | ontology guide open questions |
| 7.2 | Stop/resume capability for ontology and graph build steps (currently no cancellation) | resilience audit |
| 7.3 | Orphan project cleanup on failed ontology generation | resilience audit |
| 7.4 | Simulation subprocess state reconciliation after server restart | resilience audit |
| 7.5 | `_wait_for_episodes` should log Zep API errors instead of silently passing | resilience audit |
| 7.6 | Structured input mode (CSV of stakeholders) alongside unstructured docs | ontology guide |
| 7.7 | `/llm-provider-tracker audit` automation as a GitHub Action | llm_providers.md |
| 7.8 | User-facing cost warning when picking a paid provider at high agent counts | budget planning |
| 7.9 | Dry-run mode (estimate without running) | budget planning |
| 7.10 | Per-step token budgets in `state.json` for partial resume | Phase 3 follow-up |

---

## Not Doing (Explicit rejections)

| Idea | Why rejected |
|------|-------------|
| Role-based model assignment ("smarter models for important agents") | Introduces unjustified assumptions about model-to-role fit; user feedback |
| Mid-simulation model swap as a fallback | Breaks agent identity/continuity; user feedback |
| Forking `camel-oasis` to support Python 3.12+ | Too much maintenance burden; Docker sidesteps the issue |
| Replacing Zep Cloud with self-hosted Neo4j | Huge engineering lift for modest gain; see ARCHITECTURE.md |
| Replacing Flask with FastAPI | App is primarily I/O bound, no real benefit; would require rewriting blueprints |
| Removing torch entirely (since only OASIS recsys uses it) | Tried — OASIS would need a fork to disable recsys mode |

---

## Dependency Graph

```
Phase 0 (done)  ──►  Phase 1 (catalogue sync)  ──►  Phase 2 (step routing)
                                                         │
                                                         ▼
                     Phase 7 (QoL, any time)      Phase 3 (token tracking)
                                                         │
                                                         ▼
                                                  Phase 4 (budget allocator)
                                                         │
                                                         ▼
                                                  Phase 5 (capability detection)  ──►  Phase 6 (multi-model personas)
```

---

## Version Roadmap

| Version | Contents | Estimated phases |
|---------|----------|------------------|
| v0.2.0 | Phase 0 | ✅ |
| v0.3.0 (current) | Phase 1 (catalogue sync) | ✅ |
| v0.4.0 | Phase 2 (step routing) | 📋 |
| v0.5.0 | Phase 3 (token tracking) | 📋 |
| v0.6.0 | Phase 4 (budget allocator) | 📋 |
| v0.7.0 | Phase 5 (capability detection) | 📋 |
| v0.8.0 | Phase 6 (multi-model personas) | 📋 |
| v1.0.0 | Full feature set, stable API | 💡 |

Versions are indicative, not deadlines. Features may ship sooner if they unlock testable value.
