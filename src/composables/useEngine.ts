import { nextTick } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'
import { save } from '@tauri-apps/plugin-dialog'
import { useEditorStore } from '../stores/editor'
import { useRenderStore } from '../stores/render'
import { useTerminalStore } from '../stores/terminal'
import { useProjectStore } from '../stores/project'
import { useResourceStore } from '../stores/resource'
import { waitForGameCanvasReady } from '../utils/gameCanvasReady'
import type { AnyEngineCommand } from '../types/engine'

let unlisteners: (() => void)[] = []
let runGeneration = 0

export function useEngine() {
  const editorStore = useEditorStore()
  const renderStore = useRenderStore()
  const terminalStore = useTerminalStore()
  const projectStore = useProjectStore()
  const resourceStore = useResourceStore()

  function parseInstruction(jsonStr: string): AnyEngineCommand | null {
    try {
      const msg = JSON.parse(jsonStr)
      if (msg && msg.type && typeof msg.type === 'string') {
        return msg as AnyEngineCommand
      }
    } catch {}
    return null
  }

  // 活跃音频元素
  const activeAudios = new Map<string, HTMLAudioElement>()

  function dispatchInstruction(cmd: AnyEngineCommand) {
    switch (cmd.type) {
      case 'CREATE':
        renderStore.createSprite(cmd.id!, {
          x: cmd.data.x,
          y: cmd.data.y,
          angle: cmd.data.angle,
          scale: cmd.data.scale,
          scaleX: cmd.data.scale_x,
          scaleY: cmd.data.scale_y,
          visible: true,
          layer: cmd.data.layer,
          imagePath: cmd.data.image,
        })
        break

      case 'UPDATE':
        renderStore.updateSprite(cmd.id!, {
          x: cmd.data.x,
          y: cmd.data.y,
          angle: cmd.data.angle,
          scale: cmd.data.scale,
          scaleX: cmd.data.scale_x,
          scaleY: cmd.data.scale_y,
          visible: cmd.data.visible ?? true,
          layer: cmd.data.layer,
          imagePath: cmd.data.image,
        })
        // 更新碰撞盒
        if (cmd.data.hitbox) {
          renderStore.setHitbox(cmd.id!, cmd.data.hitbox)
        } else {
          renderStore.removeHitbox(cmd.id!)
        }
        // 同步气泡位置
        const sayText = renderStore.sayTexts.get(cmd.id!)
        if (sayText) {
          sayText.x = cmd.data.x
          sayText.y = cmd.data.y - 40
        }
        break

      case 'DELETE':
        renderStore.deleteSprite(cmd.id!)
        renderStore.removeHitbox(cmd.id!)
        renderStore.sayTexts.delete(cmd.id!)
        break

      case 'SAY':
        renderStore.setSayText(cmd.id!, cmd.data.text)
        break

      case 'CREATE_BATCH':
        renderStore.createBatch({
          tiles: cmd.data.tiles,
          tile_sets: cmd.data.tile_sets,
          tile_size: cmd.data.tile_size,
        })
        break

      case 'UPDATE_BATCH':
        for (const update of cmd.data.updates) {
          renderStore.updateSprite(update.id, {
            x: update.x,
            y: update.y,
            angle: update.angle,
            scale: update.scale,
            scaleX: update.scale_x,
            scaleY: update.scale_y,
            visible: update.visible ?? true,
            layer: update.layer,
          })
          if (update.hitbox) {
            renderStore.setHitbox(update.id, update.hitbox)
          } else {
            renderStore.removeHitbox(update.id)
          }
          // 同步气泡位置
          const sayText = renderStore.sayTexts.get(update.id)
          if (sayText) {
            sayText.x = update.x
            sayText.y = update.y - 40
          }
        }
        break

      case 'CAMERA_UPDATE':
        renderStore.updateCamera({
          x: cmd.data.x,
          y: cmd.data.y,
          limitLeft: cmd.data.limit_left ?? 0,
          limitRight: cmd.data.limit_right ?? 640,
          limitTop: cmd.data.limit_top ?? 0,
          limitBottom: cmd.data.limit_bottom ?? 480,
        })
        break

      case 'SCENE_UPDATE':
        renderStore.updateCamera({
          limitLeft: cmd.data.world_bounds.left,
          limitRight: cmd.data.world_bounds.right,
          limitTop: cmd.data.world_bounds.top,
          limitBottom: cmd.data.world_bounds.bottom,
        })
        break

      case 'FPS_UPDATE':
        renderStore.setFps(cmd.data.fps)
        break

      case 'PLAY_SOUND':
        try {
          const url = convertFileSrc(cmd.data.sound)
          const audio = new Audio(url)
          audio.loop = cmd.data.loop
          activeAudios.set(cmd.data.sound, audio)
          audio.play().catch(() => {})
        } catch {}
        break

      case 'STOP_SOUND':
        if (cmd.data.sound) {
          const audio = activeAudios.get(cmd.data.sound)
          if (audio) {
            audio.pause()
            audio.currentTime = 0
            activeAudios.delete(cmd.data.sound)
          }
        } else {
          activeAudios.forEach(a => { a.pause(); a.currentTime = 0 })
          activeAudios.clear()
        }
        break

      case 'DRAW_TEXT':
        renderStore.setDrawText(cmd.id!, cmd.data.text, cmd.data.x, cmd.data.y)
        break

      case 'SCREEN_SHAKE':
        renderStore.triggerShake(cmd.data.intensity, cmd.data.duration)
        break

      case 'PAUSE_STATE':
        renderStore.isPaused = cmd.data.paused
        break

      case 'UI_COMMAND':
        if (cmd.data.visible !== undefined) {
          renderStore.showFps = cmd.data.visible
        }
        break
    }
  }

  async function setupListeners() {
    cleanup()

    const isCodeMode = !editorStore.isGameMode
    const myRunId = runGeneration

    const unlisten1 = await listen<{ run_id: number; data: string }>('engine:stdout', (event) => {
      // ★ 按 run_id 精确过滤：旧进程事件被完全忽略
      if (event.payload.run_id !== myRunId) {
        return
      }
      const data = event.payload.data

      // 代码模式：直接写入终端
      if (isCodeMode) {
        terminalStore.handleCodeStdout(data)
        return
      }

      // 游戏模式：需要解析 JSON 指令
      const lines = data.split('\n')
      const nonJsonParts: string[] = []

      for (const line of lines) {
        const stripped = line.trim()
        if (!stripped) continue

        if (stripped.startsWith('{') && stripped.endsWith('}')) {
          const cmd = parseInstruction(stripped)
          if (cmd) {
            dispatchInstruction(cmd)
            continue
          }
        }

        nonJsonParts.push(line)
      }

      if (nonJsonParts.length > 0) {
        terminalStore.handleStdout(nonJsonParts.join('\n'))
      }
    })

    const unlisten2 = await listen<{ run_id: number; data: string }>('engine:stderr', (event) => {
      if (event.payload.run_id !== myRunId) return
      const msg = event.payload.data
      // 学生友好的错误提示
      if (msg.includes('KeyboardInterrupt')) {
        // 用户主动中断，静默处理
      } else if (msg.includes('No such file') && msg.includes('.temp_run.py')) {
        terminalStore.handleStderr('程序文件出错了，请再试一次\n')
      } else if (msg.includes('ModuleNotFoundError')) {
        const match = msg.match(/No module named '(\w+)'/)
        const moduleName = match ? match[1] : '未知模块'
        terminalStore.handleStderr(`找不到模块 "${moduleName}"，请检查 import 语句\n`)
      } else if (msg.includes('SyntaxError')) {
        const lineMatch = msg.match(/line (\d+)/)
        const lineInfo = lineMatch ? `（第 ${lineMatch[1]} 行）` : ''
        terminalStore.handleStderr(`代码语法有误${lineInfo}，请检查拼写和括号\n`)
      } else if (msg.includes('NameError')) {
        const match = msg.match(/name '(\w+)'/)
        const name = match ? match[1] : '未知'
        terminalStore.handleStderr(`变量或函数 "${name}" 未定义，请检查拼写\n`)
      } else if (msg.includes('IndentationError') || msg.includes('TabError')) {
        terminalStore.handleStderr('缩进有误，请检查空格是否对齐\n')
      } else if (msg.includes('TypeError')) {
        const match = msg.match(/unsupported operand type\(s\)/)
        if (match) {
          terminalStore.handleStderr('数据类型不匹配，请检查运算是否正确\n')
        } else {
          terminalStore.handleStderr('数据类型有误，请检查变量类型\n')
        }
      } else if (msg.includes('ZeroDivisionError')) {
        terminalStore.handleStderr('不能除以 0\n')
      } else if (msg.includes('IndexError')) {
        terminalStore.handleStderr('列表下标超出范围\n')
      } else if (msg.includes('KeyError')) {
        const match = msg.match(/KeyError:\s*'?(\w+)'?/)
        const key = match ? match[1] : ''
        terminalStore.handleStderr(key ? `找不到键 "${key}"\n` : '字典中找不到指定的键\n')
      } else if (msg.includes('ValueError')) {
        terminalStore.handleStderr('数值有误，请检查输入是否正确\n')
      } else if (msg.includes('FileNotFoundError')) {
        terminalStore.handleStderr('找不到文件，请检查文件路径\n')
      } else {
        terminalStore.handleStderr(msg)
      }
    })

    let stdoutEnded = false

    const unlisten3 = await listen<{ run_id: number }>('engine:finished', (event) => {
      if (event.payload.run_id !== myRunId) {
        return
      }
      const tryFinish = () => {
        if (stdoutEnded) {
          terminalStore.flushNow()
          terminalStore.resetInputState()
          editorStore.setRunning(false)
          if (terminalStore.terminalMode === 'python') {
            terminalStore.terminalMode = 'shell'
          }
        } else {
          setTimeout(tryFinish, 50)
        }
      }
      tryFinish()
    })

    const unlisten4 = await listen<{ run_id: number }>('engine:stdout:end', (event) => {
      if (event.payload.run_id !== myRunId) {
        return
      }
      stdoutEnded = true
    })

    unlisteners.push(
      () => { unlisten1() },
      () => { unlisten2() },
      () => { unlisten3() },
      () => { unlisten4() },
    )
  }

  function cleanup() {
    unlisteners.forEach((fn) => fn())
    unlisteners = []
  }

  async function run() {
    // 等待项目初始化完成（onMounted 可能尚未完成）
    if (!projectStore.root) {
      await projectStore.initProject()
    }

    let tab = editorStore.currentTab
    if (!tab) {
      // 可能是 newProject 期间的竞态，等待下一次事件循环再重试
      await new Promise(r => setTimeout(r, 50))
      tab = editorStore.currentTab
      if (!tab) {
        terminalStore.appendLine('\x1b[31m没有打开的文件\x1b[0m')
        return
      }
    }

    // 如果文件未保存，弹窗让用户保存后即止（不运行）
    if (!tab.path) {
      const filePath = await save({
        title: '保存 Python 文件',
        filters: [{ name: 'Python 文件', extensions: ['py'] }],
        defaultPath: tab.name,
      })
      if (!filePath) {
        return
      }
      // 保存文件
      await invoke('write_file', { path: filePath, content: tab.content })
      tab.path = filePath
      tab.name = filePath.split('/').pop() || tab.name
      // 同步更新资源管理器
      const resource = resourceStore.codes.find(c => c.id === tab.id)
      if (resource) {
        resource.path = filePath
        resource.name = tab.name
      }
      terminalStore.appendLine('\x1b[33m文件已保存，点击运行\x1b[0m')
      editorStore.setRunning(false)
      return
    }

    renderStore.clearAll()
    renderStore.resetTextureLoading()
    terminalStore.clear()
    editorStore.setRunning(true)
    runGeneration++

    // 等待 GameCanvas 挂载并完成 PixiJS 初始化
    // 确保引擎发送渲染指令时 PixiJS 已就绪
    // 仅在 GameCanvas 会挂载时才等待（游戏模式 + 代码编辑器）
    const canvasWillMount = editorStore.isGameMode && editorStore.activeEditorMode === 'code'
    if (canvasWillMount) {
      await nextTick() // 让 Vue 处理 DOM 更新，触发 GameCanvas 挂载
      await waitForGameCanvasReady()
    }

    await setupListeners()

    try {
      const projectDir = projectStore.root || ''

      // 清理临时脚本
      if (projectDir) {
        await invoke('cleanup_temp_script', { projectDir }).catch(() => {})
      }

      // 先写入临时文件获取路径（resolve_engine_env 需要）
      const tab = editorStore.currentTab
      const tempScriptPath = await invoke<string>('save_temp_script', {
        projectDir,
        content: tab?.content || '',
      })

      // 获取引擎环境（python路径、engine目录、工作目录）
      const env = await invoke<{
        python_path: string
        engine_dir: string
        working_dir: string
      }>('resolve_engine_env', { scriptPath: tempScriptPath, projectRoot: projectDir || undefined })

      // 根据模式决定如何运行
      if (editorStore.isGameMode) {
        // ═══ 游戏模式：保存所有 tab 到 code/ 目录，引擎自动发现并运行 ═══
        const gameKeywords = ['run()', 'Sprite(', 'load_map(', 'key_down(', 'key_pressed(', 'Timer(', 'mouse', 'wait(']
        const codeDir = projectDir ? `${projectDir}/code` : ''

        // 确保 code/ 目录存在
        if (codeDir) {
          await invoke('create_dir', { path: codeDir }).catch(() => {})
        }

        let allNeedsEngine = false
        const usedFileNames = new Set<string>()

        // 保存每个 tab 为独立 .py 文件
        for (const t of editorStore.currentTabs) {
          if (!t.content.trim()) continue
          // 检查是否需要引擎
          const hasImport = t.content.includes('from bingo_engine import') || t.content.includes('import bingo_engine')
          if (!hasImport && gameKeywords.some(kw => t.content.includes(kw))) {
            allNeedsEngine = true
          }
          // 确定文件名：优先用已保存的 path，否则用 tab name
          let fileName = t.name
          if (t.path) {
            const parts = t.path.replace(/\\/g, '/').split('/')
            fileName = parts[parts.length - 1]
          }
          if (!fileName.endsWith('.py')) fileName += '.py'
          // 文件名去重：同名加后缀避免覆盖
          let finalName = fileName
          let suffix = 1
          while (usedFileNames.has(finalName)) {
            const dotIdx = fileName.lastIndexOf('.')
            finalName = `${fileName.slice(0, dotIdx)}_${suffix}${fileName.slice(dotIdx)}`
            suffix++
          }
          usedFileNames.add(finalName)
          const filePath = codeDir ? `${codeDir}/${finalName}` : finalName

          // 需要引擎时注入 sys.path 和 import
          let content = t.content
          if (allNeedsEngine) {
            const escapedPath = env.engine_dir.replace(/\\/g, '\\\\')
            content = `import sys\nif "${escapedPath}" not in sys.path:\n    sys.path.insert(0, "${escapedPath}")\nfrom bingo_engine import *\n` + content
          }

          await invoke('write_file', { path: filePath, content })
        }

        // 不传 scriptPath，让 discover_and_merge 扫描 code/ 目录运行所有文件
        await invoke('run_script', {
          workingDir: env.working_dir,
          pythonPath: env.python_path,
          engineDir: env.engine_dir,
          runId: runGeneration,
        })
      } else {
        // ═══ 代码模式：通过子进程运行 Python，不走 PTY，完全无回显 ═══
        if (!tab) {
          terminalStore.appendLine('\x1b[31m没有打开的文件\x1b[0m')
          editorStore.setRunning(false)
          return
        }

        let runPath: string
        if (tab.path) {
          // 将编辑器最新内容写入磁盘
          await invoke('write_file', { path: tab.path, content: tab.content })
          runPath = tab.path
        } else {
          await invoke<string>('save_temp_script', {
            projectDir,
            content: tab.content,
          })
          runPath = `${projectDir}/.temp_run.py`
        }

        terminalStore.clear()
        terminalStore.terminalMode = 'python'
        // 使用子进程运行（和游戏模式同一套管道通信机制）
        await invoke('run_script_file', {
          workingDir: env.working_dir,
          pythonPath: env.python_path,
          scriptPath: runPath,
          runId: runGeneration,
        })
      }
    } catch (err) {
      terminalStore.appendLine(`\x1b[31m启动失败: ${err}\x1b[0m`)
      editorStore.setRunning(false)
    }
  }

  async function stop() {
    if (editorStore.isGameMode) {
      try { await invoke('stop_script') } catch {}
    } else {
      try { await invoke('stop_script') } catch {}
    }
    terminalStore.flushNow()
    editorStore.setRunning(false)
    renderStore.resetTextureLoading()
    terminalStore.resetInputState()
    if (terminalStore.terminalMode === 'python') {
      terminalStore.terminalMode = 'shell'
    }
  }

  async function sendInput(data: string) {
    try {
      await invoke('send_stdin', { data })
    } catch {}
  }

  function sendKey(key: string, down: boolean) {
    const event = down ? `K_DOWN:${key}` : `K_UP:${key}`
    sendInput(event)
  }

  function sendMouseMove(x: number, y: number) {
    sendInput(`M_MOVE:${x},${y}`)
  }

  function sendMouseDown() {
    sendInput('M_DOWN:')
  }

  function sendMouseUp() {
    sendInput('M_UP:')
  }

  // ─── 调试工具 ───
  function sendPause() { sendInput('PAUSE:') }
  function sendResume() { sendInput('RESUME:') }
  function sendShowFps(on: boolean) { sendInput(`SHOW_FPS:${on ? 1 : 0}`) }
  function sendShowCollision(on: boolean) { sendInput(`SHOW_COLLISION:${on ? 1 : 0}`) }

  return {
    run,
    stop,
    sendInput,
    sendKey,
    sendMouseMove,
    sendMouseDown,
    sendMouseUp,
    sendPause,
    sendResume,
    sendShowFps,
    sendShowCollision,
    cleanup,
  }
}
