import type { MapResource } from '../stores/map'
import { useMapStore } from '../stores/map'
import { useMapEditorStore } from '../stores/mapEditor'

interface TilePainterOptions {
  getApp: () => any
  getPIXI: () => any
  // 由画布渲染核心提供
  renderTile: (layerId: number, x: number, y: number, tileId: number) => Promise<void>
  getTileSprite: (key: string) => any
  getTileTexture: (resource: MapResource, tileIndex: number) => Promise<any>
  onTilePainted: (x: number, y: number, tileId: number) => void
  onTileErased: (x: number, y: number) => void
  onRenderRequest: () => void
}

/**
 * 绘制图层瓦片操作：画笔/橡皮/油漆桶/移动工具与预览框。
 */
export function useTilePainter(options: TilePainterOptions) {
  const mapStore = useMapStore()
  const mapEditorStore = useMapEditorStore()
  const { getApp, getPIXI } = options

  let lastPaintedKey = ''
  let previewTile: any = null

  // Move tool state
  let moveStartPos: { x: number; y: number } | null = null
  let moveTileId = 0
  let moveStartSprite: any = null
  let moveDragSprite: any = null

  // 编码 tileId: 使用Tiled标准，GID = firstgid + tileIndex
  // firstgid 由 tileSets 数组中的瓦片集确定
  function encodeTileId(_layerId: number, localRIdx: number, tileIndex: number): number {
    // 直接用素材自己的 firstgid，不再依赖图层顺序偏移
    const resource = mapStore.activeLayerResources[localRIdx]
    if (resource) return resource.firstgid + tileIndex
    return tileIndex + 1
  }

  async function updateTileAt(layerIndex: number, x: number, y: number) {
    const layer = mapStore.mapData.layers[layerIndex]
    if (!layer || layer.type !== 'drawing') return
    const tileId = layer.tiles[`${x},${y}`] ?? 0
    await options.renderTile(layer.id, x, y, tileId)
  }

  function updatePreview(pos: { x: number; y: number } | null) {
    const app = getApp()
    const PIXI = getPIXI()
    if (!app || !PIXI) return

    if (!pos) {
      if (previewTile) previewTile.visible = false
      return
    }

    const tileSize = mapStore.mapData.tileSize

    if (!previewTile) {
      previewTile = new PIXI.Graphics()
      app.stage.addChild(previewTile)
    }
    previewTile.clear()
    previewTile.rect(pos.x * tileSize, pos.y * tileSize, tileSize, tileSize)
    previewTile.stroke({ width: 1, color: 0x5BFB84, alpha: 0.8 })
    previewTile.fill({ color: 0x5BFB84, alpha: 0.15 })
    previewTile.visible = true
  }

  function hidePreview() {
    if (previewTile) previewTile.visible = false
  }

  function resetPaintKey() {
    lastPaintedKey = ''
  }

  // 绘制工具按下：左键绘制，右键擦除；橡皮、油漆桶、移动工具同理
  function handlePaintPointerDown(e: PointerEvent, pos: { x: number; y: number }) {
    // 绘制工具：左键绘制，右键擦除
    if (mapEditorStore.currentTool === 'draw' && mapStore.activeLayer && mapStore.activeLayer.type === 'drawing') {
      if (e.button === 0 && mapStore.selectedTileIndex >= 0) {
        const tileId = encodeTileId(mapStore.activeLayer.id, mapStore.selectedResourceIndex, mapStore.selectedTileIndex)
        mapStore.setTile(pos.x, pos.y, tileId)
        lastPaintedKey = `${pos.x},${pos.y}`
        updateTileAt(mapStore.activeLayerIndex, pos.x, pos.y)
        options.onTilePainted(pos.x, pos.y, tileId)
      } else if ((e.button as number) === 2) {
        mapStore.setTile(pos.x, pos.y, 0)
        lastPaintedKey = `${pos.x},${pos.y}`
        updateTileAt(mapStore.activeLayerIndex, pos.x, pos.y)
        options.onTileErased(pos.x, pos.y)
      }
    } else if (mapEditorStore.currentTool === 'erase') {
      mapStore.setTile(pos.x, pos.y, 0)
      lastPaintedKey = `${pos.x},${pos.y}`
      updateTileAt(mapStore.activeLayerIndex, pos.x, pos.y)
      options.onTileErased(pos.x, pos.y)
    } else if (mapEditorStore.currentTool === 'fill' && mapStore.selectedTileIndex >= 0 && mapStore.activeLayer) {
      const tileId = encodeTileId(mapStore.activeLayer.id, mapStore.selectedResourceIndex, mapStore.selectedTileIndex)
      floodFill(pos.x, pos.y, tileId)
    } else if (mapEditorStore.currentTool === 'move') {
      const layer = mapStore.activeLayer
      if (layer && layer.type === 'drawing') {
        const tileId = layer.tiles[`${pos.x},${pos.y}`] ?? 0
        if (tileId !== 0) {
          moveStartPos = pos
          moveTileId = tileId
          const spriteKey = `${layer.id}:${pos.x},${pos.y}`
          moveStartSprite = options.getTileSprite(spriteKey) ?? null
          if (moveStartSprite) moveStartSprite.visible = false
          // 异步加载纹理创建拖拽 sprite
          const PIXI = getPIXI()
          const app = getApp()
          const tileSize = mapStore.mapData.tileSize
          const tileSets = mapStore.mapData.tileSets
          let matchedTs: any = null
          for (let i = tileSets.length - 1; i >= 0; i--) {
            if (tileId >= tileSets[i].firstgid) { matchedTs = tileSets[i]; break }
          }
          const tIdx = matchedTs ? tileId - matchedTs.firstgid : 0
          const texRes = matchedTs
            ? mapStore.mapData.resources.find((r: MapResource) => r.firstgid === matchedTs.firstgid)
              ?? mapStore.mapData.resources.find((r: MapResource) => r.path === matchedTs.imagePath)
            : null
          if (texRes && PIXI && app) {
            options.getTileTexture(texRes, tIdx).then(texture => {
              if (!texture || !moveTileId) return
              moveDragSprite = new PIXI.Sprite(texture)
              moveDragSprite.width = tileSize
              moveDragSprite.height = tileSize
              moveDragSprite.x = pos.x * tileSize
              moveDragSprite.y = pos.y * tileSize
              app.stage.addChild(moveDragSprite)
            }).catch(() => {})
          }
        }
      }
    }
  }

  // 绘制工具拖动：连续绘制 + 移动工具预览
  function handlePaintPointerMove(e: PointerEvent, pos: { x: number; y: number } | null) {
    // Move tool preview
    if (moveStartPos && moveTileId && moveDragSprite && pos) {
      const tileSize = mapStore.mapData.tileSize
      moveDragSprite.x = pos.x * tileSize
      moveDragSprite.y = pos.y * tileSize
    }

    if (mapEditorStore.currentTool === 'draw' || mapEditorStore.currentTool === 'erase' || mapEditorStore.currentTool === 'fill') {
      updatePreview(pos)

      if (pos && (e.buttons === 1 || e.buttons === 2)) {
        const key = `${pos.x},${pos.y}`
        if (key !== lastPaintedKey) {
          // 绘制工具：左键绘制，右键擦除
          if (mapEditorStore.currentTool === 'draw' && mapStore.activeLayer && mapStore.activeLayer.type === 'drawing') {
            if (e.buttons === 2) {
              mapStore.setTile(pos.x, pos.y, 0)
              updateTileAt(mapStore.activeLayerIndex, pos.x, pos.y)
            } else if (mapStore.selectedTileIndex >= 0) {
              const tileId = encodeTileId(mapStore.activeLayer.id, mapStore.selectedResourceIndex, mapStore.selectedTileIndex)
              mapStore.setTile(pos.x, pos.y, tileId)
              updateTileAt(mapStore.activeLayerIndex, pos.x, pos.y)
              options.onTilePainted(pos.x, pos.y, tileId)
            }
          } else if (mapEditorStore.currentTool === 'erase') {
            mapStore.setTile(pos.x, pos.y, 0)
            updateTileAt(mapStore.activeLayerIndex, pos.x, pos.y)
            options.onTileErased(pos.x, pos.y)
          }
          lastPaintedKey = key
        }
      }
    }
  }

  // 移动工具落子：把瓦片放到新位置
  function handlePointerUp(pos: { x: number; y: number } | null) {
    if (moveStartPos && moveTileId) {
      if (pos && (pos.x !== moveStartPos.x || pos.y !== moveStartPos.y)) {
        const layer = mapStore.activeLayer
        if (layer && layer.type === 'drawing') {
          mapStore.setTile(moveStartPos.x, moveStartPos.y, 0)
          mapStore.setTile(pos.x, pos.y, moveTileId)
          updateTileAt(mapStore.activeLayerIndex, moveStartPos.x, moveStartPos.y)
          updateTileAt(mapStore.activeLayerIndex, pos.x, pos.y)
        }
      } else if (moveStartSprite) {
        // 未移动，恢复原始 sprite 可见
        moveStartSprite.visible = true
      }
      moveStartPos = null
      moveTileId = 0
      moveStartSprite = null
      if (moveDragSprite) {
        const app = getApp()
        app?.stage.removeChild(moveDragSprite)
        moveDragSprite.destroy()
        moveDragSprite = null
      }
    }
  }

  function floodFill(startX: number, startY: number, fillTileId: number) {
    const layer = mapStore.activeLayer
    if (!layer || layer.type !== 'drawing') return

    const targetTileId = layer.tiles[`${startX},${startY}`] ?? 0
    if (targetTileId === fillTileId) return

    const { width, height } = mapStore.mapData
    const stack: [number, number][] = [[startX, startY]]
    const visited = new Set<string>()

    while (stack.length > 0) {
      const [x, y] = stack.pop()!
      const key = `${x},${y}`
      if (visited.has(key)) continue
      visited.add(key)

      if (x < 0 || x >= width || y < 0 || y >= height) continue

      const currentId = layer.tiles[key] ?? 0
      if (currentId !== targetTileId) continue

      mapStore.setTile(x, y, fillTileId)

      stack.push([x + 1, y], [x - 1, y], [x, y + 1], [x, y - 1])
    }

    options.onRenderRequest()
  }

  // 切换地图时清理移动工具状态
  function resetMoveState() {
    moveStartPos = null
    moveTileId = 0
    if (moveDragSprite) {
      const app = getApp()
      app?.stage.removeChild(moveDragSprite)
      moveDragSprite.destroy()
      moveDragSprite = null
    }
  }

  return {
    encodeTileId,
    updateTileAt,
    updatePreview,
    hidePreview,
    resetPaintKey,
    handlePaintPointerDown,
    handlePaintPointerMove,
    handlePointerUp,
    floodFill,
    resetMoveState,
  }
}
