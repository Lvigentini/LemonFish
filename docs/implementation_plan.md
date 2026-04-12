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

## Phase 2 — Step-Specific Model Routing (v0.4.0) ✅ SHIPPED

**Goal:** Expand the existing `LLM_ONTOLOGY_*` mechanism to all 5 pipeline steps. Users can assign different providers/models to each step.

**Why:** Different steps have wildly different cost/quality profiles. Simulation is ~90% of tokens and must be cheap; ontology needs large context; report needs reasoning. A single model config is always a compromise.

### Design

Symmetrical env vars for all steps, all optional (fall back to primary `LLM_*` config). A `Config.get_step_llm_config(step)` helper handles the fallback logic so services don't need to duplicate the lookup pattern.

```env
LLM_ONTOLOGY_*     # Step 1 — large-context (Gemini 3 Flash recommended)
LLM_PROFILES_*     # Step 2 — cheap/fast JSON-capable
LLM_CONFIG_*       # Step 3 — small context, JSON mode
LLM_SIMULATION_*   # Step 4 — free/near-free (dominates token cost)
LLM_REPORT_*       # Step 5 — reasoning-capable
```

### Tasks

| # | Task | File | Status |
|---|------|------|--------|
| 2.0 | Add `Config.get_step_llm_config(step)` helper with automatic fallback | `backend/app/config.py` | ✅ |
| 2.1 | Wire `LLM_PROFILES_*` in `oasis_profile_generator.py` | same | ✅ |
| 2.2 | Wire `LLM_CONFIG_*` in `simulation_config_generator.py` | same | ✅ |
| 2.3 | Wire `LLM_SIMULATION_*` in all 3 simulation scripts (parallel, reddit, twitter) | `backend/scripts/*.py` | ✅ |
| 2.4 | Wire `LLM_REPORT_*` in `report_agent.py` | same | ✅ |
| 2.5 | Refactor ontology generator to use the new helper | `backend/app/services/ontology_generator.py` | ✅ |
| 2.6 | Document all 5 step overrides in `.env.example` | `.env.example` | ✅ |

### Design Notes

- **Subprocess inheritance**: `simulation_runner.py` already does `env = os.environ.copy()` before spawning OASIS, so `LLM_SIMULATION_*` vars automatically flow through to the subprocess. No IPC changes needed.
- **Legacy boost config**: The original `LLM_BOOST_*` mechanism still works for parallel-platform acceleration; it takes precedence over `LLM_SIMULATION_*` when `use_boost=True`.
- **No wizard changes**: Per-step overrides are advanced configuration; the wizard still asks for one primary provider. Users who want per-step routing edit `.env` directly.

### Acceptance

- ✅ A user can configure Gemini for ontology + Groq for simulation + OpenAI for report in one `.env`
- ✅ Default behaviour (single `LLM_*` block) unchanged
- 📋 Tokens consumed per-step are logged separately — deferred to Phase 3

---

## Phase 3 — Token Tracking & Budget Prediction (v0.5.0) ✅ SHIPPED

**Goal:** Before starting a simulation, show the user the estimated token cost. During the run, track actual consumption. This is the foundation for the budget allocator (Phase 4).

### Tasks

| # | Task | File | Status |
|---|------|------|--------|
| 3.1 | Read `response.usage` in `LLMClient` and thread context | `backend/app/utils/llm_client.py` | ✅ |
| 3.1a | Thread-local `TokenTracker` with file-backed persistence | `backend/app/utils/token_tracker.py` (new) | ✅ |
| 3.1b | Instrument direct `OpenAI` calls in profile + config generators | services | ✅ |
| 3.1c | Subprocess token instrumentation (monkey-patch openai SDK) | `backend/scripts/token_instrumentation.py` (new) | ✅ |
| 3.2 | Set step context in API entry points (ontology/profiles/config/report) | api modules | ✅ |
| 3.2a | Pass `MIROFISH_SIMULATION_ID` env var to OASIS subprocess | `simulation_runner.py` | ✅ |
| 3.3 | Pre-flight estimator using formula from `llm_budget_planning.md` | `backend/app/services/token_estimator.py` (new) | ✅ |
| 3.4 | Expose `/api/simulation/estimate` endpoint (POST) | `api/simulation.py` | ✅ |
| 3.4a | Expose `/api/simulation/token-usage/<id>` endpoint (GET) | `api/simulation.py` | ✅ |
| 3.5 | Frontend pre-flight confirmation modal | frontend | 📋 deferred |
| 3.6 | Post-simulation summary (actual vs estimated) | frontend | 📋 deferred |

### Design Notes

- **Thread-local context**: `TokenTracker.set_context(simulation_id, step)` at the start of each background task; `LLMClient._call_with_retry` reads the context on every call. Clean separation — services don't need to know about tracking.
- **Subprocess instrumentation**: Simulation runs in a separate Python process (OASIS). The subprocess can't share thread-local state with the parent, so we monkey-patch `openai.resources.chat.completions.Completions.create` in `token_instrumentation.py` and install it at script startup. It reads `MIROFISH_SIMULATION_ID` from env and writes to the same JSON file as the parent process.
- **File-backed storage**: `backend/uploads/token_usage/{sim_id}.json`. Survives restarts. Atomic writes via `.tmp` + `rename`.
- **Per-model breakdown**: Each step tracks which models contributed how many tokens — essential for Phase 6 (multi-model personas).

### Acceptance

- ✅ `TokenTracker` records every LLM call from the Flask process
- ✅ Subprocess monkey-patch records simulation step calls
- ✅ `POST /api/simulation/estimate` returns per-step estimates + cost tiers
- ✅ `GET /api/simulation/token-usage/<id>` returns actual usage
- 📋 Frontend modal deferred — backend surface is complete and usable via API

---

## Phase 4 — Multi-Provider Token Budget Allocator (v0.6.0) 🚧 FOUNDATION SHIPPED

**Goal:** Automatically distribute agent LLM calls across multiple free-tier providers to stretch daily budgets. Depends on Phase 3 (tracking) and Phase 2 (per-step routing).

**Status:** The foundation (config, pool, probe, allocator, API surface) is shipped in v0.6.0. The final piece — **per-agent runtime routing in the OASIS simulation step** — is blocked on upstream camel-oasis work and will ship in Phase 6 alongside the multi-model persona feature.

### Tasks

| # | Task | Status | Notes |
|---|------|--------|-------|
| 4.1 | Multi-provider config schema (`LLM_PROVIDERS=groq,google,ollama` plus per-provider blocks) | ✅ | `Config.get_provider_pool()` parses env vars with `LLM_<NAME>_*` convention |
| 4.2 | `ProviderPool` service with entry parsing | ✅ | `backend/app/services/provider_pool.py` |
| 4.3 | Pre-flight probe (ping each provider with 5-token sample call) | ✅ | `pool.probe_all()` returns latency, reachability, sample usage |
| 4.4 | Random seeded agent-to-provider allocation | ✅ | `pool.allocate_agents(ids, seed=...)` — reproducible |
| 4.5 | API endpoints | ✅ | `GET /api/simulation/providers/pool`, `POST /api/simulation/providers/probe`, `POST /api/simulation/providers/allocate` |
| 4.6 | `.env.example` multi-provider section | ✅ | Documented with Groq + Google + Ollama sample |
| 4.7 | **Per-agent runtime routing in OASIS subprocess** | 📋 | **Blocked on OASIS integration — see design note below** |
| 4.8 | Store allocation in agent profile JSON so simulation can read it | 📋 | Phase 6 |
| 4.9 | Skip-turn logic when assigned provider hits rate limit | 📋 | Phase 6 |
| 4.10 | Live monitor UI | 📋 | Future QoL |

### Design Notes

**Why the OASIS piece is deferred:** OASIS's `generate_reddit_agent_graph()` takes a **single model instance** that is shared by every agent. Per-agent model assignment requires either:
1. Forking camel-oasis to accept a per-agent model map (rejected in "Not Doing")
2. Running multiple OASIS environments in parallel, one per provider, and coordinating state (significant rewrite)
3. Monkey-patching camel-oasis at subprocess startup to intercept agent action calls and route them dynamically (fragile)

This is a research question for Phase 6. The infrastructure shipped in Phase 4 (pool, probe, allocator, tracking) makes the eventual wire-up straightforward — we just need to decide *how* to plumb per-agent models through OASIS.

**What Phase 4 does deliver right now:** Users can probe multiple providers, preview allocations, and track usage per provider. Services that use `LLMClient` directly (ontology, profiles, config, report — Steps 1, 2, 3, 5) can already be pointed at different providers via the Phase 2 per-step overrides. Only the simulation step (Step 4) is locked to a single provider until Phase 6.

### Acceptance (for the shipped foundation)

- ✅ `GET /api/simulation/providers/pool` returns configured pool (or empty state)
- ✅ `POST /api/simulation/providers/probe` pings every provider and reports health
- ✅ `POST /api/simulation/providers/allocate` returns reproducible random assignment given a seed
- ✅ Allocation is seed-deterministic (same seed → same assignment)
- 📋 OASIS subprocess per-agent routing — deferred to Phase 6

---

## Phase 5 — Provider Capability Detection (v0.7.0) ✅ SHIPPED

**Goal:** Automatically detect whether a provider supports features like `response_format` JSON mode, and fall back to prompt-based JSON extraction if not.

### Why

Previously `chat_json()` in `llm_client.py` always passed `response_format={"type": "json_object"}` and relied on a markdown-fence-strip workaround for providers that didn't support it (Anthropic, some Grok models). This failed on edge cases where the model returned prose around the JSON.

### Tasks

| # | Task | Status |
|---|------|--------|
| 5.1 | Capability probe: test basic chat + `response_format` with a tiny call | ✅ |
| 5.2 | File-backed cache per `(base_url, model)` with 7-day TTL | ✅ |
| 5.3 | `chat_json` auto-detects JSON support and augments the system prompt if unsupported | ✅ |
| 5.4 | More resilient JSON extraction (also finds JSON embedded in prose) | ✅ |
| 5.5 | API endpoints: list, force-probe, clear cache | ✅ |

### Design Notes

- **Caching is per (base_url, model), not per (api_key, base_url, model)** — capability is a provider property, not a per-account property. This avoids exposing API keys in cache keys.
- **Optimistic fallback on probe failure**: if the capability check itself errors out, we assume JSON mode works and try it anyway. Better to fail fast than to block on a capability probe.
- **Two kinds of "JSON mode" failure**: some providers accept `response_format` but return invalid JSON anyway. The probe tests both: HTTP acceptance AND parseable JSON output. Only models that pass both get `supports_json_mode=true`.
- **Prompt-based fallback**: appends "Respond with ONLY valid JSON. Start with { and end with }." to the system message, then uses a regex to extract the first `{...}` or `[...]` block from the response if the model wrapped it in prose.

### Acceptance

- ✅ `GET /api/simulation/providers/capabilities` returns cache contents
- ✅ `POST /api/simulation/providers/capabilities/probe` force-probes a specific model
- ✅ `POST /api/simulation/providers/capabilities/clear` resets the cache
- ✅ `chat_json` transparently handles providers without `response_format` support
- 📋 Anthropic/Grok integration testing deferred — available on demand when users configure those providers

---

## Phase 6 — Multi-Model Persona Assignment (v0.8.0) ✅ SHIPPED

**Goal:** Randomly assign different LLMs to different agents to break monoculture artifacts in simulation output.

Full design: [`docs/new_features_planning.md#feature-multi-model-persona-assignment`](./new_features_planning.md).

### Discovery

Digging into the installed `camel-oasis==0.2.5` source code revealed that **per-agent models are already supported upstream**: `SocialAgent.__init__` accepts `model: Optional[Union[BaseModelBackend, List[BaseModelBackend], ModelManager]]`. The only reason MiroFish agents all shared one model is that `generate_reddit_agent_graph` / `generate_twitter_agent_graph` pass the same object reference to every `SocialAgent(..., model=model)`. No upstream fork required.

The solution is a **subprocess-side monkey-patch**: wrap the two `generate_*_agent_graph` functions so they check an env-var-pointed JSON file for per-agent assignments and instantiate a distinct `BaseModelBackend` per agent when the file is present. Falls back to the original single-model behaviour when no assignment exists.

### Tasks

| # | Task | File | Status |
|---|------|------|--------|
| 6.1 | Reuse `ProviderPool.allocate_agents` (from Phase 4) | — | ✅ |
| 6.2 | `agent_model_assignment.py` service: build + persist assignment JSON | `backend/app/services/agent_model_assignment.py` | ✅ |
| 6.3 | `oasis_model_patch.py`: monkey-patch `generate_reddit/twitter_agent_graph` | `backend/scripts/oasis_model_patch.py` | ✅ |
| 6.4 | Install patch from all 3 simulation scripts at startup | `backend/scripts/run_*.py` | ✅ |
| 6.5 | `simulation_runner.py` counts agents, builds assignment, passes env var to subprocess | `simulation_runner.py` | ✅ |
| 6.6 | `GET /api/simulation/assignment/<sim_id>` endpoint (API keys redacted) | `api/simulation.py` | ✅ |
| 6.7 | Seed-based reproducibility via `LLM_MULTI_PROVIDER_SEED` env var | — | ✅ |
| 6.8 | Per-agent token attribution (already free from Phase 3 token tracking) | — | ✅ |
| 6.9 | Analysis tools: did agents on model X behave differently? | — | 📋 Phase 7 / research |

### Design Notes

- **Per-agent lock**: each agent is assigned one model at simulation start and uses it for all actions. No fallback swap — if an agent's provider rate-limits, the agent's action fails for that round (which is the correct behaviour per `new_features_planning.md`).
- **Model backend caching**: the patch caches `ModelFactory.create(...)` results by `(base_url, model)` so two agents sharing a provider share the underlying backend. The `ChatAgent` state is still per-agent (memory, tool state) — only the outbound HTTP client is shared.
- **Graceful degradation**: if `MIROFISH_AGENT_MODEL_ASSIGNMENTS` is not set, the patch is a no-op. Existing single-provider deployments see zero behavioural change.
- **No upstream fork**: the entire feature lives in MiroFish. Zero modifications to `camel-ai` or `oasis` packages. An upstream update would not break this.

### Acceptance

- ✅ A simulation with `LLM_PROVIDERS=provider1,provider2,provider3` configured distributes agents across all three
- ✅ `LLM_MULTI_PROVIDER_SEED=42` produces reproducible assignments
- ✅ `GET /api/simulation/assignment/<sim_id>` returns the distribution with redacted keys
- ✅ Token tracking (Phase 3) per-model breakdown shows which provider each agent hit
- 📋 End-to-end simulation run with multi-provider mode — needs live testing (requires working simulation start flow)

---

## Phase 7 — Quality-of-Life Improvements (v0.9.0 partially shipped)

Backlog items that are self-contained and can be picked up anytime.

| # | Task | Source | Status |
|---|------|--------|--------|
| 7.1 | Document quality scoring before ontology generation | ontology guide | 📋 |
| 7.2 | **Stop/cancel for graph build task** (TaskManager cancel events + `/task/<id>/cancel` endpoint + batch-boundary checks) | resilience audit | ✅ |
| 7.3 | **Orphan project cleanup on ontology generation failure** | resilience audit | ✅ |
| 7.4 | Simulation subprocess state reconciliation after server restart | resilience audit | 📋 |
| 7.5 | `_wait_for_episodes` log Zep API errors | resilience audit | 📋 |
| 7.6 | Structured input mode (CSV of stakeholders) | ontology guide | 📋 |
| 7.7 | `/llm-provider-tracker audit` as GitHub Action | llm_providers.md | 📋 |
| 7.8 | Cost warning for paid providers at high agent counts | budget planning | 📋 |
| 7.9 | **Dry-run mode** (estimate without running) — via the pre-flight modal | budget planning | ✅ |
| 7.10 | Per-step token budgets in `state.json` for partial resume | Phase 3 follow-up | 📋 |
| 7.11 | **Frontend pre-flight modal** with estimate, cost tiers, provider pool | Phase 3 UX | ✅ |
| 7.12 | **Frontend API client** for Phase 3/4/5/6 endpoints | Phase 3-6 UX | ✅ |

### Shipped in v0.9.0

- **`PreflightModal.vue`**: full-featured modal showing per-step token breakdown, 6-tier cost estimates, and provider pool status. Shown automatically when clicking "Start simulation" in Step 2.
- **`api/simulation.js` extensions**: `estimateTokens`, `getTokenUsage`, `getProviderPool`, `probeProviders`, `allocateProviders`, `getProviderCapabilities`, `probeCapability`, `getAgentAssignment`.
- **`api/graph.js` `cancelTask`**: frontend hook for the new cancel endpoint.
- **`TaskStatus.CANCELLED`** + `TaskManager.request_cancel / is_cancelled / cancel_task`: cancellation event infrastructure, safe to call from any thread.
- **`graph_builder.CancelledError`** + cancel_check callback: graph build loop checks at every batch boundary and raises on cancel. Partial progress (episodes already sent to Zep) is preserved.
- **`/api/graph/task/<task_id>/cancel`**: REST endpoint to request cancellation.
- **Orphan cleanup**: ontology generation failure now deletes the half-built project record so the project list stays clean.

---

## Phase 8 — Research-From-Prompt Add-On Module (v0.10.0 target)

**Goal:** Replace the hard requirement to upload curated documents with an optional research-from-prompt entry point. The user provides a vague intent ("predict EV truck adoption in EU haulage 2026-2030"), the system orchestrates several research agents in parallel via web search, and the compiled output feeds the existing Step 1 → 5 pipeline unchanged.

**Why now:** With Phases 1-7 shipped, the platform has every primitive this feature needs — per-step LLM routing (Phase 2), token tracking (Phase 3), provider pool with allocation (Phase 4), capability detection for synthesis JSON output (Phase 5), task cancellation + orphan cleanup (Phase 7). Building this earlier would have meant duplicating those primitives.

**Architecture summary** (full design: [`docs/new_features_planning.md#feature-research-from-prompt-add-on-module`](./new_features_planning.md)):

- **Add-on module** at `backend/research/` — own Flask blueprint, conditionally registered. Main app starts unchanged when disabled or absent.
- **Plug-in seam**: research output is written to `uploads/projects/{project_id}/extracted_text.txt` and the project is promoted to `ONTOLOGY_GENERATED`-ready. The existing `OntologyGenerator` consumes it as if it were uploaded text. **No changes to Step 1-5 code paths.**
- **Three-phase orchestrator**: Plan (1 LLM call decomposes prompt into 3-8 sub-topics) → Research (ThreadPoolExecutor fans out to N runners in parallel) → Synthesise (1 LLM call merges summaries with citations).
- **Runner abstraction** with 4 implementations: `claude_runner.py`, `codex_runner.py`, `kimi_runner.py` (subprocess wrappers around the user's locally-installed CLIs, using their cached OAuth credentials and built-in web search), and `api_runner.py` (fallback using `LLMClient` + `duckduckgo-search`).
- **Pre-flight availability probe**: frontend hits `/api/research/availability` to detect which CLIs are installed and authenticated, then surfaces an explicit picker. No silent fallback.
- **Step 0 frontend**: new optional step before existing Step 1. Home view gets a second "Start with research" entry point alongside "Upload documents".

### Tasks

| # | Task | File | Priority |
|---|------|------|----------|
| 8.A | Module scaffold: `backend/research/` skeleton, `__init__.py`, conditional mount in `backend/app/__init__.py`, `RESEARCH_ENABLED` config, `/health` endpoint | new module + `app/__init__.py` | High |
| 8.B | `models.py`: `ResearchTask`, `SubTopic`, `ResearchSummary` dataclasses. Reuse `TaskManager` for tracking. Persist state to `uploads/research/{task_id}/state.json` | new | High |
| 8.C | `runners/api_runner.py` + `search/ddg.py`: fallback runner using existing `LLMClient` + DuckDuckGo. No CLI dependency. | new | High |
| 8.D | `orchestrator.py`: Plan → Research → Synthesise loop. ThreadPoolExecutor for parallel sub-topics. Per-phase routing via `Config.get_step_llm_config('research_plan')` and `('research_synthesis')` | new | High |
| 8.E | `availability.py`: probe `claude` / `codex` / `kimi` on PATH + auth status. Return structured `{name, available, auth, reason}` per runner | new | High |
| 8.F | `runners/claude_runner.py`: Claude Code CLI subprocess wrapper. Verify flags via `claude --help` first | new | Medium |
| 8.G | `runners/codex_runner.py`: OpenAI Codex CLI wrapper. Verify flags first | new | Medium |
| 8.H | `runners/kimi_runner.py`: Kimi CLI wrapper. Verify availability + flags first | new | Medium |
| 8.I | Frontend Step 0: `Step0Research.vue`, `ResearchSetup.vue`, `ResearchProgress.vue`, `ResearchPreview.vue`, `api/research.js`, router entry, Home.vue button, locale strings × 8 | frontend | High |
| 8.J | `docker-compose.research.yml` overlay mounting `~/.claude`, `~/.codex`, `~/.config/kimi` read-only. `setup.sh` opt-in prompt. Documentation. | new + setup.sh + docs | Medium |
| 8.K | `docs/research_module.md` user guide; update `docs/ARCHITECTURE.md` with module section | docs | Low |

### Reuses from earlier phases

| Phase 8 needs | Provided by | File |
|---------------|-------------|------|
| Per-step LLM routing for Plan + Synthesise phases | Phase 2 | `Config.get_step_llm_config()` in `backend/app/config.py` |
| Token tracking for research-phase consumption | Phase 3 | `TokenTracker` thread-local context |
| Provider capability detection (synthesis needs JSON) | Phase 5 | `LLMClient.chat_json` auto-fallback |
| Background task lifecycle + cancellation | Phase 7 | `TaskManager` + cancel events |
| Orphan project cleanup if research fails partway | Phase 7 | existing cleanup hook in graph API |
| ThreadPoolExecutor pattern for parallel work | Phase 0 (already present) | `oasis_profile_generator.py` |
| Subprocess + monitor thread pattern | Phase 0 (already present) | `simulation_runner.py` |

### Risks

- **CLI invocation flags**: each tool's unattended-mode flags must be verified via `--help` before writing the runner. Failed runners fall back to ApiRunner cleanly.
- **Subprocess env leakage**: pass an explicit minimal env dict to `subprocess.Popen` (only `PATH`, `HOME`, CLI's own config dir) to avoid leaking `LLM_API_KEY` etc into the CLI tool's context.
- **Output parsing**: CLIs print prose, not JSON. System prompt instructs runners to emit `=== SUMMARY ===` and `=== SOURCES ===` blocks; orchestrator captures all stdout regardless and treats cleaned text as the summary.
- **Docker volume mounts on Windows**: document Linux/macOS as primary; Windows users use API fallback or WSL.
- **`duckduckgo-search` reliability**: pin a version. If DDG breaks, swap for `tavily-python` (paid but reliable).

### Acceptance

- With `RESEARCH_ENABLED=false`, app starts unchanged and `/api/research/*` returns 404
- With `RESEARCH_ENABLED=true` and `RESEARCH_RUNNERS=api`, end-to-end research → compiled doc → Step 1 ontology generation works on a host with no CLI tools installed
- With Claude Code CLI installed locally, research using `runner_choice=claude` produces a compiled document with citations
- Pre-flight `/api/research/availability` correctly reports installed/uninstalled CLIs with reasons
- Docker overlay (`docker-compose.research.yml`) lets the slim image use the host's CLI configs for research
- Token usage from research phase is recorded under simulation `research_plan` and `research_synthesis` step labels
- Cancel button works during all three phases (Plan, Research, Synthesise)

### Plan reference

Detailed implementation steps and verification: `/Users/lor/.claude/plans/temporal-shimmying-moore.md` (plan file from the planning session).

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
                                                                                              │
                                                                                              ▼
                                                                                       Phase 8 (research-from-prompt)
                                                                                       (independent — can ship anytime
                                                                                        after Phases 2, 3, 5, 7)
```

---

## Version Roadmap

| Version | Contents | Estimated phases |
|---------|----------|------------------|
| v0.2.0 | Phase 0 | ✅ |
| v0.3.0 | Phase 1 (catalogue sync) | ✅ |
| v0.4.0 | Phase 2 (step routing) | ✅ |
| v0.5.0 | Phase 3 (token tracking) | ✅ |
| v0.6.0 | Phase 4 (multi-provider pool foundation) | 🚧 shipped without OASIS routing |
| v0.7.0 | Phase 5 (capability detection) | ✅ |
| v0.8.0 | Phase 6 (multi-model personas) | ✅ |
| v0.9.0 (current) | Phase 7 (QoL: pre-flight modal, cancel, orphan cleanup) | ✅ |
| v0.10.0 | Phase 8 (research-from-prompt add-on module) | 📋 next |
| v1.0.0 | Full feature set, stable API + live end-to-end tested | 💡 |

Versions are indicative, not deadlines. Features may ship sooner if they unlock testable value.
