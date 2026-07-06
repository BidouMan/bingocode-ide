/**
 * GameCanvas 就绪信号机制
 * 让 engine.run() 等待 PixiJS 初始化完成后再启动 Python 脚本
 *
 * 使用引用计数支持多个 GameCanvas 实例（侧边栏 + 全屏）
 */

let readyCallback: (() => void) | null = null
let mountCount = 0

/** GameCanvas 初始化完成后调用 */
export function signalGameCanvasReady() {
  if (readyCallback) {
    readyCallback()
    readyCallback = null
  }
}

/** GameCanvas 挂载时调用（在 initPixi 之前） */
export function registerGameCanvasMount() {
  mountCount++
}

/** GameCanvas 卸载时调用 */
export function unregisterGameCanvasMount() {
  mountCount = Math.max(0, mountCount - 1)
}

/** engine.run() 调用：等待 GameCanvas 就绪 */
export function waitForGameCanvasReady(): Promise<void> {
  return new Promise(resolve => {
    readyCallback = resolve
  })
}
