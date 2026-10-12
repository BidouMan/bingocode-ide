import { ref } from 'vue'
import { check } from '@tauri-apps/plugin-updater'
import { relaunch } from '@tauri-apps/plugin-process'

export function useUpdater() {
  const isChecking = ref(false)
  const updateAvailable = ref(false)
  const updateInfo = ref<{ version: string; notes: string } | null>(null)
  const downloadProgress = ref(0)
  const isDownloading = ref(false)
  // 安装阶段：downloading 下载中 / installing 安装替换中 / done 安装完成待重启
  const installPhase = ref<'idle' | 'downloading' | 'installing' | 'done'>('idle')

  async function checkForUpdates() {
    if (isChecking.value) return

    isChecking.value = true
    try {
      const update = await check()
      if (update) {
        updateAvailable.value = true
        updateInfo.value = {
          version: update.version || '未知',
          notes: update.body || '无更新说明',
        }
        return update
      }
      updateAvailable.value = false
      updateInfo.value = null
      return null
    } catch (e: unknown) {
      const errorMsg = e instanceof Error ? e.message : String(e)
      console.error('[Updater] 检查更新失败:', errorMsg)
      updateInfo.value = {
        version: '',
        notes: errorMsg,
      }
      throw e
    } finally {
      isChecking.value = false
    }
  }

  async function downloadAndInstall() {
    const update = await check()
    if (!update) return

    isDownloading.value = true
    downloadProgress.value = 0
    installPhase.value = 'downloading'

    try {
      let downloaded = 0
      let contentLength = 0

      await update.downloadAndInstall((event) => {
        switch (event.event) {
          case 'Started':
            contentLength = event.data.contentLength || 0
            console.log(`[Updater] 开始下载，大小: ${(contentLength / 1024 / 1024).toFixed(1)}MB`)
            break
          case 'Progress':
            downloaded += event.data.chunkLength
            downloadProgress.value = contentLength > 0
              ? Math.round((downloaded / contentLength) * 100)
              : 0
            break
          case 'Finished':
            // 下载完成，进入安装替换阶段（此时 UI 应显示安装中而非操作按钮）
            installPhase.value = 'installing'
            console.log('[Updater] 下载完成')
            break
        }
      })

      installPhase.value = 'done'
      console.log('[Updater] 安装完成，准备重启')
      await relaunch()
    } catch (e) {
      console.error('[Updater] 下载安装失败:', e)
      throw e
    } finally {
      isDownloading.value = false
    }
  }

  return {
    isChecking,
    updateAvailable,
    updateInfo,
    downloadProgress,
    isDownloading,
    installPhase,
    checkForUpdates,
    downloadAndInstall,
  }
}
