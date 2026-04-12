#!/usr/bin/env node
/**
 * lemonfish-cli — thin CLI for MiroFish [LemonFish]
 *
 * A single-file Node script (no external deps beyond Node built-ins) that:
 *   1. Manages the Docker container lifecycle (start, stop, status, logs, upgrade)
 *   2. Drives the research-from-prompt API (the agent-native Phase 8 entry point)
 *   3. Wraps the setup wizard for first-time .env creation
 *
 * Design patterns, in brief:
 *   - Mirrors the `mcporter` skill pattern: same binary owns both the daemon
 *     lifecycle commands and the primary operation verbs
 *   - Streams progress for long-running operations so calling agents see
 *     meaningful status instead of a black-box wait
 *   - JSON mode (--json) for machine consumption; human mode by default
 *   - Non-zero exit with parseable error code on failure
 *
 * Bundled compose file is shipped next to this script at ../compose/docker-compose.yml.
 * The CLI operates out of the user's current working directory (where .env lives).
 */

import { spawn, spawnSync } from 'node:child_process';
import { createInterface } from 'node:readline/promises';
import { readFile, writeFile, access, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { stdin as input, stdout as output } from 'node:process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// --------------------------------------------------------------------------
// Constants
// --------------------------------------------------------------------------

const PKG_VERSION = '1.1.0';
const BACKEND_BASE = process.env.LEMONFISH_API || 'http://localhost:5001';
const FRONTEND_BASE = process.env.LEMONFISH_UI || 'http://localhost:3000';
const BUNDLED_COMPOSE = resolve(__dirname, '..', 'compose', 'docker-compose.yml');
const WORK_DIR = process.cwd();
const ENV_FILE = join(WORK_DIR, '.env');

// Default startup wait: the slim image takes ~15-30s to be ready on cold start
const HEALTH_WAIT_MS = 90_000;
const HEALTH_POLL_INTERVAL = 2_000;

// Research polling
const RESEARCH_POLL_INTERVAL = 2_500;
const RESEARCH_MAX_WAIT_MS = 20 * 60 * 1_000; // 20 minutes upper bound

// --------------------------------------------------------------------------
// Output helpers (respect --json mode)
// --------------------------------------------------------------------------

let jsonMode = false;

function log(msg) {
  if (!jsonMode) process.stderr.write(`${msg}\n`);
}

function info(msg) { log(`  ${msg}`); }
function step(msg) { log(`→ ${msg}`); }
function ok(msg) { log(`✓ ${msg}`); }
function warn(msg) { log(`! ${msg}`); }

function err(msg) {
  if (jsonMode) {
    process.stdout.write(JSON.stringify({ ok: false, error: msg }) + '\n');
  } else {
    process.stderr.write(`error: ${msg}\n`);
  }
}

function json(obj) {
  process.stdout.write(JSON.stringify(obj, null, jsonMode ? 0 : 2) + '\n');
}

function die(code, msg) {
  err(msg);
  process.exit(code || 1);
}

// --------------------------------------------------------------------------
// Docker compose wrapper
// --------------------------------------------------------------------------

function runCompose(args, { capture = false, env = process.env } = {}) {
  const cmd = ['docker', 'compose', '-f', BUNDLED_COMPOSE, ...args];
  if (capture) {
    const result = spawnSync(cmd[0], cmd.slice(1), {
      env,
      encoding: 'utf-8',
      cwd: WORK_DIR,
    });
    return result;
  }
  return spawnSync(cmd[0], cmd.slice(1), {
    env,
    stdio: 'inherit',
    cwd: WORK_DIR,
  });
}

function ensureDockerAvailable() {
  const v = spawnSync('docker', ['--version'], { encoding: 'utf-8' });
  if (v.status !== 0) {
    die(2, 'docker is not installed or not on PATH. See https://docs.docker.com/get-docker/');
  }
  const c = spawnSync('docker', ['compose', 'version'], { encoding: 'utf-8' });
  if (c.status !== 0) {
    die(2, 'docker compose plugin not available. Install a recent Docker Desktop or the compose-plugin package.');
  }
}

function ensureEnvFile() {
  if (!existsSync(ENV_FILE)) {
    die(
      3,
      `no .env file in ${WORK_DIR}. Run \`lemonfish setup\` first, or create one from https://github.com/Lvigentini/LemonFish/blob/main/.env.example`
    );
  }
}

// --------------------------------------------------------------------------
// HTTP helpers (uses Node 18+ global fetch)
// --------------------------------------------------------------------------

async function httpGet(path) {
  const url = `${BACKEND_BASE}${path}`;
  const res = await fetch(url);
  const text = await res.text();
  let body;
  try { body = JSON.parse(text); } catch { body = { raw: text }; }
  return { status: res.status, ok: res.ok, body };
}

async function httpPost(path, payload) {
  const url = `${BACKEND_BASE}${path}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: payload !== undefined ? JSON.stringify(payload) : undefined,
  });
  const text = await res.text();
  let body;
  try { body = JSON.parse(text); } catch { body = { raw: text }; }
  return { status: res.status, ok: res.ok, body };
}

async function waitForHealthy(timeoutMs = HEALTH_WAIT_MS) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const r = await httpGet('/health');
      if (r.ok) return true;
    } catch { /* container not up yet */ }
    await sleep(HEALTH_POLL_INTERVAL);
  }
  return false;
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// --------------------------------------------------------------------------
// Command: version
// --------------------------------------------------------------------------

function cmdVersion() {
  if (jsonMode) {
    json({ ok: true, version: PKG_VERSION });
  } else {
    console.log(`lemonfish-cli v${PKG_VERSION}`);
  }
}

// --------------------------------------------------------------------------
// Command: setup
// --------------------------------------------------------------------------

async function cmdSetup() {
  ensureDockerAvailable();

  if (existsSync(ENV_FILE)) {
    warn(`.env already exists at ${ENV_FILE}`);
    const rl = createInterface({ input, output });
    const ans = (await rl.question('Overwrite? [y/N] ')).trim().toLowerCase();
    rl.close();
    if (ans !== 'y' && ans !== 'yes') {
      info('Aborted.');
      return;
    }
  }

  const rl = createInterface({ input, output });
  log('');
  log('┌─────────────────────────────────────────────┐');
  log('│  MiroFish [LemonFish] — minimal setup        │');
  log('└─────────────────────────────────────────────┘');
  log('');
  log('This wizard creates a minimal .env to get you running.');
  log('For the full range of per-step model routing, multi-provider');
  log('pools, and research module options, see .env.example at:');
  log('  https://github.com/Lvigentini/LemonFish/blob/main/.env.example');
  log('');

  // Provider selection — keep it short
  const providers = [
    { label: 'OpenRouter (free models)', baseUrl: 'https://openrouter.ai/api/v1', model: 'meta-llama/llama-3.3-70b-instruct:free', keysUrl: 'https://openrouter.ai/keys' },
    { label: 'Google Gemini (free tier)', baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai/', model: 'gemini-3-flash-preview', keysUrl: 'https://aistudio.google.com/apikey' },
    { label: 'Groq (free tier, fast)',    baseUrl: 'https://api.groq.com/openai/v1', model: 'llama-3.1-8b-instant', keysUrl: 'https://console.groq.com/keys' },
    { label: 'OpenAI',                    baseUrl: 'https://api.openai.com/v1', model: 'gpt-5-nano', keysUrl: 'https://platform.openai.com/api-keys' },
    { label: 'Anthropic Claude',          baseUrl: 'https://api.anthropic.com/v1/', model: 'claude-sonnet-4-6', keysUrl: 'https://console.anthropic.com/settings/keys' },
  ];

  log('Pick an LLM provider:');
  providers.forEach((p, i) => log(`  ${i + 1}) ${p.label}`));
  const pickRaw = await rl.question('Choice [1]: ');
  const idx = Math.max(1, Math.min(providers.length, parseInt(pickRaw || '1', 10))) - 1;
  const picked = providers[idx];

  log('');
  log(`Get your API key at: ${picked.keysUrl}`);
  const apiKey = (await rl.question('LLM API key: ')).trim();
  if (!apiKey) {
    rl.close();
    die(4, 'API key is required');
  }

  const modelRaw = (await rl.question(`Model [${picked.model}]: `)).trim();
  const model = modelRaw || picked.model;

  log('');
  log('Zep Cloud is used for the knowledge graph.');
  log('Free tier is sufficient. Sign up at: https://app.getzep.com/');
  const zepKey = (await rl.question('Zep API key: ')).trim();
  if (!zepKey) {
    rl.close();
    die(4, 'Zep API key is required');
  }

  log('');
  const researchAns = (await rl.question('Enable research-from-prompt module? [Y/n] ')).trim().toLowerCase();
  rl.close();
  const researchEnabled = researchAns === '' || researchAns === 'y' || researchAns === 'yes';

  const envContent = [
    '# Generated by lemonfish-cli setup',
    `LLM_API_KEY=${apiKey}`,
    `LLM_BASE_URL=${picked.baseUrl}`,
    `LLM_MODEL_NAME=${model}`,
    '',
    '# Retry / resilience',
    'LLM_MAX_RETRIES=3',
    'LLM_RETRY_BASE_DELAY=2.0',
    '',
    '# Zep Cloud',
    `ZEP_API_KEY=${zepKey}`,
    '',
    '# Phase 8 research-from-prompt module',
    `RESEARCH_ENABLED=${researchEnabled ? 'true' : 'false'}`,
    'RESEARCH_RUNNERS=api',
    'RESEARCH_DEFAULT_RUNNER=api',
    '',
  ].join('\n');

  await writeFile(ENV_FILE, envContent);
  ok(`.env written to ${ENV_FILE}`);
  log('');
  log('Next step:');
  log('  lemonfish start');
}

// --------------------------------------------------------------------------
// Command: start
// --------------------------------------------------------------------------

async function cmdStart({ detach = true } = {}) {
  ensureDockerAvailable();
  ensureEnvFile();

  step('Pulling latest image (if newer)...');
  runCompose(['pull']);

  step('Starting container...');
  const result = runCompose(detach ? ['up', '-d'] : ['up']);
  if (result.status !== 0) {
    die(5, `docker compose up failed with exit code ${result.status}`);
  }

  step('Waiting for backend to be healthy...');
  const healthy = await waitForHealthy();
  if (!healthy) {
    die(6, 'backend did not become healthy within 90s. Run `lemonfish logs` to see why.');
  }

  ok(`Running. Open ${FRONTEND_BASE} in your browser.`);
  if (jsonMode) {
    json({ ok: true, action: 'start', backend: BACKEND_BASE, frontend: FRONTEND_BASE });
  }
}

// --------------------------------------------------------------------------
// Command: stop
// --------------------------------------------------------------------------

function cmdStop() {
  ensureDockerAvailable();
  step('Stopping container...');
  const result = runCompose(['down']);
  if (result.status !== 0) {
    die(5, `docker compose down failed with exit code ${result.status}`);
  }
  ok('Stopped.');
  if (jsonMode) json({ ok: true, action: 'stop' });
}

// --------------------------------------------------------------------------
// Command: status
// --------------------------------------------------------------------------

async function cmdStatus() {
  ensureDockerAvailable();

  // Compose view: only sees containers managed by the bundled compose file.
  // A container started via a different compose project (e.g. the repo's
  // docker-compose.slim.yml used for local dev) will appear as "not found"
  // here even though the backend is perfectly healthy.
  let composeManaged = false;
  let composeState = 'not managed by bundled compose';
  try {
    const ps = runCompose(['ps', '--format', 'json'], { capture: true });
    if (ps.status === 0 && ps.stdout.trim()) {
      const lines = ps.stdout.trim().split('\n');
      for (const line of lines) {
        const obj = JSON.parse(line);
        if (obj.Service === 'mirofish' || obj.Name === 'mirofish') {
          composeManaged = obj.State === 'running';
          composeState = obj.State || 'unknown';
          break;
        }
      }
    }
  } catch { /* compose ps failed — treat as "not managed" */ }

  // Backend health: check via HTTP *independently* of compose visibility.
  // An externally-managed container is still a valid "running" state.
  let backendHealthy = false;
  try {
    const h = await httpGet('/health');
    backendHealthy = h.ok;
  } catch { backendHealthy = false; }

  // Research module: same independence principle.
  let researchEnabled = false;
  let availability = null;
  if (backendHealthy) {
    try {
      const r = await httpGet('/api/research/availability');
      if (r.ok) {
        researchEnabled = true;
        availability = r.body;
      }
    } catch { /* research module probably disabled */ }
  }

  // "Running" = backend is reachable OR compose sees it. Compose-only is a
  // partial state that shouldn't happen in practice (container starting up).
  const running = backendHealthy || composeManaged;

  const status = {
    container: {
      running,
      compose_managed: composeManaged,
      compose_state: composeState,
    },
    backend: { healthy: backendHealthy, url: BACKEND_BASE },
    frontend: { url: FRONTEND_BASE },
    research: { enabled: researchEnabled, runners: availability?.runners || [] },
  };

  if (jsonMode) {
    json({ ok: true, ...status });
    return;
  }

  if (backendHealthy && !composeManaged) {
    log(`Container:  ✓ running (externally managed, not via lemonfish-cli)`);
  } else if (composeManaged) {
    log(`Container:  ✓ running (lemonfish-cli managed)`);
  } else {
    log(`Container:  ✗ ${composeState}`);
  }
  log(`Backend:    ${backendHealthy ? `✓ healthy (${BACKEND_BASE})` : '✗ unreachable'}`);
  log(`Frontend:   ${FRONTEND_BASE}`);
  if (researchEnabled) {
    log('Research:   ✓ enabled');
    for (const r of availability?.runners || []) {
      const icon = r.available && r.auth_ok ? '✓' : (r.available ? '!' : '✗');
      const reason = r.reason ? ` — ${r.reason}` : '';
      log(`  ${icon} ${r.name}${reason}`);
    }
  } else if (running) {
    log('Research:   ✗ disabled (set RESEARCH_ENABLED=true in .env to enable)');
  }

  if (!running) process.exit(10);
  if (!backendHealthy) process.exit(11);
}

// --------------------------------------------------------------------------
// Command: logs
// --------------------------------------------------------------------------

function cmdLogs(args) {
  ensureDockerAvailable();
  const follow = !args.includes('--no-follow');
  const composeArgs = ['logs'];
  if (follow) composeArgs.push('-f');
  runCompose(composeArgs);
}

// --------------------------------------------------------------------------
// Command: upgrade
// --------------------------------------------------------------------------

async function cmdUpgrade() {
  ensureDockerAvailable();
  step('Pulling latest image...');
  const pull = runCompose(['pull']);
  if (pull.status !== 0) die(5, 'docker compose pull failed');

  step('Restarting container...');
  const restart = runCompose(['up', '-d', '--force-recreate']);
  if (restart.status !== 0) die(5, 'docker compose up --force-recreate failed');

  step('Waiting for backend to be healthy...');
  const healthy = await waitForHealthy();
  if (!healthy) die(6, 'backend did not become healthy after upgrade');

  ok('Upgraded.');
  if (jsonMode) json({ ok: true, action: 'upgrade' });
}

// --------------------------------------------------------------------------
// Command: research <prompt>
// --------------------------------------------------------------------------

async function cmdResearch(args) {
  // Flags
  const flagIdx = args.findIndex((a) => a.startsWith('--'));
  const positional = flagIdx === -1 ? args : args.slice(0, flagIdx);
  const flags = flagIdx === -1 ? [] : args.slice(flagIdx);

  if (positional.length === 0) {
    die(1, 'usage: lemonfish research [--runner api|claude|codex|kimi] [--requirement "<text>"] [--promote] <prompt>');
  }

  const prompt = positional.join(' ');
  const runnerFlag = flags.find((f) => f.startsWith('--runner='))?.split('=')[1];
  const runner = runnerFlag || 'api';
  const reqFlag = flags.find((f) => f.startsWith('--requirement='))?.split('=')[1];
  const simulationRequirement = reqFlag || `Simulate social dynamics and stakeholder reactions related to: ${prompt}`;
  const shouldPromote = flags.includes('--promote');

  ensureDockerAvailable();
  ensureEnvFile();

  // Auto-start if not running
  try {
    const h = await httpGet('/health');
    if (!h.ok) throw new Error('not healthy');
  } catch {
    step('Container not running — starting it first...');
    await cmdStart({ detach: true });
  }

  // Confirm research module is available
  const avail = await httpGet('/api/research/availability');
  if (!avail.ok) {
    die(7, 'research module is not enabled. Set RESEARCH_ENABLED=true in .env and restart.');
  }

  const pickedRunner = (avail.body?.runners || []).find(
    (r) => r.name === runner && r.available && r.auth_ok
  );
  if (!pickedRunner) {
    const usable = (avail.body?.runners || [])
      .filter((r) => r.available && r.auth_ok)
      .map((r) => r.name);
    die(
      8,
      `runner '${runner}' is not available. Usable runners: ${usable.join(', ') || '(none)'}`
    );
  }

  step(`Starting research with runner=${runner}`);
  const start = await httpPost('/api/research/start', {
    prompt,
    simulation_requirement: simulationRequirement,
    runner_choice: runner,
  });

  if (!start.ok || !start.body?.task_id) {
    die(9, `failed to start research: ${JSON.stringify(start.body)}`);
  }

  const taskId = start.body.task_id;
  const projectId = start.body.project_id;
  info(`task_id=${taskId} project_id=${projectId}`);

  // Poll until completed / failed / cancelled
  const deadline = Date.now() + RESEARCH_MAX_WAIT_MS;
  let lastPhase = '';
  let lastProgress = -1;

  while (Date.now() < deadline) {
    const statusRes = await httpGet(`/api/research/status/${taskId}`);
    if (!statusRes.ok) {
      warn(`status poll failed: ${statusRes.status}`);
      await sleep(RESEARCH_POLL_INTERVAL);
      continue;
    }

    const task = statusRes.body?.task;
    if (!task) {
      await sleep(RESEARCH_POLL_INTERVAL);
      continue;
    }

    const phase = task.phase || 'pending';
    const nSubtopics = task.sub_topics?.length || 0;
    const nCompleted = (task.sub_topics || []).filter((s) => s.status === 'completed').length;
    const progress = nSubtopics > 0 ? Math.round((nCompleted / nSubtopics) * 100) : 0;

    if (phase !== lastPhase || progress !== lastProgress) {
      if (phase === 'planning') step('Planning sub-topics...');
      else if (phase === 'researching') step(`Researching: ${nCompleted}/${nSubtopics} sub-topics complete`);
      else if (phase === 'synthesising') step('Synthesising compiled document...');
      lastPhase = phase;
      lastProgress = progress;
    }

    if (phase === 'completed') {
      ok('Research complete.');
      const result = await httpGet(`/api/research/result/${taskId}`);
      if (!result.ok) die(11, `failed to fetch result: ${JSON.stringify(result.body)}`);

      const body = result.body;
      const output = {
        ok: true,
        task_id: taskId,
        project_id: projectId,
        compiled_text_length: body.compiled_text?.length || 0,
        citations: body.citations || [],
        sub_topics: (body.sub_topics || []).map((s) => ({
          index: s.index,
          topic: s.topic,
          status: s.status,
          runner: s.runner,
        })),
        continue_url: `${FRONTEND_BASE}/process/${projectId}`,
      };

      if (shouldPromote) {
        step('Promoting to project pipeline...');
        const promote = await httpPost(`/api/research/promote/${taskId}`);
        if (!promote.ok) die(12, `promote failed: ${JSON.stringify(promote.body)}`);
        output.promoted = true;
        ok(`Project promoted: ${projectId}`);
      }

      if (jsonMode) {
        json(output);
      } else {
        log('');
        log(`Compiled document: ${output.compiled_text_length} chars, ${output.citations.length} citations`);
        log(`Sub-topics: ${output.sub_topics.length}`);
        for (const s of output.sub_topics) {
          const icon = s.status === 'completed' ? '✓' : (s.status === 'failed' ? '✗' : '◯');
          log(`  ${icon} ${s.topic}`);
        }
        log('');
        log('Next step: open the project in your browser to run ontology → simulation → report:');
        log(`  ${output.continue_url}`);
        if (!shouldPromote) {
          log('');
          log('Re-run with --promote to advance the project into the Step 1 pipeline.');
        }
      }
      return;
    }

    if (phase === 'failed') {
      die(13, `research failed: ${task.error || 'unknown error'}`);
    }
    if (phase === 'cancelled') {
      die(14, 'research was cancelled');
    }

    await sleep(RESEARCH_POLL_INTERVAL);
  }

  die(15, 'research timed out (20 minutes)');
}

// --------------------------------------------------------------------------
// Command: help
// --------------------------------------------------------------------------

function cmdHelp() {
  console.log(`lemonfish-cli v${PKG_VERSION}

USAGE
  lemonfish <command> [args] [--json]

LIFECYCLE
  setup             Interactive .env wizard (pick a provider, paste keys)
  start             Pull latest image and start the container
  status            Show container + API health and research runner status
  stop              Stop and remove the container
  logs              Tail container logs (add --no-follow to print-and-exit)
  upgrade           Pull latest image and recreate the container

RESEARCH (Phase 8)
  research "<prompt>"
                    Run research-from-prompt on <prompt>. Auto-starts the
                    container if not running. Streams phase progress.
                    Returns a compiled document + citations and prints
                    the URL to continue in the browser.

      --runner <name>          api | claude | codex | kimi  (default: api)
      --requirement "<text>"   Override the default simulation requirement
      --promote                Also advance the project into Step 1 pipeline

MISC
  version           Print CLI version
  help              Show this message

GLOBAL FLAGS
  --json            Machine-readable output (one JSON object per command)

ENVIRONMENT
  LEMONFISH_API     Backend URL (default http://localhost:5001)
  LEMONFISH_UI      Frontend URL (default http://localhost:3000)

EXAMPLES
  # First-time setup + start
  lemonfish setup
  lemonfish start

  # Run research on a prompt
  lemonfish research "predict adoption of EV trucks in EU haulage 2026-2030"

  # Run research and advance to Step 1, JSON output for an agent
  lemonfish research --promote --json "what will happen with padel in Australia?"

  # Check everything is healthy
  lemonfish status --json

DOCS
  Full guide:       https://github.com/Lvigentini/LemonFish
  Research module:  https://github.com/Lvigentini/LemonFish/blob/main/docs/research_module.md
`);
}

// --------------------------------------------------------------------------
// Main dispatch
// --------------------------------------------------------------------------

async function main() {
  const argv = process.argv.slice(2);

  // Strip global --json flag wherever it appears
  const jsonIdx = argv.indexOf('--json');
  if (jsonIdx !== -1) {
    jsonMode = true;
    argv.splice(jsonIdx, 1);
  }

  const [command, ...rest] = argv;

  try {
    switch (command) {
      case 'version':
      case '--version':
      case '-v':
        cmdVersion();
        break;
      case 'setup':
        await cmdSetup();
        break;
      case 'start':
        await cmdStart();
        break;
      case 'stop':
        cmdStop();
        break;
      case 'status':
        await cmdStatus();
        break;
      case 'logs':
        cmdLogs(rest);
        break;
      case 'upgrade':
        await cmdUpgrade();
        break;
      case 'research':
        await cmdResearch(rest);
        break;
      case undefined:
      case 'help':
      case '--help':
      case '-h':
        cmdHelp();
        break;
      default:
        die(1, `unknown command: ${command}. Run \`lemonfish help\` for usage.`);
    }
  } catch (e) {
    die(99, `${e.message || e}`);
  }
}

main();
