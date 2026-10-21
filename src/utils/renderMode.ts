/**
 * 渲染模式（平滑 / 像素 / 自动）与「自动」判定的唯一出处。
 *
 * 为什么按素材尺寸判：双线性（smooth）只在**缩小**时正确——放大时它只会把已有像素
 * 抹开来凑面积，观感就是糊；最近邻（pixelated）只在**放大/1:1** 时正确，缩小会抽样
 * 丢细节、边缘抖动。而角色素材在 640×480 舞台上、在角色编辑器的画布/预览/缩略图里
 * 几乎总是被放大显示（预览区 248px 上限对 108px 素材是 2.3 倍放大，46px 素材是 5 倍），
 * 所以「小图」应一律最近邻；「大图」（插画）常被缩小或 1:1 显示，必须平滑。
 *
 * 内置素材实测（2026-10-21）：46 个 .bsf 里 42 个画布最大边 ≤128px（帧 rect 最小 12px），
 * 57 张单图 PNG 里 45 张 ≤136px（108px 道具、128~136px 角色），仅 12 张 196~500px 插画。
 */
export type RenderMode = 'auto' | 'smooth' | 'pixelated'

/** 小图阈值（自然尺寸最大边，像素）：≤ 此值按像素画处理，走最近邻 */
export const SMALL_ART_MAX_SIDE = 128

/**
 * 解析实际采样方式。
 * @param naturalW/naturalH 素材自然尺寸（.bsf 取 canvas 或帧 rect，不能取 sheet 尺寸）
 */
export function effectiveScaleMode(
  mode: RenderMode,
  naturalW?: number,
  naturalH?: number
): 'nearest' | 'linear' {
  if (mode === 'pixelated') return 'nearest'
  if (mode === 'smooth') return 'linear'
  // 自动：尺寸未知时保守走平滑（大图缩小是更常见的场景，缩小时最近邻更糟）
  if (!naturalW || !naturalH) return 'linear'
  return Math.max(naturalW, naturalH) <= SMALL_ART_MAX_SIDE ? 'nearest' : 'linear'
}

/** CSS `image-rendering` 取值（<img> 面用：角色编辑器画布/预览/造型缩略图） */
export function cssImageRendering(
  mode: RenderMode,
  naturalW?: number,
  naturalH?: number
): 'pixelated' | 'auto' {
  return effectiveScaleMode(mode, naturalW, naturalH) === 'nearest' ? 'pixelated' : 'auto'
}
