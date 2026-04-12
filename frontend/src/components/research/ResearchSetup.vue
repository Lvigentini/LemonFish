<template>
  <div class="research-setup">
    <h2 class="setup-title">{{ $t('research.setupTitle') }}</h2>
    <p class="setup-desc">{{ $t('research.setupDesc') }}</p>

    <div class="form-group">
      <label class="form-label">{{ $t('research.promptLabel') }}</label>
      <textarea
        v-model="localPrompt"
        class="form-textarea"
        :placeholder="$t('research.promptPlaceholder')"
        rows="4"
      />
    </div>

    <div class="form-group">
      <label class="form-label">{{ $t('research.simulationRequirementLabel') }}</label>
      <textarea
        v-model="localSimulationRequirement"
        class="form-textarea"
        :placeholder="$t('research.simulationRequirementPlaceholder')"
        rows="3"
      />
    </div>

    <div class="form-group">
      <label class="form-label">
        {{ $t('research.runnerLabel') }}
        <button
          v-if="!availabilityLoading"
          class="refresh-btn"
          type="button"
          @click="$emit('refresh-availability')"
          :title="$t('research.refreshRunners')"
        >↻</button>
      </label>

      <div v-if="availabilityLoading" class="runner-loading">
        {{ $t('research.checkingRunners') }}
      </div>
      <div v-else-if="availabilityError" class="runner-error">
        {{ availabilityError }}
      </div>
      <div v-else class="runner-list">
        <label
          v-for="runner in availableRunners"
          :key="runner.name"
          class="runner-card"
          :class="{
            selected: localRunner === runner.name,
            disabled: !canPickRunner(runner),
          }"
        >
          <input
            type="radio"
            :value="runner.name"
            v-model="localRunner"
            :disabled="!canPickRunner(runner)"
          />
          <div class="runner-card-body">
            <div class="runner-name">
              <span class="runner-status-dot" :class="statusClass(runner)"></span>
              <strong>{{ runnerLabel(runner.name) }}</strong>
              <span v-if="runner.version" class="runner-version">v{{ runner.version }}</span>
            </div>
            <div class="runner-description">{{ runnerDescription(runner) }}</div>
          </div>
        </label>
      </div>
    </div>

    <div class="action-row">
      <button
        class="primary-btn"
        :disabled="!canStart"
        @click="$emit('start', { prompt: localPrompt, simulationRequirement: localSimulationRequirement, runner: localRunner })"
      >
        {{ $t('research.startResearch') }}
      </button>
      <button class="secondary-btn" type="button" @click="$emit('cancel')">
        {{ $t('common.cancel') }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  availability: { type: Object, default: () => ({ runners: [], default_runner: 'api' }) },
  availabilityLoading: { type: Boolean, default: false },
  availabilityError: { type: String, default: '' },
  initialPrompt: { type: String, default: '' },
  initialSimulationRequirement: { type: String, default: '' },
})

defineEmits(['start', 'cancel', 'refresh-availability'])

const { t } = useI18n()

const localPrompt = ref(props.initialPrompt)
const localSimulationRequirement = ref(props.initialSimulationRequirement)
const localRunner = ref(props.availability?.default_runner || 'api')

const availableRunners = computed(() => props.availability?.runners || [])

// When the availability list arrives, default to the first usable runner
// (preferring the configured default if it is usable).
watch(
  () => props.availability,
  (val) => {
    if (!val?.runners?.length) return
    const def = val.default_runner
    const usable = val.runners.filter(canPickRunner)
    if (def && usable.find((r) => r.name === def)) {
      localRunner.value = def
    } else if (usable.length) {
      localRunner.value = usable[0].name
    }
  },
  { immediate: true, deep: true }
)

function canPickRunner(runner) {
  return Boolean(runner.available && runner.auth_ok)
}

function statusClass(runner) {
  if (runner.available && runner.auth_ok) return 'status-ok'
  if (runner.available && !runner.auth_ok) return 'status-warn'
  return 'status-off'
}

function runnerLabel(name) {
  const labels = {
    claude: 'Claude Code',
    codex: 'OpenAI Codex',
    kimi: 'Kimi CLI',
    api: t('research.runnerApiLabel'),
  }
  return labels[name] || name
}

function runnerDescription(runner) {
  if (runner.available && runner.auth_ok) {
    return t('research.runnerReady')
  }
  if (runner.available && !runner.auth_ok) {
    return t('research.runnerNeedsAuth') + (runner.reason ? ` — ${runner.reason}` : '')
  }
  return runner.reason || t('research.runnerNotInstalled')
}

const canStart = computed(() => {
  if (!localPrompt.value.trim()) return false
  if (!localSimulationRequirement.value.trim()) return false
  if (!localRunner.value) return false
  const runner = availableRunners.value.find((r) => r.name === localRunner.value)
  return Boolean(runner && canPickRunner(runner))
})
</script>

<style scoped>
.research-setup {
  max-width: 800px;
  margin: 0 auto;
  padding: 32px;
  background: #ffffff;
  border: 1px solid #e5e5e5;
  border-radius: 4px;
}

.setup-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 28px;
  font-weight: 700;
  margin: 0 0 8px;
}

.setup-desc {
  color: #666666;
  margin: 0 0 24px;
  font-size: 14px;
}

.form-group {
  margin-bottom: 20px;
}

.form-label {
  display: block;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: #333;
  margin-bottom: 6px;
}

.refresh-btn {
  background: none;
  border: none;
  color: #ff4500;
  font-size: 14px;
  cursor: pointer;
  margin-left: 8px;
  padding: 0 4px;
}

.form-textarea {
  width: 100%;
  font-family: inherit;
  font-size: 14px;
  padding: 10px 12px;
  border: 1px solid #cccccc;
  border-radius: 4px;
  background: #fafafa;
  resize: vertical;
}

.form-textarea:focus {
  outline: none;
  border-color: #ff4500;
  background: #ffffff;
}

.runner-loading,
.runner-error {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  padding: 12px;
  background: #fafafa;
  border: 1px dashed #cccccc;
  border-radius: 4px;
}

.runner-error {
  color: #c00;
  border-color: #c00;
}

.runner-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.runner-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid #e5e5e5;
  border-radius: 4px;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}

.runner-card:hover:not(.disabled) {
  border-color: #ff4500;
}

.runner-card.selected {
  border-color: #ff4500;
  background: #fff8f5;
}

.runner-card.disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.runner-card input[type='radio'] {
  margin-top: 4px;
}

.runner-card-body {
  flex: 1;
}

.runner-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  margin-bottom: 4px;
}

.runner-status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}

.status-ok {
  background: #00b800;
}

.status-warn {
  background: #f5a623;
}

.status-off {
  background: #cccccc;
}

.runner-version {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #999;
}

.runner-description {
  font-size: 12px;
  color: #666;
}

.action-row {
  display: flex;
  gap: 12px;
  margin-top: 24px;
}

.primary-btn {
  background: #ff4500;
  color: #ffffff;
  border: none;
  padding: 12px 24px;
  font-family: inherit;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border-radius: 4px;
}

.primary-btn:disabled {
  background: #cccccc;
  cursor: not-allowed;
}

.secondary-btn {
  background: transparent;
  color: #333;
  border: 1px solid #cccccc;
  padding: 12px 24px;
  font-family: inherit;
  font-size: 14px;
  cursor: pointer;
  border-radius: 4px;
}
</style>
