// 地图编辑器「智能吸附」（参考 Godot 2D 编辑器）
// 开启时在候选线里就近吸附：像素整数、网格线、图像图层边缘/中心、地图边界。
// 关闭时由调用方直接使用原始坐标（本模块不做任何处理）。

/** 吸附触发距离（屏幕像素，随画布缩放换算成世界坐标） */
export const SMART_SNAP_SCREEN_PX = 8

export interface SnapLines {
  xs: number[]
  ys: number[]
}

/** 屏幕像素阈值 → 世界坐标距离 */
export function snapThreshold(scale: number): number {
  return SMART_SNAP_SCREEN_PX / Math.max(0.1, scale)
}

/**
 * 单值吸附：优先就近吸附候选线（图像边缘/中心、地图边界）；
 * 其次是网格线（只在离格线较近时生效，避免所有点都被拉到网格上）；
 * 都没有时兜底到像素整数。
 */
export function snapAxisValue(value: number, lines: number[], grid: number, threshold: number): number {
  let best = value
  let bestDist = Infinity
  const consider = (candidate: number) => {
    const dist = Math.abs(candidate - value)
    if (dist < bestDist) {
      bestDist = dist
      best = candidate
    }
  }
  for (const line of lines) consider(line)
  // 网格只在小范围内吸附加持，保持像素级微调的余地
  const gridLimit = Math.min(threshold, grid > 0 ? grid / 3 : 0)
  if (grid > 0) {
    const snapped = Math.round(value / grid) * grid
    if (Math.abs(snapped - value) <= gridLimit) consider(snapped)
  }
  if (Number.isFinite(bestDist) && bestDist <= threshold) return best
  // 像素吸附兜底
  return Math.round(value)
}

/**
 * 矩形移动吸附：让矩形的 左/中/右、上/中/下 就近对齐候选线（或网格线）。
 * 附近没有线时按像素吸附（左上角对齐整数像素）。
 * 返回需要施加的位移。
 */
export function snapRectOffset(
  rect: { left: number; top: number; right: number; bottom: number },
  lines: SnapLines,
  grid: number,
  threshold: number,
): { dx: number; dy: number } {
  const axisDelta = (anchors: number[], candidates: number[], pixelAnchor: number): number => {
    let bestDelta = 0
    let bestDist = Infinity
    const consider = (anchor: number, target: number) => {
      const dist = Math.abs(target - anchor)
      if (dist < bestDist) {
        bestDist = dist
        bestDelta = target - anchor
      }
    }
    for (const anchor of anchors) {
      for (const candidate of candidates) consider(anchor, candidate)
      if (grid > 0) {
        const snapped = Math.round(anchor / grid) * grid
        if (Math.abs(snapped - anchor) <= Math.min(threshold, grid / 3)) consider(anchor, snapped)
      }
    }
    if (bestDist <= threshold) return bestDelta
    // 像素吸附兜底：左上角对齐整数像素
    return Math.round(pixelAnchor) - pixelAnchor
  }
  return {
    dx: axisDelta([rect.left, (rect.left + rect.right) / 2, rect.right], lines.xs, rect.left),
    dy: axisDelta([rect.top, (rect.top + rect.bottom) / 2, rect.bottom], lines.ys, rect.top),
  }
}

export interface SnapImageLike {
  imagePath?: string
  position?: number[]
  width?: number
  height?: number
  scale?: number
  scaleX?: number
  scaleY?: number
  rotation?: number
}

export interface SnapLayerLike {
  id?: number
  type?: string
  visible?: boolean
  image?: SnapImageLike | null
}

/** 图像图层在世界坐标下的矩形（旋转时取四角 AABB） */
export function imageWorldRect(img: SnapImageLike): { left: number; top: number; right: number; bottom: number } | null {
  const sx = Math.abs(img.scaleX ?? img.scale ?? 1)
  const sy = Math.abs(img.scaleY ?? img.scale ?? 1)
  const w = (img.width || 0) * sx
  const h = (img.height || 0) * sy
  if (w <= 0 || h <= 0) return null
  const x = img.position?.[0] ?? 0
  const y = img.position?.[1] ?? 0
  const rot = ((img.rotation ?? 0) * Math.PI) / 180
  if (Math.abs(rot) < 1e-6) {
    return { left: x, top: y, right: x + w, bottom: y + h }
  }
  const cx = x + w / 2
  const cy = y + h / 2
  const cos = Math.cos(rot)
  const sin = Math.sin(rot)
  const corners = [
    [-w / 2, -h / 2], [w / 2, -h / 2], [w / 2, h / 2], [-w / 2, h / 2],
  ].map(([lx, ly]) => ({ x: cx + lx * cos - ly * sin, y: cy + lx * sin + ly * cos }))
  const xs = corners.map(c => c.x)
  const ys = corners.map(c => c.y)
  return {
    left: Math.min(...xs),
    top: Math.min(...ys),
    right: Math.max(...xs),
    bottom: Math.max(...ys),
  }
}

/**
 * 收集吸附候选线：可见图像图层的边缘与中心 + 地图边界。
 * excludeLayerId：正在拖动的图层，避免吸附到自身。
 */
export function collectSnapLines(
  layers: SnapLayerLike[],
  mapWidth: number,
  mapHeight: number,
  excludeLayerId?: number,
): SnapLines {
  const xs: number[] = [0, mapWidth]
  const ys: number[] = [0, mapHeight]
  for (const layer of layers) {
    if (layer.type !== 'image' || !layer.visible) continue
    if (excludeLayerId !== undefined && layer.id === excludeLayerId) continue
    if (!layer.image?.imagePath) continue
    const rect = imageWorldRect(layer.image)
    if (!rect) continue
    xs.push(rect.left, (rect.left + rect.right) / 2, rect.right)
    ys.push(rect.top, (rect.top + rect.bottom) / 2, rect.bottom)
  }
  return { xs, ys }
}
