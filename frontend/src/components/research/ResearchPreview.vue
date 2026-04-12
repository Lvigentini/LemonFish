<template>
  <div class="research-preview">
    <h2 class="preview-title">{{ $t('research.previewTitle') }}</h2>
    <p class="preview-desc">{{ $t('research.previewDesc') }}</p>

    <div class="metadata">
      <span class="meta-pill">{{ $t('research.charsCount', { n: compiledLength }) }}</span>
      <span class="meta-pill">{{ $t('research.subTopicsCount', { n: subTopicsCount }) }}</span>
      <span class="meta-pill">{{ $t('research.citationsCount', { n: citations.length }) }}</span>
    </div>

    <div class="compiled-doc">
      <pre>{{ compiledText }}</pre>
    </div>

    <div v-if="citations.length" class="citations">
      <h4>{{ $t('research.citations') }}</h4>
      <ol>
        <li v-for="(url, i) in citations" :key="i">
          <a :href="url" target="_blank" rel="noopener">{{ url }}</a>
        </li>
      </ol>
    </div>

    <div class="action-row">
      <button class="primary-btn" type="button" @click="$emit('promote')">
        {{ $t('research.promote') }}
      </button>
      <button class="secondary-btn" type="button" @click="$emit('start-over')">
        {{ $t('research.startOver') }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  compiledText: { type: String, default: '' },
  citations: { type: Array, default: () => [] },
  subTopics: { type: Array, default: () => [] },
})

defineEmits(['promote', 'start-over'])

const compiledLength = computed(() => props.compiledText.length)
const subTopicsCount = computed(() => props.subTopics.length)
</script>

<style scoped>
.research-preview {
  max-width: 900px;
  margin: 0 auto;
  padding: 32px;
  background: #ffffff;
  border: 1px solid #e5e5e5;
  border-radius: 4px;
}

.preview-title {
  font-family: 'Space Grotesk', sans-serif;
  font-size: 24px;
  margin: 0 0 8px;
}

.preview-desc {
  color: #666;
  margin: 0 0 16px;
  font-size: 14px;
}

.metadata {
  display: flex;
  gap: 8px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.meta-pill {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  text-transform: uppercase;
  color: #ff4500;
  border: 1px solid #ff4500;
  padding: 3px 8px;
  border-radius: 999px;
}

.compiled-doc {
  background: #fafafa;
  border: 1px solid #e5e5e5;
  border-radius: 4px;
  max-height: 400px;
  overflow-y: auto;
  padding: 16px;
  margin-bottom: 20px;
}

.compiled-doc pre {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  line-height: 1.6;
  margin: 0;
}

.citations {
  margin-bottom: 20px;
}

.citations h4 {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  text-transform: uppercase;
  color: #666;
  margin: 0 0 8px;
}

.citations ol {
  font-size: 12px;
  padding-left: 24px;
}

.citations a {
  color: #ff4500;
  text-decoration: none;
  word-break: break-all;
}

.citations a:hover {
  text-decoration: underline;
}

.action-row {
  display: flex;
  gap: 12px;
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
