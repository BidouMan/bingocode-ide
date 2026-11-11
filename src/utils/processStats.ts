// 进程资源轮询：把「主进程 + WebView2 子进程 + Python 引擎」的整棵进程树汇总起来。
//
// 为什么需要它：Windows 任务管理器会把 WebView2 的渲染/GPU 进程和其它应用的
// 同类进程混在一起，开发者无法直接看出 IDE 真实的内存/CPU 占用。
// Rust 侧（sysstat.rs）按父子关系归属，这里只做定时拉取与共享缓存。
//
// 模块级单例：MainLayout 同时挂着预览窗与全屏窗两个 GameCanvas，
// 若各自轮询会重复调用 IPC，这里用共享 ref + inFlight 去重。
import { ref } from 'vue'
import { invoke } from '@tauri-apps/api/core'

export interface ProcessGroupStat {
  kind: 'main' | 'webview' | 'python' | 'other'
  cpu: number
  memory: number
}

export interface AppResourceStats {
  total_memory: number
  total_cpu: number
  process_count: number
  groups: ProcessGroupStat[]
}

/** 最近一次采样结果（null = 尚未采到 / 非 Tauri 环境） */
export const processStats = ref<AppResourceStats | null>(null)

let timer: number | null = null
let inFlight = false

async function sample() {
  if (inFlight) return
  inFlight = true
  try {
    processStats.value = await invoke<AppResourceStats>('get_app_resource_stats')
  } catch {
    // 浏览器环境（pnpm dev 纯前端调试）没有该命令，静默降级
    processStats.value = null
  } finally {
    inFlight = false
  }
}

export function startProcessStatsPolling(intervalMs = 1500) {
  if (timer !== null) return
  void sample()
  timer = window.setInterval(() => void sample(), intervalMs)
}

export function stopProcessStatsPolling() {
  if (timer !== null) {
    window.clearInterval(timer)
    timer = null
  }
  processStats.value = null
}

export const PROCESS_GROUP_LABELS: Record<ProcessGroupStat['kind'], string> = {
  main: '主进程',
  webview: 'WebView2',
  python: 'Python 引擎',
  other: '其它',
}
