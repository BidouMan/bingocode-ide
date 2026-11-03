/**
 * 缩略图统一显示尺寸（px）：所有素材都按这个方框展示，
 * 小图取整数倍放大（16x16 → 4 倍 = 64px），大图缩进方框，整体改用像素渲染。
 * 想整体调大/调小只改这个常量即可。
 */
export const THUMB_SIZE = 64

export function fitPixelImage(img: HTMLImageElement) {
  // 尺寸统一交给 CSS 的固定方框 + object-fit: contain 处理；
  // 这里只保证像素图按最近邻缩放，不被浏览器双线性插值模糊。
  // 同时清掉可能残留的内联宽高，避免覆盖 CSS 的 100% 尺寸。
  img.style.imageRendering = 'pixelated'
  img.style.width = ''
  img.style.height = ''
}

/** img @load 事件：加载完就应用像素渲染（尺寸由 CSS 控制） */
export function fitPixelThumb(event: Event) {
  const img = event.currentTarget as HTMLImageElement | null
  if (img) fitPixelImage(img)
}
