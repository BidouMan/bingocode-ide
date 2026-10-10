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
}

export interface SpriteData {
  name: string
  frames: SpriteFrame[]
  animations: SpriteAnimation[]
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
