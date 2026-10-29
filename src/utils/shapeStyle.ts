import type { ShapeItem, ShapeKind } from '../stores/map'

/**
 * 判定形状的展示规格（作用类型名称 / 颜色）。
 * 画布叠加层（Canvas）与属性面板（DOM）共用这一份，
 * 避免两边颜色各写一套、改一处漏一处。
 */

/** 作用类型中文名 */
export const SHAPE_KIND_LABELS: Record<ShapeKind, string> = {
  solid: '碰撞',
  sensor: '感应',
  both: '碰撞 + 感应',
}

/** 作用类型颜色（0xRRGGBB，画布叠加层用） */
export const SHAPE_KIND_COLORS_HEX: Record<ShapeKind, number> = {
  solid: 0xff5050,
  sensor: 0xe5c07b,
  both: 0x528bff,
}

/** 禁用形状统一灰色 */
export const SHAPE_DISABLED_COLOR_HEX = 0x888888

/** 形状颜色（数值形式，画布叠加层用）：禁用统一灰色，否则按能力类型 */
export function shapeColorHex(shape: ShapeItem): number {
  if (shape.disabled) return SHAPE_DISABLED_COLOR_HEX
  const kind = (shape.kind || 'solid') as ShapeKind
  return SHAPE_KIND_COLORS_HEX[kind] ?? SHAPE_KIND_COLORS_HEX.solid
}

/** 形状颜色（CSS 字符串，属性面板列表圆点用），与画布保持同一套颜色 */
export function shapeColorCss(shape: ShapeItem): string {
  return `#${shapeColorHex(shape).toString(16).padStart(6, '0')}`
}

/** 作用类型中文名（容错：旧数据缺 kind 时按碰撞显示） */
export function shapeKindLabel(kind: string | undefined): string {
  const key = (kind || 'solid') as ShapeKind
  return SHAPE_KIND_LABELS[key] ?? SHAPE_KIND_LABELS.solid
}
