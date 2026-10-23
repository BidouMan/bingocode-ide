import { onBeforeUnmount, ref } from 'vue'

/**
 * 序列帧拖拽排序（PS 图层面板观感）：按下后超过阈值才进入拖拽，
 * 拖动时显示跟随光标的半透明快照 + 目标插入线，靠近边缘自动滚动。
 *
 * 用 mousedown/mousemove/mouseup 实现（Tauri WebView 下 HTML5 DnD 不可靠），
 * 松手后才真正重排，拖动过程中列表本身不移动。
 */
export interface FrameReorderOptions {
  /** 列表方向：造型列表为纵向，绘制页底部帧带为横向 */
  orientation: 'vertical' | 'horizontal'
  count: () => number
  /** 与 count 对齐的项元素（用于计算插入位置与范围） */
  getItemEls: () => HTMLElement[]
  /** 滚动容器（插入线范围 + 自动滚动） */
  getScrollEl: () => HTMLElement | null
  /** 放下回调：from = 原下标，to = 目标下标（已按移除后位置换算） */
  onReorder: (from: number, to: number) => void
}

const DRAG_THRESHOLD = 4
/** 松手后短暂屏蔽 click，避免拖拽尾随的 click 选中错误帧 */
const CLICK_GUARD_MS = 250

export function useFrameReorder(options: FrameReorderOptions) {
  const draggingIndex = ref<number | null>(null)
  /** 拖拽快照（固定定位跟随光标） */
  const ghost = ref<{ index: number; x: number; y: number } | null>(null)
  /** 插入线几何（固定定位，vertical 为横线 / horizontal 为竖线） */
  const indicator = ref<{ x: number; y: number; length: number } | null>(null)

  const isVertical = options.orientation === 'vertical'
  let pressedIndex: number | null = null
  let startX = 0
  let startY = 0
  let pointerX = 0
  let pointerY = 0
  let insertionSlot = 0
  let dragActive = false
  let rafId = 0
  let listening = false
  let clickGuardUntil = 0

  /** 更新插入位与插入线几何（拖动期间列表不变，直接按项中心判定） */
  function updateInsertion() {
    const els = options.getItemEls()
    const scroll = options.getScrollEl()
    if (els.length === 0 || !scroll) {
      insertionSlot = 0
      indicator.value = null
      return
    }
    const rects = els.map(el => el.getBoundingClientRect())
    const scrollRect = scroll.getBoundingClientRect()
    // 指针离开列表（留 8px 余量）时不显示插入线，松手落在列表外视为取消
    const inside =
      pointerX >= scrollRect.left - 8 && pointerX <= scrollRect.right + 8 &&
      pointerY >= scrollRect.top - 8 && pointerY <= scrollRect.bottom + 8
    if (!inside) {
      insertionSlot = -1
      indicator.value = null
      return
    }
    let slot = 0
    for (const r of rects) {
      if (isVertical ? pointerY > r.top + r.height / 2 : pointerX > r.left + r.width / 2) {
        slot++
      }
    }
    insertionSlot = slot
    if (isVertical) {
      const boundary = slot < rects.length ? rects[slot].top : rects[rects.length - 1].bottom
      indicator.value = { x: scrollRect.left + 6, y: boundary, length: scrollRect.width - 12 }
    } else {
      const boundary = slot < rects.length ? rects[slot].left : rects[rects.length - 1].right
      indicator.value = { x: boundary, y: scrollRect.top + 10, length: scrollRect.height - 20 }
    }
  }

  /** 靠近滚动容器边缘时自动滚动（速度随越界深度增加） */
  function autoScrollTick() {
    rafId = requestAnimationFrame(autoScrollTick)
    if (!dragActive || !indicator.value) return
    const el = options.getScrollEl()
    if (!el) return
    const rect = el.getBoundingClientRect()
    const edge = 28
    let delta = 0
    if (isVertical) {
      if (pointerY < rect.top + edge) delta = -Math.min(14, ((rect.top + edge - pointerY) / edge) * 12)
      else if (pointerY > rect.bottom - edge) delta = Math.min(14, ((pointerY - (rect.bottom - edge)) / edge) * 12)
      if (delta !== 0) {
        const before = el.scrollTop
        el.scrollTop += delta
        if (el.scrollTop !== before) updateInsertion()
      }
    } else {
      if (pointerX < rect.left + edge) delta = -Math.min(14, ((rect.left + edge - pointerX) / edge) * 12)
      else if (pointerX > rect.right - edge) delta = Math.min(14, ((pointerX - (rect.right - edge)) / edge) * 12)
      if (delta !== 0) {
        const before = el.scrollLeft
        el.scrollLeft += delta
        if (el.scrollLeft !== before) updateInsertion()
      }
    }
  }

  function beginDrag() {
    if (pressedIndex === null) return
    dragActive = true
    draggingIndex.value = pressedIndex
    ghost.value = { index: pressedIndex, x: pointerX, y: pointerY }
    document.body.style.cursor = 'grabbing'
    updateInsertion()
    cancelAnimationFrame(rafId)
    autoScrollTick()
  }

  function onMouseMove(e: MouseEvent) {
    if (pressedIndex === null) return
    pointerX = e.clientX
    pointerY = e.clientY
    if (!dragActive) {
      if (
        Math.abs(e.clientX - startX) <= DRAG_THRESHOLD &&
        Math.abs(e.clientY - startY) <= DRAG_THRESHOLD
      ) return
      beginDrag()
    }
    if (ghost.value) ghost.value = { ...ghost.value, x: pointerX, y: pointerY }
    updateInsertion()
  }

  function resetDragState() {
    dragActive = false
    pressedIndex = null
    draggingIndex.value = null
    ghost.value = null
    indicator.value = null
    cancelAnimationFrame(rafId)
    rafId = 0
    document.body.style.cursor = ''
    if (listening) {
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
      document.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('blur', onCancel)
      listening = false
    }
  }

  /** 结束拖拽：commit=true 时按插入位重排，否则取消 */
  function finishDrag(commit: boolean) {
    const from = draggingIndex.value
    const wasActive = dragActive
    const count = options.count()
    const outside = insertionSlot < 0
    let to = outside ? -1 : insertionSlot
    if (!outside && from !== null && to > from) to -= 1
    if (!outside) to = Math.min(Math.max(0, to), Math.max(0, count - 1))
    resetDragState()
    if (!wasActive || from === null) return
    if (commit && !outside && to !== from && from < count && to < count) {
      // 仅真正重排时屏蔽尾随 click（松手位置未变时 click 下标仍有效，保留正常选中）
      clickGuardUntil = performance.now() + CLICK_GUARD_MS
      options.onReorder(from, to)
    }
  }

  function onMouseUp() {
    finishDrag(true)
  }

  function onKeyDown(e: KeyboardEvent) {
    if (e.key === 'Escape') {
      e.stopPropagation()
      finishDrag(false)
    }
  }

  function onCancel() {
    finishDrag(false)
  }

  function onItemMouseDown(index: number, e: MouseEvent) {
    if (e.button !== 0) return
    if (index < 0 || index >= options.count()) return
    pressedIndex = index
    startX = e.clientX
    startY = e.clientY
    pointerX = e.clientX
    pointerY = e.clientY
    if (!listening) {
      document.addEventListener('mousemove', onMouseMove)
      document.addEventListener('mouseup', onMouseUp)
      document.addEventListener('keydown', onKeyDown)
      window.addEventListener('blur', onCancel)
      listening = true
    }
  }

  /** 拖拽结束后短暂屏蔽 click（防止松手时的 click 命中旧下标） */
  function shouldSuppressClick() {
    return performance.now() < clickGuardUntil
  }

  onBeforeUnmount(resetDragState)

  return {
    draggingIndex,
    ghost,
    indicator,
    onItemMouseDown,
    shouldSuppressClick,
  }
}
