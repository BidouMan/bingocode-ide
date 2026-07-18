import { invoke } from '@tauri-apps/api/core'
import { listen } from '@tauri-apps/api/event'
import { useProjectStore } from '../stores/project'

let unlisteners: (() => void)[] = []
let onStdout: ((data: string) => void) | null = null
let onExited: (() => void) | null = null

export function useShell() {
  const projectStore = useProjectStore()

  async function startShell(stdoutCallback: (data: string) => void, exitedCallback: () => void) {
    await stopShell()

    onStdout = stdoutCallback
    onExited = exitedCallback

    const unlisten1 = await listen<string>('shell:stdout', (event) => {
      onStdout?.(event.payload)
    })

    const unlisten2 = await listen('shell:exited', () => {
      onExited?.()
    })

    unlisteners.push(() => { unlisten1() }, () => { unlisten2() })

    let workingDir = projectStore.root || ''
    if (!workingDir) {
      try {
        const env = await invoke<{ working_dir: string }>('resolve_engine_env', {
          scriptPath: '',
          projectRoot: undefined,
        })
        workingDir = env.working_dir
      } catch {
        workingDir = ''
      }
    }

    await invoke('start_shell', { workingDir })
  }

  async function stopShell() {
    cleanup()
    try {
      await invoke('stop_shell')
    } catch {}
  }

  async function sendInput(data: string) {
    try {
      await invoke('send_shell_input', { data })
    } catch {}
  }

  async function resize(cols: number, rows: number) {
    try {
      await invoke('resize_shell', { cols, rows })
    } catch {}
  }

  function cleanup() {
    unlisteners.forEach((fn) => fn())
    unlisteners = []
  }

  return {
    startShell,
    stopShell,
    sendInput,
    resize,
    cleanup,
  }
}
