<template>
  <div class="home-container">
    <!-- top navigation bar (now provided by global AppHeader) -->

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
      <!-- Tab bar: New project | Previous sessions
           Right side carries the card/list view toggle, but only while
           the Previous sessions tab is active. Keeps controls in one
           horizontal row so the table area stays uncluttered. -->
      <nav class="tab-bar" role="tablist">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'new' }"
          role="tab"
          :aria-selected="activeTab === 'new'"
          @click="setTab('new')"
        >
          <span class="tab-glyph">＋</span> {{ $t('home.tabNew') }}
        </button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'history' }"
          role="tab"
          :aria-selected="activeTab === 'history'"
          @click="setTab('history')"
        >
          <span class="tab-glyph">◇</span> {{ $t('home.tabHistory') }}
          <span v-if="historyCount > 0" class="tab-count">{{ historyCount }}</span>
        </button>

        <div v-if="activeTab === 'history'" class="tab-bar-actions">
          <span class="toggle-label">{{ $t('history.viewLabel') }}</span>
          <div class="view-toggle">
            <button
              class="vt-btn"
              :class="{ active: historyView === 'card' }"
              @click="setHistoryView('card')"
              :title="$t('history.viewCard')"
            >
              <span class="vt-icon">▦</span> {{ $t('history.viewCard') }}
            </button>
            <button
              class="vt-btn"
              :class="{ active: historyView === 'list' }"
              @click="setHistoryView('list')"
              :title="$t('history.viewList')"
            >
              <span class="vt-icon">≡</span> {{ $t('history.viewList') }}
            </button>
          </div>
        </div>
      </nav>

      <!-- New project tab -->
      <section v-show="activeTab === 'new'" class="dashboard-section">
        <!-- Workflow rail (15%): condensed 5-step legend with hover tooltip -->
        <aside class="workflow-rail" :aria-label="$t('home.workflowSequence')">
          <div class="rail-header">
            <span class="diamond-icon">◇</span> {{ $t('home.workflowSequence') }}
          </div>
          <ol class="rail-steps">
            <li
              v-for="n in 5"
              :key="n"
              class="rail-step"
              :title="$t('home.step0' + n + 'Desc')"
            >
              <span class="rail-num">0{{ n }}</span>
              <span class="rail-label">{{ $t('home.stepShort0' + n) }}</span>
            </li>
          </ol>
        </aside>

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

      <!-- Previous sessions tab -->
      <section v-show="activeTab === 'history'" class="history-tab">
        <HistoryDatabase ref="historyRef" :viewMode="historyView" />
      </section>
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

const historyRef = ref(null)
const historyCount = ref(0)

// ============ Tab state ============
// Persisted to localStorage so returning users land on whichever tab
// they last used. Default is 'new' for first-time visits.
const TAB_KEY = 'home-tab'
const validTabs = ['new', 'history']
const initialTab = (() => {
  try {
    const saved = localStorage.getItem(TAB_KEY)
    return validTabs.includes(saved) ? saved : 'new'
  } catch { return 'new' }
})()
const activeTab = ref(initialTab)
const setTab = (t) => {
  if (!validTabs.includes(t)) return
  activeTab.value = t
  try { localStorage.setItem(TAB_KEY, t) } catch { /* ignore */ }
}

// History card/list view — owned by Home so the toggle can live in the
// tab bar. HistoryDatabase reads it via prop.
const HISTORY_VIEW_KEY = 'history-view-mode'
const validHistoryViews = ['card', 'list']
const historyView = ref((() => {
  try {
    const saved = localStorage.getItem(HISTORY_VIEW_KEY)
    return validHistoryViews.includes(saved) ? saved : 'card'
  } catch { return 'card' }
})())
const setHistoryView = (m) => {
  if (!validHistoryViews.includes(m)) return
  historyView.value = m
  try { localStorage.setItem(HISTORY_VIEW_KEY, m) } catch { /* ignore */ }
}

// History count for the tab badge — reads from the same endpoint
// HistoryDatabase uses, but we only need the length.
const loadHistoryCount = async () => {
  try {
    const res = await getSimulationHistory(50)
    if (res?.success && Array.isArray(res.data)) {
      historyCount.value = res.data.length
    }
  } catch (err) {
    console.warn('History count fetch failed', err)
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
  // Populate the history-count badge on the Previous sessions tab.
  // Non-blocking — failure just leaves the badge at 0.
  loadHistoryCount()
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
/* ============================================================
   v1.1.9 — tabbed home with thin workflow rail
   Replaces the old 50/50 dashboard split. The hero stays as-is;
   tabs sit between the hero and the content; the New project
   tab uses a 15/85 column split so the console gets breathing
   room while the workflow legend remains visible as a sidebar.
   ============================================================ */

/* Tab bar — GitHub-style underline tabs.
   The bar itself has a 1px bottom rule; each tab is a borderless
   button that gains a thick coloured underline when active, visually
   "anchoring" it to the content area below. */
.tab-bar {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--border);
  margin-top: 48px;
  padding: 0;
  position: relative;
}
.tab-btn {
  background: transparent;
  border: none;
  padding: 16px 24px 14px;
  font-family: var(--font-mono);
  font-size: 0.95rem;
  letter-spacing: 0.04em;
  color: var(--gray-text);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  border-bottom: 3px solid transparent;
  margin-bottom: -1px;  /* overlap the bar's 1px border */
  transition: color 0.15s, border-color 0.15s;
  text-transform: uppercase;
  font-weight: 500;
}
.tab-btn:hover {
  color: var(--black);
  border-bottom-color: var(--border);
}
.tab-btn.active {
  color: var(--black);
  border-bottom-color: var(--orange, #FF4500);
  font-weight: 700;
}
.tab-glyph {
  font-size: 1.05rem;
  line-height: 1;
  opacity: 0.7;
}
.tab-btn.active .tab-glyph {
  opacity: 1;
  color: var(--orange, #FF4500);
}
.tab-count {
  background: var(--border);
  color: var(--gray-text);
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.tab-btn.active .tab-count {
  background: var(--orange, #FF4500);
  color: #ffffff;
}

/* Right-aligned actions group inside the tab bar */
.tab-bar-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 6px;  /* visual align with tab labels */
}
.tab-bar-actions .toggle-label {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--gray-text);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.tab-bar-actions .view-toggle {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: 5px;
  overflow: hidden;
}
.tab-bar-actions .vt-btn {
  background: transparent;
  border: none;
  padding: 5px 12px;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--gray-text);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-right: 1px solid var(--border);
  transition: background 0.15s, color 0.15s;
}
.tab-bar-actions .vt-btn:last-child { border-right: none; }
.tab-bar-actions .vt-btn:hover { background: #f5f5f5; color: var(--black); }
.tab-bar-actions .vt-btn.active {
  background: var(--black);
  color: #ffffff;
}
.tab-bar-actions .vt-icon { font-size: 0.9rem; line-height: 1; }

/* New project tab: 15% rail + 85% console */
.dashboard-section {
  display: flex;
  gap: 32px;
  padding-top: 40px;
  align-items: flex-start;
}

/* Workflow rail — narrow vertical legend */
.workflow-rail {
  flex: 0 0 15%;
  max-width: 200px;
  min-width: 140px;
  border: 1px solid var(--border);
  padding: 18px 16px;
  position: sticky;
  top: 80px;
}
.rail-header {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #999;
  margin-bottom: 18px;
  display: flex;
  align-items: center;
  gap: 6px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.diamond-icon {
  font-size: 1rem;
  line-height: 1;
}
.rail-steps {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.rail-step {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: default;
  position: relative;
}
.rail-step + .rail-step::before {
  content: '';
  position: absolute;
  left: 11px;
  top: -14px;
  height: 14px;
  width: 1px;
  background: var(--border);
}
.rail-num {
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 0.78rem;
  color: var(--black);
  opacity: 0.32;
  flex: 0 0 auto;
  width: 22px;
}
.rail-label {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  letter-spacing: 0.03em;
  color: var(--black);
  text-transform: uppercase;
}
.rail-step:hover .rail-num { opacity: 0.7; }
.rail-step:hover .rail-label { color: var(--orange); }

/* Right panel: console grows into the freed space */
.right-panel {
  flex: 1;
  min-width: 0;
}

/* History tab wrapper — the existing HistoryDatabase styles handle internals */
.history-tab {
  padding-top: 32px;
}

/* Narrow viewports: collapse rail to a horizontal strip above the console */
@media (max-width: 900px) {
  .dashboard-section {
    flex-direction: column;
    gap: 20px;
  }
  .workflow-rail {
    flex: 1 1 auto;
    max-width: none;
    min-width: 0;
    width: 100%;
    position: static;
  }
  .rail-steps {
    flex-direction: row;
    gap: 18px;
    flex-wrap: wrap;
  }
  .rail-step + .rail-step::before { display: none; }
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

html[lang="en"] .rail-label,
html[lang="en"] .rail-num {
  font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
}
</style>
