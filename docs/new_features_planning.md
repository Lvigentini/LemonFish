# MiroFish — New Features Planning

## Feature: Multi-Model Persona Assignment

### Rationale

Using a single LLM for all simulated agents introduces monoculture artifacts — correlated biases in tone, reasoning patterns, conflict behaviour, and topic avoidance that are characteristic of a specific model's training. Randomising model assignment across agents produces more authentic variation in group dynamics, analogous to how real people have fundamentally different cognitive architectures despite similar stated beliefs.

### Design Principles

1. **Random assignment, not role-based**: Models should be randomly assigned to personas. We explicitly reject the premise that "stronger" models should play "more important" roles — this introduces an unjustified assumption about model capability mapping to social influence. A 7B model playing a professor may produce behaviour that is *different*, not *worse*.

2. **Model lock per agent**: Once a model is assigned to an agent at simulation start, that agent MUST use the same model for the entire simulation run. Fallback to a different model mid-simulation would compromise positional integrity — the agent's "voice", reasoning patterns, and established positions could shift in ways that break continuity and contaminate results.

3. **Fallback affects availability, not identity**: If an agent's assigned model becomes unavailable (rate limit, outage), the correct behaviour is to **skip that agent's turn** or **pause and retry**, NOT to route to a fallback model. The agent should remain silent rather than speak with a different cognitive architecture.

### Implementation Considerations

- Model pool defined in config (e.g., `LLM_AGENT_MODELS=model1,model2,model3`)
- Assignment stored in agent profile at simulation start (reproducible via seed)
- Simulation runner respects per-agent model config when making LLM calls
- Rate limit handling: per-model backoff; agent skips turn if model exhausted
- Reporting: track which model each agent used (for analysis of model-specific patterns)

### Open Questions

- How many distinct models are needed before monoculture effects meaningfully reduce? (2? 4? 8?)
- Should assignment be uniform random or weighted by model availability/rate limits?
- Should the user be able to see/control the distribution (e.g., "60% Gemma, 30% Llama, 10% Mistral")?
- How to handle the case where ALL instances of a model are rate-limited — do those agents go permanently silent for that round, or do we extend the round duration?
- Would mixing model families (e.g., one open-source, one proprietary) in the same sim introduce confounds that make results harder to interpret?

### Impact on Current Architecture

- **simulation_runner.py / run_*_simulation.py**: Currently call `ModelFactory.create()` once for all agents. Would need per-agent model instantiation.
- **OASIS framework**: Need to verify whether camel-oasis supports per-agent model configs or if this requires a fork/patch.
- **Rate limiting**: Currently global; would need per-model tracking.
- **Cost**: Multi-model runs using paid APIs need per-model cost tracking.
- **Reproducibility**: Random seed must be stored for model assignment to allow re-runs.

---

## Feature: LLM Provider & Model Modernisation

### Rationale

A live audit of all 10 supported providers (2026-04-11) found significant drift between `setup.sh` defaults and actual current model availability/pricing. See [`docs/llm_providers.md`](./llm_providers.md) for the verified state of each provider — that file is the source of truth and is maintained on a weekly cadence by the `/llm-provider-tracker` skill.

The drift falls into three categories: stale defaults (newer/cheaper/better models exist), deprecated models still being pointed at, and outdated pricing assumptions in our docs. This needs to be addressed before — or alongside — the multi-model persona work above, because both features depend on having an accurate, current provider catalogue.

### Concrete Issues Found

| File | Line | Current | Should be | Why |
|------|------|---------|-----------|-----|
| `setup.sh` | 82 | `claude-sonnet-4-20250514` | `claude-sonnet-4-6` | Same price, better model. Current is `4-6`, not `4-20250514` |
| `setup.sh` | 91 | `grok-3-mini` | `grok-4-1-fast-non-reasoning` | `grok-3-mini` not visible in current xAI docs; `grok-4-1-fast` is the current budget option |
| `setup.sh` | 58 | `gpt-4o-mini` | Consider `gpt-5-nano` ($0.05/$0.40) or `gpt-4.1-nano` ($0.10/$0.40) | Cheaper, newer; gpt-4o-mini is mid-tier now |
| `docs/llm_budget_planning.md` | DeepSeek section | `$0.27/$1.10` | `$0.28/$0.42` | Pricing changed Sep 2025; reasoner now matches chat |
| `docs/llm_budget_planning.md` | Groq section | Lists `gemma2-9b-it` | Replace with `gpt-oss-20b`, `kimi-k2-instruct`, `qwen3-32b` | gemma2 no longer in Groq lineup |
| `setup.sh` | provider list | No Groq option | Add Groq as option 9 (move custom to 10) | Documented free tier, fast inference, strong fit |
| `setup.sh` | provider list | No Ollama option | Add as option 10 | Already documented as compatible |

### Scope

**Phase 1 — Sync existing defaults** (small, high-value):
1. Update `setup.sh` defaults for Anthropic, Grok, OpenAI
2. Update `docs/llm_budget_planning.md` provider tables to match `docs/llm_providers.md`
3. Add Groq and Ollama as first-class options in the wizard (currently only reachable via "custom")
4. Update `.env.example` if any new env vars are needed for Groq/Ollama defaults

**Phase 2 — Per-step model overrides** (already partially scaffolded):
The codebase already has `LLM_ONTOLOGY_API_KEY` / `LLM_ONTOLOGY_BASE_URL` / `LLM_ONTOLOGY_MODEL` env vars in `backend/app/config.py:36-39` but they're not exposed in the wizard or documented. Different pipeline steps have very different requirements:

| Step | Best fit | Why |
|------|----------|-----|
| Ontology generation | Long-context, high-quality (Gemini 2.5 Pro, Claude Sonnet 4.6, GPT-5.4) | One call, large input, must produce structured ontology — quality matters more than cost |
| Profile generation | Cheap, fast, JSON-capable (gpt-5-nano, gemini-flash-lite, deepseek-chat) | N parallel calls, structured output, low individual stakes |
| Simulation | Cheap free-tier (Groq llama-3.1-8b, OpenRouter free, Gemini Flash) | Dominates cost (~90% of tokens) — must be free or near-free to be viable |
| Report (ReACT) | Mid-tier reasoning (Claude Sonnet, Gemini 2.5 Pro, gpt-4.1) | Tool calls + multi-step reasoning, but single user-facing artefact |

Expose the per-step overrides in the wizard and document them. This is the natural precursor to multi-model persona assignment because it proves the codebase can route different calls to different providers.

**Phase 3 — Provider capability detection** (defensive):
At LLMClient init, probe whether the configured provider supports `response_format`. If not (Anthropic, possibly Grok), switch to prompt-based JSON extraction automatically rather than relying on the current "strip markdown fences" workaround. Currently `chat_json()` in `backend/app/utils/llm_client.py:126` always passes `response_format` and hopes for the best.

### Open Questions

- Do we want a "recommended preset" UX? E.g., wizard asks "free tier" / "best quality" / "balanced" / "Chinese-language" and picks providers + per-step assignments accordingly
- Should the wizard fetch the live provider catalogue (via the `/llm-provider-tracker` skill output) at install time, or trust the static defaults
- The per-step overrides currently only exist for ontology — should we add `LLM_SIMULATION_*`, `LLM_REPORT_*`, `LLM_PROFILES_*` for symmetry, or does that overcomplicate the env file?
- How does this interact with the multi-model persona feature? Per-step overrides are orthogonal to per-agent assignment, but the config schema needs to accommodate both without becoming unreadable

### Dependencies

- Must run after / alongside `/llm-provider-tracker audit` to get the latest verified data
- Multi-model persona feature (above) depends on Phase 2 of this — having a clean way to route different calls to different providers is a prerequisite

---

## Feature: Research-From-Prompt Add-On Module

### Rationale

LemonFish currently requires the user to upload curated documents (PDF/MD/TXT) before Step 1 can generate an ontology. This is a high-friction starting point for users with a vague intent ("predict EV truck adoption in EU haulage 2026-2030") but no curated source material. This feature adds an optional **Step 0** that decomposes a vague prompt into research questions, dispatches multiple research agents in parallel via web search, and compiles their findings into the same `extracted_text.txt` artefact the existing pipeline already consumes. **No changes to Step 1-5 code paths.**

The user has explicitly asked for this to be built as a **separate but connected add-on module** so heavy/optional dependencies (CLI wrappers, search libs) stay isolated from the main backend, the module can be enabled/disabled per deployment, and the CLI-OAuth integration does not bleed into the core app's hard requirements.

The user has also explicitly asked to use **CLI OAuth** for OpenAI Codex CLI, Claude Code CLI, and Kimi CLI for the research phase — this lets research-heavy work consume the user's personal subscription rather than burn API credits, and gives each research agent native web search via the CLI tools' built-in capabilities.

### Confirmed design decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Runtime support | Both local dev and Docker, with automatic API fallback when CLIs unavailable | Local hosts have CLIs; Docker users can mount config dirs or fall back to API runner |
| UI integration | New optional Step 0 prefix before Step 1 | Skippable — user can still upload documents directly |
| CLI fallback | Pre-flight availability check + explicit user choice | No silent fallback; the user picks Claude / Codex / Kimi / API after seeing what's available |
| Module structure | Add-on module: own dir, conditionally registered Flask blueprint | Main app starts unchanged when disabled or absent |

### Architecture

```
User: vague prompt + simulation_requirement
   ↓
Frontend Step 0 → POST /api/research/start
   ↓
ResearchOrchestrator (background thread, daemon)
   │
   ├── PLAN phase (1 LLM call via Config.get_step_llm_config('research_plan'))
   │     Decompose the prompt into 3-8 sub-topics with research questions
   │
   ├── RESEARCH phase (ThreadPoolExecutor, parallel)
   │     For each sub-topic, dispatch to a CLIRunner or ApiRunner
   │     Each runner returns a structured ResearchSummary with citations
   │
   └── SYNTHESIS phase (1 LLM call via Config.get_step_llm_config('research_synthesis'))
         Merge N summaries into a single coherent compiled document
   ↓
Write compiled document to uploads/projects/{project_id}/extracted_text.txt
   ↓
Promote project to ONTOLOGY_GENERATED-ready state
   ↓
Frontend transitions to existing Step 1 (ontology generator consumes the file unchanged)
```

### Module layout

```
backend/
  research/                                # NEW add-on module
    __init__.py                            # exports register_blueprint(app), is_enabled()
    config.py                              # RESEARCH_* env vars, CLI list, parallelism, timeouts
    api.py                                 # Flask blueprint with /api/research/* endpoints
    orchestrator.py                        # ResearchOrchestrator: plan → research → synthesise
    models.py                              # ResearchTask state, ResearchSummary, SubTopic dataclasses
    availability.py                        # detect installed/authenticated CLIs and search libs
    runners/
      base.py                              # CLIRunner abstract base + ApiRunner protocol
      claude_runner.py                     # subprocess wrapper for `claude` CLI
      codex_runner.py                      # subprocess wrapper for `codex` CLI
      kimi_runner.py                       # subprocess wrapper for `kimi` CLI
      api_runner.py                        # fallback: LLMClient + duckduckgo_search
    search/
      ddg.py                               # DuckDuckGo client wrapper

backend/app/__init__.py                    # ~5-line addition: conditionally register research blueprint

frontend/src/
  views/Step0Research.vue                  # NEW
  components/research/ResearchSetup.vue    # prompt + CLI picker (driven by availability probe)
  components/research/ResearchProgress.vue # per-sub-topic progress
  components/research/ResearchPreview.vue  # compiled output + citations preview
  api/research.js                          # NEW

docker-compose.research.yml                # NEW overlay mounting CLI config dirs
```

### API surface (Flask blueprint at `/api/research`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/availability` | Pre-flight: returns `{cli_runners: [{name, available, auth, reason}], api_fallback, docker_mode}` |
| `POST` | `/start` | Body: `{prompt, simulation_requirement, runner_choice, project_name?}`. Creates project + research task, spawns background thread, returns `{project_id, task_id}` |
| `GET` | `/status/<task_id>` | Returns `{status, phase, sub_topics: [...], error?}`. Frontend polls this |
| `GET` | `/result/<task_id>` | Returns compiled document text + citation list |
| `POST` | `/promote/<task_id>` | Writes compiled document to `uploads/projects/{project_id}/extracted_text.txt`, sets project status, returns `{project_id}` |

### CLI runner contract

Each runner implements:

```python
class CLIRunner(ABC):
    name: str  # 'claude' | 'codex' | 'kimi' | 'api'

    @abstractmethod
    def is_available(self) -> AvailabilityResult: ...

    @abstractmethod
    def run(self, sub_topic: SubTopic, system_prompt: str, timeout: int) -> ResearchSummary: ...
```

| Runner | Invocation pattern (verify via `--help` before implementing) |
|--------|--------------------------------------------------------------|
| `claude_runner.py` | `claude -p "<prompt>" --output-format text` (Claude Code CLI; web search built in) |
| `codex_runner.py` | `codex exec --no-tui "<prompt>"` (OpenAI Codex CLI; web search via tools) |
| `kimi_runner.py` | Verify Kimi CLI command and unattended-mode flags during implementation |
| `api_runner.py` | `LLMClient` + `duckduckgo-search`: loop search → fetch → summarise |

### Configuration (new env vars)

```env
# Master switch — if false, the research blueprint is not registered
RESEARCH_ENABLED=true

# Which runners to enable (comma-separated subset of: claude,codex,kimi,api)
RESEARCH_RUNNERS=claude,codex,kimi,api

# Default runner if frontend doesn't override
RESEARCH_DEFAULT_RUNNER=api

# Parallelism / timeouts
RESEARCH_MAX_PARALLEL=5
RESEARCH_AGENT_TIMEOUT=600
RESEARCH_PLAN_MIN_SUBTOPICS=3
RESEARCH_PLAN_MAX_SUBTOPICS=8

# Per-phase LLM overrides (consume Phase 2's get_step_llm_config helper)
LLM_RESEARCH_PLAN_API_KEY=
LLM_RESEARCH_PLAN_BASE_URL=
LLM_RESEARCH_PLAN_MODEL=
LLM_RESEARCH_SYNTHESIS_API_KEY=
LLM_RESEARCH_SYNTHESIS_BASE_URL=
LLM_RESEARCH_SYNTHESIS_MODEL=
```

`Config.get_step_llm_config()` (added in Phase 2) is consumed unchanged — `'research_plan'` and `'research_synthesis'` become recognised step names purely by convention.

### Conditional blueprint registration

In `backend/app/__init__.py` (~5 lines added):

```python
try:
    from ..research import register_blueprint as register_research, is_enabled as research_enabled
    if research_enabled():
        register_research(app)
        app.logger.info("Research module enabled")
except ImportError:
    app.logger.info("Research module not installed")
```

If the `research/` package is missing or `RESEARCH_ENABLED=false`, the main app starts unchanged with no `/api/research/*` routes.

### Docker support

A new compose overlay `docker-compose.research.yml` mounts the user's CLI config dirs read-only:

```yaml
services:
  lemonfish:
    volumes:
      - ${HOME}/.claude:/root/.claude:ro
      - ${HOME}/.codex:/root/.codex:ro
      - ${HOME}/.config/kimi:/root/.config/kimi:ro
    environment:
      - RESEARCH_ENABLED=true
```

Used as `docker compose -f docker-compose.slim.yml -f docker-compose.research.yml up`. The `setup.sh` wizard adds an optional final prompt: "Enable research module? Requires CLI tools installed locally and mounts your `~/.claude`, `~/.codex`, `~/.config/kimi` config dirs into the container." Default: no.

If declined or if the CLIs aren't installed, `RESEARCH_ENABLED=true` with `RESEARCH_RUNNERS=api` still works via the API fallback runner.

### Reuses from earlier phases

| Phase 8 needs | Provided by | File |
|---------------|-------------|------|
| Per-step LLM routing for Plan + Synthesise | Phase 2 | `Config.get_step_llm_config()` in `backend/app/config.py` |
| Token tracking for research-phase LLM consumption | Phase 3 | `TokenTracker` thread-local context |
| Provider capability detection (synthesis JSON output) | Phase 5 | `LLMClient.chat_json` auto-fallback |
| Background task lifecycle + cancellation | Phase 7 | `TaskManager` + cancel events |
| Orphan project cleanup if research fails partway | Phase 7 | existing cleanup hook in graph API |
| ThreadPoolExecutor pattern for parallel work | already present | `oasis_profile_generator.py` |
| Subprocess + monitor thread pattern | already present | `simulation_runner.py` |
| Frontend task polling pattern | already present | `Step1GraphBuild.vue` |

### Implementation phasing

| Step | Scope | Verification |
|------|-------|--------------|
| **8.A — Module scaffold** | `backend/research/` skeleton, `__init__.py` with `register_blueprint`/`is_enabled`, conditional mount in `backend/app/__init__.py`, `RESEARCH_ENABLED` config, `/health` endpoint | `curl /api/research/health` returns 200 when enabled, 404 when disabled. App still starts when `research/` dir is removed entirely. |
| **8.B — Models + storage** | `models.py`, reuse `TaskManager`, persist research task state to `uploads/research/{task_id}/state.json` | Unit test: create task, update progress, read back state |
| **8.C — ApiRunner + DDG search** | `runners/api_runner.py` and `search/ddg.py`. Loop: search → fetch top N URLs → summarise via `LLMClient`. No CLI dependency. | End-to-end with `runner_choice=api`: compiled doc lands in project's `extracted_text.txt` |
| **8.D — Orchestrator** | Plan → Research → Synthesise loop. ThreadPoolExecutor for parallel sub-topics. Per-phase LLM calls via `get_step_llm_config('research_plan')` and `('research_synthesis')` | Run end-to-end with just ApiRunner; verify N parallel sub-topics finish independently |
| **8.E — Availability probe** | `availability.py`: check `claude`/`codex`/`kimi` on PATH; run each tool's `--version` or auth-check; return structured result | `GET /api/research/availability` returns correct results in env where Claude is installed but Codex isn't |
| **8.F — ClaudeRunner** | Verify flags via `claude --help`. Capture stdout, parse, return summary with citations | End-to-end with `runner_choice=claude` on a host with Claude Code CLI installed |
| **8.G — CodexRunner** | Verify flags first | Same end-to-end test pattern |
| **8.H — KimiRunner** | Verify availability + flags first | Same end-to-end test pattern |
| **8.I — Frontend Step 0** | New view, components, router entry, API client, locale strings × 8. Wire `/availability` probe into the picker. Promote button transitions to existing Step 1 | Manual run-through: enter prompt, watch progress, preview, promote, ontology runs against compiled doc |
| **8.J — Docker overlay** | `docker-compose.research.yml`, `setup.sh` prompt, docs | `docker compose -f docker-compose.slim.yml -f docker-compose.research.yml up` and verify Claude CLI subprocess works inside the container |
| **8.K — Plan doc updates** | Cross-link `implementation_plan.md` Phase 8 ↔ this section ↔ `research_module.md` | Docs review |

Steps 8.A–8.D produce a fully functional research feature with no CLI dependency at all (API fallback only). Steps 8.E–8.H layer the CLI runners on top. Steps 8.I–8.K are UX and packaging.

### Risks

| Risk | Mitigation |
|------|-----------|
| CLI unattended-mode flags differ from assumed (Codex `exec` syntax may have changed, Kimi CLI may not exist or be alpha) | Verify with `--help` and a smoke test before writing each runner. Failed runners fall back to ApiRunner cleanly. |
| Output parsing brittleness — CLIs print prose, not JSON | System prompt asks runners to emit `=== SUMMARY ===` and `=== SOURCES ===` blocks. Capture all stdout regardless and treat cleaned text as the summary. |
| Docker volume mounts fail on Windows hosts | Document Linux/macOS as primary; Windows users use API fallback or WSL |
| `duckduckgo-search` rate-limited or breaking changes | Pin a version. If DDG breaks, swap for `tavily-python` (paid but reliable) |
| Citation tracking — research agents must surface source URLs | Make this part of the runner output contract (`ResearchSummary.citations: list[str]`). Synthesis prompt is told to preserve citations inline. |
| The CLI subprocess inherits parent process environment, leaking `LLM_API_KEY` etc into the CLI tool's context | Pass an explicit minimal environment dict to `subprocess.Popen` (only `PATH`, `HOME`, CLI's own config dir) |
| Project status state machine — research-driven projects skip the upload step but still need to land in `ONTOLOGY_GENERATED`-ready state | The `/promote` endpoint sets the status explicitly. Verified by exploration that `OntologyGenerator` doesn't care how the file arrived. |

### Open questions (not blockers)

- Should the compiled document target a specific length (~10K-50K chars) to match what an uploaded document looks like? Lean yes — feed this constraint into the synthesis prompt.
- Should the module emit a `metadata.json` alongside `extracted_text.txt` recording the prompt, sub-topics, runners used, citations, and total tokens? Useful for auditability but not required for v1.
- Add a "re-research" button if the user is unhappy with the synthesis output, or expect them to start over with a refined prompt? Lean toward the latter for v1.
- Should the orchestrator emit user-facing strings via existing `t()` keys, or add new keys under a `research` section in each locale file? Lean toward new keys for translator clarity.

### Out of scope (deliberate)

- Persistent caching of research results across runs with the same prompt
- Automatic re-research when synthesis confidence is low
- Admin UI for managing CLI installations
- Multi-pass research (Plan → Research → Critique → Re-research → Synthesise)

### Plan reference

Detailed file-by-file implementation plan: `/Users/lor/.claude/plans/temporal-shimmying-moore.md`
Roadmap slot: `docs/implementation_plan.md` Phase 8 / v0.10.0
