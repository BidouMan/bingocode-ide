/**
 * 位图钢笔（自定义形状）：逐点落锚 + 橡皮筋预览 + 闭合后一次烤成像素。
 *
 * 与矢量钢笔共用同一套交互外观（锚点方块、首点闭合提示、固定预览配色），
 * 但产出直接写进位图，用于「位图模式」——不切换绘制模式。
 *
 * 所有尺寸按「屏幕像素 ÷ 缩放」换算，缩放变化时锚点/提示环大小保持恒定。
 * 预览配色固定（不跟随绘制颜色面板），闭合后才使用当前填充/描边设置落色。
 */

export interface BitmapPenStyle {
  /** 闭合后的落色（rgba css）；outline 时用作描边色 */
  color: string
  mode: 'fill' | 'outline'
  /** outline 模式下的描边宽度（画布像素） */
  lineWidth: number
}

export interface BitmapPenHost {
  /** 当前活动画布的 2D 上下文 */
  ctx: () => CanvasRenderingContext2D | null
  /** 取当前底稿（首个锚点落下的像素快照） */
  snapshot: () => ImageData | null
  restore: (img: ImageData) => void
  pushHistory: () => void
  popHistory: () => void
  zoom: () => number
  style: () => BitmapPenStyle
  /** 可选：把绘制裁剪到像素选区内 */
  clip?: (ctx: CanvasRenderingContext2D) => void
  /** 预览重绘后通知外层刷新（地图侧需要更新纹理） */
  onPreview?: () => void
  /**
   * 闭合落笔完成：回传图形像素包围盒（画布像素）、落笔前底稿，以及把闭合路径
   * 按相同样式画到任意 ctx 的绘制函数（外层据此把图形转成独立浮动对象）。
   */
  onFinish?: (
    bounds: { x: number; y: number; w: number; h: number },
    origin: ImageData,
    paint: (target: CanvasRenderingContext2D) => void
  ) => void
  /** 闭合落笔后通知外层（标脏 / 导出 / 存盘） */
  onDirty: () => void
}

/** 预览固定配色：与矢量钢笔一致（线段/提示环 = #818cf8，锚点描边 = #6366f1） */
const PREVIEW_COLOR = '#818cf8'
const ANCHOR_BORDER = '#6366f1'

export function createBitmapPen(host: BitmapPenHost) {
  /** 已落锚点（画布逻辑坐标） */
  let anchors: { x: number; y: number }[] = []
  /** 首个锚点落下时的底稿；null = 未在绘制中 */
  let base: ImageData | null = null

  function zoom() {
    return Math.max(0.1, host.zoom())
  }

  /** 屏幕像素 → 逻辑像素（随缩放反比） */
  function screen(v: number) {
    return v / zoom()
  }

  /** 闭合命中半径：屏幕 10px */
  function closeRadius() {
    return Math.max(6, screen(10))
  }

  function isActive() {
    return !!base
  }

  /** 重绘预览：先还原底稿，再画路径 / 锚点 / 闭合提示 */
  function drawPreview(cursor: { x: number; y: number } | null) {
    const ctx = host.ctx()
    if (!ctx || !base) return
    host.restore(base)
    const first = anchors[0]
    const hoveringClose =
      anchors.length >= 3 && !!cursor &&
      Math.hypot(cursor.x - first.x, cursor.y - first.y) <= closeRadius()

    ctx.save()
    host.clip?.(ctx)

    // 已落点连线 + 末段橡皮筋（虚线）
    const pts = cursor ? [...anchors, cursor] : anchors
    if (pts.length >= 2) {
      ctx.beginPath()
      ctx.moveTo(pts[0].x, pts[0].y)
      for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i].x, pts[i].y)
      ctx.strokeStyle = PREVIEW_COLOR
      ctx.lineWidth = Math.max(1, screen(1.4))
      ctx.lineJoin = 'round'
      ctx.lineCap = 'round'
      ctx.setLineDash([screen(5), screen(3)])
      ctx.stroke()
      ctx.setLineDash([])
    }

    // 首锚闭合提示环：≥3 点时常驻；光标进入命中半径后填充高亮，示意「点下去一定闭合」
    if (anchors.length >= 3) {
      ctx.beginPath()
      ctx.arc(first.x, first.y, screen(9), 0, Math.PI * 2)
      if (hoveringClose) {
        ctx.fillStyle = 'rgba(99, 102, 241, 0.28)'
        ctx.fill()
      }
      ctx.strokeStyle = ANCHOR_BORDER
      ctx.lineWidth = Math.max(1, screen(hoveringClose ? 2.2 : 1.4))
      ctx.stroke()
    }

    // 锚点方块：白底 + 蓝紫描边（屏幕恒定 6.5px）
    const half = Math.max(1.5, screen(3.25))
    ctx.lineWidth = Math.max(1, screen(1.5))
    for (const a of anchors) {
      ctx.fillStyle = '#ffffff'
      ctx.fillRect(a.x - half, a.y - half, half * 2, half * 2)
      ctx.strokeStyle = ANCHOR_BORDER
      ctx.strokeRect(a.x - half, a.y - half, half * 2, half * 2)
    }

    // 光标点：表示下一锚点落点；贴近首锚时隐藏，避免与提示环叠影
    if (cursor && !hoveringClose) {
      ctx.beginPath()
      ctx.arc(cursor.x, cursor.y, Math.max(1, screen(2.5)), 0, Math.PI * 2)
      ctx.fillStyle = ANCHOR_BORDER
      ctx.fill()
    }

    ctx.restore()
    host.onPreview?.()
  }

  /** 落点：首点起笔；双击 / 回到首锚（≥3 点）闭合 */
  function press(p: { x: number; y: number }, detail = 1) {
    if (!base) {
      const snap = host.snapshot()
      if (!snap) return
      host.pushHistory()
      base = snap
      anchors = [{ x: p.x, y: p.y }]
      drawPreview(p)
      return
    }
    if (detail >= 2) {
      // 双击：先落点（不足 3 点时补成有效锚点），再尝试闭合（与矢量钢笔一致）
      if (anchors.length < 3) anchors = [...anchors, { x: p.x, y: p.y }]
      finish()
      return
    }
    const first = anchors[0]
    if (anchors.length >= 3 && Math.hypot(p.x - first.x, p.y - first.y) <= closeRadius()) {
      finish()
      return
    }
    anchors.push({ x: p.x, y: p.y })
    drawPreview(p)
  }

  /** 移动：橡皮筋预览跟随（不需要按住鼠标） */
  function move(p: { x: number; y: number }) {
    if (!base) return
    drawPreview(p)
  }

  /** 锚点包围盒（画布像素，按落色外扩 pad）——用于闭合后自动建立编辑选框 */
  function anchorBounds(pad: number) {
    let minX = Infinity
    let minY = Infinity
    let maxX = -Infinity
    let maxY = -Infinity
    for (const a of anchors) {
      if (a.x < minX) minX = a.x
      if (a.y < minY) minY = a.y
      if (a.x > maxX) maxX = a.x
      if (a.y > maxY) maxY = a.y
    }
    return {
      x: minX - pad,
      y: minY - pad,
      w: maxX - minX + pad * 2,
      h: maxY - minY + pad * 2,
    }
  }

  /** 闭合：按当前填充/描边设置把多边形烤进像素 */
  function finish(): boolean {
    const ctx = host.ctx()
    if (!base || anchors.length < 3 || !ctx) return false
    const origin = base
    host.restore(base)
    const style = host.style()
    // 描边模式线条会向外扩 lw/2，包围盒同步外扩（填充模式留 1px 抗锯齿余量）
    const pad = Math.ceil((style.mode === 'outline' ? Math.max(1, style.lineWidth) : 2) / 2) + 1
    const bounds = anchorBounds(pad)
    // 闭合路径绘制函数：按当前样式画到任意 ctx（锚点坐标 = 画布像素；
    // anchors 随后清空，这里先拷贝一份供外层转浮动对象时复用）
    const pts = anchors.map(a => ({ x: a.x, y: a.y }))
    const paint = (target: CanvasRenderingContext2D) => {
      target.save()
      host.clip?.(target)
      target.beginPath()
      target.moveTo(pts[0].x, pts[0].y)
      for (let i = 1; i < pts.length; i++) target.lineTo(pts[i].x, pts[i].y)
      target.closePath()
      if (style.mode === 'fill') {
        target.fillStyle = style.color
        target.fill()
      } else {
        target.strokeStyle = style.color
        target.lineWidth = Math.max(1, style.lineWidth)
        target.lineJoin = 'round'
        target.lineCap = 'round'
        target.stroke()
      }
      target.restore()
    }
    paint(ctx)
    base = null
    anchors = []
    host.onFinish?.(bounds, origin, paint)
    host.onDirty()
    return true
  }

  /** 丢弃半成品：还原底稿并回滚起笔时压的撤销步 */
  function cancel(rollbackHistory = true): boolean {
    if (!base) return false
    host.restore(base)
    base = null
    anchors = []
    if (rollbackHistory) host.popHistory()
    host.onPreview?.()
    return true
  }

  return { isActive, press, move, finish, cancel }
}
