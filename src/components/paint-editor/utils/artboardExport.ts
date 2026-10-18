/** 画板导出工具：把当前绘制内容导出为 PNG Blob（保存管线第一步） */

/** canvas → PNG Blob（canvas 自带透明背景，棋盘格只是视图辅助不进导出） */
export function exportCanvasPngBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (blob) resolve(blob)
      else reject(new Error('画板导出 PNG 失败：toBlob 返回空'))
    }, 'image/png')
  })
}

/**
 * 按画板逻辑尺寸导出 PNG。
 * HiDPI 下 canvas 后备缓冲是物理像素（如 Retina 960×720），直接导出会得到
 * 随机器变化的分辨率——输出必须恒等于用户选择的画板尺寸（480×360），
 * 因此先高质量缩到逻辑尺寸再编码（等效 2x 超采样，边缘质量反而更好）。
 */
export function exportArtboardPngBlob(
  canvas: HTMLCanvasElement,
  logicalWidth: number,
  logicalHeight: number
): Promise<Blob> {
  if (canvas.width === logicalWidth && canvas.height === logicalHeight) {
    return exportCanvasPngBlob(canvas)
  }
  const off = document.createElement('canvas')
  off.width = logicalWidth
  off.height = logicalHeight
  const oc = off.getContext('2d')
  if (!oc) return exportCanvasPngBlob(canvas)
  oc.imageSmoothingEnabled = true
  oc.imageSmoothingQuality = 'high'
  oc.drawImage(canvas, 0, 0, logicalWidth, logicalHeight)
  return exportCanvasPngBlob(off)
}

/** hex 颜色 + 0-100 透明度 → CSS rgba() 字符串 */
export function rgbaCss(hex: string, opacityPercent: number): string {
  const m = hex.match(/^#?([0-9a-f]{6})$/i)
  if (!m) return hex
  const n = parseInt(m[1], 16)
  const r = (n >> 16) & 0xff
  const g = (n >> 8) & 0xff
  const b = n & 0xff
  const a = Math.max(0, Math.min(100, opacityPercent)) / 100
  return `rgba(${r}, ${g}, ${b}, ${a})`
}

/** hex → RGBA 分量 */
export function hexToRgba(hex: string, opacityPercent: number): { r: number; g: number; b: number; a: number } {
  const m = hex.match(/^#?([0-9a-f]{6})$/i)
  if (!m) return { r: 0, g: 0, b: 0, a: 1 }
  const n = parseInt(m[1], 16)
  return {
    r: (n >> 16) & 0xff,
    g: (n >> 8) & 0xff,
    b: n & 0xff,
    a: Math.max(0, Math.min(100, opacityPercent)) / 100,
  }
}
