<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { open } from '@tauri-apps/plugin-shell'
import { useUpdater } from '../../composables/useUpdater'

const emit = defineEmits<{
  close: []
}>()

const {
  updateInfo,
  downloadProgress,
  isDownloading,
  installPhase,
  downloadAndInstall,
} = useUpdater()

const showDialog = ref(false)
const dialogMode = ref<'update' | 'none' | 'error' | 'download-error' | 'install-done'>('update')
const errorMessage = ref('')
const isLatestHint = ref(false) // 已是最新版时点击立即更新的提示
const skippedVersion = localStorage.getItem('skippedVersion')
const RELEASE_PAGE = 'https://github.com/BidouMan/bingocode-ide/releases/latest'

// 手动下载兜底：按平台拼安装包直链（走 ghfast 国内加速代理）
const manualDownloadUrl = computed(() => {
  const ver = (updateInfo.value?.version || '').replace(/^v/, '')
  const isMac = (navigator.platform || navigator.userAgent).toLowerCase().includes('mac')
  const file = isMac ? `BingoCode_${ver}_aarch64.dmg` : `BingoCode_${ver}_x64-setup.exe`
  return `https://ghfast.top/https://github.com/BidouMan/bingocode-ide/releases/download/v${ver}/${file}`
})

// 解析 latest.json 返回的用户向更新说明（CHANGELOG_USER.md 格式：### 分组 / - 条目）
type NoteLine = { type: 'title' | 'bullet' | 'text'; text: string }
const parsedNotes = computed<NoteLine[]>(() => {
  const raw = updateInfo.value?.notes?.trim()
  if (!raw) return []
  const lines = raw.split('\n')
  const result: NoteLine[] = []
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue
    if (trimmed.startsWith('### ')) {
      result.push({ type: 'title', text: trimmed.slice(4) })
    } else if (trimmed.startsWith('- ')) {
      result.push({ type: 'bullet', text: trimmed.slice(2) })
    } else {
      result.push({ type: 'text', text: trimmed })
    }
  }
  return result
})

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

function handleUpdateNone(event: Event) {
  const customEvent = event as CustomEvent
  const detail = customEvent.detail || {}
  updateInfo.value = {
    version: detail.version || '未知',
    notes: detail.notes || '',
  }
  isLatestHint.value = false
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
  isLatestHint.value = false
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
    // relaunch 成功时进程已退出走不到这里；能走到说明重启被系统拒绝
    dialogMode.value = 'install-done'
  } catch (e) {
    // 安装已完成只是重启失败时，提示手动重启而不是报下载错误
    if (installPhase.value === 'done') {
      dialogMode.value = 'install-done'
    } else {
      dialogMode.value = 'download-error'
    }
    console.error('更新失败:', e)
  }
}

function retryUpdate() {
  dialogMode.value = 'update'
}

function handleLatestClick() {
  isLatestHint.value = true
}

async function openManualDownload() {
  try {
    await open(manualDownloadUrl.value)
  } catch {
    try { await open(RELEASE_PAGE) } catch { /* ignore */ }
  }
}

async function openReleasePage() {
  try {
    await open(RELEASE_PAGE)
  } catch { /* ignore */ }
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
            <div class="update-notes" v-if="parsedNotes.length > 0">
              <template v-for="(item, index) in parsedNotes" :key="index">
                <div v-if="item.type === 'title'" class="update-note-title">{{ item.text }}</div>
                <div v-else-if="item.type === 'bullet'" class="update-note-item">{{ item.text }}</div>
                <div v-else class="update-note-text">{{ item.text }}</div>
              </template>
            </div>
            <div v-else class="update-note-item">本次更新包含新功能、问题修复和体验改进，欢迎更新体验！</div>
            <button class="update-link" @click="openReleasePage">查看完整更新日志 →</button>
          </div>
          <div v-if="isDownloading" class="update-progress-wrapper">
            <div class="update-progress">
              <div class="update-progress-bar" :style="{ width: `${downloadProgress}%` }" />
              <span class="update-progress-text">{{ downloadProgress }}%</span>
            </div>
          </div>
          <div v-else-if="installPhase === 'installing'" class="update-progress-wrapper">
            <div class="update-status">安装更新中…</div>
          </div>
          <div v-else-if="installPhase === 'done'" class="update-progress-wrapper">
            <div class="update-status update-status-done">更新完成，正在重启应用…</div>
          </div>
          <div v-if="installPhase === 'idle'" class="update-footer">
            <button class="update-btn update-btn-skip" @click="skipVersion">跳过此版本</button>
            <div class="update-footer-right">
              <button class="update-btn update-btn-later" @click="closeDialog">稍后再说</button>
              <button
                class="update-btn update-btn-install"
                :disabled="isDownloading"
                @click="handleUpdate"
              >
                立即更新
              </button>
            </div>
          </div>
        </template>

        <!-- 无更新（已是最新版，仍展示当前版本的更新内容） -->
        <template v-else-if="dialogMode === 'none'">
          <div class="update-header">
            <span class="update-title">最新版本</span>
            <button class="update-close" @click="closeDialog">×</button>
          </div>
          <div class="update-body">
            <div class="update-version">Version {{ updateInfo?.version }}</div>
            <div class="update-notes" v-if="parsedNotes.length > 0">
              <template v-for="(item, index) in parsedNotes" :key="index">
                <div v-if="item.type === 'title'" class="update-note-title">{{ item.text }}</div>
                <div v-else-if="item.type === 'bullet'" class="update-note-item">{{ item.text }}</div>
                <div v-else class="update-note-text">{{ item.text }}</div>
              </template>
            </div>
            <div v-else class="update-note-item">暂无更新说明</div>
            <button class="update-link" @click="openReleasePage">查看完整更新日志 →</button>
          </div>
          <div v-if="isLatestHint" class="update-progress-wrapper">
            <div class="update-status update-status-done">当前已是最新版本</div>
          </div>
          <div v-else class="update-footer">
            <button class="update-btn update-btn-skip" @click="closeDialog">关闭</button>
            <div class="update-footer-right">
              <button class="update-btn update-btn-install" @click="handleLatestClick">立即更新</button>
            </div>
          </div>
        </template>

        <!-- 下载失败 -->
        <template v-else-if="dialogMode === 'download-error'">
          <div class="update-header">
            <span class="update-title">更新下载失败</span>
            <button class="update-close" @click="closeDialog">×</button>
          </div>
          <div class="update-body">
            <div class="update-message update-message-error">下载中断了，可能是网络不稳定</div>
            <div class="update-hint">可重试自动更新，或手动下载安装包覆盖安装</div>
          </div>
          <div class="update-footer update-footer-center">
            <button class="update-btn update-btn-later" @click="openManualDownload">手动下载</button>
            <button class="update-btn update-btn-later" @click="openReleasePage">下载页</button>
            <button class="update-btn update-btn-install" @click="retryUpdate">重试</button>
          </div>
        </template>

        <!-- 安装完成但重启失败 -->
        <template v-else-if="dialogMode === 'install-done'">
          <div class="update-header">
            <span class="update-title">更新完成</span>
            <button class="update-close" @click="closeDialog">×</button>
          </div>
          <div class="update-body">
            <div class="update-message">新版本已安装，但自动重启未成功</div>
            <div class="update-hint">请手动退出应用后重新打开</div>
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
  width: 640px;
  max-height: 65vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
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
  overflow-y: auto;
  flex: 1;
  min-height: 0;
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

.update-note-title {
  font-size: 12px;
  font-weight: 600;
  color: #c0caf5;
  margin-top: 10px;
  margin-bottom: 4px;
}

.update-note-title:first-child {
  margin-top: 0;
}

.update-note-item {
  padding: 2px 0 2px 14px;
  position: relative;
}

.update-note-item::before {
  content: '•';
  color: #565f89;
  position: absolute;
  left: 0;
}

.update-note-text {
  padding: 2px 0;
  color: #a9b1d6;
}

.update-link {
  display: block;
  margin-top: 12px;
  padding: 0;
  background: none;
  border: none;
  color: #7aa2f7;
  font-size: 12px;
  cursor: pointer;
  text-align: left;
}

.update-link:hover {
  color: #89b4fa;
  text-decoration: underline;
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

.update-hint {
  font-size: 12px;
  color: #565f89;
  text-align: center;
  padding-bottom: 8px;
}

.update-progress-wrapper {
  padding: 0 14px 8px;
  flex-shrink: 0;
}

.update-status {
  font-size: 12px;
  color: #a9b1d6;
  text-align: center;
  padding: 4px 0;
}

.update-status-done {
  color: #5BFB84;
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
  flex-shrink: 0;
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
