<template>
  <div class="home-container">
    <!-- top navigation bar -->
    <nav class="navbar">
      <div class="nav-brand">MIROFISH <span class="brand-suffix">[LEMONFISH]</span> <span class="version-pill">v{{ appVersion }}</span></div>
      <div class="nav-links">
        <LanguageSwitcher />
        <a href="https://github.com/Lvigentini/LemonFish" target="_blank" class="github-link">
          {{ $t('nav.visitGithub') }} <span class="arrow">↗</span>
        </a>
      </div>
    </nav>

    <div class="main-content">
      <!-- 上半部分：Hero 区域 -->
      <section class="hero-section">
        <div class="hero-left">
          <div class="tag-row">
            <span class="orange-tag">{{ $t('home.tagline') }}</span>
            <span class="version-pill">v{{ appVersion }}</span>
          </div>
          
          <h1 class="main-title">
            {{ $t('home.heroTitle1') }}<br>
            <span class="gradient-text">{{ $t('home.heroTitle2') }}</span>
          </h1>
          
          <div class="hero-desc">
            <p>
              <i18n-t keypath="home.heroDesc" tag="span">
                <template #brand><span class="highlight-bold">{{ $t('home.heroDescBrand') }}</span></template>
                <template #agentScale><span class="highlight-orange">{{ $t('home.heroDescAgentScale') }}</span></template>
                <template #optimalSolution><span class="highlight-code">{{ $t('home.heroDescOptimalSolution') }}</span></template>
              </i18n-t>
            </p>
            <p class="slogan-text">
              {{ $t('home.slogan') }}<span class="blinking-cursor">_</span>
            </p>
          </div>
           
          <div class="decoration-square"></div>
        </div>
        
        <div class="hero-right">
          <!-- Logo 区域 -->
          <div class="logo-container">
            <img src="/MiroFish_lemonLogo.jpeg" alt="MiroFish [LemonFish] Logo" class="hero-logo" />
          </div>
          
          <button class="scroll-down-btn" @click="scrollToBottom">
            ↓
          </button>
        </div>
      </section>

      <!-- 下半部分：双栏布局 -->
      <section class="dashboard-section">
        <!-- 左栏：状态与步骤 -->
        <div class="left-panel">
          <div class="panel-header">
            <span class="status-dot">■</span> {{ $t('home.systemStatus') }}
          </div>
          
          <h2 class="section-title">{{ $t('home.systemReady') }}</h2>
          <p class="section-desc">
            {{ $t('home.systemReadyDesc') }}
          </p>
          
          <!-- 数据指标卡片 -->
          <div class="metrics-row">
            <div class="metric-card">
              <div class="metric-value">{{ $t('home.metricLowCost') }}</div>
              <div class="metric-label">{{ $t('home.metricLowCostDesc') }}</div>
            </div>
            <div class="metric-card">
              <div class="metric-value">{{ $t('home.metricHighAvail') }}</div>
              <div class="metric-label">{{ $t('home.metricHighAvailDesc') }}</div>
            </div>
          </div>

          <!-- 项目模拟步骤介绍 (新增区域) -->
          <div class="steps-container">
            <div class="steps-header">
               <span class="diamond-icon">◇</span> {{ $t('home.workflowSequence') }}
            </div>
            <div class="workflow-list">
              <div class="workflow-item">
                <span class="step-num">01</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('home.step01Title') }}</div>
                  <div class="step-desc">{{ $t('home.step01Desc') }}</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">02</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('home.step02Title') }}</div>
                  <div class="step-desc">{{ $t('home.step02Desc') }}</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">03</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('home.step03Title') }}</div>
                  <div class="step-desc">{{ $t('home.step03Desc') }}</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">04</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('home.step04Title') }}</div>
                  <div class="step-desc">{{ $t('home.step04Desc') }}</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">05</span>
                <div class="step-info">
                  <div class="step-title">{{ $t('home.step05Title') }}</div>
                  <div class="step-desc">{{ $t('home.step05Desc') }}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Right panel: interactive console -->
        <div class="right-panel">
          <div class="console-box">

            <!-- Step 1 source selector: upload OR research, side by side -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">{{ $t('home.step1Label') || 'STEP 01 · REALITY SEED' }}</span>
                <span class="console-meta">{{ $t('home.step1Hint') || 'Choose one' }}</span>
              </div>

              <div class="mode-picker">
                <button
                  type="button"
                  class="mode-card"
                  :class="{ active: inputMode === 'upload' }"
                  @click="setInputMode('upload')"
                  :disabled="loading"
                >
                  <div class="mode-card-icon">📄</div>
                  <div class="mode-card-title">{{ $t('home.modeUploadTitle') || 'Upload documents' }}</div>
                  <div class="mode-card-desc">{{ $t('home.modeUploadDesc') || 'PDF, Markdown, TXT, CSV. You already have the source material.' }}</div>
                </button>
                <button
                  type="button"
                  class="mode-card"
                  :class="{ active: inputMode === 'research', disabled: !researchAvailable }"
                  @click="setInputMode('research')"
                  :disabled="loading || !researchAvailable"
                  :title="!researchAvailable ? 'Research module disabled. Set RESEARCH_ENABLED=true in .env.' : ''"
                >
                  <div class="mode-card-icon">🔎</div>
                  <div class="mode-card-title">{{ $t('home.modeResearchTitle') || 'Research from prompt' }}</div>
                  <div class="mode-card-desc">{{ $t('home.modeResearchDesc') || 'Describe what to predict. AI agents gather source material via web search.' }}</div>
                  <div v-if="!researchAvailable" class="mode-card-badge">disabled</div>
                </button>
              </div>
            </div>

            <!-- Upload zone (only when upload mode selected) -->
            <div v-if="inputMode === 'upload'" class="console-section">
              <div
                class="upload-zone"
                :class="{ 'drag-over': isDragOver, 'has-files': files.length > 0 }"
                @dragover.prevent="handleDragOver"
                @dragleave.prevent="handleDragLeave"
                @drop.prevent="handleDrop"
                @click="triggerFileInput"
              >
                <input
                  ref="fileInput"
                  type="file"
                  multiple
                  accept=".pdf,.md,.txt,.csv"
                  @change="handleFileSelect"
                  style="display: none"
                  :disabled="loading"
                />

                <div v-if="files.length === 0" class="upload-placeholder">
                  <div class="upload-icon">↑</div>
                  <div class="upload-title">{{ $t('home.dragToUpload') }}</div>
                  <div class="upload-hint">{{ $t('home.orBrowse') }}</div>
                </div>

                <div v-else class="file-list">
                  <div v-for="(file, index) in files" :key="index" class="file-item">
                    <span class="file-icon">📄</span>
                    <span class="file-name">{{ file.name }}</span>
                    <button @click.stop="removeFile(index)" class="remove-btn">×</button>
                  </div>
                </div>
              </div>
            </div>

            <!-- Research notice (only when research mode selected) -->
            <div v-if="inputMode === 'research'" class="console-section">
              <div class="research-notice">
                <div class="research-notice-icon">⚡</div>
                <div class="research-notice-body">
                  <div class="research-notice-title">{{ $t('home.researchNoticeTitle') || 'Research mode selected' }}</div>
                  <div class="research-notice-desc">
                    {{ $t('home.researchNoticeDesc') || 'Describe your prediction goal below. When you click Start, research agents will gather source material automatically before the simulation begins.' }}
                  </div>
                </div>
              </div>
            </div>

            <!-- Divider -->
            <div class="console-divider">
              <span>{{ $t('home.inputParams') }}</span>
            </div>

            <!-- Prompt input (shared across modes) -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">{{ $t('home.simulationPrompt') }}</span>
              </div>
              <div class="input-wrapper">
                <textarea
                  v-model="formData.simulationRequirement"
                  class="code-input"
                  :placeholder="inputMode === 'research' ? ($t('home.researchPromptPlaceholder') || 'e.g. Predict public reaction to a new padel/pickleball centre in Wollongong, with a 6+6 vs 10+0 court split...') : $t('home.promptPlaceholder')"
                  rows="6"
                  :disabled="loading"
                ></textarea>
                <div class="model-badge">{{ $t('home.engineBadge') }}</div>
              </div>
            </div>

            <!-- Start button — branches on input mode -->
            <div class="console-section btn-section">
              <button
                class="start-engine-btn"
                @click="startEntry"
                :disabled="!canStart || loading"
              >
                <span v-if="!loading">
                  {{ inputMode === 'research'
                     ? ($t('home.startEngineResearch') || 'Start with research')
                     : $t('home.startEngine') }}
                </span>
                <span v-else>{{ $t('home.initializing') }}</span>
                <span class="btn-arrow">→</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- Resume previous session: compact banner, only renders when partials exist -->
      <section v-if="resumableSessions.length > 0" class="resume-section">
        <div class="resume-header">
          <span class="resume-diamond">◇</span>
          <h3 class="resume-title">Resume previous session</h3>
          <span class="resume-count">
            {{ resumableSessions.length }}
            {{ resumableSessions.length === 1 ? 'unfinished sim' : 'unfinished sims' }}
          </span>
        </div>
        <div class="resume-list">
          <button
            v-for="sim in resumableSessions.slice(0, 4)"
            :key="sim.simulation_id"
            class="resume-card"
            :class="`resume-stage-${getResumeStage(sim)}`"
            @click="resumeSession(sim)"
            :title="`Resume at ${getResumeTarget(sim)}`"
          >
            <div class="resume-card-head">
              <span class="resume-stage-pill" :class="`pill-${getResumeStage(sim)}`">
                {{ getResumeStage(sim).toUpperCase() }}
              </span>
              <span class="resume-card-id">{{ formatSimId(sim.simulation_id) }}</span>
            </div>
            <div class="resume-card-title">{{ truncate(sim.simulation_requirement, 70) || '(no requirement)' }}</div>
            <div class="resume-card-meta">
              <span>{{ sim.entities_count || 0 }} agents</span>
              <span>·</span>
              <span>{{ formatRelative(sim.updated_at || sim.created_at) }}</span>
              <span class="resume-arrow">→ {{ getResumeTarget(sim) }}</span>
            </div>
          </button>
        </div>
        <button
          v-if="resumableSessions.length > 4"
          class="resume-more"
          @click="scrollToHistory"
        >
          + {{ resumableSessions.length - 4 }} more — see full history below
        </button>
      </section>

      <!-- historyprojectdatabase -->
      <HistoryDatabase ref="historyRef" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import HistoryDatabase from '../components/HistoryDatabase.vue'
import LanguageSwitcher from '../components/LanguageSwitcher.vue'
import { getResearchAvailability } from '../api/research'
import { getSimulationHistory } from '../api/simulation'

const router = useRouter()
const appVersion = __APP_VERSION__

// ============ Resume previous session ============
//
// Fetches the history on mount, filters to partials (anything not
// completed/failed), and renders a compact banner above HistoryDatabase
// so returning users can pick up where they left off without hunting
// through the full carousel.
//
// The classifier mirrors HistoryDatabase.getLifecycleStage — kept inline
// here rather than extracted to a util because the duplication is ~15
// lines and both views need to own the semantic independently for now.
const resumableSessions = ref([])
const historyRef = ref(null)

const getResumeStage = (sim) => {
  if (!sim) return 'unknown'
  const s = (sim.status || '').toLowerCase()
  const rs = (sim.runner_status || '').toLowerCase()
  if (s === 'stopped' || rs === 'stopped' || rs === 'cancelled') return 'stopped'
  if (s === 'running' || rs === 'running') return 'running'
  if (s === 'ready') return 'ready'
  if (s === 'preparing') return 'preparing'
  if (s === 'created') return 'created'
  return s || 'unknown'
}
const isResumable = (sim) => {
  const stage = getResumeStage(sim)
  // Skip completed/failed — those aren't "unfinished".
  return ['created', 'preparing', 'ready', 'running', 'stopped'].includes(stage)
}

const getResumeTarget = (sim) => {
  if (!sim) return '—'
  if (sim.report_id) return 'Report'
  if (sim.simulation_id) return 'Step 2 · Environment'
  if (sim.project_id) return 'Step 1 · Graph build'
  return '—'
}

const resumeSession = (sim) => {
  if (!sim) return
  if (sim.report_id) {
    router.push({ name: 'Report', params: { reportId: sim.report_id } })
  } else if (sim.simulation_id) {
    router.push({ name: 'Simulation', params: { simulationId: sim.simulation_id } })
  } else if (sim.project_id) {
    router.push({ name: 'Process', params: { projectId: sim.project_id } })
  }
}

const formatSimId = (id) => {
  if (!id) return ''
  return id.replace(/^sim_/, '').slice(0, 10)
}

const truncate = (text, n) => {
  if (!text) return ''
  if (text.length <= n) return text
  return text.slice(0, n) + '…'
}

const formatRelative = (iso) => {
  if (!iso) return 'unknown'
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return 'unknown'
  const diff = Date.now() - t
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins} min ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days < 7) return `${days}d ago`
  return new Date(iso).toLocaleDateString()
}

const scrollToHistory = () => {
  const el = document.querySelector('.history-database')
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

const loadResumableSessions = async () => {
  try {
    const res = await getSimulationHistory(50)
    if (res?.success && Array.isArray(res.data)) {
      // Sort by updated_at desc so the most recently touched partial is first
      const partials = res.data
        .filter(isResumable)
        .sort((a, b) => {
          const ta = new Date(a.updated_at || a.created_at || 0).getTime()
          const tb = new Date(b.updated_at || b.created_at || 0).getTime()
          return tb - ta
        })
      resumableSessions.value = partials
    }
  } catch (err) {
    // Non-fatal — if history fetch fails the section stays hidden
    console.warn('Resume section: history fetch failed', err)
  }
}

// Form state
const formData = ref({
  simulationRequirement: ''
})

// Uploaded files
const files = ref([])

// UI state
const loading = ref(false)
const error = ref('')
const isDragOver = ref(false)

// Input mode toggle: 'upload' (Phase 0) or 'research' (Phase 8)
const inputMode = ref('upload')
const researchAvailable = ref(false)

// File input ref
const fileInput = ref(null)

// On mount, probe the research endpoint to see if the module is enabled.
// If available, the research card is clickable; otherwise it's disabled
// with a tooltip explaining how to enable it.
onMounted(async () => {
  try {
    const res = await getResearchAvailability()
    // getResearchAvailability returns the response body directly (interceptor)
    researchAvailable.value = !!res && (res.enabled !== false)
  } catch (e) {
    researchAvailable.value = false
  }
  // Populate the "Resume previous session" banner. Non-blocking — the
  // section is v-if gated on resumableSessions.length > 0 so a failure
  // simply leaves it hidden.
  loadResumableSessions()
})

const setInputMode = (mode) => {
  if (loading.value) return
  if (mode === 'research' && !researchAvailable.value) return
  inputMode.value = mode
}

// Upload mode requires files + prompt; research mode only needs prompt
const canSubmit = computed(() => {
  return formData.value.simulationRequirement.trim() !== '' && files.value.length > 0
})
const canStart = computed(() => {
  const hasPrompt = formData.value.simulationRequirement.trim() !== ''
  if (inputMode.value === 'upload') {
    return hasPrompt && files.value.length > 0
  }
  return hasPrompt && researchAvailable.value
})

// 触发文件选择
const triggerFileInput = () => {
  if (!loading.value) {
    fileInput.value?.click()
  }
}

// processfileselect
const handleFileSelect = (event) => {
  const selectedFiles = Array.from(event.target.files)
  addFiles(selectedFiles)
}

// 处理拖拽相关
const handleDragOver = (e) => {
  if (!loading.value) {
    isDragOver.value = true
  }
}

const handleDragLeave = (e) => {
  isDragOver.value = false
}

const handleDrop = (e) => {
  isDragOver.value = false
  if (loading.value) return
  
  const droppedFiles = Array.from(e.dataTransfer.files)
  addFiles(droppedFiles)
}

// addfile
const addFiles = (newFiles) => {
  const validFiles = newFiles.filter(file => {
    const ext = file.name.split('.').pop().toLowerCase()
    return ['pdf', 'md', 'txt'].includes(ext)
  })
  files.value.push(...validFiles)
}

// removefile
const removeFile = (index) => {
  files.value.splice(index, 1)
}

// 滚动到底部
const scrollToBottom = () => {
  window.scrollTo({
    top: document.body.scrollHeight,
    behavior: 'smooth'
  })
}

// Start button entry point — branches on the chosen input mode.
// - upload mode: stash files + requirement, jump to Process view
// - research mode: jump to Step0Research with the requirement pre-filled
const startEntry = () => {
  if (!canStart.value || loading.value) return

  if (inputMode.value === 'research') {
    router.push({
      name: 'Research',
      query: { requirement: formData.value.simulationRequirement },
    })
    return
  }

  // Upload mode (default)
  import('../store/pendingUpload.js').then(({ setPendingUpload }) => {
    setPendingUpload(files.value, formData.value.simulationRequirement)
    router.push({
      name: 'Process',
      params: { projectId: 'new' }
    })
  })
}
</script>

<style scoped>
/* 全局变量与重置 */
:root {
  --black: #000000;
  --white: #FFFFFF;
  --orange: #FF4500;
  --gray-light: #F5F5F5;
  --gray-text: #666666;
  --border: #E5E5E5;
  /* 
    使用 Space Grotesk 作为主要标题字体，JetBrains Mono 作为代码/标签字体
    确保已在 index.html 引入这些 Google Fonts 
  */
  --font-mono: 'JetBrains Mono', monospace;
  --font-sans: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
  --font-cn: 'Noto Sans SC', system-ui, sans-serif;
}

.home-container {
  min-height: 100vh;
  background: var(--white);
  font-family: var(--font-sans);
  color: var(--black);
}

/* 顶部导航 */
.navbar {
  height: 60px;
  background: var(--black);
  color: var(--white);
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 40px;
}

.nav-brand {
  font-family: var(--font-mono);
  font-weight: 800;
  letter-spacing: 1px;
  font-size: 1.2rem;
}

.brand-suffix {
  font-weight: 500;
  font-size: 0.7em;
  color: #DAA520;
  letter-spacing: 0.5px;
  margin-left: 4px;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 16px;
}

.github-link {
  color: var(--white);
  text-decoration: none;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: opacity 0.2s;
}

.github-link:hover {
  opacity: 0.8;
}

.arrow {
  font-family: sans-serif;
}

/* 主要内容区 */
.main-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 60px 40px;
}

/* Hero 区域 */
.hero-section {
  display: flex;
  justify-content: space-between;
  margin-bottom: 80px;
  position: relative;
}

.hero-left {
  flex: 1;
  padding-right: 60px;
}

.tag-row {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 25px;
  font-family: var(--font-mono);
  font-size: 0.8rem;
}

.orange-tag {
  background: var(--orange);
  color: var(--white);
  padding: 4px 10px;
  font-weight: 700;
  letter-spacing: 1px;
  font-size: 0.75rem;
}

.version-pill {
  display: inline-block;
  background: rgba(218, 165, 32, 0.15);
  color: #DAA520;
  font-weight: 600;
  font-size: 0.7rem;
  letter-spacing: 0.5px;
  padding: 3px 10px;
  border-radius: 999px;
  border: 1px solid rgba(218, 165, 32, 0.3);
}

.main-title {
  font-size: 4.5rem;
  line-height: 1.2;
  font-weight: 500;
  margin: 0 0 40px 0;
  letter-spacing: -2px;
  color: var(--black);
}

.gradient-text {
  background: linear-gradient(90deg, #000000 0%, #444444 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  display: inline-block;
}

.hero-desc {
  font-size: 1.05rem;
  line-height: 1.8;
  color: var(--gray-text);
  max-width: 640px;
  margin-bottom: 50px;
  font-weight: 400;
  text-align: justify;
}

.hero-desc p {
  margin-bottom: 1.5rem;
}

.highlight-bold {
  color: var(--black);
  font-weight: 700;
}

.highlight-orange {
  color: var(--orange);
  font-weight: 700;
  font-family: var(--font-mono);
}

.highlight-code {
  background: rgba(0, 0, 0, 0.05);
  padding: 2px 6px;
  border-radius: 2px;
  font-family: var(--font-mono);
  font-size: 0.9em;
  color: var(--black);
  font-weight: 600;
}

.slogan-text {
  font-size: 1.2rem;
  font-weight: 520;
  color: var(--black);
  letter-spacing: 1px;
  border-left: 3px solid var(--orange);
  padding-left: 15px;
  margin-top: 20px;
}

.blinking-cursor {
  color: var(--orange);
  animation: blink 1s step-end infinite;
  font-weight: 700;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.decoration-square {
  width: 16px;
  height: 16px;
  background: var(--orange);
}

.hero-right {
  flex: 0.8;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-end;
}

.logo-container {
  width: 100%;
  display: flex;
  justify-content: flex-end;
  padding-right: 40px;
}

.hero-logo {
  max-width: 500px; /* 调整logo大小 */
  width: 100%;
}

.scroll-down-btn {
  width: 40px;
  height: 40px;
  border: 1px solid var(--border);
  background: transparent;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--orange);
  font-size: 1.2rem;
  transition: all 0.2s;
}

.scroll-down-btn:hover {
  border-color: var(--orange);
}

/* Dashboard 双栏布局 */
.dashboard-section {
  display: flex;
  gap: 60px;
  border-top: 1px solid var(--border);
  padding-top: 60px;
  align-items: flex-start;
}

.dashboard-section .left-panel,
.dashboard-section .right-panel {
  display: flex;
  flex-direction: column;
}

/* left panel */
.left-panel {
  flex: 0.8;
}

.panel-header {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #999;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
}

.status-dot {
  color: var(--orange);
  font-size: 0.8rem;
}

.section-title {
  font-size: 2rem;
  font-weight: 520;
  margin: 0 0 15px 0;
}

.section-desc {
  color: var(--gray-text);
  margin-bottom: 25px;
  line-height: 1.6;
}

.metrics-row {
  display: flex;
  gap: 20px;
  margin-bottom: 15px;
}

.metric-card {
  border: 1px solid var(--border);
  padding: 20px 30px;
  min-width: 150px;
}

.metric-value {
  font-family: var(--font-mono);
  font-size: 1.8rem;
  font-weight: 520;
  margin-bottom: 5px;
}

.metric-label {
  font-size: 0.85rem;
  color: #999;
}

/* 项目模拟步骤介绍 */
.steps-container {
  border: 1px solid var(--border);
  padding: 30px;
  position: relative;
}

.steps-header {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #999;
  margin-bottom: 25px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.diamond-icon {
  font-size: 1.2rem;
  line-height: 1;
}

.workflow-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.workflow-item {
  display: flex;
  align-items: flex-start;
  gap: 20px;
}

.step-num {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--black);
  opacity: 0.3;
}

.step-info {
  flex: 1;
}

.step-title {
  font-weight: 520;
  font-size: 1rem;
  margin-bottom: 4px;
}

.step-desc {
  font-size: 0.85rem;
  color: var(--gray-text);
}

/* 右侧交互控制台 */
.right-panel {
  flex: 1.2;
}

.console-box {
  border: 1px solid #CCC; /* 外部实线 */
  padding: 8px; /* 内边距形成双重边框感 */
}

.console-section {
  padding: 20px;
}

.console-section.btn-section {
  padding-top: 0;
}

.console-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 15px;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #666;
}

.upload-zone {
  border: 1px dashed #CCC;
  height: 200px;
  overflow-y: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s;
  background: #FAFAFA;
}

.upload-zone.has-files {
  align-items: flex-start;
}

.upload-zone:hover {
  background: #F0F0F0;
  border-color: #999;
}

.upload-placeholder {
  text-align: center;
}

.upload-icon {
  width: 40px;
  height: 40px;
  border: 1px solid #DDD;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 15px;
  color: #999;
}

.upload-title {
  font-weight: 500;
  font-size: 0.9rem;
  margin-bottom: 5px;
}

.upload-hint {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #999;
}

.file-list {
  width: 100%;
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.file-item {
  display: flex;
  align-items: center;
  background: var(--white);
  padding: 8px 12px;
  border: 1px solid #EEE;
  font-family: var(--font-mono);
  font-size: 0.85rem;
}

.file-name {
  flex: 1;
  margin: 0 10px;
}

.remove-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.2rem;
  color: #999;
}

.console-divider {
  display: flex;
  align-items: center;
  margin: 10px 0;
}

.console-divider::before,
.console-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #EEE;
}

.console-divider span {
  padding: 0 15px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #BBB;
  letter-spacing: 1px;
}

.input-wrapper {
  position: relative;
  border: 1px solid #DDD;
  background: #FAFAFA;
}

.code-input {
  width: 100%;
  border: none;
  background: transparent;
  padding: 20px;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  line-height: 1.6;
  resize: vertical;
  outline: none;
  min-height: 150px;
}

.model-badge {
  position: absolute;
  bottom: 10px;
  right: 15px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #AAA;
}

.start-engine-btn {
  width: 100%;
  background: var(--black);
  color: var(--white);
  border: none;
  padding: 20px;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 1.1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: all 0.3s ease;
  letter-spacing: 1px;
  position: relative;
  overflow: hidden;
}

/* 可点击状态（非禁用） */
.start-engine-btn:not(:disabled) {
  background: var(--black);
  border: 1px solid var(--black);
  animation: pulse-border 2s infinite;
}

.start-engine-btn:hover:not(:disabled) {
  background: var(--orange);
  border-color: var(--orange);
  transform: translateY(-2px);
}

.start-engine-btn:active:not(:disabled) {
  transform: translateY(0);
}

.start-engine-btn:disabled {
  background: #E5E5E5;
  color: #999;
  cursor: not-allowed;
  transform: none;
  border: 1px solid #E5E5E5;
}

/* Phase 8 UI — side-by-side input mode picker (upload vs research) */
.mode-picker {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-top: 12px;
}

.mode-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  text-align: left;
  padding: 16px 14px;
  background: #fafafa;
  border: 2px solid #e0e0e0;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
  font-family: inherit;
  color: inherit;
}

.mode-card:hover:not(:disabled):not(.disabled) {
  border-color: #ff4500;
  background: #fff8f5;
}

.mode-card.active {
  border-color: #ff4500;
  background: #fff;
  box-shadow: 0 2px 8px rgba(255, 69, 0, 0.15);
}

.mode-card:disabled,
.mode-card.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mode-card-icon {
  font-size: 1.6rem;
  margin-bottom: 8px;
}

.mode-card-title {
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
  color: #000;
}

.mode-card-desc {
  font-size: 11px;
  color: #666;
  line-height: 1.4;
}

.mode-card-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  padding: 2px 6px;
  background: #e0e0e0;
  color: #666;
  font-size: 9px;
  text-transform: uppercase;
  border-radius: 2px;
  letter-spacing: 0.5px;
}

/* Research mode info banner */
.research-notice {
  display: flex;
  gap: 12px;
  padding: 12px 14px;
  background: #fff8f5;
  border: 1px solid #ffd9c9;
  border-radius: 6px;
}

.research-notice-icon {
  font-size: 1.2rem;
  line-height: 1;
  flex-shrink: 0;
}

.research-notice-body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.research-notice-title {
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 11px;
  text-transform: uppercase;
  color: #ff4500;
  letter-spacing: 0.5px;
}

.research-notice-desc {
  font-size: 11px;
  color: #666;
  line-height: 1.4;
}

/* 引导动画：微妙的边框脉冲 */
@keyframes pulse-border {
  0% { box-shadow: 0 0 0 0 rgba(0, 0, 0, 0.2); }
  70% { box-shadow: 0 0 0 6px rgba(0, 0, 0, 0); }
  100% { box-shadow: 0 0 0 0 rgba(0, 0, 0, 0); }
}

/* 响应式适配 */
@media (max-width: 1024px) {
  .dashboard-section {
    flex-direction: column;
  }
  
  .hero-section {
    flex-direction: column;
  }
  
  .hero-left {
    padding-right: 0;
    margin-bottom: 40px;
  }
  
  .hero-logo {
    max-width: 200px;
    margin-bottom: 20px;
  }
}

/* ============ Resume previous session banner ============ */

.resume-section {
  margin: 48px auto 24px;
  max-width: 1180px;
  padding: 22px 28px;
  background: #ffffff;
  border: 1px solid #eeeeee;
  border-left: 4px solid #FF5722;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.resume-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}
.resume-diamond {
  color: #FF5722;
  font-size: 1.1rem;
}
.resume-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: #1a1a1a;
  margin: 0;
  letter-spacing: 0.02em;
}
.resume-count {
  margin-left: auto;
  font-size: 0.8rem;
  color: #666;
  font-variant-numeric: tabular-nums;
  background: #f5f5f5;
  padding: 3px 10px;
  border-radius: 999px;
}

.resume-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 12px;
}

.resume-card {
  text-align: left;
  background: #fafafa;
  border: 1px solid #eeeeee;
  border-radius: 7px;
  padding: 12px 14px;
  cursor: pointer;
  transition: all 0.15s;
  font-family: inherit;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-height: 100px;
}
.resume-card:hover {
  background: #ffffff;
  border-color: #FF5722;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(255, 87, 34, 0.12);
}

.resume-card-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.resume-stage-pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.pill-created     { background: #f0f0f0; color: #666; }
.pill-preparing   { background: #fff3e0; color: #b25a00; }
.pill-ready       { background: #e1f5fe; color: #0277bd; }
.pill-running     { background: #fff8e1; color: #8a6100; }
.pill-stopped     { background: #f3e5f5; color: #7b1fa2; }
.pill-unknown     { background: #eeeeee; color: #aaa; }

.resume-card-id {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.7rem;
  color: #888;
}

.resume-card-title {
  font-size: 0.88rem;
  color: #1a1a1a;
  line-height: 1.35;
  font-weight: 500;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.resume-card-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.72rem;
  color: #888;
  margin-top: auto;
}
.resume-arrow {
  margin-left: auto;
  color: #FF5722;
  font-weight: 600;
}

.resume-more {
  background: none;
  border: none;
  color: #FF5722;
  font-weight: 600;
  font-size: 0.82rem;
  cursor: pointer;
  margin-top: 12px;
  padding: 6px 0;
}
.resume-more:hover {
  text-decoration: underline;
}
</style>

<style>
/* English locale adjustments (unscoped to target html[lang]) */
html[lang="en"] .main-title {
  font-size: 3.5rem;
  font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  letter-spacing: -1px;
}

html[lang="en"] .hero-desc {
  text-align: left;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  letter-spacing: 0;
}

html[lang="en"] .slogan-text {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  letter-spacing: 0;
}

html[lang="en"] .tag-row {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

html[lang="en"] .navbar .nav-links {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

/* Left pane: system status + workflow */
html[lang="en"] .status-section {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

html[lang="en"] .status-section .status-ready {
  font-size: 1.6rem;
}

html[lang="en"] .status-section .metric-value {
  font-family: 'Space Grotesk', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  font-size: 1.4rem;
}

html[lang="en"] .workflow-list .step-title {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

html[lang="en"] .workflow-list .step-desc {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
  font-size: 0.72rem !important;
  line-height: 1.4 !important;
}

html[lang="en"] .workflow-list {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}
</style>
