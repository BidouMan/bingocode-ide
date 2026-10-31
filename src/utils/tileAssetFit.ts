/**
 * 图块素材与地图网格的尺寸适配。
 *
 * 设计前提：一张地图只有一个格子尺寸（mapData.tileSize），所有图块层共用；
 * 图块集可以自带不同的原始尺寸，但进入地图前必须换算成当前格子尺寸，
 * 否则会出现「32 的图块跨 2×2 格、碰撞却只算 1 格」这类问题。
 *
 * 换算只做「整数倍」的最近邻缩放（16 ↔ 32 ↔ 64），像素风不会糊；
 * 非整数倍不做任何处理，交给调用方按原尺寸导入。
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

/**
 * 把整张图块图按整数倍缩放到目标格子尺寸。
 * 只缩放「完整图块」覆盖的区域，切片仍按目标格子尺寸走，因此切出来的图块数量不变。
 * 真实图集常有 1px 边角（如 191×192），这里把凑不满一格的残余裁掉，和原本按格切片的结果一致。
 * 无法整数倍换算时返回 null（调用方保持原样）。
 */
export async function fitTileSheet(
  dataUrl: string,
  nativeTileSize: number,
  gridSize: number,
): Promise<FittedTileSheet | null> {
  if (!canFitTileSize(nativeTileSize, gridSize) || nativeTileSize === gridSize) return null

  const img = await loadImageElement(dataUrl)
  if (img.width <= 0 || img.height <= 0) return null

  const cols = Math.floor(img.width / nativeTileSize)
  const rows = Math.floor(img.height / nativeTileSize)
  if (cols <= 0 || rows <= 0) return null

  const width = cols * gridSize
  const height = rows * gridSize
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')
  if (!ctx) return null

  // 最近邻：像素风整数倍缩放的唯一正确做法（关掉浏览器默认的双线性平滑）
  ctx.imageSmoothingEnabled = false
  // 源区域只取完整图块覆盖的范围，避免把右侧/底部的残余像素也缩放进来
  ctx.drawImage(img, 0, 0, cols * nativeTileSize, rows * nativeTileSize, 0, 0, width, height)

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
