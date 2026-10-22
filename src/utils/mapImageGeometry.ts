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
