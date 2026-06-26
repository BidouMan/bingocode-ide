import { invoke } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'
import { useEditorStore } from '../stores/editor'
import { useRenderStore } from '../stores/render'
import { useTerminalStore } from '../stores/terminal'
import { useProjectStore } from '../stores/project'
import type { AnyEngineCommand } from '../types/engine'

let unlisteners: (() => void)[] = []

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
        break

      case 'DELETE':
      case 'REMOVE':
        renderStore.deleteSprite(cmd.id!)
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
        // Sound playback handled separately
        break

      case 'STOP_SOUND':
        break

      case 'DRAW_TEXT':
        // Text rendering handled by PixiJS
        break

      case 'SCREEN_SHAKE':
        renderStore.triggerShake(cmd.data.intensity, cmd.data.duration)
        break

      case 'SAY':
        renderStore.updateSprite(cmd.id!, {
          // Store say text as custom property
        } as any)
        break
    }
  }

  async function setupListeners() {
    cleanup()

    const unlisten1 = await listen<string>('engine:stdout', (event) => {
      const line = event.payload
      const stripped = line.trim()

      if (stripped.startsWith('{') && stripped.endsWith('}')) {
        const cmd = parseInstruction(stripped)
        if (cmd) {
          dispatchInstruction(cmd)
          return
        }
      }

      terminalStore.handleStdout(line + '\n')
    })

    const unlisten2 = await listen<string>('engine:stderr', (event) => {
      terminalStore.handleStderr(event.payload)
    })

    const unlisten3 = await listen('engine:finished', () => {
      editorStore.setRunning(false)
      terminalStore.appendLine('\x1b[33m[进程已退出]\x1b[0m')
    })

    const unlisten4 = await listen('engine:stdout:end', () => {
      // stdout stream closed
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
    const tab = editorStore.currentTab
    if (!tab) {
      terminalStore.appendLine('\x1b[31m❌ 没有打开的文件\x1b[0m')
      return
    }

    renderStore.clearAll()
    terminalStore.clear()
    editorStore.setRunning(true)
    await setupListeners()

    try {
      const env = await invoke<{
        python_path: string
        engine_dir: string
        working_dir: string
      }>('resolve_engine_env', { scriptPath: tab.path })

      await invoke('run_script', {
        scriptPath: tab.path,
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
    terminalStore.appendLine('\x1b[33m[已停止]\x1b[0m')
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
