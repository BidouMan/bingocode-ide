import { invoke } from '@tauri-apps/api/core'

/**
 * 内置素材清单（正式包专用）
 *
 * 打包时由 scripts/gen-assets-manifest.mjs 生成 engine/assets/manifest.json，
 * 记录本版本实际打包了哪些文件。覆盖安装后安装目录里可能残留旧版本已删除的素材，
 * 运行时按清单过滤（并后台清理），避免「更新完老资源还在」。
 *
 * dev 模式直接读源码树，永远不做过滤/删除。
 */

/** 相对 engine/assets 的路径，统一正斜杠 + 小写，便于跨平台比较 */
export function normalizeAssetRelPath(path: string): string {
  return path.replace(/\\/g, '/').replace(/^\.?\//, '').toLowerCase()
}

let manifestPromise: Promise<Set<string> | null> | null = null

/** 读取清单；返回 null 表示不过滤（dev 模式或清单缺失/损坏） */
export function loadBuiltinAssetManifest(): Promise<Set<string> | null> {
  if (manifestPromise) return manifestPromise
  manifestPromise = (async () => {
    if (import.meta.env.DEV) return null
    try {
      const engineDir = await invoke<string>('get_engine_assets_dir')
      const raw = await invoke<string>('read_file', { path: `${engineDir}/manifest.json` })
      const data = JSON.parse(raw)
      if (!Array.isArray(data?.files)) return null
      return new Set<string>(data.files.map(normalizeAssetRelPath))
    } catch (e) {
      // 清单缺失/损坏时退回旧行为（全部显示），绝不因为清单问题让素材库变空
      console.warn('[Assets] 内置素材清单不可用，跳过过滤:', e)
      return null
    }
  })()
  return manifestPromise
}

/** 该文件是否属于本版本的内置素材（manifest 为 null 时一律通过） */
export function isBuiltinAsset(manifest: Set<string> | null, relPath: string): boolean {
  return !manifest || manifest.has(normalizeAssetRelPath(relPath))
}

let cleanupStarted = false

/**
 * 后台清理清单外的残留文件（旧版本已删除的素材）。
 * 仅正式包执行；安装到 Program Files 等无写权限目录时删除失败会被忽略，
 * 不影响列表正确性（列表已按清单过滤）。
 */
export async function cleanStaleBuiltinAssets(): Promise<void> {
  if (import.meta.env.DEV || cleanupStarted) return
  cleanupStarted = true

  const manifest = await loadBuiltinAssetManifest()
  if (!manifest) return

  let engineDir = ''
  try {
    engineDir = await invoke<string>('get_engine_assets_dir')
  } catch {
    return
  }

  // 上限防止极端情况下长时间占用（正常内置素材只有几百个文件）
  const MAX_SCAN = 4000
  const MAX_DELETE = 300
  let scanned = 0
  let deleted = 0

  async function walk(relDir: string): Promise<void> {
    if (scanned >= MAX_SCAN || deleted >= MAX_DELETE) return
    let entries: string[]
    try {
      entries = await invoke<string[]>('list_dir', { path: `${engineDir}/${relDir}` })
    } catch {
      return
    }
    for (const entry of entries) {
      if (scanned >= MAX_SCAN || deleted >= MAX_DELETE) return
      const name = entry.replace(/\/+$/, '')
      const rel = `${relDir}/${name}`
      if (entry.endsWith('/')) {
        await walk(rel)
        continue
      }
      scanned++
      if (name === 'manifest.json') continue
      if (manifest.has(normalizeAssetRelPath(rel))) continue
      try {
        await invoke('delete_path', { path: `${engineDir}/${rel}` })
        deleted++
      } catch {
        // 无写权限（如 Program Files）时跳过，列表过滤已经保证看不到
      }
    }
  }

  for (const sub of ['sprites', 'sounds', 'maps']) {
    await walk(sub)
  }

  if (deleted > 0) {
    console.log(`[Assets] 已清理 ${deleted} 个旧版本残留素材`)
  }
}
