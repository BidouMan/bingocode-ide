import { defineStore } from 'pinia'
import { ref } from 'vue'

/** 可选的图块格子尺寸 */
export const TILE_SIZE_OPTIONS = [16, 32, 64] as const

const STORAGE_KEY = 'bingo-default-tile-size'
/** 新建地图的默认格子尺寸（参考 Tiled / Godot 的 32px 默认值） */
const DEFAULT_TILE_SIZE = 32

const PERF_MODE_KEY = 'bingo-perf-mode'

/** 性能模式：低端机器上牺牲画面细节换流畅度（默认关闭） */
function readPerfMode(): boolean {
  try {
    return localStorage.getItem(PERF_MODE_KEY) === '1'
  } catch {
    return false
  }
}

function readDefaultTileSize(): number {
  try {
    const saved = Number(localStorage.getItem(STORAGE_KEY))
    if ((TILE_SIZE_OPTIONS as readonly number[]).includes(saved)) return saved
  } catch {
    // localStorage 不可用时用默认值
  }
  return DEFAULT_TILE_SIZE
}

/**
 * 全局偏好设置（与具体项目/地图无关）：新建地图的默认图块尺寸、性能模式。
 */
export const useSettingsStore = defineStore('settings', () => {
  const defaultTileSize = ref(readDefaultTileSize())
  // 性能模式：画面刷新降到 30 帧并关闭抗锯齿，降低老机器 CPU/GPU 占用。
  // 游戏逻辑仍按 60Hz 步进，移动速度、重力、动画时长都不会改变。
  const perfMode = ref(readPerfMode())

  function setDefaultTileSize(size: number) {
    if (!(TILE_SIZE_OPTIONS as readonly number[]).includes(size)) return
    defaultTileSize.value = size
    try {
      localStorage.setItem(STORAGE_KEY, String(size))
    } catch {
      // 写入失败不影响本次会话
    }
  }

  function setPerfMode(on: boolean) {
    perfMode.value = on
    try {
      localStorage.setItem(PERF_MODE_KEY, on ? '1' : '0')
    } catch {
      // 写入失败不影响本次会话
    }
  }

  return { defaultTileSize, setDefaultTileSize, perfMode, setPerfMode }
})
