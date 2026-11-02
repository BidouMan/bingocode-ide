/**
 * 缩略图统一显示尺寸（px）：所有素材都按这个方框展示，
 * 小图取整数倍放大（16x16 → 4 倍 = 64px），大图缩进方框，整体改用像素渲染。
 * 想整体调大/调小只改这个常量即可。
 */
export const THUMB_SIZE = 64

export function fitPixelImage(img: HTMLImageElement, boxSize: number = THUMB_SIZE) {
  const { naturalWidth, naturalHeight } = img
  if (!naturalWidth || !naturalHeight) return

  if (naturalWidth <= boxSize && naturalHeight <= boxSize) {
    // 小于方框的像素图：整数倍放大，保证像素不糊
    const factor = Math.floor(Math.min(boxSize / naturalWidth, boxSize / naturalHeight))
    img.style.width = `${naturalWidth * factor}px`
    img.style.height = `${naturalHeight * factor}px`
  } else {
    // 超过方框的大图（背景、图集）：统一按方框缩小，由 CSS contain 保持比例
    img.style.width = `${boxSize}px`
    img.style.height = `${boxSize}px`
  }
  img.style.imageRendering = 'pixelated'
}

/** img @load 事件：加载完就按统一尺寸缩放（boxSize 不传时用默认缩略图尺寸） */
export function fitPixelThumb(event: Event, boxSize: number = THUMB_SIZE) {
  const img = event.currentTarget as HTMLImageElement | null
  if (img) fitPixelImage(img, boxSize)
}
