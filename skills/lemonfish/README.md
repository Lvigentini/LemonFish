# LemonFish skill for ClawHub

This directory contains the [AgentSkills](https://agentskills.io) manifest
that publishes LemonFish as a skill on [ClawHub](https://clawhub.com), the
skills registry for the [openclaw](https://github.com/openclaw/openclaw)
personal AI assistant.

## What it does

When installed, the skill tells an agent:

1. **When to invoke LemonFish** — trigger phrases like "what will happen
   with X?", "predict X", "how will stakeholders react to Y?"
2. **How to drive it** — install via `npm install -g lemonfish-cli`, then
   `lemonfish research --json "<prompt>"` streams phase progress and returns
   a compiled document with citations
3. **Cost and time awareness** — research is 1-3 minutes; full simulation
   via the browser UI is 10+ minutes; always ask the user before running
4. **Error handling** — exit codes and parseable stderr messages mapped to
   user-facing remediation steps

See [SKILL.md](./SKILL.md) for the full manifest.

## Installing the skill

End users install via the ClawHub CLI:

```bash
clawhub install lemonfish
```

This pulls the skill manifest and its declared prerequisite (the
`lemonfish-cli` npm package, which in turn pulls the published Docker image
from `ghcr.io/lvigentini/mirofish:latest`).

## Publishing updates

From this directory:

```bash
clawhub publish
```

The ClawHub CLI hashes the file and publishes a new version to the
registry. See the openclaw documentation at
<https://docs.openclaw.ai/tools/skills> for the full publishing workflow.

## Why the skill lives in-tree

We keep the skill in the LemonFish repo (rather than a separate
`LemonFish-skill` repo) so that:

- Skill versions track LemonFish releases automatically — when we bump the
  root `package.json` to 1.2.0, the skill version moves with it
- Commits that change the underlying CLI surface can update the skill in
  the same PR, preventing drift between `SKILL.md` trigger phrases and the
  actual CLI command surface
- There's one canonical "latest stable skill" for the project — no
  second-repo discovery problem

## Related

- [openclaw](https://github.com/openclaw/openclaw) — the agent runtime
- [ClawHub](https://clawhub.com) — the skills registry
- [AgentSkills](https://agentskills.io) — the open manifest standard
- [`cli/`](../../cli/) — the `lemonfish-cli` npm package this skill installs
- [`docs/research_module.md`](../../docs/research_module.md) — Phase 8
  research-from-prompt module, the agent-native entry point this skill
  exposes to openclaw
