// SVG 超采样光栅化（借鉴 scratch-render 的 SVGRasterizer）
// GPU 只认位图：SVG 进纹理前先按 scale 倍画到 canvas，放大查看时更清晰。
// 逻辑尺寸保持 1x —— 配合 TextureSource.resolution 使用，布局/帧切割的坐标计算不受影响。

export const SVG_RASTER_SCALE = 2

export function isSvgSource(src: string): boolean {
  return src.startsWith('data:image/svg+xml') || /\.svg(\?|#|$)/i.test(src)
}

export function rasterizeSvgImage(img: HTMLImageElement, scale = SVG_RASTER_SCALE): HTMLCanvasElement {
  const w = img.naturalWidth || img.width
  const h = img.naturalHeight || img.height
  const canvas = document.createElement('canvas')
  canvas.width = Math.max(1, Math.round(w * scale))
  canvas.height = Math.max(1, Math.round(h * scale))
  const ctx = canvas.getContext('2d')!
  ctx.imageSmoothingEnabled = true
  ctx.imageSmoothingQuality = 'high'
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
  return canvas
}
