import { nextTick } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'
import { useEditorStore } from '../stores/editor'
import { useRenderStore } from '../stores/render'
import { useTerminalStore } from '../stores/terminal'
import { useProjectStore } from '../stores/project'
import { waitForGameCanvasReady } from '../utils/gameCanvasReady'
import type { AnyEngineCommand } from '../types/engine'

let unlisteners: (() => void)[] = []
let runGeneration = 0

export function useEngine() {
  const editorStore = useEditorStore()
  const renderStore = useRenderStore()
  const terminalStore = useTerminalStore()
  const projectStore = useProjectStore()

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
    }
  }

  async function setupListeners() {
    cleanup()

    const unlisten1 = await listen<string>('engine:stdout', (event) => {
      const data = event.payload
      const stripped = data.trim()

      if (stripped.startsWith('{') && stripped.endsWith('}')) {
        const cmd = parseInstruction(stripped)
        if (cmd) {
          dispatchInstruction(cmd)
          return
        }
      }

      terminalStore.handleStdout(data)
    })

    const unlisten2 = await listen<string>('engine:stderr', (event) => {
      const msg = event.payload
      // 学生友好的错误提示
      if (msg.includes('No such file') && msg.includes('.temp_run.py')) {
        terminalStore.handleStderr('❌ 程序文件出错了，请再试一次运行\n')
      } else if (msg.includes('ModuleNotFoundError')) {
        const match = msg.match(/No module named '(\w+)'/)
        const moduleName = match ? match[1] : '未知模块'
        terminalStore.handleStderr(`❌ 找不到模块 "${moduleName}"，请检查代码中的 import 语句\n`)
      } else if (msg.includes('SyntaxError')) {
        terminalStore.handleStderr('❌ 代码语法有误，请检查拼写和括号是否正确\n')
      } else if (msg.includes('NameError')) {
        const match = msg.match(/name '(\w+)'/)
        const name = match ? match[1] : '未知'
        terminalStore.handleStderr(`❌ 变量或函数 "${name}" 未定义，请检查拼写\n`)
      } else {
        terminalStore.handleStderr(msg)
      }
    })

    let stdoutEnded = false
    const myGeneration = runGeneration

    const unlisten3 = await listen('engine:finished', () => {
      const tryFinish = () => {
        if (runGeneration !== myGeneration) return // 新的 run 已启动，放弃
        if (stdoutEnded) {
          terminalStore.flushNow()
          terminalStore.resetInputState()
          editorStore.setRunning(false)
          terminalStore.appendLine('\x1b[33m[运行完毕]\x1b[0m')
        } else {
          setTimeout(tryFinish, 50)
        }
      }
      tryFinish()
    })

    const unlisten4 = await listen('engine:stdout:end', () => {
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
      terminalStore.appendLine('\x1b[33m⏳ 正在初始化项目...\x1b[0m')
      await projectStore.initProject()
    }

    let tab = editorStore.currentTab
    if (!tab) {
      // 可能是 newProject 期间的竞态，等待下一次事件循环再重试
      await new Promise(r => setTimeout(r, 50))
      tab = editorStore.currentTab
      if (!tab) {
        terminalStore.appendLine('\x1b[31m❌ 没有打开的文件\x1b[0m')
        return
      }
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

      // 先清理上一次的临时文件，再写入新文件，避免旧 cleanup 删掉新文件的竞态
      if (projectDir) {
        await invoke('cleanup_temp_script', { projectDir }).catch(() => {})
      }

      // 构建最终脚本内容：sys.path + 自动 import
      let codeToRun = tab.content
      const gameKeywords = ['run()', 'Sprite(', 'load_map(', 'key_down(', 'key_pressed(', 'Timer(', 'mouse', 'wait(']
      const hasImport = codeToRun.includes('from bingo_engine import') || codeToRun.includes('import bingo_engine')
      const needsEngine = !hasImport && gameKeywords.some(kw => codeToRun.includes(kw))

      // 先写入原始内容获取临时文件路径
      const scriptPath = await invoke<string>('save_temp_script', {
        projectDir,
        content: codeToRun,
      })

      // 获取引擎环境（python路径、engine目录、工作目录）
      const env = await invoke<{
        python_path: string
        engine_dir: string
        working_dir: string
      }>('resolve_engine_env', { scriptPath, projectRoot: projectDir || undefined })

      // 如果需要引擎，注入 sys.path 和 import 并重新写入
      if (needsEngine) {
        const escapedPath = env.engine_dir.replace(/\\/g, '\\\\')
        codeToRun = `import sys\nif "${escapedPath}" not in sys.path:\n    sys.path.insert(0, "${escapedPath}")\nfrom bingo_engine import *\n` + codeToRun
        await invoke<string>('save_temp_script', {
          projectDir,
          content: codeToRun,
        })
      }

      await invoke('run_script', {
        workingDir: env.working_dir,
        pythonPath: env.python_path,
        engineDir: env.engine_dir,
      })
    } catch (err) {
      terminalStore.appendLine(`\x1b[31m❌ 启动失败: ${err}\x1b[0m`)
      editorStore.setRunning(false)
    }
  }

  async function stop() {
    try {
      await invoke('stop_script')
    } catch {}
    editorStore.setRunning(false)
    renderStore.resetTextureLoading()
    terminalStore.resetInputState()
    terminalStore.appendLine('\x1b[33m[已停止运行]\x1b[0m')
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

  return {
    run,
    stop,
    sendInput,
    sendKey,
    sendMouseMove,
    sendMouseDown,
    sendMouseUp,
    cleanup,
  }
}
