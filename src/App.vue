<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow'
import MainLayout from './components/layout/MainLayout.vue'
import { waitForMonaco } from './utils/monaco-init'

// 是否已完成启动初始化（Monaco 加载 + 主布局挂载完成）
const bootReady = ref(false)

onMounted(async () => {
  try {
    // 等待 Monaco 加载完成。CodeEditor 一挂载就能直接创建编辑器，无 1.5 秒等待
    await waitForMonaco()
  } catch (e) {
    console.error('[Boot] Monaco load failed:', e)
  }
  // 无论如何都显示窗口（不被 Monaco 加载阻塞）
  bootReady.value = true
  const win = getCurrentWebviewWindow()
  await win.show()
  win.setFocus()
})
</script>

<template>
  <!-- 启动加载屏：Monaco 加载期间显示，加载完成后切换到主界面 -->
  <div v-if="!bootReady" class="boot-splash">
    <div class="boot-spinner" />
    <div class="boot-text">正在加载编辑器…</div>
  </div>
  <MainLayout v-show="bootReady" />
</template>

<style scoped>
.boot-splash {
  position: fixed;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  background: #1a1b26;
  color: #c0caf5;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  z-index: 9999;
}
.boot-spinner {
  width: 32px;
  height: 32px;
  border: 3px solid #3b4261;
  border-top-color: #7aa2f7;
  border-radius: 50%;
  animation: boot-spin 0.8s linear infinite;
}
.boot-text {
  font-size: 13px;
  color: #565f89;
  letter-spacing: 0.5px;
}
@keyframes boot-spin {
  to { transform: rotate(360deg); }
}
</style>
