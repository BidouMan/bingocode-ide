import type { PaperViewportAdapter } from '../paint-editor/composables/usePaperScope'

/**
 * 地图画布的矢量视口适配器。
 *
 * paper 逻辑坐标 = 当前图片图层的绘制画布像素（paintSession.canvas）。
 * 适配器把“画布像素 → 图片本地归一化 → 世界坐标 → 屏幕（stage 缩放/平移）”
 * 合成为一个仿射矩阵，因此图片自身的旋转/非等比缩放/镜像都能正确对齐。
 */

export interface MapVectorFrame {
  /** 当前图片图层数据（ImageData：position/rotation/scaleX/scaleY/width/height） */
  image: any
  /** 绘制会话画布（可能比原图大：背景图层随地图尺寸扩展） */
  canvas: HTMLCanvasElement | null
  /** Pixi 视口：舞台偏移与缩放 */
  stageX: number
  stageY: number
  scale: number
  /** 地图画布容器相对视口的偏移（用于 clientX/Y → 画布内坐标） */
  rootRect: { left: number; top: number } | null
}

export interface MapVectorMatrix {
  a: number
  b: number
  c: number
  d: number
  tx: number
  ty: number
}

const IDENTITY: MapVectorMatrix = { a: 1, b: 0, c: 0, d: 1, tx: 0, ty: 0 }

export function computeMapVectorMatrix(frame: MapVectorFrame | null): MapVectorMatrix | null {
  if (!frame?.image || !frame.canvas) return null
  const { image: img, canvas } = frame
  const cw = canvas.width
  const ch = canvas.height
  if (cw <= 0 || ch <= 0) return null

  const scaleX = img.scaleX ?? img.scale ?? 1
  const scaleY = img.scaleY ?? img.scale ?? 1
  const logicalW = (img.width || cw) * scaleX
  const logicalH = (img.height || ch) * scaleY

  // 每个画布像素对应的屏幕像素（含符号：支持水平/垂直镜像）
  const ax = (logicalW / cw) * frame.scale
  const ay = (logicalH / ch) * frame.scale

  const rot = ((img.rotation ?? 0) * Math.PI) / 180
  const cos = Math.cos(rot)
  const sin = Math.sin(rot)
  const a = ax * cos
  const b = ax * sin
  const c = -ay * sin
  const d = ay * cos

  // 精灵中心（与 renderImageLayer 的 anchor=0.5 + signed scale 一致）
  const cxWorld = (img.position?.[0] ?? 0) + logicalW / 2
  const cyWorld = (img.position?.[1] ?? 0) + logicalH / 2
  const cxScreen = frame.stageX + cxWorld * frame.scale
  const cyScreen = frame.stageY + cyWorld * frame.scale

  const tx = cxScreen - (a * (cw / 2) + c * (ch / 2))
  const ty = cyScreen - (b * (cw / 2) + d * (ch / 2))
  return { a, b, c, d, tx, ty }
}

/** 画布像素 → 屏幕（相对地图画布容器左上角） */
export function mapVectorToScreen(m: MapVectorMatrix, x: number, y: number) {
  return {
    x: m.a * x + m.c * y + m.tx,
    y: m.b * x + m.d * y + m.ty,
  }
}

export function createMapVectorViewport(getFrame: () => MapVectorFrame | null): PaperViewportAdapter {
  return {
    clientToArtboard(e) {
      const frame = getFrame()
      const m = computeMapVectorMatrix(frame)
      if (!m || !frame?.rootRect) return null
      const sx = e.clientX - frame.rootRect.left
      const sy = e.clientY - frame.rootRect.top
      const det = m.a * m.d - m.b * m.c
      if (Math.abs(det) < 1e-9) return null
      return {
        x: (m.d * (sx - m.tx) - m.c * (sy - m.ty)) / det,
        y: (-m.b * (sx - m.tx) + m.a * (sy - m.ty)) / det,
      }
    },
    getViewMatrix() {
      return computeMapVectorMatrix(getFrame()) ?? IDENTITY
    },
    getClipPath() {
      const frame = getFrame()
      const m = computeMapVectorMatrix(frame)
      if (!m || !frame?.canvas) return undefined
      const cw = frame.canvas.width
      const ch = frame.canvas.height
      const pts = [
        [0, 0],
        [cw, 0],
        [cw, ch],
        [0, ch],
      ].map(([x, y]) => {
        const p = { x: m.a * x + m.c * y + m.tx, y: m.b * x + m.d * y + m.ty }
        return `${p.x}px ${p.y}px`
      })
      return `polygon(${pts.join(', ')})`
    },
  }
}
