<template>
  <div class="research-progress">
    <div class="phase-header">
      <h3>{{ phaseLabel }}</h3>
      <div class="progress-bar">
        <div class="progress-bar-fill" :style="{ width: percent + '%' }" />
      </div>
      <div class="progress-text">{{ percent }}% — {{ message }}</div>
    </div>

    <div v-if="task?.sub_topics?.length" class="subtopics">
      <h4 class="subtopics-title">{{ $t('research.subTopicsTitle') }}</h4>
      <div
        v-for="st in task.sub_topics"
        :key="st.index"
        class="subtopic-row"
        :class="`status-${st.status}`"
      >
        <span class="subtopic-status-icon">{{ statusIcon(st.status) }}</span>
        <div class="subtopic-body">
          <div class="subtopic-topic">{{ st.topic }}</div>
          <div v-if="st.questions?.length" class="subtopic-questions">
            <span v-for="(q, i) in st.questions" :key="i">• {{ q }}</span>
          </div>
          <div v-if="st.error" class="subtopic-error">{{ st.error }}</div>
        </div>
        <span v-if="st.runner" class="subtopic-runner">{{ st.runner }}</span>
      </div>
    </div>

    <div v-if="canCancel" class="action-row">
      <button class="cancel-btn" type="button" @click="$emit('cancel')">
        {{ $t('common.cancel') }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  task: { type: Object, default: () => null },
  percent: { type: Number, default: 0 },
  message: { type: String, default: '' },
})

defineEmits(['cancel'])

const { t } = useI18n()

const phaseLabel = computed(() => {
  const phase = props.task?.phase || 'pending'
  return t(`research.phase.${phase}`)
})

const canCancel = computed(() => {
  const phase = props.task?.phase
  return phase && phase !== 'completed' && phase !== 'failed' && phase !== 'cancelled'
})

function statusIcon(status) {
  return {
    queued: '◯',
    running: '●',
    completed: '✓',
    failed: '✗',
    skipped: '−',
  }[status] || '◯'
}
</script>

<style scoped>
.research-progress {
  max-width: 800px;
  margin: 0 auto;
  padding: 24px 32px;
  background: #ffffff;
  border: 1px solid #e5e5e5;
  border-radius: 4px;
}

.phase-header h3 {
  font-family: 'Space Grotesk', sans-serif;
  margin: 0 0 12px;
  font-size: 20px;
}

.progress-bar {
  width: 100%;
  height: 6px;
  background: #f5f5f5;
  border-radius: 3px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: #ff4500;
  transition: width 0.3s ease;
}

.progress-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #666;
  margin-top: 6px;
}

.subtopics {
  margin-top: 20px;
}

.subtopics-title {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  text-transform: uppercase;
  color: #666;
  margin: 0 0 8px;
}

.subtopic-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid #e5e5e5;
  border-radius: 4px;
  margin-bottom: 6px;
  background: #fafafa;
}

.subtopic-row.status-running {
  border-color: #ff4500;
  background: #fff8f5;
}

.subtopic-row.status-completed {
  border-color: #cce6cc;
  background: #f5fff5;
}

.subtopic-row.status-failed {
  border-color: #f5cccc;
  background: #fff5f5;
}

.subtopic-status-icon {
  font-size: 14px;
  margin-top: 2px;
  width: 16px;
  text-align: center;
}

.subtopic-body {
  flex: 1;
  font-size: 13px;
}

.subtopic-topic {
  font-weight: 600;
}

.subtopic-questions {
  display: flex;
  flex-direction: column;
  color: #666;
  font-size: 12px;
  margin-top: 4px;
}

.subtopic-error {
  color: #c00;
  font-size: 12px;
  margin-top: 4px;
}

.subtopic-runner {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: #999;
  text-transform: uppercase;
}

.action-row {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.cancel-btn {
  background: transparent;
  color: #c00;
  border: 1px solid #c00;
  padding: 8px 16px;
  font-family: inherit;
  font-size: 13px;
  cursor: pointer;
  border-radius: 4px;
}
</style>
