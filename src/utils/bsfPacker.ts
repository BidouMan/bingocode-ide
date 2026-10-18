/**
 * 绘制帧 → .bsf sheet 打包器（自研，输出与引擎/缩略图/编辑器读取端严格兼容）。
 *
 * .bsf 契约（与 BingoPacker / bingo_engine._normalize_bsf_manifest 对齐）：
 * - 每帧在 sheet 中紧致裁剪存储（rect），合成回参考画布时放在 offset 处
 * - 画布坐标系下 pivot 为锚点（本打包器统一用画布中心）
 * - clips[].frames 引用 frames[].name；manifest 2 空格缩进
 */

import type { BsfFrameMeta } from '../composables/useSpriteData'

/** 帧间打包间距（对齐 BingoPacker 观感的 2px padding） */
const PACK_PAD = 2

export interface PackedBsf {
  sheet: HTMLCanvasElement
  frames: BsfFrameMeta[]
  canvas: { w: number; h: number }
  pivot: { x: number; y: number }
}

function makeCanvas(w: number, h: number): HTMLCanvasElement {
  const c = document.createElement('canvas')
  c.width = Math.max(1, w)
  c.height = Math.max(1, h)
  return c
}

/** 扫描画布非透明内容包围盒；空画布返回 null */
export function contentBBox(canvas: HTMLCanvasElement): { x: number; y: number; w: number; h: number } | null {
  const ctx = canvas.getContext('2d')
  if (!ctx) return null
  const { width, height } = canvas
  const data = ctx.getImageData(0, 0, width, height).data
  let minX = width
  let minY = height
  let maxX = -1
  let maxY = -1
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (data[(y * width + x) * 4 + 3] !== 0) {
        if (x < minX) minX = x
        if (x > maxX) maxX = x
        if (y < minY) minY = y
        if (y > maxY) maxY = y
      }
    }
  }
  if (maxX < 0) return null
  return { x: minX, y: minY, w: maxX - minX + 1, h: maxY - minY + 1 }
}

/**
 * 把 N 张全画布帧（canvas.w × canvas.h，含透明背景）打包为 sheet + frames 元数据。
 * 空白帧退化为 1×1 透明占位（manifest.frames 不允许为空数组）。
 */
export function packDrawnFrames(
  frameCanvases: HTMLCanvasElement[],
  canvasW: number,
  canvasH: number,
  /**
   * 帧名（与 canvases 等长）：追加/重打包场景保留既有帧名供 clips 引用。
   * 缺省时自动生成 frame_NNN（1 起连续）。
   */
  names?: string[]
): PackedBsf {
  const crops = frameCanvases.map(c => contentBBox(c))

  // shelf 排布：目标宽度取 sqrt(总面积) 与最宽帧的较大者，逐行填充
  const sizes = crops.map(b => (b ? { w: b.w, h: b.h } : { w: 1, h: 1 }))
  const totalArea = sizes.reduce((s, r) => s + (r.w + PACK_PAD) * (r.h + PACK_PAD), 0)
  const maxW = Math.max(1, ...sizes.map(s => s.w))
  const targetW = Math.max(maxW, Math.ceil(Math.sqrt(totalArea)))

  const placements: { x: number; y: number }[] = []
  let px = 0
  let py = 0
  let rowH = 0
  let sheetW = 0
  let sheetH = 0
  for (let i = 0; i < sizes.length; i++) {
    const { w, h } = sizes[i]
    if (px > 0 && px + w + PACK_PAD > targetW) {
      px = 0
      py += rowH + PACK_PAD
      rowH = 0
    }
    placements.push({ x: px, y: py })
    px += w + PACK_PAD
    rowH = Math.max(rowH, h)
    sheetW = Math.max(sheetW, px - PACK_PAD)
    sheetH = Math.max(sheetH, py + h)
  }

  const sheet = makeCanvas(sheetW, sheetH)
  const sctx = sheet.getContext('2d')!

  const frames: BsfFrameMeta[] = frameCanvases.map((c, i) => {
    const b = crops[i]
    const p = placements[i]
    const name = names?.[i] ?? `frame_${String(i + 1).padStart(3, '0')}`
    if (b) {
      sctx.drawImage(c, b.x, b.y, b.w, b.h, p.x, p.y, b.w, b.h)
      return {
        name,
        rect: { x: p.x, y: p.y, w: b.w, h: b.h },
        offset: { x: b.x, y: b.y },
      }
    }
    // 空白帧：1×1 透明占位（sheet 对应区域保持透明）
    return {
      name,
      rect: { x: p.x, y: p.y, w: 1, h: 1 },
      offset: { x: 0, y: 0 },
    }
  })

  return {
    sheet,
    frames,
    canvas: { w: canvasW, h: canvasH },
    pivot: { x: canvasW / 2, y: canvasH / 2 },
  }
}

/** 生成绘制角色的 .bsf manifest（单 clip 包含全部帧；多 clip 编辑在角色编辑器中进行） */
export function buildDrawnBsfManifest(name: string, packed: PackedBsf): Record<string, unknown> {
  return {
    format: 'bsf',
    version: 2,
    name,
    sheet: 'sheet.png',
    canvas: packed.canvas,
    pivot: packed.pivot,
    frames: packed.frames,
    clips: [
      {
        name: '默认动画',
        frames: packed.frames.map(f => f.name),
        fps: 10,
        loop: true,
      },
    ],
  }
}
