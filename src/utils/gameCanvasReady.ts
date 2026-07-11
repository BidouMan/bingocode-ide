/**
 * GameCanvas 就绪信号机制
 * 让 engine.run() 等待 PixiJS 初始化完成后再启动 Python 脚本
 */

let readyCallback: (() => void) | null = null
let isReady = false

/** GameCanvas 初始化完成后调用 */
export function signalGameCanvasReady() {
  isReady = true
  if (readyCallback) {
    readyCallback()
    readyCallback = null
  }
}

/** GameCanvas 卸载时调用，重置就绪状态 */
export function resetGameCanvasReady() {
  isReady = false
}

/** engine.run() 调用：等待 GameCanvas 就绪 */
export function waitForGameCanvasReady(): Promise<void> {
  if (isReady) return Promise.resolve()
  return new Promise(resolve => {
    readyCallback = resolve
  })
}
