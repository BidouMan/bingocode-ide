import { nextTick } from 'vue'
import { useMapStore } from '../stores/map'
import { useMapEditorStore } from '../stores/mapEditor'
import { imageWorldToLocal } from '../utils/mapImageGeometry'

interface ImageTransformOptions {
  getApp: () => any
  getPIXI: () => any
  getLayerContainers: () => Map<number, any>
  screenToWorld: (e: PointerEvent | DragEvent) => { x: number; y: number } | null
  // 交互结束后请求整体重渲染（与原逻辑一致，确保最终状态落盘到精灵）
  onRenderRequest?: () => void
}

/**
 * 图像实例变换：选中判定、变换框（8 个缩放手柄 + 旋转手柄）、拖动移动与缩放旋转交互。
 */
export function useImageTransform(options: ImageTransformOptions) {
  const mapStore = useMapStore()
  const mapEditorStore = useMapEditorStore()
  const { getApp, getPIXI, getLayerContainers, screenToWorld } = options

  let transformBox: any = null
  let transformHandles: any[] = []
  let rotationHandle: any = null
  let rotationLine: any = null
  let selectedImageSprite: any = null
  let selectedImageData: any = null
  let selectedImageLayerId: number = -1
  let transformDragging = false
  let transformHandleIndex = -1
  let transformStartBox = { left: 0, top: 0, right: 0, bottom: 0 }
  let isRotating = false
  let rotationStartAngle = 0
  let isImageDragging = false

  // 图像整体拖动状态
  let isDraggingImage = false
  let imageDragStartWorld = { x: 0, y: 0 }
  let imageDragStartPos = [0, 0]

  function isTransformBusy(): boolean {
    return transformDragging || isRotating
  }

  function isImageDraggingNow(): boolean {
    return isImageDragging
  }

  function getSelectedImageLayerId(): number {
    return selectedImageLayerId
  }

  function isSelectedImage(img: any): boolean {
    return !!img && selectedImageData === img
  }

  function setSelection(layerId: number, imgData: any) {
    selectedImageData = imgData
    selectedImageLayerId = layerId
  }

  // 渲染出新精灵时，如果它正是当前选中实例就缓存下来
  function noteRenderedImage(imgData: any, sprite: any) {
    if (selectedImageData && imgData === selectedImageData) {
      selectedImageSprite = sprite
    }
  }

  // 自顶向下命中测试：扁平模型下一层一张图
  function hitTestImage(worldX: number, worldY: number): { layerId: number; layerIndex: number; imageData: any } | null {
    const layers = mapStore.mapData.layers
    for (let i = layers.length - 1; i >= 0; i--) {
      const layer = layers[i]
      if (layer.type !== 'image' || !layer.visible) continue
      const img = layer.image
      // 转到图片本地坐标判定，支持缩放与旋转
      const local = imageWorldToLocal(img, worldX, worldY)
      if (local.x >= 0 && local.x <= 1 && local.y >= 0 && local.y <= 1) {
        return { layerId: layer.id, layerIndex: i, imageData: img }
      }
    }
    return null
  }

  // 选择工具在图像模式下的按下处理，返回 true 表示事件已消费
  function handleSelectPointerDown(e: PointerEvent, layer: any): boolean {
    if (mapEditorStore.currentTool !== 'select' || !layer || layer.type !== 'image') return false
    const worldPos = screenToWorld(e)
    if (worldPos) {
      const hit = hitTestImage(worldPos.x, worldPos.y)
      if (hit) {
        if (selectedImageData !== hit.imageData) {
          // New image selected — build transform box
          selectedImageData = hit.imageData
          selectedImageLayerId = hit.layerId
          mapStore.setActiveLayer(hit.layerIndex)
          mapStore.selectImage(hit.layerId)
          showTransformBox(hit.imageData)
          cacheSelectedImageSprite()
        }
        imageDragStartWorld = { x: worldPos.x, y: worldPos.y }
        imageDragStartPos = [...hit.imageData.position]
        // Defer drag start so PixiJS handles can set their flags first
        nextTick(() => {
          if (!transformDragging && !isRotating) {
            isDraggingImage = true
            isImageDragging = true
          }
        })
        return true
      } else {
        removeTransformBox()
        mapStore.clearImageSelection()
      }
    }
    return true
  }

  // 旋转 / 缩放手柄 / 图像整体拖动，返回 true 表示事件已消费
  function handleTransformPointerMove(e: PointerEvent): boolean {
    // Rotation via handle
    if (isRotating && selectedImageData) {
      const pos = selectedImageData.position || [0, 0]
      const w = (selectedImageData.width || 64) * (selectedImageData.scaleX ?? selectedImageData.scale ?? 1)
      const h = (selectedImageData.height || 64) * (selectedImageData.scaleY ?? selectedImageData.scale ?? 1)
      const cx = pos[0] + w / 2
      const cy = pos[1] + h / 2
      const worldPos = screenToWorld(e)
      if (worldPos) {
        const angle = Math.atan2(worldPos.y - cy, worldPos.x - cx)
        selectedImageData.rotation = ((angle - rotationStartAngle) * 180 / Math.PI)
        updateTransformBox()
        updateSelectedImageSprite()
      }
      return true
    }

    // Transform handle drag
    if (transformDragging && selectedImageData && transformHandleIndex >= 0) {
      const worldPos = screenToWorld(e)
      if (!worldPos) return true
      const idx = transformHandleIndex
      let mx = worldPos.x
      let my = worldPos.y
      // 吸附网格：缩放手柄拖动的边对齐到最近网格线（与图像拖动吸附同一开关）
      if (mapEditorStore.snapToGrid) {
        const ts = mapStore.mapData.tileSize
        mx = Math.round(mx / ts) * ts
        my = Math.round(my / ts) * ts
      }

      // Each handle controls specific edges: [left, top, right, bottom]
      // Uncontrolled edges stay fixed at their initial position
      const handleEdges = [
        [true,  true,  false, false], // 0 top-left
        [false, true,  false, false], // 1 top-center
        [false, true,  true,  false], // 2 top-right
        [false, false, true,  false], // 3 right-center
        [false, false, true,  true ], // 4 bottom-right
        [false, false, false, true ], // 5 bottom-center
        [true,  false, false, true ], // 6 bottom-left
        [true,  false, false, false], // 7 left-center
      ]
      const edges = handleEdges[idx]

      let newLeft   = edges[0] ? mx : transformStartBox.left
      let newTop    = edges[1] ? my : transformStartBox.top
      let newRight  = edges[2] ? mx : transformStartBox.right
      let newBottom = edges[3] ? my : transformStartBox.bottom

      const minPx = 10

      // Corner handles (0,2,4,6): maintain aspect ratio
      const isCorner = idx % 2 === 0
      if (isCorner) {
        const origPW = transformStartBox.right - transformStartBox.left
        const origPH = transformStartBox.bottom - transformStartBox.top
        const ratio = origPW / origPH
        // Anchor is the opposite corner (fixed)
        let rawW: number, rawH: number
        if (idx === 0) { // top-left → anchor is bottom-right
          rawW = transformStartBox.right - mx
          rawH = transformStartBox.bottom - my
        } else if (idx === 2) { // top-right → anchor is bottom-left
          rawW = mx - transformStartBox.left
          rawH = transformStartBox.bottom - my
        } else if (idx === 4) { // bottom-right → anchor is top-left
          rawW = mx - transformStartBox.left
          rawH = my - transformStartBox.top
        } else { // idx === 6, bottom-left → anchor is top-right
          rawW = transformStartBox.right - mx
          rawH = my - transformStartBox.top
        }
        // Constrain to ratio using the dominant axis
        rawW = Math.max(rawW, minPx)
        rawH = Math.max(rawH, minPx)
        if (rawW / rawH > ratio) {
          rawH = rawW / ratio
        } else {
          rawW = rawH * ratio
        }
        // Recompute edges from anchor + constrained size
        if (idx === 0) { newLeft = transformStartBox.right - rawW; newTop = transformStartBox.bottom - rawH }
        else if (idx === 2) { newTop = transformStartBox.bottom - rawH; newRight = transformStartBox.left + rawW }
        else if (idx === 4) { newRight = transformStartBox.left + rawW; newBottom = transformStartBox.top + rawH }
        else { newLeft = transformStartBox.right - rawW; newBottom = transformStartBox.top + rawH }
      }

      let pixelW = Math.abs(newRight - newLeft)
      let pixelH = Math.abs(newBottom - newTop)
      if (pixelW < minPx) pixelW = minPx
      if (pixelH < minPx) pixelH = minPx

      selectedImageData.position = [
        Math.min(newLeft, newRight),
        Math.min(newTop, newBottom),
      ]
      // Update scale to match new pixel size, keeping natural width/height constant
      const origW = selectedImageData.width || 64
      const origH = selectedImageData.height || 64
      selectedImageData.scaleX = pixelW / origW
      selectedImageData.scaleY = pixelH / origH
      selectedImageData.scale = selectedImageData.scaleX
      updateTransformBox()
      updateSelectedImageSprite()
      return true
    }

    // Image body drag
    if (isDraggingImage && selectedImageData) {
      const worldPos = screenToWorld(e)
      if (worldPos) {
        const dx = worldPos.x - imageDragStartWorld.x
        const dy = worldPos.y - imageDragStartWorld.y
        let nx = imageDragStartPos[0] + dx
        let ny = imageDragStartPos[1] + dy
        // 吸附网格：图像左上角对齐到最近的网格点
        if (mapEditorStore.snapToGrid) {
          const ts = mapStore.mapData.tileSize
          nx = Math.round(nx / ts) * ts
          ny = Math.round(ny / ts) * ts
        }
        selectedImageData.position = [nx, ny]
        updateTransformBox()
        updateSelectedImageSprite()
      }
      return true
    }

    return false
  }

  // 变换/旋转/拖动结束，返回 true 表示事件已消费
  function handleTransformPointerUp(): boolean {
    if (transformDragging) {
      transformDragging = false
      transformHandleIndex = -1
      isImageDragging = false
      updateSelectedImageSprite()
      options.onRenderRequest?.()
      return true
    }

    if (isRotating) {
      isRotating = false
      isImageDragging = false
      updateSelectedImageSprite()
      options.onRenderRequest?.()
      return true
    }

    if (isDraggingImage) {
      isDraggingImage = false
      isImageDragging = false
      updateSelectedImageSprite()
      options.onRenderRequest?.()
      return true
    }

    return false
  }

  // 退出碰撞编辑时恢复选中图像的变换框
  function restoreSelectedImageUI() {
    const img = mapStore.selectedImage
    if (!img) return
    selectedImageData = img
    selectedImageLayerId = mapStore.selectedImageLayerId
    showTransformBox(img)
    cacheSelectedImageSprite()
  }

  function showTransformBox(imgData: any) {
    removeTransformBox()
    const app = getApp()
    const PIXI = getPIXI()
    if (!app || !PIXI) return

    selectedImageData = imgData
    const pos = imgData.position || [0, 0]
    const w = (imgData.width || 64) * (imgData.scaleX ?? imgData.scale ?? 1)
    const h = (imgData.height || 64) * (imgData.scaleY ?? imgData.scale ?? 1)
    const cx = pos[0] + w / 2
    const cy = pos[1] + h / 2

    // Bounding box
    transformBox = new PIXI.Graphics()
    transformBox.rect(pos[0], pos[1], w, h)
    transformBox.stroke({ width: 1, color: 0x528bff, alpha: 0.8 })
    transformBox.fill({ color: 0x528bff, alpha: 0.05 })
    app.stage.addChild(transformBox)

    // 8 handles: 4 corners + 4 edge midpoints
    const handlePositions = [
      [pos[0], pos[1]], [pos[0] + w / 2, pos[1]], [pos[0] + w, pos[1]],
      [pos[0] + w, pos[1] + h / 2],
      [pos[0] + w, pos[1] + h], [pos[0] + w / 2, pos[1] + h], [pos[0], pos[1] + h],
      [pos[0], pos[1] + h / 2],
    ]

    transformHandles = handlePositions.map((hp, i) => {
      const handle = new PIXI.Graphics()
      handle.rect(hp[0] - 4, hp[1] - 4, 8, 8)
      handle.fill({ color: 0xffffff })
      handle.stroke({ width: 1, color: 0x528bff })
      handle.cursor = ['nw-resize', 'n-resize', 'ne-resize', 'e-resize', 'se-resize', 's-resize', 'sw-resize', 'w-resize'][i]
      handle.eventMode = 'static'
      handle.on('pointerdown', (e: any) => {
        e.stopPropagation()
        transformDragging = true
        transformHandleIndex = i
        isImageDragging = true
        // Read current data at click time — not closure vars that may be stale
        const p = selectedImageData.position || [0, 0]
        const s = selectedImageData.scaleX ?? selectedImageData.scale ?? 1
        const sy = selectedImageData.scaleY ?? selectedImageData.scale ?? 1
        transformStartBox = {
          left: p[0], top: p[1],
          right: p[0] + (selectedImageData.width || 64) * s,
          bottom: p[1] + (selectedImageData.height || 64) * sy,
        }
      })
      app.stage.addChild(handle)
      return handle
    })

    // Rotation handle: circle above top-center, connected by a line
    const rotX = cx
    const rotY = pos[1] - 30

    rotationLine = new PIXI.Graphics()
    rotationLine.moveTo(cx, pos[1])
    rotationLine.lineTo(rotX, rotY)
    rotationLine.stroke({ width: 1, color: 0x528bff, alpha: 0.8 })
    app.stage.addChild(rotationLine)

    rotationHandle = new PIXI.Graphics()
    rotationHandle.circle(rotX, rotY, 6)
    rotationHandle.fill({ color: 0xffffff })
    rotationHandle.stroke({ width: 1.5, color: 0x528bff })
    rotationHandle.cursor = 'crosshair'
    rotationHandle.eventMode = 'static'
    rotationHandle.on('pointerdown', (e: any) => {
      e.stopPropagation()
      isRotating = true
      isImageDragging = true
      const angle = Math.atan2(e.globalY - cy, e.globalX - cx)
      rotationStartAngle = angle - (selectedImageData.rotation ?? 0) * Math.PI / 180
    })
    app.stage.addChild(rotationHandle)
  }

  function updateSelectedImageSprite() {
    if (!selectedImageSprite || !selectedImageData) return
    const pos = selectedImageData.position || [0, 0]
    const scaleX = selectedImageData.scaleX ?? selectedImageData.scale ?? 1
    const scaleY = selectedImageData.scaleY ?? selectedImageData.scale ?? 1
    const logicalW = selectedImageData.width || 64
    const logicalH = selectedImageData.height || 64
    const w = logicalW * scaleX
    const h = logicalH * scaleY
    selectedImageSprite.x = pos[0] + w / 2
    selectedImageSprite.y = pos[1] + h / 2
    selectedImageSprite.rotation = (selectedImageData.rotation ?? 0) * Math.PI / 180
    // SVG 等超采样纹理的像素尺寸 ≠ 逻辑尺寸，按 renderImageLayer 同款换算，
    // 直接 scale.set(scaleX) 会让 2x 纹理瞬间放大一倍
    const tw = selectedImageSprite.texture?.width || logicalW
    const th = selectedImageSprite.texture?.height || logicalH
    selectedImageSprite.scale.set(
      (logicalW * scaleX) / (tw || logicalW),
      (logicalH * scaleY) / (th || logicalH)
    )
    selectedImageSprite.alpha = selectedImageData.opacity ?? 1
    selectedImageSprite.visible = true
  }

  function cacheSelectedImageSprite() {
    const PIXI = getPIXI()
    selectedImageSprite = null
    if (selectedImageLayerId < 0 || !PIXI) return
    const container = getLayerContainers().get(selectedImageLayerId)
    if (!container) return
    // 扁平模型：一个图片图层只有一个图片精灵
    for (const child of container.children) {
      if (child instanceof PIXI.Sprite) {
        selectedImageSprite = child
        return
      }
    }
  }

  function removeTransformBox() {
    const app = getApp()
    if (transformBox) {
      app?.stage.removeChild(transformBox)
      transformBox.destroy()
      transformBox = null
    }
    for (const h of transformHandles) {
      app?.stage.removeChild(h)
      h.destroy()
    }
    transformHandles = []
    if (rotationHandle) {
      app?.stage.removeChild(rotationHandle)
      rotationHandle.destroy()
      rotationHandle = null
    }
    if (rotationLine) {
      app?.stage.removeChild(rotationLine)
      rotationLine.destroy()
      rotationLine = null
    }
    selectedImageData = null
    selectedImageSprite = null
  }

  function updateTransformBox() {
    if (!selectedImageData || !transformBox) return
    const pos = selectedImageData.position || [0, 0]
    const w = (selectedImageData.width || 64) * (selectedImageData.scaleX ?? selectedImageData.scale ?? 1)
    const h = (selectedImageData.height || 64) * (selectedImageData.scaleY ?? selectedImageData.scale ?? 1)

    transformBox.clear()
    transformBox.rect(pos[0], pos[1], w, h)
    transformBox.stroke({ width: 1, color: 0x528bff, alpha: 0.8 })
    transformBox.fill({ color: 0x528bff, alpha: 0.05 })

    const handlePositions = [
      [pos[0], pos[1]], [pos[0] + w / 2, pos[1]], [pos[0] + w, pos[1]],
      [pos[0] + w, pos[1] + h / 2],
      [pos[0] + w, pos[1] + h], [pos[0] + w / 2, pos[1] + h], [pos[0], pos[1] + h],
      [pos[0], pos[1] + h / 2],
    ]

    transformHandles.forEach((h, i) => {
      h.clear()
      h.rect(handlePositions[i][0] - 4, handlePositions[i][1] - 4, 8, 8)
      h.fill({ color: 0xffffff })
      h.stroke({ width: 1, color: 0x528bff })
    })

    // Update rotation handle position
    const cx = pos[0] + w / 2
    const rotX = cx
    const rotY = pos[1] - 30

    if (rotationLine) {
      rotationLine.clear()
      rotationLine.moveTo(cx, pos[1])
      rotationLine.lineTo(rotX, rotY)
      rotationLine.stroke({ width: 1, color: 0x528bff, alpha: 0.8 })
    }

    if (rotationHandle) {
      rotationHandle.clear()
      rotationHandle.circle(rotX, rotY, 6)
      rotationHandle.fill({ color: 0xffffff })
      rotationHandle.stroke({ width: 1.5, color: 0x528bff })
    }
  }

  // 切换地图时清理选中状态与所有拖拽标志
  function resetTransformState() {
    removeTransformBox()
    selectedImageData = null
    selectedImageLayerId = -1
    selectedImageSprite = null
    isDraggingImage = false
    isImageDragging = false
    isRotating = false
  }

  return {
    isTransformBusy,
    isImageDraggingNow,
    getSelectedImageLayerId,
    isSelectedImage,
    setSelection,
    noteRenderedImage,
    hitTestImage,
    handleSelectPointerDown,
    handleTransformPointerMove,
    handleTransformPointerUp,
    restoreSelectedImageUI,
    showTransformBox,
    updateSelectedImageSprite,
    cacheSelectedImageSprite,
    removeTransformBox,
    updateTransformBox,
    resetTransformState,
  }
}
