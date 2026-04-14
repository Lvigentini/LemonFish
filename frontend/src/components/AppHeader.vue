<template>
  <header class="app-global-header">
    <router-link to="/" class="brand">
      MIROFISH <span class="brand-suffix">[LEMONFISH]</span>
      <span class="version-pill">v{{ appVersion }}</span>
    </router-link>
    <div class="header-spacer"></div>
    <div class="header-actions">
      <LanguageSwitcher />
      <router-link to="/settings/llm" class="header-link" :title="$t('nav.llmSettings')">
        ⚙ {{ $t('nav.llmSettings') }}
      </router-link>
      <a
        href="https://github.com/Lvigentini/LemonFish"
        target="_blank"
        class="header-link"
      >
        GitHub ↗
      </a>
    </div>
  </header>
</template>

<script setup>
import LanguageSwitcher from './LanguageSwitcher.vue'

const appVersion = __APP_VERSION__
</script>

<style scoped>
.app-global-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 24px;
  background: #0f1115;
  border-bottom: 1px solid #23262d;
  font-family: 'JetBrains Mono', 'Space Grotesk', monospace;
  font-size: 13px;
  color: #e8ecf1;
  position: sticky;
  top: 0;
  z-index: 100;
}

.brand {
  text-decoration: none;
  color: #e8ecf1;
  font-weight: 700;
  letter-spacing: 0.04em;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.brand:hover { color: #fbbf24; }

.brand-suffix {
  font-weight: 500;
  font-size: 0.72em;
  color: #DAA520;
  letter-spacing: 0.5px;
}

.version-pill {
  font-weight: 500;
  font-size: 11px;
  color: #94a3b8;
  background: #1e293b;
  border: 1px solid #2f343d;
  padding: 2px 8px;
  border-radius: 10px;
  margin-left: 4px;
}

.header-spacer { flex: 1; }

.header-actions {
  display: flex;
  align-items: center;
  gap: 14px;
}

.header-link {
  color: #94a3b8;
  text-decoration: none;
  font-size: 12px;
  padding: 4px 8px;
  border-radius: 4px;
  transition: color 0.15s, background 0.15s;
}
.header-link:hover {
  color: #e8ecf1;
  background: #1e293b;
}
.router-link-active {
  color: #fbbf24;
}

/* LanguageSwitcher is styled for light backgrounds by default — invert it
   for the dark global header so the trigger and dropdown remain legible.
   :deep() reaches through scoped styles without modifying the component. */
.app-global-header :deep(.switcher-trigger) {
  background: transparent;
  color: #e8ecf1;
  border-color: #2f343d;
}
.app-global-header :deep(.switcher-trigger:hover) {
  border-color: #94a3b8;
  color: #ffffff;
}
.app-global-header :deep(.switcher-dropdown) {
  background: #161a22;
  border-color: #2f343d;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
}
.app-global-header :deep(.switcher-option) {
  color: #e8ecf1;
}
.app-global-header :deep(.switcher-option:hover) {
  background: #1e293b;
}
.app-global-header :deep(.switcher-option.active) {
  color: #fbbf24;
}
</style>
