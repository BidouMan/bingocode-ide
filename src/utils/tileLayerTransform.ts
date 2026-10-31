/**
 * 图块层整层变换（位置 / 缩放 / 旋转）
 *
 * 约定：
 * - 缩放以「地图中心」为基准（pivot = 地图像素尺寸的一半）
 * - 顺序：先缩放，再旋转，最后加位移
 * - 角度为世界角度（顺时针为正，单位度）；用户角度换算见 coords.ts
 *
 * 编辑器画布、绘制预览、画笔落点反算、引擎渲染与碰撞都共用这里的算法。
 */

export interface TileLayerTransform {
  /** 缩放基准点（世界像素） */
  pivotX: number
  pivotY: number
  scaleX: number
  scaleY: number
  /** 旋转角（世界角度，顺时针为正，单位度） */
  rotation: number
  offsetX: number
  offsetY: number
}

/** 由地图尺寸与图层字段生成变换参数 */
export function createLayerTransform(
  mapWidth: number,
  mapHeight: number,
  tileSize: number,
  layer?: { scaleX?: number; scaleY?: number; rotation?: number; offsetX?: number; offsetY?: number } | null,
): TileLayerTransform {
  return {
    pivotX: (mapWidth * tileSize) / 2,
    pivotY: (mapHeight * tileSize) / 2,
    scaleX: layer?.scaleX ?? 1,
    scaleY: layer?.scaleY ?? 1,
    rotation: layer?.rotation ?? 0,
    offsetX: layer?.offsetX ?? 0,
    offsetY: layer?.offsetY ?? 0,
  }
}

/** 正向变换：原始世界坐标 → 变换后世界坐标 */
export function transformPoint(t: TileLayerTransform, x: number, y: number): { x: number; y: number } {
  let dx = (x - t.pivotX) * t.scaleX
  let dy = (y - t.pivotY) * t.scaleY
  if (t.rotation !== 0) {
    const rad = (t.rotation * Math.PI) / 180
    const cos = Math.cos(rad)
    const sin = Math.sin(rad)
    const rx = dx * cos - dy * sin
    const ry = dx * sin + dy * cos
    dx = rx
    dy = ry
  }
  return { x: t.pivotX + dx + t.offsetX, y: t.pivotY + dy + t.offsetY }
}

/** 逆变换：变换后世界坐标 → 原始世界坐标 */
export function inverseTransformPoint(t: TileLayerTransform, x: number, y: number): { x: number; y: number } {
  let dx = x - t.offsetX - t.pivotX
  let dy = y - t.offsetY - t.pivotY
  if (t.rotation !== 0) {
    const rad = (-t.rotation * Math.PI) / 180
    const cos = Math.cos(rad)
    const sin = Math.sin(rad)
    const rx = dx * cos - dy * sin
    const ry = dx * sin + dy * cos
    dx = rx
    dy = ry
  }
  // 缩放为 0 时无法反算，按 1 处理避免除零
  const sx = t.scaleX === 0 ? 1 : t.scaleX
  const sy = t.scaleY === 0 ? 1 : t.scaleY
  return { x: t.pivotX + dx / sx, y: t.pivotY + dy / sy }
}

/** 变换后的世界坐标 → 格子坐标 */
export function worldToTile(
  t: TileLayerTransform,
  worldX: number,
  worldY: number,
  tileSize: number,
): { x: number; y: number } {
  const base = inverseTransformPoint(t, worldX, worldY)
  return {
    x: Math.floor(base.x / tileSize),
    y: Math.floor(base.y / tileSize),
  }
}

/**
 * 图块精灵在变换后的摆放：锚点取图块图片中心，位置与整体缩放/旋转同步。
 * 未变换时与原「左上角对齐格子」的视觉完全一致。
 */
export function tileSpriteTransform(
  t: TileLayerTransform,
  col: number,
  row: number,
  tileSize: number,
  tileWidth: number,
  tileHeight: number,
): { x: number; y: number; rotation: number; scaleX: number; scaleY: number } {
  const centerX = col * tileSize + tileWidth / 2
  const centerY = row * tileSize + tileHeight / 2
  const p = transformPoint(t, centerX, centerY)
  return {
    x: p.x,
    y: p.y,
    rotation: (t.rotation * Math.PI) / 180,
    scaleX: t.scaleX,
    scaleY: t.scaleY,
  }
}

/** 图块四边形在变换后的四个世界角点（绘制预览用） */
export function tileQuad(
  t: TileLayerTransform,
  col: number,
  row: number,
  tileSize: number,
): { x: number; y: number }[] {
  const x0 = col * tileSize
  const y0 = row * tileSize
  return [
    transformPoint(t, x0, y0),
    transformPoint(t, x0 + tileSize, y0),
    transformPoint(t, x0 + tileSize, y0 + tileSize),
    transformPoint(t, x0, y0 + tileSize),
  ]
}
