import { defineStore } from 'pinia'
import { ref } from 'vue'

/** 可选的图块格子尺寸 */
export const TILE_SIZE_OPTIONS = [16, 32, 64] as const

const STORAGE_KEY = 'bingo-default-tile-size'
/** 新建地图的默认格子尺寸（参考 Tiled / Godot 的 32px 默认值） */
const DEFAULT_TILE_SIZE = 32

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
 * 全局偏好设置（与具体项目/地图无关）。
 * 目前只有「新建地图的默认图块尺寸」，后续可在此扩展。
 */
export const useSettingsStore = defineStore('settings', () => {
  const defaultTileSize = ref(readDefaultTileSize())

  function setDefaultTileSize(size: number) {
    if (!(TILE_SIZE_OPTIONS as readonly number[]).includes(size)) return
    defaultTileSize.value = size
    try {
      localStorage.setItem(STORAGE_KEY, String(size))
    } catch {
      // 写入失败不影响本次会话
    }
  }

  return { defaultTileSize, setDefaultTileSize }
})
