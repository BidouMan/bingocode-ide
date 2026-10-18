import JSZip from 'jszip'
import { invoke } from '@tauri-apps/api/core'

export interface SpriteFrame {
  name: string
  blob: Blob
  url: string
}

export interface SpriteAnimation {
  name: string
  start: number
  end: number
  fps?: number
  loop?: boolean
  /** .bsf clip 的原始帧名序列（非连续帧时保留；编辑 start/end 后应清除） */
  frameNames?: string[]
}

export interface BsfFrameMeta {
  name: string
  rect: { x: number; y: number; w: number; h: number }
  offset: { x: number; y: number }
}

/** .bsf（Bingo Sheet File）sheet 元数据：保存 manifest 时完整回写 */
export interface BsfMeta {
  canvas: { w: number; h: number }
  pivot: { x: number; y: number }
  frames: BsfFrameMeta[]
}

export interface SpriteData {
  name: string
  frames: SpriteFrame[]
  animations: SpriteAnimation[]
  /** 仅 .bsf 角色有值 */
  bsf?: BsfMeta
}

/** 解码图片（Blob 或 data URL → HTMLImageElement；老 WebView 无 createImageBitmap） */
export function loadImage(source: Blob | string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    let url: string
    let revoke = false
    if (typeof source === 'string') {
      url = source
    } else {
      url = URL.createObjectURL(source)
      revoke = true
    }
    const img = new Image()
    img.onload = () => {
      if (revoke) URL.revokeObjectURL(url)
      resolve(img)
    }
    img.onerror = () => {
      if (revoke) URL.revokeObjectURL(url)
      reject(new Error('图片解码失败'))
    }
    img.src = url
  })
}

/**
 * 把 sheet 中的一帧画回完整参考画布（canvas + offset 定位）。
 * 紧致裁剪的帧直接展示会比 .bgs 整帧导出的观感"大一圈"且预览帧间不齐；
 * 按 manifest 语义还原画布尺寸后，缩略图边距与动画预览对齐都和 .bgs 一致。
 */
async function cropSheetFrame(
  image: HTMLImageElement,
  frame: BsfFrameMeta,
  canvasSize: { w: number; h: number },
): Promise<SpriteFrame> {
  const canvas = document.createElement('canvas')
  canvas.width = canvasSize.w
  canvas.height = canvasSize.h
  const ctx = canvas.getContext('2d')!
  const offset = frame.offset || { x: 0, y: 0 }
  ctx.drawImage(
    image,
    frame.rect.x, frame.rect.y, frame.rect.w, frame.rect.h,
    offset.x, offset.y, frame.rect.w, frame.rect.h,
  )
  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(b => (b ? resolve(b) : reject(new Error('canvas.toBlob 失败'))), 'image/png')
  })
  return { name: '', blob, url: URL.createObjectURL(blob) }
}

/**
 * .bsf 缩略图：裁剪 manifest 第一帧 → dataURL。
 * 支持两种形态：内置库的 .bsf zip 文件 / 项目内解压后的 sheet 目录。
 */
export async function getBsfThumbnail(path: string): Promise<string> {
  let manifest: any
  let sheetImage: HTMLImageElement

  if (path.toLowerCase().endsWith('.bsf')) {
    const bytes = await invoke<number[]>('read_binary', { path })
    const JSZip = (await import('jszip')).default
    const zip = await JSZip.loadAsync(new Uint8Array(bytes))
    const manifestEntry = zip.file('manifest.json')
    const sheetEntry = zip.file('sheet.png')
    if (!manifestEntry || !sheetEntry) throw new Error('.bsf 缺少 manifest.json 或 sheet.png')
    manifest = JSON.parse(await manifestEntry.async('text'))
    sheetImage = await loadImage(await sheetEntry.async('blob'))
  } else {
    manifest = JSON.parse(await invoke<string>('read_file', { path: `${path}/manifest.json` }))
    const dataUrl = await invoke<string>('read_image_as_data_url', {
      path: `${path}/${manifest.sheet || 'sheet.png'}`,
    })
    sheetImage = await loadImage(dataUrl)
  }

  const frame = manifest.frames?.[0]
  if (!frame?.rect) throw new Error('manifest.frames 为空')
  // 画回完整参考画布：紧致裁剪帧直接展示会比 .bgs 整帧导出"大一圈"
  const canvasSize = manifest.canvas || { w: frame.rect.w, h: frame.rect.h }
  const canvas = document.createElement('canvas')
  canvas.width = canvasSize.w
  canvas.height = canvasSize.h
  const offset = frame.offset || { x: 0, y: 0 }
  canvas.getContext('2d')!.drawImage(
    sheetImage,
    frame.rect.x, frame.rect.y, frame.rect.w, frame.rect.h,
    offset.x, offset.y, frame.rect.w, frame.rect.h,
  )
  return canvas.toDataURL('image/png')
}

/** 统一入口：项目内的角色资源（图片 / .bgs 目录 / .bsf sheet 目录） */
export async function readSpriteFromPath(path: string): Promise<SpriteData> {
  if (/\.(png|jpe?g|gif|bmp|webp)$/i.test(path)) {
    return readImageAsSprite(path)
  }
  // 本地目录：优先检测 .bsf（manifest.json），否则按 .bgs（config.json）
  if (path.startsWith('/') || /^[A-Z]:\\/i.test(path)) {
    const hasManifest = await invoke<boolean>('path_exists', { path: `${path}/manifest.json` })
      .catch(() => false)
    if (hasManifest) return readBsfFromDir(path)
  }
  return readBgsFromUrl(path)
}

/** 读取 .bsf 解压目录（manifest.json + sheet.png）：帧从 sheet 裁剪，clips 映射为动画段 */
export async function readBsfFromDir(dirPath: string): Promise<SpriteData> {
  const manifestText = await invoke<string>('read_file', { path: `${dirPath}/manifest.json` })
  const manifest = JSON.parse(manifestText)
  if (manifest.format !== 'bsf' || !Array.isArray(manifest.frames) || manifest.frames.length === 0) {
    throw new Error('不是合法的 .bsf manifest（需要 format=bsf 且 frames 非空）')
  }

  const sheetDataUrl = await invoke<string>('read_image_as_data_url', {
    path: `${dirPath}/${manifest.sheet || 'sheet.png'}`,
  })
  const sheetImage = await loadImage(sheetDataUrl)
  const canvasSize = manifest.canvas || {
    w: manifest.frames[0]?.rect.w ?? 1,
    h: manifest.frames[0]?.rect.h ?? 1,
  }

  const frames: SpriteFrame[] = []
  for (const f of manifest.frames as BsfFrameMeta[]) {
    const cropped = await cropSheetFrame(sheetImage, f, canvasSize)
    cropped.name = f.name
    frames.push(cropped)
  }

  const frameIndex = new Map((manifest.frames as BsfFrameMeta[]).map((f, i) => [f.name, i]))
  const animations: SpriteAnimation[] = (manifest.clips || []).map((c: any) => {
    const names: string[] = Array.isArray(c.frames) ? c.frames : []
    const idxs = names.map(n => frameIndex.get(n)).filter((i): i is number => i !== undefined)
    return {
      name: c.name,
      start: idxs.length ? idxs[0] + 1 : 1,
      end: idxs.length ? idxs[idxs.length - 1] + 1 : 1,
      fps: c.fps || 10,
      loop: c.loop !== false,
      frameNames: names.length ? names : undefined,
    }
  })

  return {
    name: manifest.name || '未知角色',
    frames,
    animations,
    bsf: {
      canvas: canvasSize,
      pivot: manifest.pivot || { x: canvasSize.w / 2, y: canvasSize.h / 2 },
      frames: manifest.frames,
    },
  }
}

/**
 * 保存 .bsf 角色的 manifest.json（仅回写 clips；sheet 像素与帧矩形不动）。
 * clip 帧序列规则：若 start/end 与加载时 frameNames 一致则保留原序列，否则按 start-end 区间重建。
 */
export async function saveBsfManifest(dirPath: string, sprite: SpriteData): Promise<void> {
  if (!sprite.bsf) throw new Error('不是 .bsf 角色（缺少 sheet 元数据）')
  const allNames = sprite.bsf.frames.map(f => f.name)

  const clips = sprite.animations.map(a => {
    let frameList: string[]
    if (a.frameNames && a.frameNames.length > 0) {
      const firstIdx = allNames.indexOf(a.frameNames[0])
      const lastIdx = allNames.indexOf(a.frameNames[a.frameNames.length - 1])
      // start/end 被编辑过 → 丢弃旧序列，按区间重建
      if (firstIdx === a.start - 1 && lastIdx === a.end - 1) {
        frameList = [...a.frameNames]
      } else {
        frameList = allNames.slice(a.start - 1, a.end)
      }
    } else {
      frameList = allNames.slice(a.start - 1, a.end)
    }
    return {
      name: a.name,
      frames: frameList,
      fps: a.fps ?? 10,
      loop: a.loop !== false,
    }
  })

  const manifest = {
    format: 'bsf',
    version: 2,
    name: sprite.name,
    sheet: 'sheet.png',
    canvas: sprite.bsf.canvas,
    pivot: sprite.bsf.pivot,
    frames: sprite.bsf.frames,
    clips,
  }
  await invoke('write_file', {
    path: `${dirPath}/manifest.json`,
    content: JSON.stringify(manifest, null, 2),
  })
}

export async function readBgsFile(file: File): Promise<SpriteData> {
  const zip = await JSZip.loadAsync(file)
  const configEntry = zip.file('config.json')
  if (!configEntry) throw new Error('config.json not found in .bgs')

  const config = JSON.parse(await configEntry.async('text'))

  const frames: SpriteFrame[] = []
  const frameNames: string[] = config.frames || []

  for (const frameName of frameNames) {
    const entry = zip.file(frameName)
    if (entry) {
      const blob = await entry.async('blob')
      const url = URL.createObjectURL(blob)
      frames.push({ name: frameName, blob, url })
    }
  }

  const animations: SpriteAnimation[] = (config.segments || config.animations || []).map(
    (seg: any) => ({
      name: seg.name,
      start: seg.start || 1,
      end: seg.end || seg.start || 1,
      fps: seg.fps || 10,
      loop: seg.loop !== false,
    })
  )

  return { name: config.name || '未知角色', frames, animations }
}

export async function readBgsFromUrl(url: string): Promise<SpriteData> {
  // 本地文件系统路径：通过 Tauri invoke 读取
  if (url.startsWith('/') || /^[A-Z]:\\/i.test(url)) {
    return readLocalSpriteDir(url)
  }
  // HTTP URL（engine/assets 通过 Vite publicDir 提供）：用 fetch 读取 .bgs zip
  const resp = await fetch(url)
  const blob = await resp.blob()
  const file = new File([blob], 'sprite.bgs')
  return readBgsFile(file)
}

/** 从本地解压目录读取角色（config.json + 帧图片） */
async function readLocalSpriteDir(dirPath: string): Promise<SpriteData> {
  const configText = await invoke<string>('read_file', { path: `${dirPath}/config.json` })
  const config = JSON.parse(configText)

  const frames: SpriteFrame[] = []
  const frameNames: string[] = config.frames || []

  for (const frameName of frameNames) {
    try {
      const dataUrl = await invoke<string>('read_image_as_data_url', { path: `${dirPath}/${frameName}` })
      const resp = await fetch(dataUrl)
      const blob = await resp.blob()
      const objectUrl = URL.createObjectURL(blob)
      frames.push({ name: frameName, blob, url: objectUrl })
    } catch (e) {
      console.warn(`读取帧 ${frameName} 失败:`, e)
    }
  }

  const animations: SpriteAnimation[] = (config.segments || config.animations || []).map(
    (seg: any) => ({
      name: seg.name,
      start: seg.start || 1,
      end: seg.end || seg.start || 1,
      fps: seg.fps || 10,
      loop: seg.loop !== false,
    })
  )

  return { name: config.name || '未知角色', frames, animations }
}

export function createFrameUrl(blob: Blob): string {
  return URL.createObjectURL(blob)
}

/** 释放 SpriteData 中所有 ObjectURL，防止内存泄漏 */
export function revokeSpriteUrls(sprite: SpriteData | null) {
  if (!sprite) return
  for (const frame of sprite.frames) {
    if (frame.url) URL.revokeObjectURL(frame.url)
  }
}

/**
 * 将动画/帧修改写回 config.json（自动保存）
 * 保持与旧版 PySide6 sprite_model.py save() 相同的格式：
 * 使用 "segments" 数组，保留 name/count 等原有字段
 */
export async function saveSpriteConfig(spritePath: string, sprite: SpriteData): Promise<void> {
  const config: Record<string, any> = { name: sprite.name }
  config.frames = sprite.frames.map(f => f.name)
  config.segments = sprite.animations.map(a => {
    const seg: Record<string, any> = {
      name: a.name,
      start: a.start,
      end: a.end,
    }
    if (a.fps != null) seg.fps = a.fps
    if (a.loop != null) seg.loop = a.loop
    return seg
  })

  const json = JSON.stringify(config, null, 4)
  await invoke('write_file', { path: `${spritePath}/config.json`, content: json })
}

// 图片文件 → 单帧 SpriteData（上传图片直接作角色时使用）
export async function readImageAsSprite(path: string): Promise<SpriteData> {
  const dataUrl = await invoke<string>('read_image_as_data_url', { path })
  const blob = await (await fetch(dataUrl)).blob()
  const fileName = path.split(/[\\/]/).pop() || '角色'
  const name = fileName.replace(/\.[^.]+$/, '')
  return {
    name,
    frames: [{ name, blob, url: dataUrl }],
    animations: [{ name: '默认动画', start: 1, end: 1, fps: 10, loop: true }],
  }
}

function buildSpriteConfigJson(sprite: SpriteData): string {
  const config: Record<string, any> = { name: sprite.name }
  config.frames = sprite.frames.map(f => f.name)
  config.segments = sprite.animations.map(a => {
    const seg: Record<string, any> = {
      name: a.name,
      start: a.start,
      end: a.end,
    }
    if (a.fps != null) seg.fps = a.fps
    if (a.loop != null) seg.loop = a.loop
    return seg
  })
  return JSON.stringify(config, null, 4)
}

// 图片角色编辑后转正为目录角色：把内存中的帧图 + config.json 落盘到目录
// （引擎读取目录角色时按 config.frames 的帧名自动补图片扩展名）
export async function saveImageSpriteToDirectory(dirPath: string, sprite: SpriteData): Promise<void> {
  await invoke('create_dir', { path: dirPath })
  for (const f of sprite.frames) {
    const buf = new Uint8Array(await f.blob.arrayBuffer())
    const extMatch = f.name.match(/\.(png|jpe?g|gif|bmp|webp)$/i)
    const fileName = extMatch ? f.name : `${f.name}.png`
    await invoke('write_binary', { path: `${dirPath}/${fileName}`, data: Array.from(buf) })
  }
  await invoke('write_file', { path: `${dirPath}/config.json`, content: buildSpriteConfigJson(sprite) })
}
