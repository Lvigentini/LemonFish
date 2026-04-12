# LemonFish Research Module (Phase 8)

> **Status:** v0.10.0 candidate
> **Opt-in:** disabled by default — set `RESEARCH_ENABLED=true` to mount the module

The research module is an optional add-on that replaces the "upload documents" starting point of LemonFish with a **research-from-prompt** flow. A user enters a vague intent ("predict EV truck adoption in EU haulage 2026-2030") instead of curated source material, and the module orchestrates research agents to gather the material automatically before handing off to the existing Step 1 ontology generator.

**Everything downstream of Step 1 is unchanged.** The module writes its compiled output to the same `uploads/projects/{project_id}/extracted_text.txt` the upload flow produces, and the existing ontology generator consumes it as if it had come from a file upload.

---

## Architecture at a glance

```
User: vague prompt + simulation_requirement
   ↓
Frontend Step 0 → POST /api/research/start
   ↓
ResearchOrchestrator (background thread)
   ├── Plan       — 1 LLM call, decomposes prompt into 3-8 sub-topics
   ├── Research   — N parallel runner subprocesses, one per sub-topic
   └── Synthesise — 1 LLM call, merges summaries into a compiled document
   ↓
Writes compiled document → uploads/projects/{project_id}/extracted_text.txt
   ↓
Frontend promotes → existing Step 1 ontology generation
```

### Why an add-on module

The module lives in `backend/research/` as its own package. It is conditionally mounted from `backend/app/__init__.py`:

```python
try:
    from research import is_enabled as research_enabled, register_blueprint as register_research
    if research_enabled():
        register_research(app)
except ImportError:
    pass
```

If `RESEARCH_ENABLED` is not set or the package is missing entirely, the main app starts with zero changes and no `/api/research/*` routes. This keeps the module's heavier optional dependencies (`ddgs`, CLI subprocess wrappers) out of the core LemonFish install.

---

## Enabling the module

### Local development

```bash
# 1. Install the optional research dependencies
cd backend
uv sync --extra research

# 2. Set the master switch + pick runners
export RESEARCH_ENABLED=true
export RESEARCH_RUNNERS=api              # or: claude,codex,kimi,api

# 3. Run the backend + frontend as usual
cd ..
npm run dev
```

Navigate to **http://localhost:3000**, click the "**Or start with a research prompt →**" link below the main "Start Engine" button, and you should land on the new Step 0 view.

### Docker

Use the research compose overlay on top of the slim base:

```bash
docker compose -f docker-compose.slim.yml -f docker-compose.research.yml up -d
```

The overlay sets `RESEARCH_ENABLED=true` and mounts your host's CLI OAuth directories (`~/.claude`, `~/.codex`, `~/.config/kimi`) into the container read-only so the CLI runners can find their cached credentials. Comment out any mount line in `docker-compose.research.yml` for a CLI tool you haven't installed locally.

**Windows note:** the volume mount paths assume Linux/macOS home directory layout. Windows users should either run via WSL or use `RESEARCH_RUNNERS=api` only (the API fallback runner doesn't need CLI OAuth).

---

## Runner selection

The frontend Step 0 view probes `/api/research/availability` on load and shows each runner with a status dot:

- **Green** — installed and authenticated, ready to use
- **Yellow** — installed but not authenticated (run the CLI's login command)
- **Grey** — not installed (shows the install hint)

The user explicitly picks one runner per research task. There is no silent fallback — if Claude is selected but its auth expires mid-task, the task fails with a clear error rather than quietly switching to another runner.

### Available runners

| Runner | Credentials | Web search | Best for |
|--------|-------------|-----------|----------|
| `claude` | Claude Code CLI OAuth (`~/.claude`) | Built into Claude Code | Users with a Claude Max/Pro subscription; highest-quality summaries |
| `codex` | OpenAI Codex CLI (`~/.codex`) or `OPENAI_API_KEY` | Built into Codex tools | Users with ChatGPT Plus/Pro/Business |
| `kimi` | Kimi CLI config | Built into Kimi | Users with Moonshot AI credentials |
| `api` | `LLM_RESEARCH_PLAN_*` (falls back to primary `LLM_*`) | DuckDuckGo via `ddgs` | No CLI required; always-on fallback |

### Runner contract

Each runner is a small Python subclass of `research.runners.base.CLIRunner`:

```python
class CLIRunner(ABC):
    name: str

    @abstractmethod
    def is_available(self) -> AvailabilityResult:
        """Cheap probe: installed? authenticated? Called on every page load."""

    @abstractmethod
    def run(self, sub_topic, system_prompt, timeout) -> ResearchSummary:
        """Execute one sub-topic. Raises ResearchRunnerError on failure."""
```

CLI runners shell out via `subprocess.run` with an explicit minimal env dict — `LLM_API_KEY` and other LemonFish secrets are stripped before the CLI is invoked. Only `PATH`, `HOME`, `USER`, `LANG`, `TERM`, `TMPDIR`, `SHELL`, and CLI-specific keys (`OPENAI_API_KEY` for Codex, `MOONSHOT_API_KEY` for Kimi) are passed through.

---

## API endpoints

All mounted under `/api/research/*`:

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Module liveness check (404 if module disabled, 200 if enabled) |
| `GET` | `/availability` | Probe each enabled runner, return per-runner status |
| `POST` | `/start` | Begin a research task; spawns background thread, returns `{task_id, project_id}` |
| `GET` | `/status/<task_id>` | Poll phase + per-subtopic progress |
| `GET` | `/result/<task_id>` | Fetch compiled document + citations (completed tasks only) |
| `POST` | `/promote/<task_id>` | Write compiled doc to project and advance to Step 1 |
| `POST` | `/cancel/<task_id>` | Request cooperative cancellation |

### Start payload

```json
{
  "prompt": "predict EV truck adoption in EU haulage 2026-2030",
  "simulation_requirement": "Simulate fleet operator decisions under new CO2 regulations",
  "runner_choice": "claude",
  "project_name": "EU EV Trucks",
  "additional_context": null
}
```

### Status payload (trimmed)

```json
{
  "task": {
    "task_id": "...",
    "project_id": "proj_...",
    "phase": "researching",
    "sub_topics": [
      {"index": 0, "topic": "Regulatory landscape", "status": "completed", "runner": "claude"},
      {"index": 1, "topic": "Charging infrastructure", "status": "running", "runner": "claude"},
      {"index": 2, "topic": "Fleet operator economics", "status": "queued"}
    ],
    "compiled_text_length": 0
  }
}
```

The `compiled_text` field is **only** returned by `/result/<task_id>`, never by `/status/<task_id>`, to keep the polling payload small.

---

## Configuration reference

### Module-level env vars

| Variable | Default | Purpose |
|----------|---------|---------|
| `RESEARCH_ENABLED` | `false` | Master switch — module is not registered at all unless true |
| `RESEARCH_RUNNERS` | `api` | Comma-separated subset of `claude,codex,kimi,api` |
| `RESEARCH_DEFAULT_RUNNER` | `api` | Runner pre-selected in the frontend picker |
| `RESEARCH_MAX_PARALLEL` | `5` | Max concurrent sub-topic runners |
| `RESEARCH_AGENT_TIMEOUT` | `600` | Seconds per runner call |
| `RESEARCH_PLAN_MIN_SUBTOPICS` | `3` | Lower bound on plan decomposition |
| `RESEARCH_PLAN_MAX_SUBTOPICS` | `8` | Upper bound on plan decomposition |
| `RESEARCH_SYNTHESIS_MIN_CHARS` | `8000` | Target lower bound on compiled document length |
| `RESEARCH_SYNTHESIS_MAX_CHARS` | `40000` | Target upper bound on compiled document length |
| `RESEARCH_API_SEARCH_RESULTS` | `8` | Max DDG results per sub-topic (api runner) |
| `RESEARCH_API_FETCH_TOP` | `4` | How many top URLs to fetch + summarise (api runner) |

### LLM routing (reuses Phase 2)

The Plan and Synthesise phases use `Config.get_step_llm_config('research_plan')` and `('research_synthesis')` — the same helper Phase 2 introduced for per-step model routing. That means you can route these two phases to different providers independently:

```env
# Plan: structured output, JSON mode
LLM_RESEARCH_PLAN_API_KEY=...
LLM_RESEARCH_PLAN_BASE_URL=https://api.groq.com/openai/v1
LLM_RESEARCH_PLAN_MODEL=llama-3.3-70b-versatile

# Synthesise: long-context, high-quality writer
LLM_RESEARCH_SYNTHESIS_API_KEY=...
LLM_RESEARCH_SYNTHESIS_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_RESEARCH_SYNTHESIS_MODEL=gemini-3-flash-preview
```

If unset, both phases fall back to the primary `LLM_*` config.

---

## Storage layout

Each research task has its own directory under `uploads/research/{task_id}/`:

```
uploads/research/{task_id}/
  state.json         # full ResearchTask snapshot, atomically rewritten on every phase transition
```

Research tasks are persisted across server restarts — `/status/<task_id>` reads from disk, not memory — so a user can close the browser tab, return, and still see the final result. This differs from the graph-build task pattern (in-memory only) and is necessary because research runs can take several minutes.

When the user clicks "Continue to ontology generation" on the preview screen, the `/promote/<task_id>` endpoint copies the compiled document into the project's `extracted_text.txt` and updates the project metadata. From then on, the project is indistinguishable from one created by the upload flow.

---

## Troubleshooting

### `/api/research/availability` returns 404

The research module is not enabled. Check:

1. `RESEARCH_ENABLED=true` is set in your `.env`
2. The `backend/research/` package exists (it's committed to the repo; only missing if you're on an old branch)
3. Backend logs show `"Research module enabled — /api/research/* registered"` on startup

### All runners show "not installed" in the picker

The `api` runner is always available as a fallback — if it's also showing unavailable, the likely causes are:

- `ddgs` is not installed → run `uv sync --extra research` or `pip install ddgs`
- `LLM_API_KEY` is not set → you need at least one LLM provider configured

### Claude runner shows "Installed but not authenticated"

Run `claude auth login` on the host (or inside the container). In Docker, the container's `/root/.claude` is a read-only mount of the host's `~/.claude`, so you need to log in on the host, not inside the container.

### Codex or Kimi runner flags don't match your install

The Codex and Kimi CLIs change their unattended-mode flags between releases. The runners in `backend/research/runners/codex_runner.py` and `kimi_runner.py` try a small list of candidate invocation patterns. If none work with your installed version, update `_INVOCATION_TEMPLATES` in those files to match your CLI's `--help` output and open a PR.

### Research task stuck in `running` state

The orchestrator polls for cooperative cancellation at phase boundaries. Individual runner subprocess timeouts are enforced via `RESEARCH_AGENT_TIMEOUT` (default 600s). If you need to force-kill a task, hit `/api/research/cancel/<task_id>` — the orchestrator will mark the task `cancelled` the next time it checks between phases.

---

## Design decisions (reference)

**Why not reuse the simulation subprocess pattern?** The simulation runner is tightly coupled to OASIS; research runners are simpler (one-shot invocation per sub-topic, no IPC, no long-lived subprocess). A thin ThreadPoolExecutor fan-out gave us everything we needed.

**Why write state to disk instead of TaskManager only?** TaskManager is in-memory and loses tasks on restart. Research runs can take several minutes, and a browser refresh or a quick backend restart during development shouldn't throw away work. The on-disk `state.json` also gives us forensic access to failed runs.

**Why explicit runner choice instead of auto-fallback?** Each runner produces noticeably different output characteristics (Claude Code writes polished prose with inline URLs, the API runner writes drier technical summaries). Auto-swapping mid-task would produce an inconsistent compiled document. The user picks one runner and lives with it for that task.

**Why JSON mode for the Plan phase?** The orchestrator needs a structured list of sub-topics with guaranteed shape. The Synthesise phase is free-form prose, so it uses regular chat completion. Phase 5 (capability detection) means even providers without native `response_format` support (Anthropic, Grok) will work — the client falls back to prompt-based JSON extraction.
