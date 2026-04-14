<template>
  <div v-if="diag" class="sim-diagnostics" :class="severity">
    <header class="diag-header">
      <span class="diag-icon">{{ severityIcon }}</span>
      <h3>{{ $t('diagnostics.title') }}</h3>
      <span v-if="diag.is_reportable" class="pill ok">{{ $t('diagnostics.reportable') }}</span>
      <span v-else class="pill bad">{{ $t('diagnostics.notReportable') }}</span>
      <button class="refresh-btn" @click="refresh" :disabled="loading">
        {{ loading ? $t('diagnostics.loading') : $t('diagnostics.refresh') }}
      </button>
    </header>

    <!-- Blocker message (only when not reportable) -->
    <div v-if="diag.blocker" class="blocker">
      <strong>{{ $t('diagnostics.blocker.' + diag.blocker) }}</strong>
      <p class="muted">{{ $t('diagnostics.blocker.' + diag.blocker + '_desc',
        { actions: diag.activity.actions_total, expected: diag.expected_min_actions })
      }}</p>
    </div>

    <!-- Activity summary -->
    <section class="activity">
      <h4>{{ $t('diagnostics.activity') }}</h4>
      <div class="grid">
        <div class="cell">
          <span class="label">{{ $t('diagnostics.actions') }}</span>
          <span class="value" :class="{ bad: diag.activity.actions_total < diag.expected_min_actions }">
            {{ diag.activity.actions_total }}
            <small class="muted">/ {{ diag.expected_min_actions }}+</small>
          </span>
        </div>
        <div class="cell">
          <span class="label">{{ $t('diagnostics.posts') }}</span>
          <span class="value">{{ diag.activity.posts }}</span>
        </div>
        <div class="cell">
          <span class="label">{{ $t('diagnostics.comments') }}</span>
          <span class="value">{{ diag.activity.comments }}</span>
        </div>
        <div class="cell">
          <span class="label">{{ $t('diagnostics.likes') }}</span>
          <span class="value">{{ diag.activity.likes }}</span>
        </div>
        <div class="cell">
          <span class="label">{{ $t('diagnostics.follows') }}</span>
          <span class="value">{{ diag.activity.follows }}</span>
        </div>
        <div class="cell">
          <span class="label">{{ $t('diagnostics.twitter') }}</span>
          <span class="value">{{ diag.activity.actions_twitter }}</span>
        </div>
        <div class="cell">
          <span class="label">{{ $t('diagnostics.reddit') }}</span>
          <span class="value">{{ diag.activity.actions_reddit }}</span>
        </div>
      </div>
    </section>

    <!-- Warnings -->
    <section v-if="diag.warnings.length" class="warnings">
      <h4>{{ $t('diagnostics.warnings') }}</h4>
      <ul>
        <li v-for="w in diag.warnings" :key="w">
          <span class="warn-icon">⚠</span> {{ $t('diagnostics.warning.' + w) }}
        </li>
      </ul>
    </section>

    <!-- Error breakdown -->
    <section v-if="diag.errors.total > 0" class="errors">
      <h4>
        {{ $t('diagnostics.errors') }}
        <span class="pill bad">{{ diag.errors.total }}</span>
      </h4>
      <table class="err-table">
        <tr v-for="(count, key) in diag.errors.counts" :key="key">
          <td><code>{{ key }}</code></td>
          <td class="right">{{ count }}</td>
        </tr>
      </table>
      <details v-if="diag.errors.sample_lines.length" class="samples">
        <summary>{{ $t('diagnostics.sampleLines') }} ({{ diag.errors.sample_lines.length }})</summary>
        <pre>{{ diag.errors.sample_lines.join('\n') }}</pre>
      </details>
      <details v-if="diag.errors.log_tail.length" class="samples">
        <summary>{{ $t('diagnostics.logTail') }} ({{ diag.errors.log_tail.length }})</summary>
        <pre>{{ diag.errors.log_tail.join('\n') }}</pre>
      </details>
    </section>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { getSimDiagnostics } from '../api/simulation'

const props = defineProps({
  simulationId: { type: String, required: true },
  autoLoad: { type: Boolean, default: true }
})

const diag = ref(null)
const loading = ref(false)
const error = ref(null)

const severity = computed(() => {
  if (!diag.value) return ''
  if (!diag.value.is_reportable) return 'bad'
  if (diag.value.warnings.length > 0 || diag.value.errors.total > 0) return 'warn'
  return 'ok'
})

const severityIcon = computed(() => {
  switch (severity.value) {
    case 'bad': return '✗'
    case 'warn': return '⚠'
    case 'ok': return '✓'
    default: return '·'
  }
})

async function refresh() {
  if (!props.simulationId) return
  loading.value = true
  error.value = null
  try {
    const res = await getSimDiagnostics(props.simulationId)
    if (res.data.success) diag.value = res.data.data
    else error.value = res.data.error
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(() => { if (props.autoLoad) refresh() })
watch(() => props.simulationId, () => { if (props.autoLoad) refresh() })

defineExpose({ refresh, diag })
</script>

<style scoped>
.sim-diagnostics {
  background: #161a22;
  border: 1px solid #23262d;
  border-left: 4px solid #6b7280;
  border-radius: 8px;
  padding: 16px 20px;
  color: #e8ecf1;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  font-size: 13px;
  margin: 16px 0;
}
.sim-diagnostics.bad { border-left-color: #ef4444; background: #1f1417; }
.sim-diagnostics.warn { border-left-color: #fbbf24; background: #1f1b14; }
.sim-diagnostics.ok { border-left-color: #22c55e; }

.diag-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.diag-header h3 { margin: 0; font-size: 14px; font-weight: 600; flex: 0 0 auto; }
.diag-icon { font-size: 16px; }
.refresh-btn {
  margin-left: auto;
  background: #23262d;
  color: #e8ecf1;
  border: 1px solid #2f343d;
  border-radius: 5px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
}
.refresh-btn:hover:not(:disabled) { background: #2f343d; }
.refresh-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.pill {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
}
.pill.ok { background: #14532d; color: #86efac; }
.pill.bad { background: #450a0a; color: #fca5a5; }

.blocker {
  background: #450a0a;
  border: 1px solid #7f1d1d;
  border-radius: 6px;
  padding: 10px 14px;
  margin-bottom: 14px;
}
.blocker strong { color: #fca5a5; }
.blocker .muted { color: #94a3b8; margin: 4px 0 0 0; font-size: 12px; }

section { margin-top: 14px; }
section h4 { margin: 0 0 8px; font-size: 12px; color: #8b96a8; text-transform: uppercase; letter-spacing: 0.04em; }

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 10px;
}
.cell {
  background: #0f1115;
  border: 1px solid #23262d;
  border-radius: 5px;
  padding: 8px 10px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.cell .label { font-size: 11px; color: #8b96a8; }
.cell .value { font-size: 16px; font-weight: 600; color: #e8ecf1; }
.cell .value.bad { color: #fca5a5; }
.cell .value small { font-weight: 400; font-size: 11px; margin-left: 4px; }

.warnings ul { margin: 0; padding: 0; list-style: none; }
.warnings li {
  padding: 6px 0;
  color: #fbbf24;
  font-size: 13px;
}
.warn-icon { margin-right: 6px; }

.err-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.err-table td { padding: 4px 8px; border-bottom: 1px solid #23262d; }
.err-table .right { text-align: right; color: #fca5a5; font-weight: 600; }
.err-table code { background: #0f1115; padding: 2px 6px; border-radius: 3px; font-family: "SF Mono", Menlo, monospace; }

.samples { margin-top: 8px; }
.samples summary {
  cursor: pointer;
  color: #8b96a8;
  font-size: 12px;
  padding: 4px 0;
}
.samples pre {
  background: #0f1115;
  border: 1px solid #23262d;
  border-radius: 4px;
  padding: 10px;
  font-size: 11px;
  font-family: "SF Mono", Menlo, monospace;
  overflow-x: auto;
  max-height: 240px;
  color: #c9d1d9;
}

.muted { color: #6b7280; }
</style>
