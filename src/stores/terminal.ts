import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useTerminalStore = defineStore('terminal', () => {
  const lines = ref<string[]>([])
  const MAX_LINES = 5000

  let terminalInstance: any = null
  const earlyBuffer: string[] = []
  const waitingForInput = ref(false)
  // 终端模式：'python' = Python 控制台，'shell' = 系统终端
  const terminalMode = ref<'python' | 'shell'>('python')
  // shell 运行命令回调（由 TerminalPanel 注册）
  let shellRunCallback: ((cmd: string) => void) | null = null

  // 输出限流：高频写入时合并到 animation frame，防止 xterm 渲染阻塞主线程
  let writeRaf: number | null = null
  let pendingWrite = ''
  // 每帧写入上限：超过此行数则丢弃旧行
  const MAX_WRITE_LINES = 50

  function scheduleWrite() {
    if (writeRaf !== null) return
    writeRaf = requestAnimationFrame(doWrite)
  }

  function doWrite() {
    writeRaf = null
    if (!pendingWrite) return
    if (!terminalInstance) {
      // 终端还没创建，保留数据，等 bindTerminal 后再写入
      return
    }

    const text = pendingWrite
    pendingWrite = ''

    // 过滤游戏引擎 JSON 指令
    const filtered = filterEngineJson(text)
    if (!filtered) return

    // 行数限流：高频输出时只保留最新行，避免 xterm 卡死
    const lineCount = (filtered.match(/\n/g) || []).length
    if (lineCount > MAX_WRITE_LINES) {
      const allLines = filtered.split('\n')
      const kept = allLines.slice(-MAX_WRITE_LINES)
      terminalInstance.write(kept.join('\n'))
    } else {
      terminalInstance.write(filtered)
    }
    terminalInstance.scrollToBottom()
  }

  // 过滤游戏引擎 JSON 指令行
  function filterEngineJson(text: string): string {
    // 快速检查：如果不包含 JSON 特征，直接返回
    if (!text.includes('{"type":')) return text
    const lines = text.split('\n')
    const filtered = lines.filter(line => {
      const trimmed = line.trim()
      return !(trimmed.startsWith('{"type":') && trimmed.endsWith('}'))
    })
    return filtered.join('\n')
  }

  // 立即写入终端（不走 RAF 缓冲），用于需要即时显示的内容
  function writeImmediate(text: string) {
    if (!terminalInstance) return
    const filtered = filterEngineJson(text)
    if (filtered) {
      terminalInstance.write(filtered)
      terminalInstance.scrollToBottom()
    }
  }

  function registerShellRunner(callback: (cmd: string) => void) {
    shellRunCallback = callback
  }

  function runInShell(cmd: string) {
    shellRunCallback?.(cmd)
  }

  function bindTerminal(terminal: any) {
    terminalInstance = terminal
    for (const line of earlyBuffer) {
      terminalInstance.writeln(line)
    }
    earlyBuffer.length = 0
    // 刷新积压的输出数据（首次运行时终端可能还没创建）
    if (pendingWrite) {
      doWrite()
    }
    if (lines.value.length > 0) {
      terminalInstance.scrollToBottom()
    }
  }

  function appendLine(text: string) {
    lines.value.push(text)
    if (lines.value.length > MAX_LINES) {
      const excess = lines.value.length - MAX_LINES
      lines.value.splice(0, excess)
    }
    if (terminalInstance) {
      terminalInstance.writeln(text)
    } else {
      earlyBuffer.push(text)
    }
  }

  function writeRaw(text: string) {
    if (terminalInstance) {
      terminalInstance.write(text)
    }
  }

  // 游戏模式的高频 stdout（JSON 指令 + 普通输出混合）
  // 使用 RAF 缓冲避免高频写入卡死
  function handleStdout(data: string) {
    pendingWrite += data
    // 缓冲上限 64KB
    if (pendingWrite.length > 65536) {
      pendingWrite = pendingWrite.slice(-65536)
    }
    scheduleWrite()
  }

  // 代码模式：也使用 RAF 缓冲，但保证实时性
  // input() prompt 的延迟仅 16ms，用户无感知
  // 高频输出时限流丢弃旧行，防止 xterm 卡死
  function handleCodeStdout(data: string) {
    pendingWrite += data
    if (pendingWrite.length > 65536) {
      pendingWrite = pendingWrite.slice(-65536)
    }
    scheduleWrite()
  }

  function handleStderr(data: string) {
    // 错误信息用红色显示
    writeImmediate(`\x1b[31m${data}\x1b[0m`)
  }

  function consumeInput() {
    waitingForInput.value = false
  }

  function resetInputState() {
    waitingForInput.value = false
  }

  function flushNow() {
    if (writeRaf !== null) {
      cancelAnimationFrame(writeRaf)
      writeRaf = null
    }
    if (pendingWrite) {
      doWrite()
    }
  }

  function clear() {
    earlyBuffer.length = 0
    pendingWrite = ''
    if (writeRaf !== null) {
      cancelAnimationFrame(writeRaf)
      writeRaf = null
    }
    if (terminalInstance) {
      // reset() 完全重置终端（清空 scrollback + viewport），
      // clear() 只清空 viewport 不清 scrollback，会导致残留内容
      terminalInstance.reset()
    }
    lines.value = []
  }

  function destroy() {
    if (writeRaf !== null) {
      cancelAnimationFrame(writeRaf)
      writeRaf = null
    }
    pendingWrite = ''
    terminalInstance = null
  }

  return {
    lines,
    waitingForInput,
    terminalMode,
    registerShellRunner,
    runInShell,
    bindTerminal,
    appendLine,
    writeRaw,
    writeImmediate,
    handleStdout,
    handleCodeStdout,
    handleStderr,
    flushNow,
    consumeInput,
    resetInputState,
    clear,
    destroy,
  }
})
