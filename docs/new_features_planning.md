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

## Feature: [placeholder — add next feature here]
