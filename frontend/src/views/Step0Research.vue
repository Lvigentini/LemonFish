<template>
  <div class="step0-container">
    <nav class="navbar">
      <router-link to="/" class="nav-brand">LEMONFISH</router-link>
      <div class="nav-links">
        <span class="step-pill">STEP 0 — RESEARCH</span>
      </div>
    </nav>

    <div class="main">
      <ResearchSetup
        v-if="screen === 'setup'"
        :availability="availability"
        :availability-loading="availabilityLoading"
        :availability-error="availabilityError"
        :initial-prompt="form.prompt"
        :initial-simulation-requirement="form.simulationRequirement"
        @start="onStart"
        @cancel="onCancelToHome"
        @refresh-availability="loadAvailability"
      />

      <ResearchProgress
        v-else-if="screen === 'progress'"
        :task="task"
        :percent="task?.progress || 0"
        :message="task?.message || ''"
        @cancel="onCancelTask"
      />

      <ResearchPreview
        v-else-if="screen === 'preview' && result"
        :compiled-text="result.compiled_text"
        :citations="result.citations"
        :sub-topics="result.sub_topics"
        @promote="onPromote"
        @start-over="onStartOver"
      />

      <div v-else-if="screen === 'error'" class="error-card">
        <h2>{{ $t('research.errorTitle') }}</h2>
        <p>{{ errorMessage }}</p>
        <button class="primary-btn" type="button" @click="onStartOver">
          {{ $t('research.tryAgain') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import ResearchSetup from '../components/research/ResearchSetup.vue'
import ResearchProgress from '../components/research/ResearchProgress.vue'
import ResearchPreview from '../components/research/ResearchPreview.vue'
import {
  getResearchAvailability,
  startResearch,
  getResearchStatus,
  getResearchResult,
  promoteResearch,
  cancelResearch,
} from '../api/research'

const router = useRouter()
const { t } = useI18n()

// Screen state machine: setup → progress → preview (→ error)
const screen = ref('setup')

// Setup form
const form = ref({
  prompt: '',
  simulationRequirement: '',
})

// Runner availability
const availability = ref({ runners: [], default_runner: 'api' })
const availabilityLoading = ref(false)
const availabilityError = ref('')

// Active task state
const taskId = ref('')
const projectId = ref('')
const task = ref(null)
const result = ref(null)
const errorMessage = ref('')

// Polling
let pollHandle = null

onMounted(() => {
  loadAvailability()
})

onBeforeUnmount(() => {
  stopPolling()
})

async function loadAvailability() {
  availabilityLoading.value = true
  availabilityError.value = ''
  try {
    const res = await getResearchAvailability()
    availability.value = res
  } catch (err) {
    // 404 = research module disabled on the backend
    if (err?.response?.status === 404) {
      availabilityError.value = t('research.moduleDisabled')
    } else {
      availabilityError.value = err?.message || String(err)
    }
  } finally {
    availabilityLoading.value = false
  }
}

async function onStart({ prompt, simulationRequirement, runner }) {
  form.value.prompt = prompt
  form.value.simulationRequirement = simulationRequirement
  errorMessage.value = ''
  task.value = null
  result.value = null

  try {
    const res = await startResearch({
      prompt,
      simulation_requirement: simulationRequirement,
      runner_choice: runner,
    })
    taskId.value = res.task_id
    projectId.value = res.project_id
    screen.value = 'progress'
    startPolling()
  } catch (err) {
    errorMessage.value = err?.message || String(err)
    screen.value = 'error'
  }
}

function startPolling() {
  stopPolling()
  pollHandle = setInterval(pollOnce, 2500)
  pollOnce()
}

function stopPolling() {
  if (pollHandle) {
    clearInterval(pollHandle)
    pollHandle = null
  }
}

async function pollOnce() {
  if (!taskId.value) return
  try {
    const res = await getResearchStatus(taskId.value)
    task.value = res.task

    const phase = res.task?.phase
    if (phase === 'completed') {
      stopPolling()
      await loadResult()
    } else if (phase === 'failed') {
      stopPolling()
      errorMessage.value = res.task?.error || t('research.unknownError')
      screen.value = 'error'
    } else if (phase === 'cancelled') {
      stopPolling()
      errorMessage.value = t('research.cancelledByUser')
      screen.value = 'error'
    }
  } catch (err) {
    // Poll errors are non-fatal — keep polling
    console.warn('research status poll failed:', err)
  }
}

async function loadResult() {
  try {
    const res = await getResearchResult(taskId.value)
    result.value = res
    screen.value = 'preview'
  } catch (err) {
    errorMessage.value = err?.message || String(err)
    screen.value = 'error'
  }
}

async function onCancelTask() {
  try {
    await cancelResearch(taskId.value)
  } catch (err) {
    console.warn('cancel request failed:', err)
  }
}

async function onPromote() {
  try {
    const res = await promoteResearch(taskId.value)
    // Hand off to existing Step 1 / Process flow with the new project_id
    router.push({ name: 'Process', params: { projectId: res.project_id } })
  } catch (err) {
    errorMessage.value = err?.message || String(err)
    screen.value = 'error'
  }
}

function onStartOver() {
  stopPolling()
  taskId.value = ''
  projectId.value = ''
  task.value = null
  result.value = null
  errorMessage.value = ''
  screen.value = 'setup'
}

function onCancelToHome() {
  router.push({ name: 'Home' })
}
</script>

<style scoped>
.step0-container {
  min-height: 100vh;
  background: #f5f5f5;
}

.navbar {
  background: #000000;
  color: #ffffff;
  padding: 16px 32px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.nav-brand {
  font-family: 'Space Grotesk', sans-serif;
  font-weight: 700;
  font-size: 20px;
  color: #ffffff;
  text-decoration: none;
  letter-spacing: 1px;
}

.step-pill {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #ff4500;
  border: 1px solid #ff4500;
  padding: 4px 10px;
  border-radius: 999px;
}

.main {
  padding: 40px 24px;
}

.error-card {
  max-width: 600px;
  margin: 0 auto;
  padding: 32px;
  background: #ffffff;
  border: 1px solid #c00;
  border-radius: 4px;
  text-align: center;
}

.error-card h2 {
  font-family: 'Space Grotesk', sans-serif;
  margin: 0 0 12px;
  color: #c00;
}

.error-card p {
  color: #666;
  margin-bottom: 20px;
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
</style>
