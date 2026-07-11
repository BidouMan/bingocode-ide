<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { invoke } from '@tauri-apps/api/core'

const emit = defineEmits<{ 'close': [] }>()

// ─── 内置包：引擎运行 + IDE 功能依赖，普通模式下不显示 ───
const BUILTIN_PACKAGES = new Set([
  // 引擎核心
  'pillow', 'numpy',
  // 包管理
  'pip', 'setuptools', 'wheel',
  // 代码格式化 (black)
  'black', 'click', 'mypy_extensions', 'pathspec',
  // 代码检查 (pyflakes)
  'pyflakes',
  // 其他内置依赖
  'packaging', 'platformdirs', 'pytokens', 'tomli', 'typing_extensions',
])

function isBuiltin(name: string): boolean {
  return BUILTIN_PACKAGES.has(name.toLowerCase())
}

// ─── 状态 ───
const activeTab = ref<'installed' | 'search'>('installed')
const searchQuery = ref('')
const installedPackages = ref<{ name: string; version: string }[]>([])
const outdatedPackages = ref<{ name: string; current_version: string; latest_version: string }[]>([])
const searchResults = ref<{ name: string; version: string; summary: string }[]>([])
const availableVersions = ref<string[]>([])
const selectedVersion = ref('')
const isLoading = ref(false)
const loadingMessage = ref('')
const errorMessage = ref('')
const successMessage = ref('')
const mirrorIndex = ref(0)
const advancedMode = ref(false)
const confirmDialog = ref<{ visible: boolean; message: string; onConfirm: () => void }>({ visible: false, message: '', onConfirm: () => {} })

// 快速查找：某包是否有可更新版本
function getLatestVersion(name: string): string | null {
  const found = outdatedPackages.value.find(p => p.name === name)
  return found ? found.latest_version : null
}

const MIRRORS = [
  { label: '清华镜像 (推荐)', url: 'https://pypi.tuna.tsinghua.edu.cn/simple' },
  { label: '阿里云镜像', url: 'https://mirrors.aliyun.com/pypi/simple/' },
  { label: '官方源', url: 'https://pypi.org/simple' },
]

const currentMirror = computed(() => MIRRORS[mirrorIndex.value].url)

// 过滤后的列表：普通模式隐藏内置包
const displayPackages = computed(() => {
  if (advancedMode.value) return installedPackages.value
  return installedPackages.value.filter(p => !isBuiltin(p.name))
})

function showConfirm(message: string, onConfirm: () => void) {
  confirmDialog.value = { visible: true, message, onConfirm }
}
function closeConfirm() { confirmDialog.value.visible = false }
function executeConfirm() {
  confirmDialog.value.onConfirm()
  confirmDialog.value.visible = false
}

// ─── 已安装列表 ───
async function loadInstalled() {
  isLoading.value = true
  loadingMessage.value = '正在加载已安装的包...'
  errorMessage.value = ''
  try {
    installedPackages.value = await invoke('pip_list_installed')
    if (advancedMode.value) {
      await checkOutdated()
    }
  } catch (e: any) {
    errorMessage.value = e || '加载失败'
  } finally {
    isLoading.value = false
  }
}

// ─── 检查可更新的包（高级模式） ───
async function checkOutdated() {
  try {
    outdatedPackages.value = await invoke('pip_check_outdated')
  } catch {
    outdatedPackages.value = []
  }
}

// ─── 升级单个包（高级模式） ───
function upgradePackage(name: string, latestVersion: string) {
  showConfirm(`将 "${name}" 从 ${outdatedPackages.value.find(p => p.name === name)?.current_version || '?'} 升级到 ${latestVersion}？`, async () => {
    isLoading.value = true
    loadingMessage.value = `正在升级 ${name}...`
    errorMessage.value = ''
    successMessage.value = ''
    try {
      await invoke('pip_upgrade_package', {
        package: name,
        mirror: currentMirror.value,
      })
      successMessage.value = `${name} 已升级到 ${latestVersion}`
      await loadInstalled()
    } catch (e: any) {
      errorMessage.value = e || '升级失败'
    } finally {
      isLoading.value = false
    }
  })
}

// ─── 全部更新（高级模式） ───
function upgradeAll() {
  const count = outdatedPackages.value.length
  if (count === 0) return
  showConfirm(`确定要升级全部 ${count} 个包吗？`, async () => {
    isLoading.value = true
    loadingMessage.value = `正在升级全部包...`
    errorMessage.value = ''
    successMessage.value = ''
    try {
      await invoke('pip_upgrade_package', {
        package: 'pip setuptools wheel pillow numpy black pyflakes',
        mirror: currentMirror.value,
      })
      successMessage.value = '升级完成'
      await loadInstalled()
    } catch (e: any) {
      errorMessage.value = e || '升级失败'
    } finally {
      isLoading.value = false
    }
  })
}

// ─── 搜索 ───
let searchTimer: ReturnType<typeof setTimeout> | null = null

function onSearchInput() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => doSearch(), 500)
}

async function doSearch() {
  const q = searchQuery.value.trim()
  if (!q) { searchResults.value = []; return }
  isLoading.value = true
  loadingMessage.value = `正在搜索 "${q}"...`
  errorMessage.value = ''
  searchResults.value = []
  try {
    const versions = await invoke<string[]>('pip_get_versions', { package: q })
    if (versions.length > 0) {
      let summary = ''
      try {
        const resp = await fetch(`https://pypi.org/pypi/${q}/json`)
        if (resp.ok) {
          const data = await resp.json()
          summary = data.info?.summary || ''
        }
      } catch {}
      searchResults.value = [{ name: q, version: versions[0], summary }]
    } else {
      errorMessage.value = `未找到 "${q}"，请检查包名是否正确`
    }
  } catch (e: any) {
    errorMessage.value = e || '搜索失败'
  } finally {
    isLoading.value = false
  }
}

// ─── 安装 ───
async function installPackage(name: string) {
  isLoading.value = true
  loadingMessage.value = `正在安装 ${name}...`
  errorMessage.value = ''
  successMessage.value = ''
  try {
    await invoke('pip_install_package', {
      package: name,
      version: selectedVersion.value || null,
      mirror: currentMirror.value,
    })
    successMessage.value = `${name} 安装成功`
    selectedVersion.value = ''
    await loadInstalled()
  } catch (e: any) {
    errorMessage.value = e || '安装失败'
  } finally {
    isLoading.value = false
  }
}

// ─── 卸载 ───
function uninstallPackage(name: string) {
  const isBuiltin = BUILTIN_PACKAGES.has(name.toLowerCase())
  const warning = isBuiltin ? `"${name}" 是 IDE 内置包，卸载可能影响编辑器功能。\n` : ''
  showConfirm(`${warning}确定要卸载 "${name}" 吗？`, async () => {
    isLoading.value = true
    loadingMessage.value = `正在卸载 ${name}...`
    errorMessage.value = ''
    successMessage.value = ''
    try {
      await invoke('pip_uninstall_package', { package: name })
      successMessage.value = `${name} 已卸载`
      await loadInstalled()
    } catch (e: any) {
      errorMessage.value = e || '卸载失败'
    } finally {
      isLoading.value = false
    }
  })
}

// ─── 查看版本 ───
async function showVersions(name: string) {
  try {
    availableVersions.value = await invoke('pip_get_versions', { package: name })
  } catch {
    availableVersions.value = []
  }
}

onMounted(() => { loadInstalled() })

// 切换高级模式时自动检查更新
watch(advancedMode, async (val) => {
  if (val && outdatedPackages.value.length === 0) {
    isLoading.value = true
    loadingMessage.value = '正在检查可用更新...'
    await checkOutdated()
    isLoading.value = false
  }
})
</script>

<template>
  <div class="plugin-overlay" @click.self="emit('close')">
    <div class="plugin-dialog">
      <!-- 标题栏 -->
      <div class="plugin-header">
        <span class="plugin-title">插件库</span>
        <span class="plugin-subtitle">Python 包管理</span>
        <div class="plugin-spacer" />
        <button
          class="plugin-adv-toggle"
          :class="{ 'plugin-adv-active': advancedMode }"
          @click="advancedMode = !advancedMode"
          v-tooltip="advancedMode ? '关闭高级模式' : '显示内置包'"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
          高级
        </button>
        <button class="plugin-close" @click="emit('close')">×</button>
      </div>

      <!-- 搜索栏 -->
      <div class="plugin-search-bar">
        <input
          v-model="searchQuery"
          class="plugin-search-input"
          placeholder="搜索 Python 包..."
          @input="onSearchInput"
          @keydown.enter="doSearch"
        />
        <button class="plugin-btn plugin-btn-search" @click="doSearch">搜索</button>
      </div>

      <!-- 镜像源选择 -->
      <div class="plugin-mirror-bar">
        <span class="plugin-mirror-label">镜像源:</span>
        <select v-model="mirrorIndex" class="plugin-mirror-select">
          <option v-for="(m, i) in MIRRORS" :key="i" :value="i">{{ m.label }}</option>
        </select>
        <div class="plugin-spacer" />
        <button class="plugin-btn-icon" @click="loadInstalled" v-tooltip="'刷新'">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="23 4 23 10 17 10" />
            <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
          </svg>
        </button>
      </div>

      <!-- Tab 栏 -->
      <div class="plugin-tabs">
        <button
          class="plugin-tab"
          :class="{ 'plugin-tab-active': activeTab === 'installed' }"
          @click="activeTab = 'installed'"
        >
          已安装
          <span class="plugin-tab-count">{{ displayPackages.length }}</span>
        </button>
        <button
          class="plugin-tab"
          :class="{ 'plugin-tab-active': activeTab === 'search' }"
          @click="activeTab = 'search'"
        >
          搜索结果
        </button>
      </div>

      <!-- 高级模式提示 -->
      <div v-if="advancedMode" class="plugin-msg plugin-msg-warn">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
          <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
        </svg>
        高级模式：显示内置包，可检查更新，误操作可能影响 IDE 功能
        <button
          v-if="outdatedPackages.length > 0"
          class="plugin-btn plugin-btn-sm plugin-btn-upgrade-all"
          @click="upgradeAll"
        >
          全部更新 ({{ outdatedPackages.length }})
        </button>
      </div>

      <!-- 消息提示 -->
      <div v-if="errorMessage" class="plugin-msg plugin-msg-error">
        <span>{{ errorMessage }}</span>
        <button class="plugin-msg-close" @click="errorMessage = ''">×</button>
      </div>
      <div v-if="successMessage" class="plugin-msg plugin-msg-success">
        <span>{{ successMessage }}</span>
        <button class="plugin-msg-close" @click="successMessage = ''">×</button>
      </div>

      <!-- 内容区 -->
      <div class="plugin-content">
        <div v-if="isLoading" class="plugin-loading">
          <div class="plugin-spinner" />
          <span>{{ loadingMessage }}</span>
        </div>

        <!-- 已安装列表 -->
        <template v-else-if="activeTab === 'installed'">
          <div v-if="displayPackages.length === 0" class="plugin-empty">
            {{ advancedMode ? '暂未安装任何包' : '暂未安装额外的包' }}
          </div>
          <div v-else class="plugin-list">
            <div
              v-for="pkg in displayPackages"
              :key="pkg.name"
              class="plugin-item"
            >
              <div class="plugin-item-info">
                <span class="plugin-item-name">{{ pkg.name }}</span>
                <span class="plugin-item-version">{{ pkg.version }}</span>
                <template v-if="advancedMode">
                  <span v-if="isBuiltin(pkg.name)" class="plugin-item-badge" title="IDE 内置包">内置</span>
                  <span v-else-if="getLatestVersion(pkg.name)" class="plugin-item-badge plugin-item-badge-update" :title="`可更新到 ${getLatestVersion(pkg.name)}`">
                    {{ getLatestVersion(pkg.name) }}
                  </span>
                </template>
              </div>
              <div class="plugin-item-actions">
                <!-- 更新按钮 -->
                <button
                  v-if="advancedMode && getLatestVersion(pkg.name)"
                  class="plugin-btn plugin-btn-sm plugin-btn-upgrade"
                  @click="upgradePackage(pkg.name, getLatestVersion(pkg.name)!)"
                >
                  更新
                </button>
                <!-- 删除按钮 -->
                <button
                  v-if="!isBuiltin(pkg.name)"
                  class="plugin-btn plugin-btn-sm plugin-btn-danger"
                  @click="uninstallPackage(pkg.name)"
                >
                  删除
                </button>
                <template v-else-if="advancedMode">
                  <button
                    class="plugin-btn plugin-btn-sm plugin-btn-danger"
                    @click="uninstallPackage(pkg.name)"
                  >
                    删除
                  </button>
                </template>
              </div>
            </div>
          </div>
        </template>

        <!-- 搜索结果 -->
        <template v-else-if="activeTab === 'search'">
          <div v-if="searchResults.length === 0 && !isLoading" class="plugin-empty">
            输入包名进行搜索
          </div>
          <div v-else class="plugin-list">
            <div
              v-for="pkg in searchResults"
              :key="pkg.name"
              class="plugin-item"
            >
              <div class="plugin-item-info">
                <span class="plugin-item-name">{{ pkg.name }}</span>
                <span class="plugin-item-version">{{ pkg.version }}</span>
                <span v-if="pkg.summary" class="plugin-item-desc">{{ pkg.summary }}</span>
                <span v-if="isBuiltin(pkg.name)" class="plugin-item-badge" title="已内置">已安装</span>
              </div>
              <div class="plugin-item-actions">
                <select
                  v-if="availableVersions.length > 0 && pkg.name === searchQuery.trim()"
                  v-model="selectedVersion"
                  class="plugin-version-select"
                >
                  <option value="">最新版本</option>
                  <option v-for="v in availableVersions.slice(0, 30)" :key="v" :value="v">{{ v }}</option>
                </select>
                <button
                  v-if="availableVersions.length === 0 || pkg.name !== searchQuery.trim()"
                  class="plugin-btn plugin-btn-sm plugin-btn-secondary"
                  @click="showVersions(pkg.name)"
                >
                  选择版本
                </button>
                <button
                  class="plugin-btn plugin-btn-sm plugin-btn-install"
                  @click="installPackage(pkg.name)"
                >
                  安装
                </button>
              </div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- 确认弹窗 -->
    <Teleport to="body">
      <div v-if="confirmDialog.visible" class="plugin-confirm-overlay" @click.self="closeConfirm">
        <div class="plugin-confirm-box">
          <div class="plugin-confirm-msg" style="white-space: pre-line;">{{ confirmDialog.message }}</div>
          <div class="plugin-confirm-actions">
            <button class="plugin-btn plugin-btn-sm" @click="closeConfirm">取消</button>
            <button class="plugin-btn plugin-btn-sm plugin-btn-danger" @click="executeConfirm">确定</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.plugin-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
}

.plugin-dialog {
  background: var(--bg-root);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  width: 560px;
  max-height: 70vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
  overflow: hidden;
}

/* 标题栏 */
.plugin-header {
  display: flex;
  align-items: center;
  padding: 14px 16px 10px;
  gap: 8px;
}
.plugin-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}
.plugin-subtitle {
  font-size: 12px;
  color: var(--text-muted);
}
.plugin-spacer { flex: 1; }
.plugin-close {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 18px;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.plugin-close:hover { background: var(--bg-hover); color: var(--text); }

/* 高级模式按钮 */
.plugin-adv-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  height: 26px;
  padding: 0 8px;
  border: 1px solid var(--border-light);
  border-radius: 4px;
  background: transparent;
  color: var(--text-muted);
  font-size: 11px;
  cursor: pointer;
  transition: all 0.15s;
}
.plugin-adv-toggle:hover {
  color: var(--text-secondary);
  border-color: var(--text-muted);
}
.plugin-adv-active {
  color: #e8a838;
  border-color: #e8a838;
  background: rgba(232, 168, 56, 0.08);
}
.plugin-adv-active:hover {
  color: #e8a838;
}

/* 搜索栏 */
.plugin-search-bar {
  display: flex;
  padding: 0 16px 8px;
  gap: 8px;
}
.plugin-search-input {
  flex: 1;
  height: 32px;
  background: var(--bg-base);
  border: 1px solid var(--border-light);
  border-radius: 6px;
  color: var(--text);
  padding: 0 10px;
  font-size: 13px;
  outline: none;
}
.plugin-search-input:focus { border-color: var(--accent); }
.plugin-search-input::placeholder { color: var(--text-muted); }

/* 按钮 */
.plugin-btn {
  height: 30px;
  padding: 0 12px;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--bg-base);
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
}
.plugin-btn:hover { background: var(--bg-hover); color: var(--text); }
.plugin-btn-sm {
  height: 26px;
  padding: 0 10px;
  font-size: 11px;
}
.plugin-btn-search {
  background: var(--accent);
  border-color: var(--accent);
  color: #1a1a1a;
  font-weight: 500;
}
.plugin-btn-search:hover {
  background: var(--accent-hover);
  border-color: var(--accent-hover);
}
.plugin-btn-install {
  background: var(--accent);
  border-color: var(--accent);
  color: #1a1a1a;
  font-weight: 500;
}
.plugin-btn-install:hover {
  background: var(--accent-hover);
  border-color: var(--accent-hover);
}
.plugin-btn-danger {
  color: var(--danger);
  border-color: var(--danger);
}
.plugin-btn-danger:hover {
  background: var(--danger);
  color: white;
}
.plugin-btn-secondary {
  color: var(--text-secondary);
}
.plugin-btn-icon {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.plugin-btn-icon:hover { background: var(--bg-hover); color: var(--text); }

/* 镜像源 */
.plugin-mirror-bar {
  display: flex;
  align-items: center;
  padding: 0 16px 8px;
  gap: 6px;
}
.plugin-mirror-label {
  font-size: 12px;
  color: var(--text-muted);
}
.plugin-mirror-select {
  height: 26px;
  background: var(--bg-base);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: var(--text-secondary);
  padding: 0 8px;
  font-size: 11px;
  outline: none;
  cursor: pointer;
}
.plugin-mirror-select:focus { border-color: var(--accent); }

/* Tab 栏 */
.plugin-tabs {
  display: flex;
  border-bottom: 1px solid var(--border-light);
  padding: 0 16px;
}
.plugin-tab {
  padding: 8px 14px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  font-size: 13px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.15s;
}
.plugin-tab:hover { color: var(--text-secondary); }
.plugin-tab-active {
  color: var(--accent);
  border-bottom-color: var(--accent);
}
.plugin-tab-count {
  font-size: 11px;
  background: var(--bg-hover);
  border-radius: 10px;
  padding: 0 6px;
  margin-left: 4px;
  color: var(--text-muted);
}

/* 消息 */
.plugin-msg {
  display: flex;
  align-items: center;
  padding: 8px 16px;
  font-size: 12px;
  gap: 8px;
}
.plugin-msg-error {
  background: rgba(220, 53, 69, 0.12);
  color: #ff6b6b;
}
.plugin-msg-success {
  background: rgba(40, 167, 69, 0.12);
  color: var(--accent);
}
.plugin-msg-warn {
  background: rgba(232, 168, 56, 0.1);
  color: #e8a838;
}
.plugin-msg-close {
  margin-left: auto;
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-size: 14px;
  opacity: 0.7;
}
.plugin-msg-close:hover { opacity: 1; }

/* 内容区 */
.plugin-content {
  flex: 1;
  overflow-y: auto;
  min-height: 200px;
  max-height: 420px;
  padding: 8px 0;
}

/* 空状态 */
.plugin-empty {
  padding: 40px 16px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
}

/* 加载中 */
.plugin-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 40px 16px;
  color: var(--text-muted);
  font-size: 13px;
}
.plugin-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--border-light);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: plugin-spin 0.8s linear infinite;
}
@keyframes plugin-spin {
  to { transform: rotate(360deg); }
}

/* 包列表 */
.plugin-list {
  padding: 0 16px;
}
.plugin-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 6px;
  border: 1px solid transparent;
  transition: background 0.12s;
}
.plugin-item:hover {
  background: var(--bg-hover);
}
.plugin-item-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  min-width: 0;
}
.plugin-item-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text);
}
.plugin-item-version {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-base);
  border-radius: 4px;
  padding: 1px 6px;
}
.plugin-item-desc {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 260px;
}
.plugin-item-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

/* 内置包标记 */
.plugin-item-badge {
  font-size: 10px;
  color: #e8a838;
  background: rgba(232, 168, 56, 0.12);
  border: 1px solid rgba(232, 168, 56, 0.3);
  border-radius: 4px;
  padding: 0 5px;
  line-height: 18px;
}
.plugin-item-badge-update {
  color: var(--accent);
  background: rgba(91, 251, 132, 0.1);
  border-color: rgba(91, 251, 132, 0.3);
}

/* 更新按钮 */
.plugin-btn-upgrade {
  color: var(--accent);
  border-color: var(--accent);
}
.plugin-btn-upgrade:hover {
  background: var(--accent);
  color: #1a1a1a;
}
.plugin-btn-upgrade-all {
  margin-left: auto;
  color: var(--accent);
  border-color: var(--accent);
  height: 22px;
  font-size: 11px;
  padding: 0 8px;
}
.plugin-btn-upgrade-all:hover {
  background: var(--accent);
  color: #1a1a1a;
}

/* 版本选择下拉 */
.plugin-version-select {
  height: 26px;
  background: var(--bg-base);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: var(--text-secondary);
  padding: 0 6px;
  font-size: 11px;
  outline: none;
  cursor: pointer;
  max-width: 120px;
}
.plugin-version-select:focus { border-color: var(--accent); }

/* 滚动条 */
.plugin-content::-webkit-scrollbar { width: 6px; }
.plugin-content::-webkit-scrollbar-track { background: transparent; }
.plugin-content::-webkit-scrollbar-thumb { background: var(--border-light); border-radius: 3px; }
.plugin-content::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

/* 确认弹窗 */
.plugin-confirm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10001;
}
.plugin-confirm-box {
  background: var(--bg-root);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 16px 20px;
  min-width: 300px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4);
}
.plugin-confirm-msg {
  font-size: 13px;
  color: var(--text);
  margin-bottom: 16px;
  line-height: 1.5;
}
.plugin-confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
