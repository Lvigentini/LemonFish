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

## Feature: [placeholder — add next feature here]
