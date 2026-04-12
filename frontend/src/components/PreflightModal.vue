<template>
  <div v-if="visible" class="preflight-overlay" @click.self="close">
    <div class="preflight-modal">
      <header class="preflight-header">
        <h2>{{ $t('preflight.title') || 'Pre-flight Estimate' }}</h2>
        <button class="close-btn" @click="close">×</button>
      </header>

      <div class="preflight-body">
        <!-- Inputs summary -->
        <section class="section">
          <h3>{{ $t('preflight.inputs') || 'Inputs' }}</h3>
          <div class="grid-2">
            <div class="metric">
              <span class="metric-label">Agents</span>
              <span class="metric-value">{{ agents }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">Rounds</span>
              <span class="metric-value">{{ rounds }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">Document</span>
              <span class="metric-value">{{ formatChars(documentChars) }}</span>
            </div>
            <div class="metric">
              <span class="metric-label">Report sections</span>
              <span class="metric-value">{{ reportSections }}</span>
            </div>
          </div>
        </section>

        <!-- Loading -->
        <section v-if="loading" class="section loading-section">
          <div class="spinner"></div>
          <p>{{ $t('preflight.estimating') || 'Estimating token usage…' }}</p>
        </section>

        <!-- Error -->
        <section v-else-if="error" class="section error-section">
          <p class="error-msg">{{ error }}</p>
        </section>

        <!-- Estimate -->
        <section v-else-if="estimate" class="section">
          <h3>{{ $t('preflight.estimate') || 'Estimated token consumption' }}</h3>

          <div class="total-box">
            <div class="total-value">{{ estimate.total.tokens_formatted }}</div>
            <div class="total-label">tokens total</div>
          </div>

          <div class="steps">
            <div v-for="(step, name) in estimate.per_step" :key="name" class="step-row">
              <div class="step-name">{{ formatStep(name) }}</div>
              <div class="step-bar-container">
                <div class="step-bar" :style="{ width: stepPercent(step.tokens) + '%' }"></div>
              </div>
              <div class="step-tokens">{{ formatTokens(step.tokens) }}</div>
              <div class="step-calls">{{ step.calls }} {{ step.calls === 1 ? 'call' : 'calls' }}</div>
            </div>
          </div>

          <p class="dominant-note">
            <strong>{{ formatStep(estimate.total.dominant_step) }}</strong>
            accounts for {{ estimate.total.dominant_step_percent }}% of the total.
          </p>
        </section>

        <!-- Cost estimates -->
        <section v-if="estimate" class="section">
          <h3>{{ $t('preflight.cost') || 'Approximate cost (if single provider)' }}</h3>

          <div v-if="costWarningTier" class="cost-warning" :class="costWarningLevel">
            <span class="warning-icon">⚠</span>
            <div class="warning-body">
              <strong>{{ costWarningTitle }}</strong>
              <span class="warning-hint">{{ costWarningMessage }}</span>
            </div>
          </div>

          <div class="cost-grid">
            <div v-for="(cost, tier) in estimate.total.approx_cost_usd" :key="tier" class="cost-pill" :class="tierClass(tier)">
              <span class="cost-tier">{{ formatTier(tier) }}</span>
              <span class="cost-value">${{ cost.toFixed(3) }}</span>
            </div>
          </div>
        </section>

        <!-- Token distribution across multi-provider pool -->
        <section v-if="allocation && pool && pool.configured" class="section">
          <div class="allocation-header">
            <h3>{{ $t('preflight.distribution') || 'Token distribution across providers' }}</h3>
            <button class="btn-link" @click="resetWeights" :disabled="allocLoading">Reset to uniform</button>
          </div>
          <p class="help-text">
            Adjust the share each provider will absorb. Projected usage is compared to each provider's
            daily budget (minus what's already been used today).
          </p>

          <div v-if="allocation.any_over" class="alloc-banner over">
            <strong>⚠ One or more providers will exceed their daily budget</strong>
            <span>You can still proceed — rate-limited agents will skip their turn — but consider re-balancing.</span>
          </div>
          <div v-else-if="allocation.any_warn" class="alloc-banner warn">
            <strong>One or more providers will be near their daily limit</strong>
            <span>Projected usage pushes a provider above 80% of its daily budget.</span>
          </div>

          <div class="alloc-table">
            <div class="alloc-row alloc-head">
              <div class="col-name">Provider</div>
              <div class="col-slider">Share</div>
              <div class="col-agents">Agents</div>
              <div class="col-projected">Projected</div>
              <div class="col-budget">Today / Budget</div>
              <div class="col-status">Status</div>
            </div>
            <div
              v-for="row in allocation.providers"
              :key="row.name"
              class="alloc-row"
              :class="`status-${row.status}`"
            >
              <div class="col-name">
                <div class="provider-name">{{ row.name }}</div>
                <div class="provider-model">{{ row.model }}</div>
              </div>
              <div class="col-slider">
                <input
                  type="range"
                  min="0"
                  max="100"
                  step="5"
                  :value="sliderValues[row.name] || 0"
                  @input="onSliderInput(row.name, $event.target.value)"
                />
                <span class="slider-pct">{{ row.share_percent }}%</span>
              </div>
              <div class="col-agents">{{ row.assigned_agents }}</div>
              <div class="col-projected">{{ formatTokens(row.projected_tokens) }}</div>
              <div class="col-budget">
                <template v-if="row.daily_budget">
                  {{ formatTokens(row.consumed_today) }} / {{ formatTokens(row.daily_budget) }}
                </template>
                <template v-else>
                  <span class="muted">no budget set</span>
                </template>
              </div>
              <div class="col-status">
                <span class="status-badge" :class="`badge-${row.status}`">
                  <template v-if="row.status === 'over'">OVER by {{ formatTokens(row.overage) }}</template>
                  <template v-else-if="row.status === 'warn'">{{ row.percent_of_budget }}%</template>
                  <template v-else-if="row.status === 'ok'">OK</template>
                  <template v-else>∞</template>
                </span>
              </div>
            </div>
          </div>
        </section>
      </div>

      <footer class="preflight-footer">
        <button class="btn-cancel" @click="close">{{ $t('common.cancel') || 'Cancel' }}</button>
        <button
          class="btn-proceed"
          :class="{ 'btn-proceed-warn': allocation && allocation.any_over }"
          :disabled="loading || !!error"
          @click="confirm"
        >
          <template v-if="allocation && allocation.any_over">Proceed anyway</template>
          <template v-else>{{ $t('preflight.proceed') || 'Proceed' }}</template>
        </button>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed, reactive } from 'vue'
import { estimateTokens, getProviderPool, preflightAllocation } from '../api/simulation'

const props = defineProps({
  visible: { type: Boolean, default: false },
  simulationId: { type: String, default: '' },
  agents: { type: Number, default: 0 },
  rounds: { type: Number, default: 10 },
  documentChars: { type: Number, default: 0 },
  reportSections: { type: Number, default: 4 },
})

const emit = defineEmits(['close', 'confirm'])

const loading = ref(false)
const error = ref(null)
const estimate = ref(null)
const pool = ref(null)
const allocation = ref(null)
const allocLoading = ref(false)

// sliderValues holds the raw slider positions (0-100) keyed by provider name.
// They're the user's input; the backend normalizes them to shares that sum to 1.
const sliderValues = reactive({})

const close = () => emit('close')

const confirm = () => {
  // Persist the weights so Step3Simulation can attach them to /start.
  // Store normalized {name: 0..1} — backend accepts any positive scale but
  // keeping it normalized makes the log line readable.
  if (pool.value && pool.value.configured && props.simulationId) {
    const total = Object.values(sliderValues).reduce((a, b) => a + Number(b || 0), 0)
    const payload = {}
    if (total > 0) {
      for (const [name, v] of Object.entries(sliderValues)) {
        payload[name] = Number(v) / total
      }
    }
    try {
      if (Object.keys(payload).length) {
        localStorage.setItem(
          `lemonfish.providerWeights.${props.simulationId}`,
          JSON.stringify(payload),
        )
      }
    } catch (_) { /* localStorage unavailable — harmless */ }
  }
  emit('confirm', { estimate: estimate.value, weights: { ...sliderValues } })
}

function weightsPayload() {
  // Send raw slider values to the backend. It normalizes internally.
  const out = {}
  for (const [k, v] of Object.entries(sliderValues)) out[k] = Number(v) || 0
  return out
}

async function refresh() {
  if (!props.visible) return
  loading.value = true
  error.value = null
  estimate.value = null
  allocation.value = null
  try {
    const [estRes, poolRes] = await Promise.all([
      estimateTokens({
        agents: props.agents,
        rounds: props.rounds,
        document_chars: props.documentChars,
        report_sections: props.reportSections,
      }),
      getProviderPool(),
    ])
    estimate.value = estRes.data
    pool.value = poolRes.data

    // Initialize slider values from localStorage or uniform
    if (pool.value && pool.value.configured && pool.value.providers?.length) {
      let restored = null
      try {
        const raw = localStorage.getItem(`lemonfish.providerWeights.${props.simulationId}`)
        if (raw) restored = JSON.parse(raw)
      } catch (_) { /* noop */ }

      for (const p of pool.value.providers) {
        if (restored && typeof restored[p.name] === 'number') {
          // Convert 0..1 normalized back to 0..100 for the slider
          sliderValues[p.name] = Math.round(restored[p.name] * 100)
        } else {
          sliderValues[p.name] = Math.round(100 / pool.value.providers.length)
        }
      }
      await refreshAllocation()
    }
  } catch (e) {
    error.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
}

let allocDebounce = null
async function refreshAllocation() {
  if (!pool.value?.configured) return
  allocLoading.value = true
  try {
    const res = await preflightAllocation({
      agents: props.agents,
      rounds: props.rounds,
      document_chars: props.documentChars,
      report_sections: props.reportSections,
      weights: weightsPayload(),
    })
    allocation.value = res.data
  } catch (e) {
    // Non-fatal — the rest of the modal still works without quota view
    console.warn('preflight allocation failed:', e)
  } finally {
    allocLoading.value = false
  }
}

function onSliderInput(name, value) {
  sliderValues[name] = Number(value)
  if (allocDebounce) clearTimeout(allocDebounce)
  allocDebounce = setTimeout(refreshAllocation, 180)
}

function resetWeights() {
  if (!pool.value?.providers?.length) return
  const share = Math.round(100 / pool.value.providers.length)
  for (const p of pool.value.providers) sliderValues[p.name] = share
  refreshAllocation()
}

watch(() => props.visible, (v) => { if (v) refresh() })

function formatChars(n) {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K chars`
  return `${n} chars`
}

function formatTokens(n) {
  if (!n && n !== 0) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return String(n)
}

function formatStep(name) {
  const map = {
    ontology: 'Ontology',
    profiles: 'Profiles',
    config: 'Config',
    simulation: 'Simulation',
    report: 'Report',
  }
  return map[name] || name
}

function formatTier(tier) {
  const map = {
    free_openrouter: 'Free (OpenRouter)',
    cheap_groq_llama8b: 'Groq Llama-8B',
    cheap_deepseek_chat: 'DeepSeek Chat',
    mid_gemini_flash: 'Gemini Flash',
    premium_gpt5_nano: 'GPT-5 nano',
    premium_claude_sonnet: 'Claude Sonnet',
  }
  return map[tier] || tier
}

function tierClass(tier) {
  if (tier.startsWith('free')) return 'tier-free'
  if (tier.startsWith('cheap')) return 'tier-cheap'
  if (tier.startsWith('mid')) return 'tier-mid'
  return 'tier-premium'
}

function stepPercent(tokens) {
  if (!estimate.value?.total?.tokens) return 0
  return Math.max(0.5, (tokens / estimate.value.total.tokens) * 100)
}

const costWarningTier = computed(() => {
  if (!estimate.value) return null
  const costs = estimate.value.total.approx_cost_usd
  if (costs.premium_claude_sonnet > 5) return 'high'
  if (estimate.value.total.tokens > 10_000_000) return 'very-high'
  if (costs.cheap_deepseek_chat > 2) return 'medium'
  return null
})

const costWarningLevel = computed(() => {
  const tier = costWarningTier.value
  if (tier === 'very-high') return 'warn-danger'
  if (tier === 'high') return 'warn-high'
  return 'warn-medium'
})

const costWarningTitle = computed(() => {
  if (costWarningTier.value === 'very-high') return 'Very large simulation'
  if (costWarningTier.value === 'high') return 'High-cost scenario on premium models'
  return 'Moderate cost on paid providers'
})

const costWarningMessage = computed(() => {
  if (!estimate.value) return ''
  const costs = estimate.value.total.approx_cost_usd
  if (costWarningTier.value === 'very-high') {
    return `${formatTokens(estimate.value.total.tokens)} tokens is a very large run. Consider reducing agent count or rounds. Free tiers will be exhausted quickly.`
  }
  if (costWarningTier.value === 'high') {
    return `Claude Sonnet would cost ~$${costs.premium_claude_sonnet.toFixed(2)}. Consider a cheaper provider or reduce the scenario size.`
  }
  return `DeepSeek would cost ~$${costs.cheap_deepseek_chat.toFixed(2)}. Free tier on Groq or Gemini would be $0.`
})
</script>

<style scoped>
/* Light theme — matches Step2EnvSetup and the rest of the app. */

.preflight-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 20px;
}

.preflight-modal {
  background: #ffffff;
  color: #1a1a1a;
  border-radius: 12px;
  width: 100%;
  max-width: 820px;
  max-height: 92vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.25);
  border: 1px solid #e5e5e5;
}

.preflight-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 18px 24px;
  border-bottom: 1px solid #eeeeee;
}

.preflight-header h2 {
  font-size: 1.2rem;
  font-weight: 700;
  margin: 0;
  color: #1a1a1a;
}

.close-btn {
  background: none;
  border: none;
  color: #888;
  font-size: 1.7rem;
  cursor: pointer;
  line-height: 1;
  padding: 0 8px;
}
.close-btn:hover { color: #1a1a1a; }

.preflight-body {
  padding: 20px 24px;
  overflow-y: auto;
  flex: 1;
}

.section {
  margin-bottom: 24px;
}
.section:last-child { margin-bottom: 0; }

.section h3 {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #666;
  margin: 0 0 12px 0;
  font-weight: 600;
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.metric {
  display: flex;
  justify-content: space-between;
  padding: 10px 14px;
  background: #f7f7f7;
  border-radius: 6px;
  border: 1px solid #eeeeee;
}
.metric-label { color: #666; font-size: 0.9rem; }
.metric-value { font-weight: 600; color: #1a1a1a; }

.total-box {
  text-align: center;
  padding: 18px;
  background: #fafafa;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
  margin-bottom: 14px;
}
.total-value { font-size: 2.3rem; font-weight: 800; color: #1a1a1a; line-height: 1; }
.total-label { font-size: 0.78rem; color: #777; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.08em; }

.steps { display: flex; flex-direction: column; gap: 8px; }
.step-row {
  display: grid;
  grid-template-columns: 110px 1fr 80px 80px;
  align-items: center;
  gap: 12px;
  font-size: 0.85rem;
}
.step-name { color: #1a1a1a; }
.step-bar-container {
  background: #f0f0f0;
  border-radius: 4px;
  height: 8px;
  overflow: hidden;
}
.step-bar {
  background: linear-gradient(90deg, #FF5722, #ff8a5c);
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}
.step-tokens { color: #1a1a1a; font-weight: 600; text-align: right; }
.step-calls { color: #999; font-size: 0.8rem; text-align: right; }

.dominant-note {
  margin-top: 12px;
  padding: 10px 12px;
  background: #fafafa;
  border-left: 3px solid #FF5722;
  font-size: 0.85rem;
  color: #555;
  border-radius: 0 4px 4px 0;
}

/* Cost warning banner */
.cost-warning {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 14px;
  border: 1px solid;
}
.cost-warning.warn-medium { background: #fff8e6; border-color: #ffd966; }
.cost-warning.warn-high { background: #fff3e0; border-color: #ffb74d; }
.cost-warning.warn-danger { background: #ffebee; border-color: #ef9a9a; }
.warning-icon { font-size: 1.3rem; line-height: 1; flex-shrink: 0; }
.cost-warning.warn-medium .warning-icon { color: #f59e0b; }
.cost-warning.warn-high .warning-icon { color: #fb923c; }
.cost-warning.warn-danger .warning-icon { color: #ef4444; }
.warning-body { display: flex; flex-direction: column; gap: 4px; font-size: 0.82rem; }
.warning-body strong { color: #1a1a1a; }
.warning-hint { color: #555; line-height: 1.4; }

.cost-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 8px;
}
.cost-pill {
  display: flex;
  justify-content: space-between;
  padding: 10px 14px;
  background: #fafafa;
  border: 1px solid #eeeeee;
  border-radius: 6px;
  border-left: 3px solid #999;
}
.cost-pill.tier-free { border-left-color: #22c55e; }
.cost-pill.tier-cheap { border-left-color: #3b82f6; }
.cost-pill.tier-mid { border-left-color: #f59e0b; }
.cost-pill.tier-premium { border-left-color: #ef4444; }
.cost-tier { color: #555; font-size: 0.85rem; }
.cost-value { font-weight: 700; color: #1a1a1a; }

/* Allocation table */
.allocation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.allocation-header h3 { margin: 0; }

.btn-link {
  background: none;
  border: none;
  color: #FF5722;
  cursor: pointer;
  font-size: 0.82rem;
  padding: 0;
  text-transform: none;
  letter-spacing: normal;
  font-weight: 600;
}
.btn-link:hover:not(:disabled) { text-decoration: underline; }
.btn-link:disabled { color: #bbb; cursor: not-allowed; }

.help-text { color: #666; font-size: 0.85rem; margin: 0 0 12px 0; line-height: 1.4; }

.alloc-banner {
  padding: 10px 14px;
  border-radius: 6px;
  margin-bottom: 12px;
  font-size: 0.85rem;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.alloc-banner strong { color: #1a1a1a; }
.alloc-banner span { color: #555; }
.alloc-banner.over { background: #ffebee; border: 1px solid #ef9a9a; }
.alloc-banner.warn { background: #fff8e6; border: 1px solid #ffd966; }

.alloc-table {
  border: 1px solid #eeeeee;
  border-radius: 8px;
  overflow: hidden;
}
.alloc-row {
  display: grid;
  grid-template-columns: 1.4fr 1.6fr 0.6fr 0.9fr 1.3fr 1.2fr;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-bottom: 1px solid #f0f0f0;
  font-size: 0.85rem;
}
.alloc-row:last-child { border-bottom: none; }
.alloc-head {
  background: #fafafa;
  color: #666;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 600;
}
.alloc-row.status-over { background: #fff5f5; }
.alloc-row.status-warn { background: #fffdf3; }

.col-name .provider-name {
  font-weight: 600;
  color: #1a1a1a;
  text-transform: lowercase;
}
.col-name .provider-model {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.72rem;
  color: #888;
}
.col-slider {
  display: flex;
  align-items: center;
  gap: 8px;
}
.col-slider input[type=range] {
  flex: 1;
  accent-color: #FF5722;
}
.slider-pct {
  font-variant-numeric: tabular-nums;
  color: #555;
  font-size: 0.8rem;
  min-width: 38px;
  text-align: right;
}
.col-agents, .col-projected, .col-budget {
  font-variant-numeric: tabular-nums;
  color: #333;
}
.col-budget .muted { color: #aaa; font-style: italic; }

.status-badge {
  display: inline-block;
  padding: 3px 8px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.badge-ok { background: #e6f7ea; color: #1b8a3a; }
.badge-warn { background: #fff3cf; color: #8a6100; }
.badge-over { background: #fde2e2; color: #b42318; }
.badge-unbudgeted { background: #eeeeee; color: #666; }

.error-msg { color: #b42318; padding: 12px; background: #fde2e2; border-radius: 6px; }

.loading-section { text-align: center; padding: 40px 20px; }
.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #ffdccf;
  border-top-color: #FF5722;
  border-radius: 50%;
  margin: 0 auto 12px;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.preflight-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid #eeeeee;
  background: #fafafa;
}

.btn-cancel, .btn-proceed {
  padding: 10px 22px;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  font-size: 0.9rem;
  transition: all 0.15s;
}
.btn-cancel {
  background: #ffffff;
  color: #333;
  border: 1px solid #dddddd;
}
.btn-cancel:hover { background: #f5f5f5; }
.btn-proceed {
  background: #1a1a1a;
  color: #ffffff;
}
.btn-proceed:hover:not(:disabled) { background: #000000; }
.btn-proceed:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-proceed.btn-proceed-warn {
  background: #ef4444;
}
.btn-proceed.btn-proceed-warn:hover:not(:disabled) { background: #dc2626; }
</style>
