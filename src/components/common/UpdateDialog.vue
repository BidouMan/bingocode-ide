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
  downloadAndInstall,
} = useUpdater()

const showDialog = ref(false)
const dialogMode = ref<'update' | 'none' | 'error'>('update')
const errorMessage = ref('')
const skippedVersion = localStorage.getItem('skippedVersion')

// 更新日志接口 - 未来可从服务器获取
function getUpdateNotes(version: string): string[] {
  // TODO: 从服务器获取更新日志
  // 目前使用静态数据
  const notes: Record<string, string[]> = {
    // '0.6.0': ['新增应用自动更新功能', '优化控制台日志输出', '清理无用内置资源'],
  }
  return notes[version] || ['包含 bug 修复和性能优化']
}

// 处理手动检查更新事件
function handleUpdateAvailable(event: Event) {
  const customEvent = event as CustomEvent
  if (customEvent.detail) {
    const newVersion = customEvent.detail.version
    // 检查是否跳过了这个版本
    if (skippedVersion === newVersion) {
      return
    }
    updateInfo.value = {
      version: newVersion || '未知',
      notes: customEvent.detail.body || '',
    }
    dialogMode.value = 'update'
    showDialog.value = true
  }
}

function handleUpdateNone() {
  dialogMode.value = 'none'
  showDialog.value = true
}

function handleUpdateError(event: Event) {
  const customEvent = event as CustomEvent
  errorMessage.value = customEvent.detail?.message || '请检查网络连接后重试'
  dialogMode.value = 'error'
  showDialog.value = true
}

onMounted(() => {
  window.addEventListener('app-update-available', handleUpdateAvailable)
  window.addEventListener('app-update-none', handleUpdateNone)
  window.addEventListener('app-update-error', handleUpdateError)
})

onBeforeUnmount(() => {
  window.removeEventListener('app-update-available', handleUpdateAvailable)
  window.removeEventListener('app-update-none', handleUpdateNone)
  window.removeEventListener('app-update-error', handleUpdateError)
})

function closeDialog() {
  showDialog.value = false
  emit('close')
}

function skipVersion() {
  if (updateInfo.value?.version) {
    localStorage.setItem('skippedVersion', updateInfo.value.version)
  }
  closeDialog()
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
        <!-- 有更新 -->
        <template v-if="dialogMode === 'update'">
          <div class="update-header">
            <span class="update-title">发现新版本</span>
            <button class="update-close" @click="closeDialog">×</button>
          </div>
          <div class="update-body">
            <div class="update-version">Version {{ updateInfo?.version }}</div>
            <div class="update-notes">
              <template v-if="getUpdateNotes(updateInfo?.version || '').length > 0">
                <div v-for="(note, index) in getUpdateNotes(updateInfo?.version || '')" :key="index" class="update-note-item">
                  {{ note }}
                </div>
              </template>
              <template v-else>
                <div class="update-note-item">{{ updateInfo?.notes || '包含 bug 修复和性能优化' }}</div>
              </template>
            </div>
          </div>
          <div v-if="isDownloading" class="update-progress-wrapper">
            <div class="update-progress">
              <div class="update-progress-bar" :style="{ width: `${downloadProgress}%` }" />
              <span class="update-progress-text">{{ downloadProgress }}%</span>
            </div>
          </div>
          <div class="update-footer">
            <button class="update-btn update-btn-skip" @click="skipVersion">跳过此版本</button>
            <div class="update-footer-right">
              <button class="update-btn update-btn-later" @click="closeDialog">稍后再说</button>
              <button
                class="update-btn update-btn-install"
                :disabled="isDownloading"
                @click="handleUpdate"
              >
                {{ isDownloading ? '下载中...' : '立即更新' }}
              </button>
            </div>
          </div>
        </template>

        <!-- 无更新 -->
        <template v-else-if="dialogMode === 'none'">
          <div class="update-header">
            <span class="update-title">检查更新</span>
            <button class="update-close" @click="closeDialog">×</button>
          </div>
          <div class="update-body">
            <div class="update-message">当前已是最新版本</div>
          </div>
          <div class="update-footer update-footer-center">
            <button class="update-btn update-btn-later" @click="closeDialog">确定</button>
          </div>
        </template>

        <!-- 检查失败 -->
        <template v-else-if="dialogMode === 'error'">
          <div class="update-header">
            <span class="update-title">检查更新</span>
            <button class="update-close" @click="closeDialog">×</button>
          </div>
          <div class="update-body">
            <div class="update-message update-message-error">检查更新失败：{{ errorMessage }}</div>
          </div>
          <div class="update-footer update-footer-center">
            <button class="update-btn update-btn-later" @click="closeDialog">确定</button>
          </div>
        </template>
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
  width: 340px;
  overflow: hidden;
}

.update-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  border-bottom: 1px solid #3b4261;
}

.update-title {
  font-size: 13px;
  font-weight: 500;
  color: #c0caf5;
}

.update-close {
  background: none;
  border: none;
  color: #565f89;
  font-size: 18px;
  cursor: pointer;
  padding: 0;
  line-height: 1;
}

.update-close:hover {
  color: #c0caf5;
}

.update-body {
  padding: 16px 14px;
}

.update-version {
  font-size: 16px;
  font-weight: 500;
  color: #5BFB84;
  margin-bottom: 10px;
}

.update-notes {
  font-size: 12px;
  color: #a9b1d6;
  line-height: 1.6;
}

.update-note-item {
  padding: 2px 0;
}

.update-note-item::before {
  content: '•';
  color: #565f89;
  margin-right: 6px;
}

.update-message {
  font-size: 13px;
  color: #a9b1d6;
  text-align: center;
  padding: 10px 0;
}

.update-message-error {
  color: #f7768e;
}

.update-progress-wrapper {
  padding: 0 14px 8px;
}

.update-progress {
  height: 18px;
  background: #24283b;
  border-radius: 3px;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.update-progress-bar {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: rgba(91, 251, 132, 0.2);
  transition: width 0.3s;
}

.update-progress-text {
  position: relative;
  font-size: 11px;
  color: #5BFB84;
  font-weight: 500;
}

.update-footer {
  display: flex;
  gap: 6px;
  padding: 10px 14px;
  justify-content: space-between;
  align-items: center;
}

.update-footer-center {
  justify-content: center;
}

.update-footer-right {
  display: flex;
  gap: 6px;
}

.update-btn {
  padding: 5px 12px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  border: none;
  transition: all 0.2s;
}

.update-btn-skip {
  background: transparent;
  color: #565f89;
  padding-left: 0;
}

.update-btn-skip:hover {
  color: #a9b1d6;
}

.update-btn-later {
  background: #24283b;
  color: #a9b1d6;
}

.update-btn-later:hover {
  background: #3b4261;
}

.update-btn-install {
  background: #5BFB84;
  color: #1a1b26;
}

.update-btn-install:hover {
  background: #4BE074;
}

.update-btn-install:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
