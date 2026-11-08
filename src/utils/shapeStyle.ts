import type { ShapeItem, ShapeKind } from '../stores/map'

/**
 * 判定形状的展示规格（作用类型名称 / 颜色）。
 * 画布叠加层（Canvas）与属性面板（DOM）共用这一份，
 * 避免两边颜色各写一套、改一处漏一处。
 */

/** 类型（tag）预设：地图图块 / 形状 / 角色共用同一份常用玩法分类 */
export const SHAPE_TAG_PRESETS = ['墙体', '地面', '道具', '机关', '危险区']

/**
 * 角色碰撞类型预设：角色不按「地形」分类，而是按玩法身份分类。
 * 缺省「默认」覆盖没有特殊身份的普通角色；其余是代码里最常见的 is_touch 查询目标。
 */
export const SPRITE_COLLISION_TAG_PRESETS = ['默认', '玩家', '敌人', '道具', '子弹', '感应区']

/** 角色未设置类型时的默认值（引擎也按这个值处理空类型） */
export const SPRITE_DEFAULT_COLLISION_TAG = '默认'

/**
 * 单向碰撞方向四选一：值与引擎 oneWayDirX / oneWayDirY 一致（世界坐标，y 向下）。
 * 地图属性面板与角色编辑器共用，避免两边的方向含义/文案走样。
 */
export const ONE_WAY_DIRECTIONS = [
  { label: '从上方踩住', value: '0,1' },    // 下落时挡住
  { label: '从下方顶住', value: '0,-1' },   // 上升时挡住
  { label: '从左侧挡住', value: '1,0' },    // 向右走时挡住
  { label: '从右侧挡住', value: '-1,0' },   // 向左走时挡住
]

/** 碰撞材质选项：当前仅界面展示，运行时尚未接入 */
export const PHYSICS_MATERIAL_OPTIONS = [
  { label: '默认', value: 'default' },
  { label: '弹性', value: 'bouncy' },
  { label: '粗糙', value: 'friction' },
]

/** 作用类型中文名 */
export const SHAPE_KIND_LABELS: Record<ShapeKind, string> = {
  solid: '碰撞',
  sensor: '感应',
  both: '碰撞 + 感应',
}

/** 作用类型颜色（0xRRGGBB，画布叠加层用） */
export const SHAPE_KIND_COLORS_HEX: Record<ShapeKind, number> = {
  solid: 0xff5050,
  // 感应形状使用主题的强调绿（#5BFB84）
  sensor: 0x5bfb84,
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
