/**
 * 图块素材与地图网格的尺寸适配。
 *
 * 设计前提：一张地图只有一个格子尺寸（mapData.tileSize），所有图块层共用；
 * 图块集可以自带不同的原始尺寸，但进入地图前必须换算成当前格子尺寸，
 * 否则会出现「32 的图块跨 2×2 格、碰撞却只算 1 格」这类问题。
 *
 * 换算一律用最近邻（像素风不糊）：
 * - 整数倍（16 ↔ 32 ↔ 64）整张图一次性缩放，速度最快；
 * - 非整数倍（如 24 → 16）逐块缩放，保证每块都正好落进格子里，不会累积错位。
 */

/** 常见的单图块边长（单张图片即一个图块时使用） */
const SINGLE_TILE_SIZES = [8, 12, 16, 24, 32, 48, 64]

/** 判断两个尺寸能否整数倍互转（16↔32、32↔64 可以，16↔24 不行） */
export function canFitTileSize(native: number, grid: number): boolean {
  if (!Number.isFinite(native) || !Number.isFinite(grid) || native <= 0 || grid <= 0) return false
  if (native === grid) return true
  return native % grid === 0 || grid % native === 0
}

/**
 * 识别「单张图片就是一个图块」时的原始尺寸。
 * 只认正方形且边长在常见范围内的小图，避免把整张图集误判成一个大图块。
 */
export function detectSingleTileSize(width: number, height: number): number | null {
  if (width !== height) return null
  return SINGLE_TILE_SIZES.includes(width) ? width : null
}

/** 读取图片（data URL / 文件 URL 均可） */
export function loadImageElement(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error(`图片加载失败: ${src.slice(0, 64)}`))
    img.src = src
  })
}

export interface FittedTileSheet {
  dataUrl: string
  width: number
  height: number
}

/** 浏览器 canvas 能安全分配的尺寸上限（超过就放弃换算，避免直接崩掉 WebView） */
const MAX_CANVAS_SIDE = 8192
const MAX_CANVAS_AREA = 33_554_432

/**
 * 把整张图块图归一化到目标格子尺寸（最近邻，不糊）。
 * 只处理「完整图块」覆盖的区域，凑不满一格的边角残余会被裁掉，和按格切片的结果一致。
 * - 整数倍：整图一次缩放（快）；
 * - 非整数倍：逐块缩放，避免每块的位置累积误差。
 * 尺寸相同或无法换算时返回 null（调用方按原样处理）。
 */
export async function fitTileSheet(
  dataUrl: string,
  nativeTileSize: number,
  gridSize: number,
): Promise<FittedTileSheet | null> {
  if (
    !Number.isFinite(nativeTileSize) || !Number.isFinite(gridSize)
    || nativeTileSize <= 0 || gridSize <= 0 || nativeTileSize === gridSize
  ) return null

  const img = await loadImageElement(dataUrl)
  if (img.width <= 0 || img.height <= 0) return null

  const cols = Math.floor(img.width / nativeTileSize)
  const rows = Math.floor(img.height / nativeTileSize)
  if (cols <= 0 || rows <= 0) return null

  const width = cols * gridSize
  const height = rows * gridSize
  if (width > MAX_CANVAS_SIDE || height > MAX_CANVAS_SIDE || width * height > MAX_CANVAS_AREA) {
    console.warn('[TileFit] 目标画布过大，跳过尺寸归一化:', width, height)
    return null
  }

  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) return null

  // 最近邻：像素风缩放的唯一正确做法（关掉浏览器默认的双线性平滑）
  ctx.imageSmoothingEnabled = false

  if (canFitTileSize(nativeTileSize, gridSize)) {
    // 整数倍：源区域只取完整图块覆盖的范围，避免把右侧/底部的残余像素也缩放进来
    ctx.drawImage(img, 0, 0, cols * nativeTileSize, rows * nativeTileSize, 0, 0, width, height)
  } else {
    // 非整数倍（如 24 → 16）：每块单独缩放后画到对应格子，块与块之间不会错位
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        ctx.drawImage(
          img,
          c * nativeTileSize, r * nativeTileSize, nativeTileSize, nativeTileSize,
          c * gridSize, r * gridSize, gridSize, gridSize,
        )
      }
    }
  }

  return { dataUrl: canvas.toDataURL('image/png'), width, height }
}

/** data URL → 字节数组（写入项目文件用） */
export function dataUrlToBytes(dataUrl: string): number[] {
  const base64 = dataUrl.slice(dataUrl.indexOf(',') + 1)
  const binary = atob(base64)
  const bytes = new Array<number>(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return bytes
}

/** 传原始素材的相对路径，生成某个格子尺寸下的派生文件名：foo.png → foo@32.png（固定 png） */
export function derivedTilePath(originPath: string, gridSize: number): string {
  const slash = originPath.lastIndexOf('/')
  const dir = slash >= 0 ? originPath.slice(0, slash + 1) : ''
  const fileName = slash >= 0 ? originPath.slice(slash + 1) : originPath
  const dot = fileName.lastIndexOf('.')
  const base = dot > 0 ? fileName.slice(0, dot) : fileName
  return `${dir}${base}@${gridSize}.png`
}
