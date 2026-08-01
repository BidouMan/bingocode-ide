<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useUpdater } from '../../composables/useUpdater'

const emit = defineEmits<{
  close: []
}>()

const {
  updateInfo,
  downloadProgress,
  isDownloading,
  checkForUpdates,
  downloadAndInstall,
} = useUpdater()

const showDialog = ref(false)

// 处理手动检查更新事件
function handleUpdateAvailable(event: Event) {
  const customEvent = event as CustomEvent
  if (customEvent.detail) {
    updateInfo.value = {
      version: customEvent.detail.version || '未知',
      notes: customEvent.detail.body || '无更新说明',
    }
    showDialog.value = true
  }
}

onMounted(() => {
  // 只监听手动检查更新事件，不自动检查
  window.addEventListener('app-update-available', handleUpdateAvailable)
})

onBeforeUnmount(() => {
  window.removeEventListener('app-update-available', handleUpdateAvailable)
})

function closeDialog() {
  showDialog.value = false
  emit('close')
}

async function handleUpdate() {
  try {
    await downloadAndInstall()
  } catch (e) {
    console.error('更新失败:', e)
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="showDialog" class="update-overlay" @click.self="closeDialog">
      <div class="update-dialog">
        <div class="update-header">
          <span class="update-title">发现新版本</span>
          <button class="update-close" @click="closeDialog">×</button>
        </div>
        <div class="update-body">
          <div class="update-version">v{{ updateInfo?.version }}</div>
          <div class="update-notes">{{ updateInfo?.notes || '包含 bug 修复和性能优化' }}</div>
        </div>
        <div class="update-footer">
          <button class="update-btn update-btn-later" @click="closeDialog">稍后再说</button>
          <button
            class="update-btn update-btn-install"
            :disabled="isDownloading"
            @click="handleUpdate"
          >
            {{ isDownloading ? `下载中 ${downloadProgress}%` : '立即更新' }}
          </button>
        </div>
        <div v-if="isDownloading" class="update-progress">
          <div class="update-progress-bar" :style="{ width: `${downloadProgress}%` }" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.update-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
}

.update-dialog {
  background: #1a1b26;
  border: 1px solid #3b4261;
  border-radius: 8px;
  width: 360px;
  overflow: hidden;
}

.update-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #3b4261;
}

.update-title {
  font-size: 14px;
  font-weight: 500;
  color: #c0caf5;
}

.update-close {
  background: none;
  border: none;
  color: #565f89;
  font-size: 20px;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.update-close:hover {
  color: #c0caf5;
}

.update-body {
  padding: 20px 16px;
}

.update-version {
  font-size: 24px;
  font-weight: 600;
  color: #7aa2f7;
  margin-bottom: 8px;
}

.update-notes {
  font-size: 13px;
  color: #a9b1d6;
  line-height: 1.5;
}

.update-footer {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  justify-content: flex-end;
}

.update-btn {
  padding: 6px 16px;
  border-radius: 4px;
  font-size: 13px;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}

.update-btn-later {
  background: #24283b;
  color: #a9b1d6;
}

.update-btn-later:hover {
  background: #3b4261;
}

.update-btn-install {
  background: #7aa2f7;
  color: #1a1b26;
}

.update-btn-install:hover {
  background: #89b4fa;
}

.update-btn-install:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.update-progress {
  height: 3px;
  background: #24283b;
}

.update-progress-bar {
  height: 100%;
  background: #7aa2f7;
  transition: width 0.3s;
}
</style>
