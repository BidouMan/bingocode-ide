<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import MainLayout from './components/layout/MainLayout.vue'
import LoadingScreen from './components/loading/LoadingScreen.vue'

const loadingProgress = ref(0)
const showLoading = ref(true)
const showMain = ref(false)

onMounted(async () => {
  try {
    // 模拟真实加载过程
    // 1. 初始化项目
    loadingProgress.value = 10
    await invoke('init_default_project')
    
    // 2. 加载主题
    loadingProgress.value = 30
    await new Promise(resolve => setTimeout(resolve, 300))
    
    // 3. 加载资源
    loadingProgress.value = 60
    await new Promise(resolve => setTimeout(resolve, 400))
    
    // 4. 准备编辑器
    loadingProgress.value = 90
    await new Promise(resolve => setTimeout(resolve, 200))
    
    // 5. 完成
    loadingProgress.value = 100
  } catch (e) {
    console.error('Loading failed:', e)
    loadingProgress.value = 100
  }
})

function onLoadingComplete() {
  showLoading.value = false
  showMain.value = true
}

// 开发模式：手动触发Loading效果
if (import.meta.env.DEV) {
  (window as any).triggerLoading = () => {
    showLoading.value = true
    showMain.value = false
    loadingProgress.value = 0
    
    const interval = setInterval(() => {
      if (loadingProgress.value < 100) {
        loadingProgress.value += Math.random() * 15 + 5
        if (loadingProgress.value > 100) {
          loadingProgress.value = 100
        }
      } else {
        clearInterval(interval)
      }
    }, 200)
  }
}
</script>

<template>
  <LoadingScreen 
    :progress="loadingProgress" 
    :show="showLoading"
    @complete="onLoadingComplete"
  />
  <MainLayout v-if="showMain" />
</template>