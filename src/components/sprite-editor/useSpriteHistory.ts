import { computed, onBeforeUnmount, shallowRef, watch } from 'vue'
import type {
  BsfMeta,
  SpriteAnimation,
  SpriteData,
  SpriteFrame,
  SpriteTransform,
} from '../../composables/useSpriteData'

/** 一次历史快照：只包含会落盘的可编辑状态（帧的 blob/url 复用原对象引用） */
interface SpriteSnapshot {
  transform?: SpriteTransform
  defaultFrameIndex?: number
  bsf?: BsfMeta
  animations: SpriteAnimation[]
  frames: SpriteFrame[]
}

/** 历史栈上限：够用又不至于长时间编辑后占用过多内存 */
const HISTORY_LIMIT = 50
/** 连续修改合并窗口：一次拖动（mousemove 连续触发）或连续输入只记一步 */
const COMMIT_DELAY = 250

interface SpriteHistoryOptions {
  /**
   * 回写快照时逐帧处理：帧的 objectURL 可能在删除造型时被主动释放，
   * 撤销/重做复原时用它按 blob 重建 URL（否则会出现裂图）。
   */
  restoreFrame?: (frame: SpriteFrame) => SpriteFrame
}

/**
 * 角色编辑器的撤销 / 重做。
 * 监听整份可编辑状态的变化，停顿 COMMIT_DELAY 后把「修改前」的快照压栈；
 * 撤销 = 整体回写快照（帧列表、动画、变换、.bsf 标注一起复原）。
 */
export function useSpriteHistory(
  getSprite: () => SpriteData | null,
  onApply: () => void,
  options: SpriteHistoryOptions = {},
) {
  const undoStack = shallowRef<SpriteSnapshot[]>([])
  const redoStack = shallowRef<SpriteSnapshot[]>([])

  const canUndo = computed(() => undoStack.value.length > 0)
  const canRedo = computed(() => redoStack.value.length > 0)

  /** 最近一次已提交的状态（栈顶为空时代表当前实际状态） */
  let baseline: SpriteSnapshot | null = null
  let baselineKey = ''
  /** 正在回写快照：期间的状态变化不算用户编辑 */
  let applying = false
  let commitTimer: ReturnType<typeof setTimeout> | null = null

  function cloneSnapshot(sprite: SpriteData): SpriteSnapshot {
    return {
      transform: sprite.transform ? { ...sprite.transform } : undefined,
      defaultFrameIndex: sprite.defaultFrameIndex,
      bsf: sprite.bsf ? (JSON.parse(JSON.stringify(sprite.bsf)) as BsfMeta) : undefined,
      animations: sprite.animations.map(a => ({
        ...a,
        frameNames: a.frameNames ? [...a.frameNames] : undefined,
      })),
      // 帧对象浅拷贝：blob/url 沿用引用，撤销删除/换序时直接复原
      frames: sprite.frames.map(f => ({ ...f })),
    }
  }

  /** 变化签名：帧只比对 url（blob 无法序列化，也不该参与比较） */
  function snapshotKey(snap: SpriteSnapshot | null): string {
    if (!snap) return ''
    return JSON.stringify({
      transform: snap.transform,
      defaultFrameIndex: snap.defaultFrameIndex,
      bsf: snap.bsf,
      animations: snap.animations,
      frames: snap.frames.map(f => f.url),
    })
  }

  function clearTimer() {
    if (commitTimer) {
      clearTimeout(commitTimer)
      commitTimer = null
    }
  }

  /** 把「修改前」的基线压入撤销栈，并把当前状态设为新基线 */
  function commitPending() {
    if (!commitTimer) return
    clearTimer()
    const sprite = getSprite()
    if (!sprite || !baseline) return
    const snap = cloneSnapshot(sprite)
    const key = snapshotKey(snap)
    if (key === baselineKey) return
    undoStack.value = [...undoStack.value, baseline].slice(-HISTORY_LIMIT)
    redoStack.value = []
    baseline = snap
    baselineKey = key
  }

  /** 切换角色 / 重载后重置历史（当前状态直接成为基线） */
  function reset() {
    clearTimer()
    undoStack.value = []
    redoStack.value = []
    applying = false
    const sprite = getSprite()
    baseline = sprite ? cloneSnapshot(sprite) : null
    baselineKey = snapshotKey(baseline)
  }

  /** 整体回写快照（属性赋值触发响应式更新与自动保存） */
  function applySnapshot(snap: SpriteSnapshot) {
    const sprite = getSprite()
    if (!sprite) return false
    sprite.transform = snap.transform ? { ...snap.transform } : undefined
    sprite.defaultFrameIndex = snap.defaultFrameIndex
    sprite.bsf = snap.bsf ? (JSON.parse(JSON.stringify(snap.bsf)) as BsfMeta) : undefined
    sprite.animations = snap.animations.map(a => ({
      ...a,
      frameNames: a.frameNames ? [...a.frameNames] : undefined,
    }))
    sprite.frames = snap.frames.map(f => {
      const copy = { ...f }
      return options.restoreFrame ? options.restoreFrame(copy) : copy
    })
    return true
  }

  function undo() {
    commitPending()
    if (!undoStack.value.length || !baseline) return
    const current = baseline
    const prev = undoStack.value[undoStack.value.length - 1]
    undoStack.value = undoStack.value.slice(0, -1)
    redoStack.value = [...redoStack.value, current].slice(-HISTORY_LIMIT)
    applying = true
    const ok = applySnapshot(prev)
    if (ok) {
      baseline = cloneSnapshot(getSprite() as SpriteData)
      baselineKey = snapshotKey(baseline)
    }
    applying = false
    if (ok) onApply()
  }

  function redo() {
    commitPending()
    if (!redoStack.value.length || !baseline) return
    const current = baseline
    const next = redoStack.value[redoStack.value.length - 1]
    redoStack.value = redoStack.value.slice(0, -1)
    undoStack.value = [...undoStack.value, current].slice(-HISTORY_LIMIT)
    applying = true
    const ok = applySnapshot(next)
    if (ok) {
      baseline = cloneSnapshot(getSprite() as SpriteData)
      baselineKey = snapshotKey(baseline)
    }
    applying = false
    if (ok) onApply()
  }

  // 任何可编辑状态变化 → 防抖合并后提交一步历史
  watch(
    () => {
      const sprite = getSprite()
      return sprite ? snapshotKey(cloneSnapshot(sprite)) : ''
    },
    (key) => {
      if (applying || !baseline) return
      if (key === baselineKey) return
      clearTimer()
      commitTimer = setTimeout(commitPending, COMMIT_DELAY)
    },
    { flush: 'sync' },
  )

  onBeforeUnmount(clearTimer)

  return { canUndo, canRedo, undo, redo, reset }
}
