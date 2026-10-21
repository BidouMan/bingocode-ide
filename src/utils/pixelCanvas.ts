/**
 * 把图片按「CSS 显示尺寸」重绘进 canvas，采样方式由自己控制。
 *
 * 为什么不用 `<img>` + `image-rendering: pixelated`：WKWebView 下被（任何祖先）
 * transform 放大的图层会走合成层平滑重采样，pixelated 直接被覆盖，小素材一放大就糊；
 * 而 canvas 由我们按目标像素绘制、`imageSmoothingEnabled=false` 即最近邻采样——
 * 等价于 Godot 里把纹理过滤设成 nearest，不受浏览器缩放路径影响。
 *
 * 后备缓冲策略（省显存）：
 * - 平滑模式：栅格最大只到自然尺寸，再往上放大交给浏览器平滑插值（观感等价、内存最省）
 * - 最近邻模式：按设备像素栅格（否则谈不上清晰），单边受 maxBackingPx 限制
 *
 * @param smooth true = 平滑（大插画缩小/放大），false = 最近邻（像素画、小素材）
 */
export function drawImageCrisp(
  canvas: HTMLCanvasElement,
  img: HTMLImageElement,
  cssW: number,
  cssH: number,
  smooth: boolean,
  maxBackingPx = 4096,
) {
  const naturalW = img.naturalWidth || img.width
  const naturalH = img.naturalHeight || img.height
  const cssMax = Math.max(cssW, cssH, 1)
  const dpr = window.devicePixelRatio || 1
  const targetMax = smooth
    ? Math.min(Math.max(naturalW, naturalH, 1), cssMax)
    : Math.min(cssMax * dpr, maxBackingPx)
  const backingScale = targetMax / cssMax

  const bw = Math.max(1, Math.round(cssW * backingScale))
  const bh = Math.max(1, Math.round(cssH * backingScale))
  // 改 width/height 会重置上下文状态，所以尺寸与状态都在绘制前设
  if (canvas.width !== bw) canvas.width = bw
  if (canvas.height !== bh) canvas.height = bh
  canvas.style.width = `${cssW}px`
  canvas.style.height = `${cssH}px`
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.clearRect(0, 0, bw, bh)
  ctx.imageSmoothingEnabled = smooth
  ctx.drawImage(img, 0, 0, bw, bh)
}
