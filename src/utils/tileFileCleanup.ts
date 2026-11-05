import { invoke } from '@tauri-apps/api/core'

/** 把项目内绝对路径或相对路径统一成「项目根内的相对路径」，便于比对 */
function toProjectRelative(root: string, path: string): string {
  const p = path.replace(/\\/g, '/').replace(/\/+$/, '')
  const r = root.replace(/\\/g, '/').replace(/\/+$/, '')
  if (p.startsWith(`${r}/`)) return p.slice(r.length + 1)
  return p.replace(/^\.\//, '')
}

/** 收集地图数据里所有仍被引用的图片路径 */
function collectReferenced(root: string, mapData: any): Set<string> {
  const refs = new Set<string>()
  const add = (p?: string | null) => {
    if (p) refs.add(toProjectRelative(root, p))
  }
  for (const r of mapData?.resources ?? []) {
    add(r?.path)
    add(r?.originPath)
  }
  for (const ts of mapData?.tileSets ?? []) add(ts?.imagePath)
  for (const layer of mapData?.layers ?? []) {
    add(layer?.image?.imagePath)
    add(layer?.image?.vectorBasePath)
  }
  return refs
}

/**
 * 删除图块素材后清理项目里复制出来的图片。
 * 安全约束：只删当前地图 images 目录下的文件，并且必须确认全图已无任何素材 / 图层引用。
 */
export async function deleteUnreferencedTileImages(
  projectRoot: string,
  mapName: string,
  candidates: Iterable<string | undefined | null>,
  mapData: any,
): Promise<void> {
  if (!projectRoot || !mapName) return
  const root = projectRoot.replace(/\\/g, '/').replace(/\/+$/, '')
  const refs = collectReferenced(projectRoot, mapData)
  const imagesPrefix = `assets/maps/${mapName}/images/`
  const doomed = new Set<string>()
  for (const raw of candidates) {
    if (!raw) continue
    const rel = toProjectRelative(projectRoot, raw)
    // 内置素材（/maps/...）或地图目录外的文件不归这里管，绝不删除
    if (!rel.startsWith(imagesPrefix)) continue
    // 其它素材或图层还引用同一张图时保留
    if (refs.has(rel)) continue
    doomed.add(`${root}/${rel}`)
  }
  for (const path of doomed) {
    try {
      await invoke('delete_path', { path })
    } catch (e) {
      console.warn('[TileCleanup] 清理图片失败:', path, e)
    }
  }
}
