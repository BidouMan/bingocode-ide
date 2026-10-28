// 全应用统一的「框选」样式（角色绘制页 / 地图绘制 / 形状图层共用）
// 靛蓝描边 + 10% 填充；线宽按屏幕像素恒定，不随画布缩放变粗变细。

/** 主色：框选边框与选区主描边（rgb 129, 140, 248） */
export const SELECTION_COLOR = '#818cf8'
export const SELECTION_COLOR_RGB = '129, 140, 248'
/** 同系加深：手柄/旋转点描边（白底上保对比） */
export const SELECTION_COLOR_DEEP = '#6366f1'

/** Pixi / Canvas2D 使用的数值形式 */
export const SELECTION_COLOR_HEX = 0x818cf8
export const SELECTION_COLOR_DEEP_HEX = 0x6366f1

/** 选区填充透明度 */
export const SELECTION_FILL_ALPHA = 0.1
/** 选区边框线宽（屏幕像素） */
export const SELECTION_STROKE_PX = 1.4
