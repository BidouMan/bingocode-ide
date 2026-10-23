// 图像实例几何换算（世界坐标 ↔ 图片本地归一化坐标）
// MapCanvas 渲染使用 anchor=0.5 + 旋转，这里的换算与其保持一致

export const clamp01 = (v: number) => Math.max(0, Math.min(1, v))

export function getImageRectInfo(img: any) {
  const pos = img.position || [0, 0]
  const sx = img.scaleX ?? img.scale ?? 1
  const sy = img.scaleY ?? img.scale ?? 1
  const w = Math.max(1, (img.width || 64) * Math.abs(sx))
  const h = Math.max(1, (img.height || 64) * Math.abs(sy))
  return {
    x: pos[0],
    y: pos[1],
    w,
    h,
    cx: pos[0] + w / 2,
    cy: pos[1] + h / 2,
    rot: (img.rotation ?? 0) * Math.PI / 180,
  }
}

// 归一化本地坐标 → 世界坐标
export function imageLocalToWorld(img: any, p: { x: number; y: number }) {
  const r = getImageRectInfo(img)
  const lx = (p.x - 0.5) * r.w
  const ly = (p.y - 0.5) * r.h
  const cos = Math.cos(r.rot)
  const sin = Math.sin(r.rot)
  return { x: r.cx + lx * cos - ly * sin, y: r.cy + lx * sin + ly * cos }
}

export function imageWorldToLocal(img: any, x: number, y: number) {
  const r = getImageRectInfo(img)
  const dx = x - r.cx
  const dy = y - r.cy
  const cos = Math.cos(r.rot)
  const sin = Math.sin(r.rot)
  return { x: (dx * cos + dy * sin) / r.w + 0.5, y: (-dx * sin + dy * cos) / r.h + 0.5 }
}

// 吸附到图片像素，保证碰撞边缘清晰
export function snapImageLocal(img: any, p: { x: number; y: number }) {
  const iw = Math.max(1, img.width || 64)
  const ih = Math.max(1, img.height || 64)
  return {
    x: clamp01(Math.round(p.x * iw) / iw),
    y: clamp01(Math.round(p.y * ih) / ih),
  }
}

/** 吸附到图片像素但不限制在画面范围内（碰撞体允许超出图片边界） */
export function snapImageLocalFree(img: any, p: { x: number; y: number }) {
  const iw = Math.max(1, img.width || 64)
  const ih = Math.max(1, img.height || 64)
  return {
    x: Math.round(p.x * iw) / iw,
    y: Math.round(p.y * ih) / ih,
  }
}

// ====== 碰撞体命中测试（世界坐标） ======

export interface PointLike { x: number; y: number }

/** 射线法判断点是否在多边形内 */
export function pointInPolygon(p: PointLike, poly: PointLike[]): boolean {
  let inside = false
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const a = poly[i]
    const b = poly[j]
    if ((a.y > p.y) !== (b.y > p.y)
      && p.x < ((b.x - a.x) * (p.y - a.y)) / (b.y - a.y) + a.x) {
      inside = !inside
    }
  }
  return inside
}

function pointToSegmentDistance(p: PointLike, a: PointLike, b: PointLike): number {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const lenSq = dx * dx + dy * dy
  if (lenSq === 0) return Math.hypot(p.x - a.x, p.y - a.y)
  const t = Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / lenSq))
  return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy))
}

/** 点到多边形边界的最近距离 */
export function distanceToPolygon(p: PointLike, poly: PointLike[]): number {
  let best = Infinity
  for (let i = 0; i < poly.length; i++) {
    const d = pointToSegmentDistance(p, poly[i], poly[(i + 1) % poly.length])
    if (d < best) best = d
  }
  return best
}

function segmentsIntersect(a: PointLike, b: PointLike, c: PointLike, d: PointLike): boolean {
  const cross = (o: PointLike, p: PointLike, q: PointLike) =>
    (p.x - o.x) * (q.y - o.y) - (p.y - o.y) * (q.x - o.x)
  const d1 = cross(a, b, c)
  const d2 = cross(a, b, d)
  const d3 = cross(c, d, a)
  const d4 = cross(c, d, b)
  return ((d1 > 0) !== (d2 > 0) || d1 === 0 || d2 === 0)
    && ((d3 > 0) !== (d4 > 0) || d3 === 0 || d4 === 0)
}

/** 两个多边形是否相交（含包含关系） */
export function polygonsIntersect(a: PointLike[], b: PointLike[]): boolean {
  if (a.length < 3 || b.length < 3) return false
  if (a.some(p => pointInPolygon(p, b))) return true
  if (b.some(p => pointInPolygon(p, a))) return true
  for (let i = 0; i < a.length; i++) {
    const a1 = a[i]
    const a2 = a[(i + 1) % a.length]
    for (let j = 0; j < b.length; j++) {
      if (segmentsIntersect(a1, a2, b[j], b[(j + 1) % b.length])) return true
    }
  }
  return false
}
