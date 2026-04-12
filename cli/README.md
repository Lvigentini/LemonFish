# lemonfish-cli

CLI for [**MiroFish \[LemonFish\]**](https://github.com/Lvigentini/LemonFish) — a multi-agent social simulation engine for predictions.

Manages the Docker container lifecycle and drives the research-from-prompt API so agents and humans can run predictions from a single command.

## Install

```bash
npm install -g lemonfish-cli
```

Requirements:
- **Node 18+** (uses the global `fetch` API)
- **Docker** with the `compose` plugin
- A [Zep Cloud](https://app.getzep.com/) free-tier API key
- An API key from any OpenAI-compatible LLM provider (OpenRouter and Gemini have free tiers)

## Quick start

```bash
# First-time setup — interactive .env wizard
lemonfish setup

# Pull the slim image and start the container
lemonfish start

# Run research on a vague prompt
lemonfish research "predict adoption of EV trucks in EU haulage 2026-2030"

# Check health
lemonfish status
```

Open <http://localhost:3000> to use the full web UI after `lemonfish start`.

## Commands

### Lifecycle

| Command | What it does |
|---------|--------------|
| `lemonfish setup` | Interactive wizard that writes a minimal `.env` in the current directory |
| `lemonfish start` | `docker compose pull` + `up -d` on the bundled compose file, waits for `/health` |
| `lemonfish status` | Container + backend health + research module runner status |
| `lemonfish stop` | `docker compose down` |
| `lemonfish logs [--no-follow]` | Tail container logs |
| `lemonfish upgrade` | Pull latest image and recreate container |

### Research (Phase 8 — agent-native entry point)

```bash
lemonfish research "<prompt>" [flags]
```

Drives the research-from-prompt orchestrator end-to-end. Auto-starts the container if it isn't running. Streams phase progress (planning → researching → synthesising) and returns a compiled document with citations.

| Flag | Default | Purpose |
|------|---------|---------|
| `--runner <name>` | `api` | Which research runner to use: `api`, `claude`, `codex`, `kimi` |
| `--requirement "<text>"` | auto-generated from prompt | Override the simulation requirement sent to the orchestrator |
| `--promote` | off | After research completes, advance the project into the Step 1 pipeline and return the project id |

After research completes, the CLI prints a URL for the Step 1 → 5 pipeline (ontology → graph → simulation → report) to continue in the browser. With `--promote`, the project state is advanced so the browser lands directly in Step 1 with the compiled document already loaded.

### Global flags

- `--json` — machine-readable output, one JSON object per command (use for agent consumption)

## Environment overrides

| Variable | Default | Purpose |
|----------|---------|---------|
| `LEMONFISH_API` | `http://localhost:5001` | Backend URL (change if you run on a non-standard port) |
| `LEMONFISH_UI` | `http://localhost:3000` | Frontend URL (same) |

## Agent usage

The CLI is designed to be driven by AI agents (Claude Code, Codex, Cursor, openclaw, etc.). The invocation pattern for an agent that's been asked to make a prediction:

```bash
# 1. Check cost estimation is not part of this CLI yet — research itself is
#    relatively cheap. For full simulation cost preview, use the web UI.

# 2. Drive research + promote, machine-readable
lemonfish research --promote --json "what will happen with X?"

# 3. Parse the returned JSON for: task_id, project_id, compiled_text_length,
#    citations, continue_url. The agent can then either:
#    (a) return the compiled document summary to the user, or
#    (b) tell the user to open continue_url to run the full pipeline
```

The JSON envelope always includes `ok: true|false` so agents can branch on failure cleanly. Exit codes are non-zero on any failure with a parseable error on stderr.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Bad arguments / unknown command |
| 2 | Docker not available |
| 3 | No `.env` in current directory |
| 4 | Missing required credentials during setup |
| 5 | `docker compose` command failed |
| 6 | Backend did not become healthy within timeout |
| 7 | Research module is not enabled in `.env` |
| 8 | Requested runner is not available |
| 9 | `/api/research/start` failed |
| 10 | Status check: container not running |
| 11 | Status check: backend unreachable / result fetch failed |
| 12 | `/api/research/promote` failed |
| 13 | Research run failed during execution |
| 14 | Research was cancelled |
| 15 | Research timed out (20 minutes) |
| 99 | Unhandled exception |

## Troubleshooting

**`docker is not installed or not on PATH`**
Install Docker Desktop or the `docker-ce` + `docker-compose-plugin` packages.

**`no .env file in <dir>`**
Run `lemonfish setup` first — the CLI operates out of the current working directory and expects `.env` to live there.

**`backend did not become healthy within 90s`**
Cold-start on a slow machine can take longer. Run `lemonfish logs` to see what's happening. If ontology generation or graph building has consumed the container, the health check may be blocked — this is expected on first use.

**`research module is not enabled`**
Set `RESEARCH_ENABLED=true` in `.env` and `lemonfish upgrade` (or `lemonfish stop && lemonfish start`).

**Runner shows as unavailable**
The `api` runner needs only `LLM_API_KEY` and the `ddgs` package (both bundled in the slim image). The `claude`, `codex`, `kimi` runners need their respective CLIs installed and authenticated on the host. Docker runners need the host config dirs mounted via `docker-compose.research.yml`.

## License

AGPL-3.0, matching the upstream MiroFish project.
