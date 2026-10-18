/**
 * 扫描线洪水填充（标准算法 + 抗锯齿边缘处理，自研实现）
 * 对 ImageData 就地填充：从种子点向四周扩散，替换与种子颜色接近的连续区域。
 *
 * 匹配规则（解决填充后描边留缝隙）：
 * - 目标是透明区（alpha=0）：只填充完全透明的像素，不蚕食描边的抗锯齿边缘
 * - 目标是有色区（alpha>0）：RGB 接近且 alpha>0 即命中——把与描边同色的半透明
 *   抗锯齿边缘一并纳入填充，并保留其原始 alpha 作为边缘覆盖率 → 填充无缝隙且
 *   边缘过渡仍然平滑（这正是位图软件处理抗锯齿边界的通用做法）
 */

export interface RGBA {
  r: number
  g: number
  b: number
  /** 0-255（ImageData 通道约定，不是 CSS 的 0-1） */
  a: number
}

/** RGB 容差：吸收渲染器在边缘产生的轻微通道抖动 */
const RGB_TOLERANCE = 32

function rgbClose(data: Uint8ClampedArray, idx: number, t: RGBA): boolean {
  return (
    Math.abs(data[idx] - t.r) <= RGB_TOLERANCE &&
    Math.abs(data[idx + 1] - t.g) <= RGB_TOLERANCE &&
    Math.abs(data[idx + 2] - t.b) <= RGB_TOLERANCE
  )
}

/**
 * 从 (x, y) 种子点填充。
 * @param color 填充色（alpha 为 0-255）
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

  // 目标色与填充色几乎一致时无需填充
  if (
    target.a === color.a &&
    Math.abs(target.r - color.r) <= 1 &&
    Math.abs(target.g - color.g) <= 1 &&
    Math.abs(target.b - color.b) <= 1
  ) {
    return 0
  }

  // 已访问位图：保证终止（填充色与目标色接近但 alpha 不同时，避免已填像素被重复扫描）
  const visited = new Uint8Array(width * height)

  function matches(px: number, py: number): boolean {
    if (px < 0 || py < 0 || px >= width || py >= height) return false
    const pi = py * width + px
    if (visited[pi]) return false
    const i = pi * 4
    const a = data[i + 3]
    if (target.a === 0) return a === 0
    return a > 0 && rgbClose(data, i, target)
  }

  const stack: [number, number][] = [[x, y]]
  let filled = 0

  while (stack.length > 0) {
    const [px, py] = stack.pop()!
    if (visited[py * width + px]) continue

    // 向左扩到区域边界外一格，再回退一格到第一个匹配像素
    let xi = px
    while (xi >= 0 && matches(xi, py)) xi--
    xi++

    let spanUp = false
    let spanDown = false

    while (xi < width && matches(xi, py)) {
      const pi = py * width + xi
      const i = pi * 4
      const origA = data[i + 3]
      data[i] = color.r
      data[i + 1] = color.g
      data[i + 2] = color.b
      // 有色区填充：保留更透明的原始 alpha（抗锯齿边缘覆盖率），边缘不生硬；
      // 透明区填充：直接写填充色 alpha
      data[i + 3] = target.a > 0 ? Math.min(origA, color.a) : color.a
      visited[pi] = 1
      filled++

      if (py > 0) {
        const m = matches(xi, py - 1)
        if (m && !spanUp) {
          stack.push([xi, py - 1])
          spanUp = true
        } else if (!m) {
          spanUp = false
        }
      }
      if (py < height - 1) {
        const m = matches(xi, py + 1)
        if (m && !spanDown) {
          stack.push([xi, py + 1])
          spanDown = true
        } else if (!m) {
          spanDown = false
        }
      }
      xi++
    }
  }

  // 边界缝合：把填充色“垫”到紧邻填充区的半透明边界像素之下（Porter-Duff over）。
  // 闭环内部填充时，描边内沿的抗锯齿过渡带（alpha 1~254）不属于可填充的透明像素，
  // 若不处理会透出棋盘格形成 1px 缝隙；垫底后过渡带变成“描边叠在填充色上”，缝隙消失
  // 且保留边缘平滑度。
  if (filled > 0 && color.a > 0) {
    const FA = color.a / 255
    for (let py = 0; py < height; py++) {
      for (let px = 0; px < width; px++) {
        const pi = py * width + px
        if (visited[pi]) continue
        const i = pi * 4
        const pa = data[i + 3]
        if (pa === 0) continue
        // 4 邻接中存在已填充像素 → 此像素是填充区边界
        const hasFilledNeighbor =
          (px > 0 && visited[pi - 1]) ||
          (px < width - 1 && visited[pi + 1]) ||
          (py > 0 && visited[pi - width]) ||
          (py < height - 1 && visited[pi + width])
        if (!hasFilledNeighbor) continue
        // out = 当前像素 OVER 填充色（填充色作为下层）
        const pA = pa / 255
        const outA = pA + FA * (1 - pA)
        if (outA <= 0) continue
        data[i] = Math.round((data[i] * pA + color.r * FA * (1 - pA)) / outA)
        data[i + 1] = Math.round((data[i + 1] * pA + color.g * FA * (1 - pA)) / outA)
        data[i + 2] = Math.round((data[i + 2] * pA + color.b * FA * (1 - pA)) / outA)
        data[i + 3] = Math.round(outA * 255)
      }
    }
  }

  return filled
}
