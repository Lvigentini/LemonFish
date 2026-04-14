<template>
  <div class="llm-settings">
    <nav class="navbar">
      <div class="nav-brand">
        <router-link to="/" class="back-link">← {{ $t('llmSettings.back') }}</router-link>
        <span class="title">{{ $t('llmSettings.title') }}</span>
      </div>
    </nav>

    <div class="content">
      <!-- .env + reload card -->
      <section class="card">
        <header class="card-head">
          <h2>{{ $t('llmSettings.envCardTitle') }}</h2>
        </header>
        <div v-if="stepData" class="env-card-body">
          <div class="kv">
            <span class="k">{{ $t('llmSettings.envPath') }}</span>
            <code class="v path" @click="copyPath">{{ stepData.env_path }}</code>
            <span v-if="copied" class="copied">{{ $t('llmSettings.copied') }}</span>
          </div>
          <div class="kv">
            <span class="k">{{ $t('llmSettings.envExists') }}</span>
            <span class="v">{{ stepData.env_exists ? '✓' : '✗' }}</span>
          </div>
          <div class="kv">
            <span class="k">{{ $t('llmSettings.backendStarted') }}</span>
            <span class="v">{{ formatTs(stepData.backend_started_at) }}</span>
          </div>
          <div class="kv">
            <span class="k">{{ $t('llmSettings.lastReload') }}</span>
            <span class="v">{{ stepData.last_env_reload_at ? formatTs(stepData.last_env_reload_at) : '—' }}</span>
          </div>
          <div class="actions">
            <button class="btn primary" :disabled="reloading" @click="doReload">
              {{ reloading ? $t('llmSettings.reloading') : $t('llmSettings.reloadEnv') }}
            </button>
            <button class="btn" :disabled="probing" @click="doProbeAll">
              {{ probing ? $t('llmSettings.probing') : $t('llmSettings.probeAll') }}
            </button>
            <button class="btn" @click="loadAll">
              {{ $t('llmSettings.refresh') }}
            </button>
          </div>
          <p class="hint">{{ $t('llmSettings.reloadHint') }}</p>
        </div>
        <div v-else-if="loadError" class="error">{{ loadError }}</div>
        <div v-else class="muted">{{ $t('llmSettings.loading') }}</div>
      </section>

      <!-- Primary + per-step configs -->
      <section v-if="stepData" class="card">
        <header class="card-head">
          <h2>{{ $t('llmSettings.primaryTitle') }}</h2>
        </header>
        <table class="data-table">
          <thead>
            <tr>
              <th>{{ $t('llmSettings.step') }}</th>
              <th>{{ $t('llmSettings.baseUrl') }}</th>
              <th>{{ $t('llmSettings.model') }}</th>
              <th>{{ $t('llmSettings.apiKey') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in stepData.steps" :key="s.step">
              <td><strong>{{ s.step }}</strong></td>
              <td><code>{{ s.base_url }}</code></td>
              <td><code>{{ s.model }}</code></td>
              <td><code class="muted">{{ s.api_key || '—' }}</code></td>
            </tr>
          </tbody>
        </table>
        <div class="fallbacks" v-if="stepData.fallback_models.length">
          <strong>{{ $t('llmSettings.fallbacks') }}:</strong>
          <code v-for="m in stepData.fallback_models" :key="m">{{ m }}</code>
        </div>
      </section>

      <!-- Provider pool -->
      <section class="card">
        <header class="card-head">
          <h2>{{ $t('llmSettings.poolTitle') }}</h2>
          <span v-if="pool" class="badge">{{ pool.size }} {{ $t('llmSettings.providers') }}</span>
        </header>
        <div v-if="!pool" class="muted">{{ $t('llmSettings.loading') }}</div>
        <div v-else-if="!pool.configured" class="warn">{{ pool.message }}</div>
        <table v-else class="data-table">
          <thead>
            <tr>
              <th>{{ $t('llmSettings.providerName') }}</th>
              <th>{{ $t('llmSettings.source') }}</th>
              <th>{{ $t('llmSettings.baseUrl') }}</th>
              <th>{{ $t('llmSettings.models') }}</th>
              <th>{{ $t('llmSettings.dailyBudget') }}</th>
              <th>{{ $t('llmSettings.health') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in pool.providers" :key="p.name">
              <td><strong>{{ p.name }}</strong></td>
              <td><span class="tag">{{ p.source }}</span></td>
              <td><code>{{ p.base_url }}</code></td>
              <td>
                <div v-if="p.models">
                  <div v-for="m in p.models" :key="m.id" class="model-row">
                    <code>{{ m.id }}</code>
                    <span v-if="m.daily_token_budget" class="muted small">
                      {{ formatNum(m.daily_token_budget) }} tok/d
                    </span>
                  </div>
                </div>
                <code v-else>{{ p.model }}</code>
              </td>
              <td>{{ p.daily_token_budget ? formatNum(p.daily_token_budget) : '—' }}</td>
              <td>
                <span
                  class="status-dot"
                  :class="healthClass(p.name)"
                  :title="healthTitle(p.name)"
                ></span>
                <span v-if="healthFor(p.name)" class="small muted">
                  {{ healthFor(p.name).reachable
                      ? healthFor(p.name).latency_ms + ' ms'
                      : (healthFor(p.name).error || $t('llmSettings.unreachable')) }}
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <!-- Ollama cheap probe -->
      <section v-if="ollama && ollama.count > 0" class="card">
        <header class="card-head">
          <h2>{{ $t('llmSettings.ollamaTitle') }}</h2>
          <button class="btn tiny" @click="doOllamaProbe">{{ $t('llmSettings.recheck') }}</button>
        </header>
        <div v-for="o in ollama.providers" :key="o.provider" class="ollama-block">
          <div class="kv">
            <span class="k">{{ o.provider }}</span>
            <span class="v">
              <span class="status-dot" :class="o.running ? 'ok' : 'bad'"></span>
              {{ o.running ? $t('llmSettings.daemonRunning') : $t('llmSettings.daemonDown') }}
            </span>
          </div>
          <div class="kv"><span class="k">{{ $t('llmSettings.endpoint') }}</span><code class="v">{{ o.tags_url }}</code></div>
          <div v-if="o.error" class="error small">{{ o.error }}</div>
          <div class="kv"><span class="k">{{ $t('llmSettings.configured') }}</span>
            <span class="v">
              <code v-for="m in o.configured_models" :key="m">{{ m }}</code>
            </span>
          </div>
          <div class="kv"><span class="k">{{ $t('llmSettings.installed') }}</span>
            <span class="v">
              <code v-for="m in o.installed_models" :key="m">{{ m }}</code>
              <span v-if="!o.installed_models.length" class="muted">—</span>
            </span>
          </div>
          <div v-if="o.missing.length" class="kv missing">
            <span class="k">{{ $t('llmSettings.missing') }}</span>
            <span class="v">
              <code v-for="m in o.missing" :key="m" class="bad">{{ m }}</code>
            </span>
          </div>
          <p v-if="o.missing.length" class="hint">
            {{ $t('llmSettings.pullHint') }}
            <code>ollama pull {{ o.missing[0] }}</code>
          </p>
        </div>
      </section>

      <!-- Capabilities -->
      <section v-if="capabilities && capabilities.count > 0" class="card">
        <header class="card-head">
          <h2>{{ $t('llmSettings.capabilitiesTitle') }}</h2>
          <span class="badge">{{ capabilities.count }}</span>
        </header>
        <table class="data-table">
          <thead>
            <tr>
              <th>{{ $t('llmSettings.model') }}</th>
              <th>{{ $t('llmSettings.baseUrl') }}</th>
              <th>JSON</th>
              <th>Tools</th>
              <th>Structured</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in capabilities.providers" :key="(c.base_url || '') + '|' + (c.model || '')">
              <td><code>{{ c.model }}</code></td>
              <td><code class="small">{{ c.base_url }}</code></td>
              <td>{{ flag(c.supports_json_mode) }}</td>
              <td>{{ flag(c.supports_tool_calls) }}</td>
              <td>{{ flag(c.supports_structured_output) }}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import {
  getStepLlmConfigs,
  getProviderPool,
  probeProviders,
  getProviderCapabilities,
  getOllamaStatus,
  reloadEnv
} from '../api/simulation'

const stepData = ref(null)
const pool = ref(null)
const probeResults = ref(null)
const capabilities = ref(null)
const ollama = ref(null)
const loadError = ref(null)
const reloading = ref(false)
const probing = ref(false)
const copied = ref(false)

function formatTs(ts) {
  if (!ts) return '—'
  return new Date(ts * 1000).toLocaleString()
}
function formatNum(n) {
  if (n == null) return '—'
  return n.toLocaleString()
}
function flag(v) {
  if (v === true) return '✓'
  if (v === false) return '✗'
  return '?'
}

function healthFor(name) {
  if (!probeResults.value) return null
  return probeResults.value.find(h => h.name === name) || null
}
function healthClass(name) {
  const h = healthFor(name)
  if (!h) return 'unknown'
  return h.reachable ? 'ok' : 'bad'
}
function healthTitle(name) {
  const h = healthFor(name)
  if (!h) return 'not probed'
  return h.reachable ? `OK (${h.latency_ms} ms)` : (h.error || 'unreachable')
}

async function loadSteps() {
  try {
    const res = await getStepLlmConfigs()
    if (res.data.success) stepData.value = res.data.data
    else loadError.value = res.data.error
  } catch (e) {
    loadError.value = e.message
  }
}
async function loadPool() {
  try {
    const res = await getProviderPool()
    if (res.data.success) pool.value = res.data.data
  } catch (e) {
    // pool endpoint returns 400 when not configured — tolerate
    pool.value = { configured: false, size: 0, providers: [], message: e.message }
  }
}
async function loadCaps() {
  try {
    const res = await getProviderCapabilities()
    if (res.data.success) capabilities.value = res.data.data
  } catch (e) { /* optional */ }
}
async function loadOllama() {
  try {
    const res = await getOllamaStatus()
    if (res.data.success) ollama.value = res.data.data
  } catch (e) { /* optional */ }
}

async function doProbeAll() {
  probing.value = true
  try {
    const res = await probeProviders()
    if (res.data.success) probeResults.value = res.data.data.results
  } catch (e) {
    loadError.value = e.message
  } finally {
    probing.value = false
  }
}

async function doOllamaProbe() {
  await loadOllama()
}

async function doReload() {
  reloading.value = true
  try {
    const res = await reloadEnv()
    if (res.data.success) {
      pool.value = res.data.data.pool
      await loadSteps()
      await loadOllama()
    } else {
      loadError.value = res.data.error
    }
  } catch (e) {
    loadError.value = e.message
  } finally {
    reloading.value = false
  }
}

async function copyPath() {
  if (!stepData.value) return
  try {
    await navigator.clipboard.writeText(stepData.value.env_path)
    copied.value = true
    setTimeout(() => { copied.value = false }, 1500)
  } catch (e) { /* ignore */ }
}

async function loadAll() {
  loadError.value = null
  await Promise.all([loadSteps(), loadPool(), loadCaps(), loadOllama()])
}

onMounted(loadAll)
</script>

<style scoped>
.llm-settings {
  min-height: 100vh;
  background: #0f1115;
  color: #e8ecf1;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.navbar {
  padding: 16px 32px;
  border-bottom: 1px solid #23262d;
  background: #141820;
}
.nav-brand { display: flex; align-items: center; gap: 24px; }
.back-link {
  color: #8b96a8;
  text-decoration: none;
  font-size: 14px;
}
.back-link:hover { color: #e8ecf1; }
.title { font-size: 18px; font-weight: 600; }

.content {
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.card {
  background: #161a22;
  border: 1px solid #23262d;
  border-radius: 8px;
  padding: 20px 24px;
}
.card-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.card-head h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.badge {
  background: #23262d;
  color: #8b96a8;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 12px;
}

.kv {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 0;
  font-size: 13px;
}
.kv .k { color: #8b96a8; min-width: 150px; }
.kv .v { color: #e8ecf1; }
.kv code, code {
  background: #0f1115;
  border: 1px solid #23262d;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: "SF Mono", Menlo, monospace;
  font-size: 12px;
  color: #c9d1d9;
}
.path { cursor: pointer; }
.path:hover { border-color: #3b82f6; }
.copied { color: #22c55e; font-size: 12px; }

.actions {
  display: flex;
  gap: 10px;
  margin-top: 16px;
}
.btn {
  background: #23262d;
  color: #e8ecf1;
  border: 1px solid #2f343d;
  border-radius: 6px;
  padding: 8px 16px;
  font-size: 13px;
  cursor: pointer;
}
.btn:hover:not(:disabled) { background: #2f343d; }
.btn.primary { background: #3b82f6; border-color: #3b82f6; }
.btn.primary:hover:not(:disabled) { background: #2563eb; }
.btn:disabled { opacity: 0.5; cursor: not-allowed; }
.btn.tiny { padding: 4px 10px; font-size: 11px; margin-left: auto; }

.hint {
  margin-top: 12px;
  color: #8b96a8;
  font-size: 12px;
  font-style: italic;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.data-table th {
  text-align: left;
  color: #8b96a8;
  font-weight: 500;
  padding: 8px 10px;
  border-bottom: 1px solid #23262d;
}
.data-table td {
  padding: 10px;
  border-bottom: 1px solid #1a1e26;
  vertical-align: top;
}
.tag {
  background: #1e293b;
  color: #93c5fd;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
}
.model-row {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 2px 0;
}
.small { font-size: 11px; }
.muted { color: #6b7280; }

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
}
.status-dot.ok { background: #22c55e; }
.status-dot.bad { background: #ef4444; }
.status-dot.unknown { background: #4b5563; }

.fallbacks {
  margin-top: 12px;
  font-size: 12px;
  color: #8b96a8;
}
.fallbacks code { margin-left: 6px; }

.ollama-block {
  padding: 12px 0;
  border-bottom: 1px solid #1a1e26;
}
.ollama-block:last-child { border-bottom: none; }
.ollama-block code { margin-right: 6px; }
.kv.missing .bad { border-color: #ef4444; color: #fca5a5; }

.error { color: #fca5a5; }
.warn { color: #fbbf24; }
</style>
