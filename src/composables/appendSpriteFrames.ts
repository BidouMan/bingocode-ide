/**
 * 向项目角色追加序列帧（统一处理 .bsf 重打包 / .bgs 落盘 / 图片角色转正）。
 *
 * - .bsf：既有帧（全画布）+ 新帧 → 整体重打包 sheet（保留原帧名与 clips 编排，
 *   覆盖到旧尾帧的 clip 自动延展），写 sheet.png + manifest.json
 * - .bgs（config.json 目录）：新帧归一化落盘 PNG + config.json（frames 追加，
 *   end 到旧尾帧的动画段延展）
 * - 图片角色（单文件）：转正为 .bsf 目录（sheet 打包；.bsf 才能承载中心点/碰撞/挂点），
 *   资源项 path 由返回值告知调用方
 *
 * 所有新帧都会归一化到目标画布尺寸（等比缩小居中，小图原尺寸居中），
 * 保证动画帧尺寸一致不抖动。
 */
import { invoke } from '@tauri-apps/api/core'
import {
  readSpriteFromPath,
  readImageAsSprite,
  loadImage,
  saveSpriteConfig,
  saveBsfManifest,
  type SpriteData,
} from './useSpriteData'
import { packDrawnFrames, buildDrawnBsfManifest } from '../utils/bsfPacker'
import type { BsfFrameMeta } from './useSpriteData'

export interface AppendFramesResult {
  added: number
  /** 图片角色首次追加时转正为目录角色：新目录路径（调用方需同步 resource item.path） */
  newPath?: string
}

function canvasToPng(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('canvas.toBlob 失败'))), 'image/png')
  })
}

/** 图片等比 contain 居中绘制到目标画布（不放大；SVG 请先在调用方栅格化为 PNG） */
async function blobToCanvas(blob: Blob, w: number, h: number): Promise<HTMLCanvasElement> {
  const img = await loadImage(blob)
  const canvas = document.createElement('canvas')
  canvas.width = w
  canvas.height = h
  const iw = img.naturalWidth || img.width
  const ih = img.naturalHeight || img.height
  const scale = Math.min(1, w / Math.max(1, iw), h / Math.max(1, ih))
  const dw = Math.max(1, Math.round(iw * scale))
  const dh = Math.max(1, Math.round(ih * scale))
  canvas.getContext('2d')!.drawImage(img, Math.round((w - dw) / 2), Math.round((h - dh) / 2), dw, dh)
  return canvas
}

/** 全画布帧 → .bsf 目录（sheet.png + manifest.json；先写 sheet 再写 manifest） */
async function writeBsfDir(
  dirPath: string,
  name: string,
  canvases: HTMLCanvasElement[],
  names?: string[]
) {
  const packed = packDrawnFrames(canvases, canvases[0].width, canvases[0].height, names)
  await invoke('create_dir', { path: dirPath })
  const sheetBlob = await canvasToPng(packed.sheet)
  await invoke('write_binary', {
    path: `${dirPath}/sheet.png`,
    data: Array.from(new Uint8Array(await sheetBlob.arrayBuffer())),
  })
  await invoke('write_file', {
    path: `${dirPath}/manifest.json`,
    content: JSON.stringify(buildDrawnBsfManifest(name, packed), null, 2),
  })
}

/** 重打包后按帧名把帧级扩展字段（pivot/collision/markers 覆盖）搬回新元数据（帧名是唯一稳定标识） */
function carryFrameMetaExtras(next: BsfFrameMeta[], prev: BsfFrameMeta[]) {
  const prevByName = new Map(prev.map(f => [f.name, f]))
  for (const f of next) {
    const p = prevByName.get(f.name)
    if (!p) continue
    if (p.pivot) f.pivot = { ...p.pivot }
    if (p.collision) f.collision = JSON.parse(JSON.stringify(p.collision))
    if (p.markers) f.markers = JSON.parse(JSON.stringify(p.markers))
  }
}

/** 图片帧归一化到目标画布（等比 contain 缩小居中；SVG 请先在调用方栅格化为 PNG） */
export async function normalizeFrameToCanvas(blob: Blob, w: number, h: number): Promise<Blob> {
  return canvasToPng(await blobToCanvas(blob, w, h))
}

/** 生成不与既有帧名冲突的 .bgs 帧文件名 */
function uniqueBgsFrameName(existing: Set<string>, startN: number): string {
  let n = startN
  let name = `frame_${String(n).padStart(2, '0')}.png`
  while (existing.has(name)) {
    n++
    name = `frame_${String(n).padStart(2, '0')}.png`
  }
  existing.add(name)
  return name
}

/** 生成不与既有帧名冲突的 .bsf 帧名（frame_NNN） */
function uniqueBsfFrameName(existing: Set<string>, startN: number): string {
  let n = startN
  let name = `frame_${String(n).padStart(3, '0')}`
  while (existing.has(name)) {
    n++
    name = `frame_${String(n).padStart(3, '0')}`
  }
  existing.add(name)
  return name
}

/**
 * 追加帧到项目角色。
 * @param spritePath 角色资源路径（目录或图片文件）
 * @param newFrames 新帧图片（调用方保证为可解码图片；SVG 已栅格化）
 */
export async function appendFramesToSprite(
  spritePath: string,
  newFrames: Blob[]
): Promise<AppendFramesResult> {
  if (newFrames.length === 0) return { added: 0 }

  // 图片角色（单文件）→ 转正为目录角色后追加
  if (/\.(png|jpe?g|gif|bmp|webp)$/i.test(spritePath)) {
    return appendImageSprite(spritePath, newFrames)
  }

  const sprite = await readSpriteFromPath(spritePath)
  if (sprite.bsf) {
    await appendToBsf(spritePath, sprite, newFrames)
  } else {
    await appendToBgs(spritePath, sprite, newFrames)
  }
  return { added: newFrames.length }
}

async function appendToBgs(dirPath: string, sprite: Awaited<ReturnType<typeof readSpriteFromPath>>, newFrames: Blob[]) {
  const first = await loadImage(sprite.frames[0].blob)
  const w = first.naturalWidth || first.width
  const h = first.naturalHeight || first.height
  const oldCount = sprite.frames.length
  const existing = new Set(sprite.frames.map(f => f.name))

  for (let i = 0; i < newFrames.length; i++) {
    const norm = await normalizeFrameToCanvas(newFrames[i], w, h)
    const name = uniqueBgsFrameName(existing, oldCount + i + 1)
    sprite.frames.push({ name, blob: norm, url: '' })
    const buf = new Uint8Array(await norm.arrayBuffer())
    await invoke('write_binary', { path: `${dirPath}/${name}`, data: Array.from(buf) })
  }

  // 覆盖到旧尾帧的动画段自动延展，把新帧纳入原动画
  for (const a of sprite.animations) {
    if (a.end === oldCount) a.end = sprite.frames.length
  }
  await saveSpriteConfig(dirPath, sprite)
}

async function appendToBsf(dirPath: string, sprite: Awaited<ReturnType<typeof readSpriteFromPath>>, newFrames: Blob[]) {
  const meta = sprite.bsf!
  const { w: canvasW, h: canvasH } = meta.canvas

  // 既有帧（已裁回全画布）+ 新帧 → 全画布 canvas 数组
  const canvases: HTMLCanvasElement[] = []
  for (const f of sprite.frames) {
    const img = await loadImage(f.blob)
    const c = document.createElement('canvas')
    c.width = canvasW
    c.height = canvasH
    c.getContext('2d')!.drawImage(img, 0, 0)
    canvases.push(c)
  }

  const names = meta.frames.map(f => f.name)
  const existing = new Set(names)
  const oldCount = names.length
  for (let i = 0; i < newFrames.length; i++) {
    const norm = await normalizeFrameToCanvas(newFrames[i], canvasW, canvasH)
    const img = await loadImage(norm)
    const c = document.createElement('canvas')
    c.width = canvasW
    c.height = canvasH
    c.getContext('2d')!.drawImage(img, 0, 0)
    canvases.push(c)
    names.push(uniqueBsfFrameName(existing, oldCount + i + 1))
  }

  const packed = packDrawnFrames(canvases, canvasW, canvasH, names)
  // 只更新帧矩形；pivot/canvas 保持原 manifest 值（saveBsfManifest 回写 sprite.bsf.*）
  // 帧级 pivot/collision 覆盖按帧名搬回新 packed 元数据（rect/offset 变了但帧名稳定）
  carryFrameMetaExtras(packed.frames, meta.frames)
  meta.frames = packed.frames

  for (const a of sprite.animations) {
    if (a.end === oldCount) a.end = oldCount + newFrames.length
  }

  const sheetBlob = await canvasToPng(packed.sheet)
  await invoke('write_binary', {
    path: `${dirPath}/sheet.png`,
    data: Array.from(new Uint8Array(await sheetBlob.arrayBuffer())),
  })
  await saveBsfManifest(dirPath, sprite)
}

async function appendImageSprite(
  imgPath: string,
  newFrames: Blob[]
): Promise<AppendFramesResult> {
  const sprite = await readImageAsSprite(imgPath)
  const first = await loadImage(sprite.frames[0].blob)
  const w = first.naturalWidth || first.width
  const h = first.naturalHeight || first.height

  // 首帧 + 新帧（统一归一化到首帧画布）→ 打包为 .bsf：中心点/碰撞/挂点此后可用
  const canvases = [await blobToCanvas(sprite.frames[0].blob, w, h)]
  for (const blob of newFrames) {
    canvases.push(await blobToCanvas(blob, w, h))
  }

  const dirPath = imgPath.replace(/\.[^.]+$/, '')
  await writeBsfDir(dirPath, sprite.name, canvases)
  // 旧的单文件删除，避免项目扫描时同时出现图片与同名目录
  await invoke('delete_path', { path: imgPath }).catch(() => {})

  return { added: newFrames.length, newPath: dirPath }
}

// ────────────────────────────────────────────────────────────────
// 整体重写（绘制页「编辑角色」保存）：以当前帧列表为准回写磁盘
// ────────────────────────────────────────────────────────────────

/**
 * 整体重写角色帧。
 * @param names 与 canvases 对齐的帧名：非空 = 保留原帧名（clips 引用）；null = 新帧，生成唯一名
 * - .bsf：全帧重打包 sheet + 手写 manifest（clips 过滤已删帧名、空 clip 移除；canvas/pivot 保留）
 * - .bgs：全量重写帧文件 + config.json（旧文件名不在新列表中的删除；动画段 start/end clamp）
 * - 图片角色（单文件）：转正为 .bsf 目录角色（sheet 打包；返回 newPath）
 */
export async function rewriteSpriteFrames(
  spritePath: string,
  canvases: HTMLCanvasElement[],
  names: (string | null)[]
): Promise<{ newPath?: string }> {
  if (canvases.length === 0) throw new Error('没有可保存的帧')

  const isImageFile = /\.(png|jpe?g|gif|bmp|webp)$/i.test(spritePath)
  const dirPath = isImageFile ? spritePath.replace(/\.[^.]+$/, '') : spritePath

  const sprite = await readSpriteFromPath(spritePath)
  const isBsf = !!sprite.bsf
  const finalNames = buildFinalNames(canvases.length, names, isBsf || isImageFile)

  if (isImageFile) {
    await writeBsfDir(dirPath, sprite.name, canvases, finalNames)
    // 旧的单文件删除，避免项目扫描时同时出现图片与同名目录
    await invoke('delete_path', { path: spritePath }).catch(() => {})
    return { newPath: dirPath }
  }
  if (isBsf) {
    await rewriteBsfDir(dirPath, sprite, canvases, finalNames)
  } else {
    await rewriteBgsDir(dirPath, sprite, canvases, finalNames)
  }
  return {}
}

/** 生成最终帧名：保留传入名；null 位生成 frame_NNN（.bsf）/ frame_NN.png（.bgs）且避开碰撞 */
function buildFinalNames(count: number, names: (string | null)[], isBsf: boolean): string[] {
  const used = new Set(names.filter((n): n is string => !!n))
  const result: string[] = []
  let nextN = 1
  for (let i = 0; i < count; i++) {
    const given = names[i]
    if (given) {
      result.push(given)
      continue
    }
    let candidate = ''
    do {
      candidate = isBsf
        ? `frame_${String(nextN).padStart(3, '0')}`
        : `frame_${String(nextN).padStart(2, '0')}.png`
      nextN++
    } while (used.has(candidate))
    used.add(candidate)
    result.push(candidate)
  }
  return result
}

async function rewriteBsfDir(
  dirPath: string,
  sprite: SpriteData,
  canvases: HTMLCanvasElement[],
  names: string[]
) {
  const meta = sprite.bsf!
  const packed = packDrawnFrames(canvases, meta.canvas.w, meta.canvas.h, names)
  // 帧级 pivot/collision 覆盖按帧名保留（重打包后 rect/offset 变化不影响语义）
  carryFrameMetaExtras(packed.frames, meta.frames)

  // clips：帧序列过滤已删帧名；空 clip 移除（readSpriteFromPath 读取的 clips 带 frameNames）
  const nameSet = new Set(names)
  const clips = sprite.animations
    .map((a) => {
      let frameList: string[]
      if (a.frameNames && a.frameNames.length > 0) {
        frameList = a.frameNames.filter((n) => nameSet.has(n))
      } else {
        // 无原始序列信息时回退为全部帧
        frameList = [...names]
      }
      if (frameList.length === 0) return null
      return {
        name: a.name,
        frames: frameList,
        fps: a.fps ?? 10,
        loop: a.loop !== false,
      }
    })
    .filter((c): c is NonNullable<typeof c> => c !== null)

  const manifest: Record<string, unknown> = {
    format: 'bsf',
    version: 2,
    name: sprite.name,
    sheet: 'sheet.png',
    canvas: meta.canvas,
    pivot: meta.pivot,
    // 根级可选标注字段：统一碰撞 / 统一挂点（缺省不写）
    ...(meta.collision ? { collision: meta.collision } : {}),
    ...(meta.markers && Object.keys(meta.markers).length > 0 ? { markers: meta.markers } : {}),
    frames: packed.frames,
    clips: clips.length > 0
      ? clips
      : [{ name: '默认动画', frames: [...names], fps: 10, loop: true }],
  }
  // 默认渲染帧：原默认帧名仍在列表中则保留
  const oldDefault = sprite.frames[sprite.defaultFrameIndex ?? 0]?.name
  if (oldDefault && nameSet.has(oldDefault)) {
    manifest.defaultFrame = oldDefault
  }

  const sheetBlob = await canvasToPng(packed.sheet)
  await invoke('write_binary', {
    path: `${dirPath}/sheet.png`,
    data: Array.from(new Uint8Array(await sheetBlob.arrayBuffer())),
  })
  await invoke('write_file', {
    path: `${dirPath}/manifest.json`,
    content: JSON.stringify(manifest, null, 2),
  })
}

async function rewriteBgsDir(
  dirPath: string,
  sprite: SpriteData,
  canvases: HTMLCanvasElement[],
  names: string[]
) {
  await invoke('create_dir', { path: dirPath })

  // 先写新帧（保留名同名文件原地覆盖；新名不冲突）
  for (let i = 0; i < canvases.length; i++) {
    const blob = await canvasToPng(canvases[i])
    await invoke('write_binary', {
      path: `${dirPath}/${names[i]}`,
      data: Array.from(new Uint8Array(await blob.arrayBuffer())),
    })
  }

  // 删除不在新列表中的旧帧文件（避免残留孤儿帧）
  const newSet = new Set(names)
  for (const f of sprite.frames) {
    const file = f.name.match(/\.(png|jpe?g|gif|bmp|webp)$/i) ? f.name : `${f.name}.png`
    if (!newSet.has(file)) {
      await invoke('delete_path', { path: `${dirPath}/${file}` }).catch(() => {})
    }
  }

  // config.json：动画段 start/end clamp 到新帧数
  const segments = sprite.animations
    .map((a) => {
      const start = Math.min(Math.max(1, a.start), names.length)
      const end = Math.min(Math.max(start, a.end), names.length)
      const seg: Record<string, unknown> = { name: a.name, start, end }
      if (a.fps != null) seg.fps = a.fps
      if (a.loop != null) seg.loop = a.loop
      return seg
    })
  const config: Record<string, unknown> = {
    name: sprite.name,
    frames: names,
    segments,
  }
  const oldDefault = sprite.frames[sprite.defaultFrameIndex ?? 0]?.name
  if (oldDefault && newSet.has(oldDefault)) {
    config.defaultFrame = oldDefault
  }
  await invoke('write_file', {
    path: `${dirPath}/config.json`,
    content: JSON.stringify(config, null, 4),
  })
}
