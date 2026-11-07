import { nextTick } from 'vue'
import { useMapStore } from '../stores/map'
import { useMapEditorStore } from '../stores/mapEditor'
import { imageWorldToLocal } from '../utils/mapImageGeometry'
import { collectSnapLines, imageWorldRect, snapAxisValue, snapRectOffset, snapThreshold } from '../utils/smartSnap'

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
  /** 变换框整体容器：定位到图像中心并按旋转角旋转，框与手柄随图像一起转 */
  let transformGizmo: any = null
  let selectedImageSprite: any = null
  let selectedImageData: any = null
  let selectedImageLayerId: number = -1
  let transformDragging = false
  let transformHandleIndex = -1
  /** 缩放手柄按下时记录：旋转前图像中心（世界坐标）与旋转角（度） */
  let transformStartCenter = { x: 0, y: 0 }
  let transformStartRotation = 0
  /** 旋转前矩形（图像本地坐标，原点 = 图像中心） */
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

  /** 当前画布缩放（用于把屏幕吸附阈值换算成世界坐标） */
  function viewportScale(): number {
    const app = getApp()
    return Math.max(0.1, app?.stage?.scale?.x ?? 1)
  }

  /** 智能吸附候选线（排除正在移动的图层，避免吸附到自身） */
  function snapLines(excludeLayerId: number) {
    const ts = Math.max(1, mapStore.mapData.tileSize)
    return collectSnapLines(
      mapStore.mapData.layers,
      mapStore.mapData.width * ts,
      mapStore.mapData.height * ts,
      excludeLayerId,
    )
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
      const rad = (transformStartRotation * Math.PI) / 180
      const cos = Math.cos(rad)
      const sin = Math.sin(rad)
      // 世界坐标 → 图像本地坐标（相对旋转前中心，按 -旋转角 反向旋转），
      // 这样旋转过的图片拖手柄时边线仍沿图片自身方向伸缩
      const dx = worldPos.x - transformStartCenter.x
      const dy = worldPos.y - transformStartCenter.y
      let mx = cos * dx + sin * dy
      let my = -sin * dx + cos * dy
      // 智能吸附：未旋转时按世界网格吸附；旋转后本地轴不对应世界轴，按像素自由拖动
      if (mapEditorStore.smartSnap && Math.abs(sin) < 1e-9 && cos > 0) {
        const ts = Math.max(1, mapStore.mapData.tileSize)
        const lines = snapLines(selectedImageLayerId)
        const threshold = snapThreshold(viewportScale())
        mx = snapAxisValue(mx + transformStartCenter.x, lines.xs, ts, threshold) - transformStartCenter.x
        my = snapAxisValue(my + transformStartCenter.y, lines.ys, ts, threshold) - transformStartCenter.y
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

      // 本地矩形中心的位移按旋转角映射回世界坐标：旋转过的图片拖动时
      // 中心沿图片自身轴向移动，未旋转时与原逻辑完全一致
      const centerLocalX = (newLeft + newRight) / 2
      const centerLocalY = (newTop + newBottom) / 2
      const centerX = transformStartCenter.x + cos * centerLocalX - sin * centerLocalY
      const centerY = transformStartCenter.y + sin * centerLocalX + cos * centerLocalY
      selectedImageData.position = [centerX - pixelW / 2, centerY - pixelH / 2]
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
        // 智能吸附：图像左/中/右、上/中/下 就近对齐像素/网格/图像边缘与中心；关闭时不吸附
        if (mapEditorStore.smartSnap) {
          const rect = imageWorldRect({ ...selectedImageData, position: [nx, ny] })
          if (rect) {
            const ts = Math.max(1, mapStore.mapData.tileSize)
            const offset = snapRectOffset(
              rect,
              snapLines(selectedImageLayerId),
              ts,
              snapThreshold(viewportScale()),
            )
            nx += offset.dx
            ny += offset.dy
          }
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
    const angle = ((imgData.rotation ?? 0) * Math.PI) / 180

    // 变换框挂到容器上：容器定位于图像中心并按图像旋转角旋转，
    // 框与手柄都画在以中心为原点的本地坐标里 → 旋转图像时框跟着一起转
    transformGizmo = new PIXI.Container()
    transformGizmo.position.set(pos[0] + w / 2, pos[1] + h / 2)
    transformGizmo.rotation = angle
    app.stage.addChild(transformGizmo)

    const l = -w / 2
    const t = -h / 2
    const r = w / 2
    const b = h / 2

    // Bounding box
    transformBox = new PIXI.Graphics()
    transformBox.rect(l, t, w, h)
    transformBox.stroke({ width: 1, color: 0x528bff, alpha: 0.8 })
    transformBox.fill({ color: 0x528bff, alpha: 0.05 })
    transformGizmo.addChild(transformBox)

    // 8 handles: 4 corners + 4 edge midpoints
    const handlePositions = [
      [l, t], [0, t], [r, t],
      [r, 0],
      [r, b], [0, b], [l, b],
      [l, 0],
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
        // 按下时记录旋转前中心与旋转角：拖动计算在图像本地坐标系里进行
        const f = selectedImageData
        const p = f.position || [0, 0]
        const sx = f.scaleX ?? f.scale ?? 1
        const sy = f.scaleY ?? f.scale ?? 1
        const pw = (f.width || 64) * sx
        const ph = (f.height || 64) * sy
        transformStartRotation = f.rotation ?? 0
        transformStartCenter = { x: p[0] + pw / 2, y: p[1] + ph / 2 }
        transformStartBox = { left: -pw / 2, top: -ph / 2, right: pw / 2, bottom: ph / 2 }
      })
      transformGizmo.addChild(handle)
      return handle
    })

    // Rotation handle: circle above top-center, connected by a line
    rotationLine = new PIXI.Graphics()
    rotationLine.moveTo(0, t)
    rotationLine.lineTo(0, t - 30)
    rotationLine.stroke({ width: 1, color: 0x528bff, alpha: 0.8 })
    transformGizmo.addChild(rotationLine)

    rotationHandle = new PIXI.Graphics()
    rotationHandle.circle(0, t - 30, 6)
    rotationHandle.fill({ color: 0xffffff })
    rotationHandle.stroke({ width: 1.5, color: 0x528bff })
    rotationHandle.cursor = 'crosshair'
    rotationHandle.eventMode = 'static'
    rotationHandle.on('pointerdown', (e: any) => {
      e.stopPropagation()
      isRotating = true
      isImageDragging = true
      const f = selectedImageData
      const p = f.position || [0, 0]
      const pw = (f.width || 64) * (f.scaleX ?? f.scale ?? 1)
      const ph = (f.height || 64) * (f.scaleY ?? f.scale ?? 1)
      const ccx = p[0] + pw / 2
      const ccy = p[1] + ph / 2
      // 起始角必须用世界坐标计算：拖动时用的是 screenToWorld，
      // 若这里用屏幕坐标会和拖动时的坐标系不一致，按下瞬间角度差被放大 → 图像和框跳一下
      const pressWorld = screenToWorld(e)
      const pointerAngle = pressWorld
        ? Math.atan2(pressWorld.y - ccy, pressWorld.x - ccx)
        : Math.atan2(e.globalY - ccy, e.globalX - ccx)
      rotationStartAngle = pointerAngle - (f.rotation ?? 0) * Math.PI / 180
    })
    transformGizmo.addChild(rotationHandle)
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
    if (transformGizmo) {
      app?.stage.removeChild(transformGizmo)
      transformGizmo.destroy({ children: true })
      transformGizmo = null
    }
    // 子对象随容器一起销毁，这里只清空引用
    transformBox = null
    transformHandles = []
    rotationHandle = null
    rotationLine = null
    selectedImageData = null
    selectedImageSprite = null
  }

  function updateTransformBox() {
    if (!selectedImageData || !transformBox || !transformGizmo) return
    const pos = selectedImageData.position || [0, 0]
    const w = (selectedImageData.width || 64) * (selectedImageData.scaleX ?? selectedImageData.scale ?? 1)
    const h = (selectedImageData.height || 64) * (selectedImageData.scaleY ?? selectedImageData.scale ?? 1)
    const angle = ((selectedImageData.rotation ?? 0) * Math.PI) / 180

    // 容器跟随图像中心与旋转角，保证旋转时框与手柄和图像保持同一姿态
    transformGizmo.position.set(pos[0] + w / 2, pos[1] + h / 2)
    transformGizmo.rotation = angle

    const l = -w / 2
    const t = -h / 2
    const r = w / 2
    const b = h / 2

    transformBox.clear()
    transformBox.rect(l, t, w, h)
    transformBox.stroke({ width: 1, color: 0x528bff, alpha: 0.8 })
    transformBox.fill({ color: 0x528bff, alpha: 0.05 })

    const handlePositions = [
      [l, t], [0, t], [r, t],
      [r, 0],
      [r, b], [0, b], [l, b],
      [l, 0],
    ]

    transformHandles.forEach((handle, i) => {
      handle.clear()
      handle.rect(handlePositions[i][0] - 4, handlePositions[i][1] - 4, 8, 8)
      handle.fill({ color: 0xffffff })
      handle.stroke({ width: 1, color: 0x528bff })
    })

    // Update rotation handle position（本地坐标，随框旋转）
    if (rotationLine) {
      rotationLine.clear()
      rotationLine.moveTo(0, t)
      rotationLine.lineTo(0, t - 30)
      rotationLine.stroke({ width: 1, color: 0x528bff, alpha: 0.8 })
    }

    if (rotationHandle) {
      rotationHandle.clear()
      rotationHandle.circle(0, t - 30, 6)
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
