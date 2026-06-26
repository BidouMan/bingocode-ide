import JSZip from 'jszip'

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
  const resp = await fetch(url)
  const blob = await resp.blob()
  const file = new File([blob], 'sprite.bgs')
  return readBgsFile(file)
}

export function createFrameUrl(blob: Blob): string {
  return URL.createObjectURL(blob)
}
