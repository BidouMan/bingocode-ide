/**
 * 扫描线洪水填充（标准算法，自研实现）
 * 对 ImageData 就地填充：从种子点向四周扩散，替换与种子颜色在容差内的连续区域。
 */

export interface RGBA {
  r: number
  g: number
  b: number
  a: number
}

/** 每通道容差：抗锯齿边缘留下的半混合像素也能被吞掉，避免填充后残留描边 */
const TOLERANCE = 32

function closeEnough(data: Uint8ClampedArray, idx: number, target: RGBA): boolean {
  return (
    Math.abs(data[idx] - target.r) <= TOLERANCE &&
    Math.abs(data[idx + 1] - target.g) <= TOLERANCE &&
    Math.abs(data[idx + 2] - target.b) <= TOLERANCE &&
    Math.abs(data[idx + 3] - target.a) <= TOLERANCE
  )
}

/**
 * 从 (x, y) 种子点填充。
 * @returns 被填充的像素数（0 表示颜色相同未产生变化）
 */
export function floodFill(
  imageData: ImageData,
  x: number,
  y: number,
  color: RGBA
): number {
  const { width, height, data } = imageData
  x = Math.floor(x)
  y = Math.floor(y)
  if (x < 0 || y < 0 || x >= width || y >= height) return 0

  const seedIdx = (y * width + x) * 4
  const target: RGBA = {
    r: data[seedIdx],
    g: data[seedIdx + 1],
    b: data[seedIdx + 2],
    a: data[seedIdx + 3],
  }

  // 目标色与填充色足够接近时无需填充
  if (
    Math.abs(target.r - color.r) <= 1 &&
    Math.abs(target.g - color.g) <= 1 &&
    Math.abs(target.b - color.b) <= 1 &&
    Math.abs(target.a - color.a) <= 1
  ) {
    return 0
  }

  // 扫描线：每行用栈保存区段起点，避免逐像素递归
  const stack: [number, number][] = [[x, y]]
  let filled = 0

  while (stack.length > 0) {
    const [px, py] = stack.pop()!
    let xi = px
    const idxBase = py * width * 4

    // 向左扩展到区域边界
    while (xi >= 0 && closeEnough(data, idxBase + xi * 4, target)) xi--
    xi++

    let spanUp = false
    let spanDown = false

    // 向右扫描一行
    while (xi < width && closeEnough(data, idxBase + xi * 4, target)) {
      const i = idxBase + xi * 4
      data[i] = color.r
      data[i + 1] = color.g
      data[i + 2] = color.b
      data[i + 3] = color.a
      filled++

      if (py > 0) {
        const up = i - width * 4
        const match = closeEnough(data, up, target)
        if (match && !spanUp) {
          stack.push([xi, py - 1])
          spanUp = true
        } else if (!match) {
          spanUp = false
        }
      }
      if (py < height - 1) {
        const down = i + width * 4
        const match = closeEnough(data, down, target)
        if (match && !spanDown) {
          stack.push([xi, py + 1])
          spanDown = true
        } else if (!match) {
          spanDown = false
        }
      }
      xi++
    }
  }

  return filled
}
