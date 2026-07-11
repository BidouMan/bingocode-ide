<script setup lang="ts">
import { onMounted } from 'vue'
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow'
import MainLayout from './components/layout/MainLayout.vue'

onMounted(() => {
  // 页面完全加载后显示窗口，隐藏白屏
  const win = getCurrentWebviewWindow()
  win.show()
  win.setFocus()
})
</script>

<template>
  <MainLayout />
</template>
