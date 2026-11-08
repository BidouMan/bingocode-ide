/**
 * 渲染模式（平滑 / 像素 / 自动）与「自动」判定的唯一出处。
 *
 * 自动模式优先看**画风**：扫描素材像素，调色板颜色很少、且颜色交界几乎都是硬边，
 * 就是像素画（走最近邻）；颜色丰富或边缘带大量过渡色，就是插画/大图（走平滑）。
 * 单纯按尺寸判会误伤：132px 的大鲨鱼是像素画，100px 的插画角色反而是平滑画风。
 * 尺寸只在画风无法判定时兜底（素材太小、纯色块、或还没来得及分析）。
 *
 * 为什么像素画要最近邻、插画要平滑：双线性（smooth）只在**缩小**时正确——放大时它
 * 只会把已有像素抹开来凑面积，观感就是糊；最近邻（pixelated）在**放大/1:1** 时最锐利，
 * 像素画的色块边界才能保持干净。
 *
 * 瓦片注意：瓦片贴图是图集子纹理，「内容尺寸」是图集格子尺寸（tileWidth/Height），
 * 绝不能拿图集整图尺寸判定——一张 16px 格的图集轻松超过 128px，会误判成大插画走平滑。
 * 瓦片/图像层的判定在 GameCanvas 的 syncTiles 里做（同款 WeakMap 逐源缓存），
 * 本文件只提供统一的阈值与解析函数。
 */
export type RenderMode = 'auto' | 'smooth' | 'pixelated'

/** 小图阈值（自然尺寸最大边，像素）：无法分析画风时，≤ 此值按像素画处理 */
export const SMALL_ART_MAX_SIDE = 128

/** 像素画调色板上限：超过这个颜色数基本就是插画/照片 */
const PIXEL_ART_MAX_COLORS = 256
/** 硬边占比下限：颜色交界里 ≥ 此比例是硬边，才认为是有意为之的像素画 */
const PIXEL_ART_MIN_HARD_EDGE_RATIO = 0.6
/** 单像素通道差 ≥ 此值算硬边，小于它但仍有差异算过渡（抗锯齿/渐变） */
const HARD_EDGE_DELTA = 24
/** 分析前把素材缩到最大 256px，控制耗时（最近邻采样，不额外制造过渡色） */
const ANALYSIS_MAX_SIDE = 256

let analyzeCanvas: HTMLCanvasElement | null = null

/**
 * 像素风判定（结果按解码后的图像对象缓存一次）。
 * 角色编辑器、游戏内渲染、缩略图生成都调这里，保证同一素材各处判定一致。
 * @returns true=像素画，false=插画/照片，null=信息不足（交给尺寸兜底）
 */
export function detectPixelArt(
  img: CanvasImageSource,
  naturalW?: number,
  naturalH?: number
): boolean | null {
  if (typeof document === 'undefined') return null
  if (!naturalW || !naturalH) return null
  if (typeof img !== 'object' || img === null) return null
  const cached = artStyleCache.get(img)
  if (cached !== undefined) return cached
  const result = analyzePixelArt(img, naturalW, naturalH)
  artStyleCache.set(img, result)
  return result
}

/** 同一次分析会被多处复用：按图像对象缓存（WeakMap 不阻止图片回收） */
const artStyleCache = new WeakMap<object, boolean | null>()

function analyzePixelArt(
  img: CanvasImageSource,
  naturalW: number,
  naturalH: number
): boolean | null {
  try {
    const scale = Math.min(1, ANALYSIS_MAX_SIDE / Math.max(naturalW, naturalH))
    const w = Math.max(1, Math.round(naturalW * scale))
    const h = Math.max(1, Math.round(naturalH * scale))
    if (!analyzeCanvas) analyzeCanvas = document.createElement('canvas')
    const canvas = analyzeCanvas
    canvas.width = w
    canvas.height = h
    const ctx = canvas.getContext('2d', { willReadFrequently: true })
    if (!ctx) return null
    // 最近邻缩采样：平滑插值会凭空造出过渡色，把像素画误判成插画
    ctx.imageSmoothingEnabled = false
    ctx.clearRect(0, 0, w, h)
    ctx.drawImage(img, 0, 0, w, h)
    const data = ctx.getImageData(0, 0, w, h).data

    const colors = new Set<number>()
    let hard = 0
    let soft = 0
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const i = (y * w + x) * 4
        if (data[i + 3] < 10) continue
        const key = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2]
        colors.add(key)
        // 调色板已超出像素画的上限：直接判定为插画，省掉剩下的全图扫描
        if (colors.size > PIXEL_ART_MAX_COLORS) return false

        // 只比较右 / 下邻居（一半遍历量足够统计边缘硬度）
        if (x + 1 < w) {
          const j = i + 4
          if (data[j + 3] >= 10) {
            const d = Math.max(
              Math.abs(data[i] - data[j]),
              Math.abs(data[i + 1] - data[j + 1]),
              Math.abs(data[i + 2] - data[j + 2]),
            )
            if (d >= HARD_EDGE_DELTA) hard++
            else if (d > 0) soft++
          }
        }
        if (y + 1 < h) {
          const j = i + w * 4
          if (data[j + 3] >= 10) {
            const d = Math.max(
              Math.abs(data[i] - data[j]),
              Math.abs(data[i + 1] - data[j + 1]),
              Math.abs(data[i + 2] - data[j + 2]),
            )
            if (d >= HARD_EDGE_DELTA) hard++
            else if (d > 0) soft++
          }
        }
      }
    }

    const edges = hard + soft
    // 几乎是纯色块 / 素材太小：没有足够样本，交给尺寸兜底
    if (edges < 40) return null
    return hard / edges >= PIXEL_ART_MIN_HARD_EDGE_RATIO
  } catch {
    // 跨域图片或 canvas 不可读：保持兜底
    return null
  }
}

/**
 * 解析实际采样方式。
 * @param naturalW/naturalH 素材自然尺寸（.bsf 取 canvas 或帧 rect，不能取 sheet 尺寸）
 * @param pixelArt 画风判定结果（detectPixelArt）；自动模式优先使用
 */
export function effectiveScaleMode(
  mode: RenderMode,
  naturalW?: number,
  naturalH?: number,
  pixelArt?: boolean | null
): 'nearest' | 'linear' {
  if (mode === 'pixelated') return 'nearest'
  if (mode === 'smooth') return 'linear'
  // 自动：画风已判定就直接照做（132px 的像素画也能保持锐利）
  if (pixelArt === true) return 'nearest'
  if (pixelArt === false) return 'linear'
  // 画风未知时按尺寸兜底；尺寸也未知则保守走平滑
  if (!naturalW || !naturalH) return 'linear'
  return Math.max(naturalW, naturalH) <= SMALL_ART_MAX_SIDE ? 'nearest' : 'linear'
}

/** CSS `image-rendering` 取值（<img> 面用：角色编辑器画布/预览/造型缩略图） */
export function cssImageRendering(
  mode: RenderMode,
  naturalW?: number,
  naturalH?: number,
  pixelArt?: boolean | null
): 'pixelated' | 'auto' {
  return effectiveScaleMode(mode, naturalW, naturalH, pixelArt) === 'nearest' ? 'pixelated' : 'auto'
}
