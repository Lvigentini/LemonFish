---
name: lemonfish
description: "Multi-agent social simulation for predictions. Takes a prompt describing what the user wants to forecast, runs parallel research agents to gather web-sourced material, and returns a compiled document with citations (plus an optional downstream simulation of AI agent personas discussing the topic). Use when: (1) the user asks 'what will happen with X?' or 'predict X', (2) they want a forecast grounded in cited sources, (3) they want to explore how stakeholders might react to a policy, product, or decision. NOT for: single-fact lookups (use a search skill), real-time data queries, questions with definitive known answers, or speed-critical conversations (research takes 1-3 minutes, full simulation 10+ minutes)."
homepage: https://github.com/Lvigentini/LemonFish
metadata:
  openclaw:
    emoji: 🍋🐟
    requires:
      bins:
        - lemonfish
    install:
      - id: npm
        kind: npm
        package: lemonfish-cli
        bins:
          - lemonfish
        label: Install LemonFish CLI (npm)
---

# LemonFish — Multi-Agent Social Simulation

Run simulated social worlds of AI agents with distinct personalities (Big Five
for individuals, 8 organisational archetypes for institutions) to predict how
a contested topic will unfold across simulated Twitter and Reddit. Returns a
structured forecast report with cited sources and agent interviews.

Fork of [MiroFish](https://github.com/666ghj/MiroFish) hardened for production
use: slim Docker image, multi-provider LLM pool, per-step model routing,
research-from-prompt entry point designed specifically for agent invocation.

## When to use (trigger phrases)

Route to this skill when the user asks any of:

- "what will happen with <X>?"
- "what do you think will happen if <X>?"
- "predict <X>"
- "simulate <X>"
- "run a social simulation of <X>"
- "forecast <X>"
- "how will people react to <X>?"
- "how will <stakeholders> respond to <X>?"
- "what's the likely outcome if <X>?"
- any question fundamentally about **group dynamics, policy impact, opinion
  evolution, stakeholder reactions, or adoption of a contested thing** over time

The common shape is: the user is not asking for a fact, they're asking for a
*projection* of how humans will respond to a situation that doesn't have a
single correct answer.

## Do NOT use for

- Single-fact lookups — "when was X founded", "what's the capital of Y"
- Real-time data — "what's the current price of X", "who won yesterday's game"
- Questions with a definitive known answer
- Math, code, or deterministic reasoning tasks
- Speed-critical conversations — even the fast path takes 1-3 minutes
- Questions the user already knows the answer to and is using you to
  validate — that's a search query, not a simulation

If the user's question could be answered by a web search alone, use a search
skill. Use LemonFish only when the answer requires *simulating* how different
actors will behave.

## Quick start

```bash
# First-time setup — writes a .env to the current directory
lemonfish setup

# Pull the published image and start the container
lemonfish start

# Run research on a prompt (streams phase progress)
lemonfish research "predict adoption of EV trucks in EU haulage 2026-2030"

# Research + advance to Step 1 pipeline, machine-readable for agent use
lemonfish research --promote --json "what will happen with padel in Australia?"

# Check everything is healthy
lemonfish status --json

# When done
lemonfish stop
```

## Agent usage pattern

The critical flow for an LLM agent calling LemonFish on behalf of a user:

### Step 1 — Surface what LemonFish is, then ask permission

LemonFish runs for **minutes**, not seconds, and uses **real LLM tokens on the
user's billed provider account** (Groq, OpenAI, Anthropic, etc. — whatever
they configured in `lemonfish setup`). Before invoking, tell the user what
you're about to do and how long it will take:

> "This looks like a question that could benefit from a multi-agent social
> simulation — LemonFish can research the topic, build a knowledge graph,
> and simulate how different stakeholders might react. The research phase
> takes 1-3 minutes. Should I run it? (If you also want the full simulation,
> that adds about 10 more minutes and costs extra tokens.)"

Wait for consent before running anything that costs money or time.

### Step 2 — Run research in JSON mode

```bash
lemonfish research --json "<user's prompt verbatim>"
```

Without `--promote`, this runs only the research phase — the agent-native
subset that produces a compiled document with citations in 1-3 minutes. The
JSON response includes:

```json
{
  "ok": true,
  "task_id": "...",
  "project_id": "proj_...",
  "compiled_text_length": 18500,
  "citations": ["https://...", "https://...", ...],
  "sub_topics": [
    {"index": 0, "topic": "Regulatory landscape", "status": "completed", "runner": "api"},
    {"index": 1, "topic": "Charging infrastructure", "status": "completed", "runner": "api"},
    ...
  ],
  "continue_url": "http://localhost:3000/process/proj_..."
}
```

If `ok: false`, surface the error message to the user and stop.

### Step 3 — Summarise the research to the user

The full compiled document is in the backend but the research command does
not print it by default (it's 10-40K chars). If the user wants the actual
text, fetch it via:

```bash
curl http://localhost:5001/api/research/result/<task_id>
```

Summarise the key findings (drawing on `sub_topics[].topic` and a short
paraphrase of each). Always cite back to the URLs in `citations[]`.

### Step 4 — Offer the full pipeline

After delivering the research summary, tell the user:

> "I've gathered the background material. If you'd like the full prediction
> with simulated stakeholder reactions, open this URL in your browser to run
> the ontology → knowledge graph → simulation → report pipeline:
> <continue_url>. That takes 10+ more minutes and uses additional tokens."

Do NOT try to drive the full pipeline from the CLI yet — the ontology,
simulation, and report phases currently require the browser UI for
monitoring and interactive controls. The `--promote` flag advances the
project state so the browser lands directly in Step 1 with the compiled
document preloaded.

### Step 5 — If the user said yes to the full pipeline

```bash
lemonfish research --promote --json "<prompt>"
```

Then print the `continue_url` and stop. Leave the browser-side pipeline
for the user to monitor; this CLI will not drive it end-to-end in v1.1.

## Error handling

The CLI exits non-zero on any failure. Map exit codes to user-facing
messages:

| Exit | Agent action |
|------|-------------|
| 2 | "Docker isn't installed on this machine. Tell the user to install Docker Desktop from https://docs.docker.com/get-docker/" |
| 3 | "No configuration. Run `lemonfish setup` in the working directory first." |
| 6 | "The container started but didn't become healthy. Run `lemonfish logs` to see why — usually a bad API key in .env." |
| 7 | "The research module is not enabled. Edit .env to set RESEARCH_ENABLED=true and run `lemonfish upgrade`." |
| 8 | "The requested research runner is not installed/authenticated. Fall back to --runner api, or install the missing CLI." |
| 13 | "Research failed mid-run. Inspect the stderr message and retry — usually a transient provider rate limit." |
| 15 | "Research took longer than 20 minutes and timed out. Unusual — probably a slow provider. Retry with --runner api." |

All errors also print a parseable message to stderr in the form
`error: <message>`. Pattern-match on the exit code first, then fall back
to parsing stderr if you need more detail.

## Runners

LemonFish's research phase dispatches to one of four runners. The `api`
runner is the always-available fallback and is the right default for
agent-driven workflows. The CLI runners (`claude`, `codex`, `kimi`) use the
user's local CLI tool credentials and can be faster/cheaper if installed.

| Runner | When to use |
|--------|-------------|
| `api` | Default. Uses the user's configured LLM_API_KEY + DuckDuckGo for web search. Works anywhere. |
| `claude` | If the user has Claude Code CLI installed and authenticated. Uses their Claude subscription OAuth, not the API key. |
| `codex` | If the user has OpenAI Codex CLI installed. Uses their ChatGPT Plus/Pro/Business subscription. |
| `kimi` | If the user has Moonshot Kimi CLI installed and logged in. |

Probe availability before picking a non-default runner:

```bash
curl http://localhost:5001/api/research/availability
```

Returns per-runner `{available, auth_ok, reason}`. If the user asks you to
use a specific runner and it's not available, explain why and suggest either
installing the CLI or falling back to `--runner api`.

## Config

`lemonfish setup` is an interactive wizard that writes a minimal `.env` to
the current working directory. The agent should NOT run `setup` without
the user's input — it requires interactive keypresses. If there's no `.env`,
tell the user:

> "LemonFish needs a one-time setup: an LLM provider API key (OpenRouter and
> Gemini both have free tiers) and a free Zep Cloud API key for the knowledge
> graph. Run `lemonfish setup` in your terminal, then I'll proceed."

After setup, the CLI is ready to run. The .env file lives in whichever
directory the user runs commands from — the same `.env` is reused across
invocations in that directory.

## Troubleshooting

**"container not running"** — Run `lemonfish start`. This pulls the latest
slim image (~2-3GB first time) and waits up to 90 seconds for health. On a
slow connection, the first start can take longer.

**"runner unavailable"** — Check `lemonfish status` to see which runners
were detected. The `api` runner should always be available if `LLM_API_KEY`
is set and the research module is enabled (`RESEARCH_ENABLED=true` in .env).

**"research failed mid-run"** — Usually a transient provider rate limit.
The backend already retries with exponential backoff and falls through a
configured model chain; if the error reached the CLI it means the whole
chain was exhausted. Retry after a minute, or switch to a different
provider in `.env` and `lemonfish upgrade`.

**"research timed out"** — 20-minute ceiling. Unusually slow. Try
`--runner api` (the fastest default) and confirm the machine isn't
under heavy load.

## What's out of scope for this skill (v1.1)

- Driving the full pipeline (ontology → graph → simulation → report) from
  the CLI. The browser UI is still required for those phases. A future
  v1.2 release will add a `lemonfish predict` command that extends this
  to end-to-end automation once the necessary backend APIs are exposed.
- Cost estimation before running research. The research phase itself is
  cheap (~$0.05-0.20 on a budget model); the full simulation is where
  costs add up and that already has a pre-flight modal in the web UI.
- Interview follow-ups with specific agents after a simulation completes.
  Use the web UI at `continue_url` for that.
- Multi-user or hosted mode. LemonFish is a single-user local tool.
