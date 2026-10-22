import { watch } from 'vue'
import { useMapStore } from '../stores/map'
import { useMapEditorStore } from '../stores/mapEditor'
import { imageLocalToWorld, imageWorldToLocal, snapImageLocal } from '../utils/mapImageGeometry'

interface ImageCollisionOptions {
  getApp: () => any
  getPIXI: () => any
  getScale: () => number
}

/**
 * 图像实例碰撞编辑：叠加层绘制、矩形/多边形/顶点工具的全部交互。
 */
export function useImageCollisionEditor(options: ImageCollisionOptions) {
  const mapStore = useMapStore()
  const mapEditorStore = useMapEditorStore()
  const { getApp, getPIXI, getScale } = options

  let collisionGraphics: any = null
  let collisionDraft: { x: number; y: number }[] = []      // 钢笔草稿（图片本地归一化坐标）
  let collisionDraftActive = false
  let collisionPreviewLocal: { x: number; y: number } | null = null
  let collisionRectStart: { x: number; y: number } | null = null
  let collisionRectCurrent: { x: number; y: number } | null = null
  let draggingVertexIndex = -1
  let selectedVertexIndex = -1
  let lastPolygonClickAt = 0

  function pointToSegmentDistance(p: { x: number; y: number }, a: { x: number; y: number }, b: { x: number; y: number }): number {
    const dx = b.x - a.x
    const dy = b.y - a.y
    const lenSq = dx * dx + dy * dy
    if (lenSq === 0) return Math.hypot(p.x - a.x, p.y - a.y)
    const t = Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / lenSq))
    return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy))
  }

  function findNearestVertex(img: any, world: { x: number; y: number }, threshold: number): number {
    const pts = img.collisionShape?.points || []
    let best = -1
    let bestDist = threshold
    pts.forEach((p: number[], i: number) => {
      const wp = imageLocalToWorld(img, { x: p[0], y: p[1] })
      const d = Math.hypot(wp.x - world.x, wp.y - world.y)
      if (d < bestDist) {
        bestDist = d
        best = i
      }
    })
    return best
  }

  // 查找最近的边，返回边起点顶点下标（用于插点）
  function findNearestEdge(img: any, world: { x: number; y: number }, threshold: number): number {
    const pts = img.collisionShape?.points || []
    if (pts.length < 2) return -1
    let best = -1
    let bestDist = threshold
    for (let i = 0; i < pts.length; i++) {
      const a = imageLocalToWorld(img, { x: pts[i][0], y: pts[i][1] })
      const b = imageLocalToWorld(img, { x: pts[(i + 1) % pts.length][0], y: pts[(i + 1) % pts.length][1] })
      const d = pointToSegmentDistance(world, a, b)
      if (d < bestDist) {
        bestDist = d
        best = i
      }
    }
    return best
  }

  function drawCollisionPolygon(
    g: any,
    img: any,
    localPoints: { x: number; y: number }[],
    color: number,
    fillAlpha: number,
    lineWidth: number,
    withHandles: boolean,
  ) {
    if (localPoints.length < 2) return
    const scale = getScale()
    const world = localPoints.map(p => imageLocalToWorld(img, p))
    g.moveTo(world[0].x, world[0].y)
    for (let i = 1; i < world.length; i++) g.lineTo(world[i].x, world[i].y)
    g.closePath()
    g.fill({ color, alpha: fillAlpha })
    g.stroke({ width: lineWidth, color, alpha: 0.9 })

    if (!withHandles) return
    const radius = 4 / scale
    world.forEach((p, i) => {
      if (i === selectedVertexIndex) {
        g.circle(p.x, p.y, radius * 1.6)
        g.fill({ color: 0x528bff, alpha: 0.9 })
      }
      g.circle(p.x, p.y, radius)
      g.fill({ color: i === 0 ? 0x5BFB84 : 0xffffff })
      g.stroke({ width: 1 / scale, color: 0xff5050 })
    })
  }

  function drawCollisionOverlay() {
    const app = getApp()
    const PIXI = getPIXI()
    if (!app || !PIXI) return
    const scale = getScale()
    if (!collisionGraphics) {
      collisionGraphics = new PIXI.Graphics()
      collisionGraphics.eventMode = 'none'
    }
    // 始终保持在舞台最上层
    if (collisionGraphics.parent) collisionGraphics.parent.removeChild(collisionGraphics)
    app.stage.addChild(collisionGraphics)

    const g = collisionGraphics
    g.clear()
    const lineWidth = 1.5 / scale

    const img = mapStore.selectedImage

    // 全局碰撞可视化（所有图像图层）
    if (mapEditorStore.showCollision) {
      for (const layer of mapStore.mapData.layers) {
        if (layer.type !== 'image' || !layer.visible) continue
        for (const layerImg of layer.images) {
          const pts = layerImg.collisionShape?.points
          if (!layerImg.collisionEnabled || !pts || pts.length < 3 || layerImg === img) continue
          drawCollisionPolygon(
            g, layerImg,
            pts.map((p: number[]) => ({ x: p[0], y: p[1] })),
            0xff5050, 0.12, lineWidth, false,
          )
        }
      }
    }

    if (!img) return

    // 已保存的碰撞形状
    const pts = img.collisionShape?.points
    if (pts && pts.length >= 3) {
      const editing = mapEditorStore.imageCollisionTool !== 'none'
      drawCollisionPolygon(
        g, img,
        pts.map((p: number[]) => ({ x: p[0], y: p[1] })),
        img.collisionEnabled ? 0xff5050 : 0x888888,
        img.collisionEnabled ? 0.2 : 0.1,
        lineWidth,
        editing,
      )
    }

    // 矩形拖拽预览
    if (collisionRectStart && collisionRectCurrent) {
      const x0 = Math.min(collisionRectStart.x, collisionRectCurrent.x)
      const x1 = Math.max(collisionRectStart.x, collisionRectCurrent.x)
      const y0 = Math.min(collisionRectStart.y, collisionRectCurrent.y)
      const y1 = Math.max(collisionRectStart.y, collisionRectCurrent.y)
      drawCollisionPolygon(
        g, img,
        [{ x: x0, y: y0 }, { x: x1, y: y0 }, { x: x1, y: y1 }, { x: x0, y: y1 }],
        0x5BFB84, 0.15, lineWidth, false,
      )
    }

    // 钢笔草稿
    if (collisionDraftActive && collisionDraft.length > 0) {
      const world = collisionDraft.map(p => imageLocalToWorld(img, p))
      g.moveTo(world[0].x, world[0].y)
      for (let i = 1; i < world.length; i++) g.lineTo(world[i].x, world[i].y)
      if (collisionPreviewLocal) {
        const preview = imageLocalToWorld(img, collisionPreviewLocal)
        g.lineTo(preview.x, preview.y)
      }
      g.stroke({ width: lineWidth, color: 0x5BFB84, alpha: 0.9 })

      const radius = 4 / scale
      world.forEach((p, i) => {
        g.circle(p.x, p.y, radius)
        g.fill({ color: i === 0 ? 0x5BFB84 : 0xffffff })
        g.stroke({ width: 1 / scale, color: 0xff5050 })
      })
    }
  }

  function cancelCollisionDraft() {
    collisionDraftActive = false
    collisionDraft = []
    collisionPreviewLocal = null
    collisionRectStart = null
    collisionRectCurrent = null
    draggingVertexIndex = -1
  }

  function closeCollisionDraft() {
    if (collisionDraft.length >= 3) {
      mapStore.setImageCollisionPoints(collisionDraft.map(p => [p.x, p.y]))
    }
    collisionDraftActive = false
    collisionDraft = []
    collisionPreviewLocal = null
    drawCollisionOverlay()
  }

  function deleteSelectedVertex() {
    const img = mapStore.selectedImage
    if (!img) return
    const pts = img.collisionShape?.points
    if (!pts || pts.length <= 3 || selectedVertexIndex < 0) return
    const next = pts.map((p: number[]) => [p[0], p[1]])
    next.splice(selectedVertexIndex, 1)
    selectedVertexIndex = -1
    mapStore.setImageCollisionPoints(next)
    drawCollisionOverlay()
  }

  function handleCollisionPointerDown(img: any, world: { x: number; y: number }, button: number) {
    const raw = imageWorldToLocal(img, world.x, world.y)
    const tool = mapEditorStore.imageCollisionTool
    // 点击图片范围外：只用于取消顶点选中，不在图片外生成锚点
    if (raw.x < -0.02 || raw.x > 1.02 || raw.y < -0.02 || raw.y > 1.02) {
      if (tool === 'vertex') {
        selectedVertexIndex = -1
        drawCollisionOverlay()
      }
      return
    }
    const local = snapImageLocal(img, raw)

    // 右键：钢笔撤销上一点 / 删除顶点
    if (button === 2) {
      if (tool === 'polygon' && collisionDraftActive && collisionDraft.length > 0) {
        collisionDraft.pop()
        if (collisionDraft.length === 0) collisionDraftActive = false
      } else if (tool === 'vertex') {
        const idx = findNearestVertex(img, world, 10 / getScale())
        if (idx >= 0) {
          selectedVertexIndex = idx
          deleteSelectedVertex()
        }
      }
      drawCollisionOverlay()
      return
    }
    if (button !== 0) return

    if (tool === 'rect') {
      collisionRectStart = local
      collisionRectCurrent = local
    } else if (tool === 'polygon') {
      if (collisionDraftActive && collisionDraft.length >= 3) {
        const firstWorld = imageLocalToWorld(img, collisionDraft[0])
        // 点首点闭合
        if (Math.hypot(firstWorld.x - world.x, firstWorld.y - world.y) < 10 / getScale()) {
          closeCollisionDraft()
          return
        }
        // 双击闭合
        const now = Date.now()
        const lastWorld = imageLocalToWorld(img, collisionDraft[collisionDraft.length - 1])
        if (now - lastPolygonClickAt < 350 &&
            Math.hypot(lastWorld.x - world.x, lastWorld.y - world.y) < 10 / getScale()) {
          closeCollisionDraft()
          return
        }
      }
      if (!collisionDraftActive) {
        collisionDraftActive = true
        collisionDraft = []
      }
      const last = collisionDraft[collisionDraft.length - 1]
      if (!last || Math.hypot(last.x - local.x, last.y - local.y) > 1e-5) {
        collisionDraft.push(local)
      }
      lastPolygonClickAt = Date.now()
    } else if (tool === 'vertex') {
      const idx = findNearestVertex(img, world, 10 / getScale())
      if (idx >= 0) {
        draggingVertexIndex = idx
        selectedVertexIndex = idx
      } else {
        const edge = findNearestEdge(img, world, 8 / getScale())
        if (edge >= 0) {
          const next = (img.collisionShape?.points || []).map((p: number[]) => [p[0], p[1]])
          next.splice(edge + 1, 0, [local.x, local.y])
          mapStore.setImageCollisionPoints(next)
          draggingVertexIndex = edge + 1
          selectedVertexIndex = edge + 1
        }
      }
    }
    drawCollisionOverlay()
  }

  function handleCollisionPointerMove(img: any, world: { x: number; y: number }) {
    const local = snapImageLocal(img, imageWorldToLocal(img, world.x, world.y))
    const tool = mapEditorStore.imageCollisionTool

    if (tool === 'rect' && collisionRectStart) {
      collisionRectCurrent = local
      drawCollisionOverlay()
    } else if (tool === 'polygon' && collisionDraftActive) {
      collisionPreviewLocal = local
      drawCollisionOverlay()
    } else if (tool === 'vertex' && draggingVertexIndex >= 0) {
      const next = (img.collisionShape?.points || []).map((p: number[]) => [p[0], p[1]])
      next[draggingVertexIndex] = [local.x, local.y]
      mapStore.setImageCollisionPoints(next)
      drawCollisionOverlay()
    }
  }

  function finishCollisionRect() {
    if (!collisionRectStart || !collisionRectCurrent) return
    const img = mapStore.selectedImage
    if (img) {
      const x0 = Math.min(collisionRectStart.x, collisionRectCurrent.x)
      const x1 = Math.max(collisionRectStart.x, collisionRectCurrent.x)
      const y0 = Math.min(collisionRectStart.y, collisionRectCurrent.y)
      const y1 = Math.max(collisionRectStart.y, collisionRectCurrent.y)
      if (x1 - x0 > 0.005 && y1 - y0 > 0.005) {
        mapStore.setImageCollisionPoints([
          [x0, y0], [x1, y0], [x1, y1], [x0, y1],
        ])
      }
    }
    collisionRectStart = null
    collisionRectCurrent = null
    drawCollisionOverlay()
  }

  // 指针抬起：矩形收尾 / 顶点结束拖拽，返回 true 表示已消费
  function handlePointerUp(): boolean {
    if (mapEditorStore.imageCollisionTool === 'rect' && collisionRectStart) {
      finishCollisionRect()
      return true
    }
    if (draggingVertexIndex >= 0) {
      draggingVertexIndex = -1
      drawCollisionOverlay()
      return true
    }
    return false
  }

  // 指针离开画布：取消未完成的草稿，避免残留预览
  function resetDraftOnLeave() {
    if (collisionRectStart) {
      collisionRectStart = null
      collisionRectCurrent = null
    }
    collisionPreviewLocal = null
    draggingVertexIndex = -1
    drawCollisionOverlay()
  }

  // 碰撞编辑快捷键；返回 true 表示碰撞编辑期间已接管键盘
  function handleKeyDown(e: KeyboardEvent): boolean {
    if (mapEditorStore.imageCollisionTool === 'none') return false
    if (e.key === 'Escape') {
      if (collisionDraftActive || collisionRectStart) {
        cancelCollisionDraft()
      } else {
        mapEditorStore.setImageCollisionTool('none')
      }
      drawCollisionOverlay()
      return true
    }
    if (e.key === 'Enter' && mapEditorStore.imageCollisionTool === 'polygon' && collisionDraftActive) {
      e.preventDefault()
      closeCollisionDraft()
      return true
    }
    if ((e.key === 'Delete' || e.key === 'Backspace') && mapEditorStore.imageCollisionTool === 'vertex') {
      e.preventDefault()
      deleteSelectedVertex()
      return true
    }
    // 碰撞编辑期间不响应工具切换快捷键
    return true
  }

  function clearVertexSelection() {
    selectedVertexIndex = -1
  }

  function dispose() {
    collisionGraphics = null
  }

  // 碰撞数据 / 显示开关变化 → 只重绘叠加层
  watch(() => mapStore.collisionRevision, () => drawCollisionOverlay())
  watch(() => mapEditorStore.showCollision, () => drawCollisionOverlay())

  return {
    drawCollisionOverlay,
    cancelCollisionDraft,
    closeCollisionDraft,
    deleteSelectedVertex,
    handleCollisionPointerDown,
    handleCollisionPointerMove,
    finishCollisionRect,
    handlePointerUp,
    resetDraftOnLeave,
    handleKeyDown,
    clearVertexSelection,
    dispose,
  }
}
