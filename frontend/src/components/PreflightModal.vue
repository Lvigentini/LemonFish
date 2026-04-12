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
          <h3>{{ $t('preflight.cost') || 'Approximate cost' }}</h3>

          <!-- Phase 7.8: warning banner when cost is high -->
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

        <!-- Provider pool -->
        <section v-if="pool && pool.configured" class="section">
          <h3>{{ $t('preflight.pool') || 'Multi-provider pool' }}</h3>
          <p class="help-text">Agents will be randomly distributed across these providers:</p>
          <ul class="provider-list">
            <li v-for="p in pool.providers" :key="p.name" class="provider-item">
              <span class="provider-name">{{ p.name }}</span>
              <span class="provider-model">{{ p.model }}</span>
              <span v-if="p.daily_token_budget" class="provider-budget">
                {{ formatTokens(p.daily_token_budget) }}/day
              </span>
            </li>
          </ul>
        </section>
      </div>

      <footer class="preflight-footer">
        <button class="btn-cancel" @click="close">{{ $t('common.cancel') || 'Cancel' }}</button>
        <button class="btn-proceed" :disabled="loading || !!error" @click="confirm">
          {{ $t('preflight.proceed') || 'Proceed' }}
        </button>
      </footer>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, computed } from 'vue'
import { estimateTokens, getProviderPool } from '../api/simulation'

const props = defineProps({
  visible: { type: Boolean, default: false },
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

const close = () => emit('close')
const confirm = () => emit('confirm', estimate.value)

async function refresh() {
  if (!props.visible) return
  loading.value = true
  error.value = null
  estimate.value = null
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
  } catch (e) {
    error.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
}

watch(() => props.visible, (v) => { if (v) refresh() })

function formatChars(n) {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K chars`
  return `${n} chars`
}

function formatTokens(n) {
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

// Phase 7.8: warn when the simulation would be expensive on paid providers
const costWarningTier = computed(() => {
  if (!estimate.value) return null
  const costs = estimate.value.total.approx_cost_usd
  // Warn if premium Claude > $5 or total tokens > 10M (high agent/round combo)
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
  if (costWarningTier.value === 'very-high') {
    return 'Very large simulation'
  }
  if (costWarningTier.value === 'high') {
    return 'High-cost scenario on premium models'
  }
  return 'Moderate cost on paid providers'
})

const costWarningMessage = computed(() => {
  if (!estimate.value) return ''
  const costs = estimate.value.total.approx_cost_usd
  if (costWarningTier.value === 'very-high') {
    return `${formatTokens(estimate.value.total.tokens)} tokens is a very large run. Consider reducing agent count or rounds before proceeding. Free tiers will be exhausted quickly.`
  }
  if (costWarningTier.value === 'high') {
    return `Claude Sonnet would cost ~$${costs.premium_claude_sonnet.toFixed(2)}. Consider a cheaper provider (Groq, DeepSeek, Gemini Flash) or reduce the scenario size.`
  }
  return `DeepSeek would cost ~$${costs.cheap_deepseek_chat.toFixed(2)}. Free tier on Groq or Gemini would be $0.`
})
</script>

<style scoped>
.preflight-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
  padding: 20px;
}

.preflight-modal {
  background: #1a1a1a;
  color: #e8e8e8;
  border-radius: 12px;
  width: 100%;
  max-width: 720px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(218, 165, 32, 0.2);
}

.preflight-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.preflight-header h2 {
  font-size: 1.3rem;
  font-weight: 700;
  margin: 0;
  color: #DAA520;
}

.close-btn {
  background: none;
  border: none;
  color: #999;
  font-size: 1.8rem;
  cursor: pointer;
  line-height: 1;
  padding: 0 8px;
}
.close-btn:hover { color: #fff; }

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
  font-size: 0.85rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: #999;
  margin: 0 0 12px 0;
  font-weight: 600;
}

.grid-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.metric {
  display: flex;
  justify-content: space-between;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
}
.metric-label { color: #999; font-size: 0.9rem; }
.metric-value { font-weight: 600; }

.total-box {
  text-align: center;
  padding: 20px;
  background: linear-gradient(135deg, rgba(218, 165, 32, 0.1), rgba(218, 165, 32, 0.03));
  border: 1px solid rgba(218, 165, 32, 0.3);
  border-radius: 8px;
  margin-bottom: 16px;
}
.total-value { font-size: 2.5rem; font-weight: 800; color: #DAA520; line-height: 1; }
.total-label { font-size: 0.85rem; color: #999; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.1em; }

.steps { display: flex; flex-direction: column; gap: 8px; }
.step-row {
  display: grid;
  grid-template-columns: 110px 1fr 80px 80px;
  align-items: center;
  gap: 12px;
  font-size: 0.85rem;
}
.step-name { color: #ccc; }
.step-bar-container {
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
  height: 8px;
  overflow: hidden;
}
.step-bar {
  background: linear-gradient(90deg, #DAA520, #f0c050);
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}
.step-tokens { color: #DAA520; font-weight: 600; text-align: right; }
.step-calls { color: #777; font-size: 0.8rem; text-align: right; }

.dominant-note {
  margin-top: 12px;
  padding: 10px;
  background: rgba(218, 165, 32, 0.05);
  border-left: 3px solid #DAA520;
  font-size: 0.85rem;
  color: #bbb;
  border-radius: 0 4px 4px 0;
}

/* Phase 7.8: cost warning banner */
.cost-warning {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 14px;
  border: 1px solid;
}
.cost-warning.warn-medium {
  background: rgba(218, 165, 32, 0.08);
  border-color: rgba(218, 165, 32, 0.4);
}
.cost-warning.warn-high {
  background: rgba(250, 204, 21, 0.1);
  border-color: rgba(250, 204, 21, 0.5);
}
.cost-warning.warn-danger {
  background: rgba(248, 113, 113, 0.1);
  border-color: rgba(248, 113, 113, 0.5);
}
.warning-icon {
  font-size: 1.3rem;
  line-height: 1;
  flex-shrink: 0;
}
.cost-warning.warn-medium .warning-icon { color: #DAA520; }
.cost-warning.warn-high .warning-icon { color: #facc15; }
.cost-warning.warn-danger .warning-icon { color: #f87171; }
.warning-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 0.8rem;
}
.warning-body strong { color: #fff; }
.warning-hint { color: #bbb; line-height: 1.4; }

.cost-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 8px;
}
.cost-pill {
  display: flex;
  justify-content: space-between;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
  border-left: 3px solid #666;
}
.cost-pill.tier-free { border-left-color: #4ade80; }
.cost-pill.tier-cheap { border-left-color: #60a5fa; }
.cost-pill.tier-mid { border-left-color: #facc15; }
.cost-pill.tier-premium { border-left-color: #f87171; }

.cost-tier { color: #bbb; font-size: 0.85rem; }
.cost-value { font-weight: 700; color: #fff; }

.provider-list { list-style: none; padding: 0; margin: 0; }
.provider-item {
  display: grid;
  grid-template-columns: 120px 1fr auto;
  gap: 12px;
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 6px;
  margin-bottom: 6px;
  font-size: 0.85rem;
  align-items: center;
}
.provider-name { color: #DAA520; font-weight: 600; text-transform: uppercase; }
.provider-model { color: #aaa; font-family: monospace; font-size: 0.8rem; }
.provider-budget { color: #777; font-size: 0.8rem; }

.help-text { color: #888; font-size: 0.85rem; margin: 0 0 10px 0; }

.error-msg { color: #f87171; padding: 12px; background: rgba(248, 113, 113, 0.08); border-radius: 6px; }

.loading-section { text-align: center; padding: 40px 20px; }
.spinner {
  width: 32px;
  height: 32px;
  border: 3px solid rgba(218, 165, 32, 0.2);
  border-top-color: #DAA520;
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
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}

.btn-cancel, .btn-proceed {
  padding: 10px 20px;
  border-radius: 6px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  font-size: 0.9rem;
  transition: all 0.15s;
}
.btn-cancel {
  background: rgba(255, 255, 255, 0.08);
  color: #ccc;
}
.btn-cancel:hover { background: rgba(255, 255, 255, 0.12); }
.btn-proceed {
  background: #DAA520;
  color: #000;
}
.btn-proceed:hover:not(:disabled) { background: #f0c050; }
.btn-proceed:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
