import { invoke } from '@tauri-apps/api/core'
import { useMapStore } from '../stores/map'
import { useProjectStore } from '../stores/project'

/**
 * 地图绘制业务逻辑：绘制结果输出 PNG → 地图目录 + 地图级图像素材 + 图片图层。
 * 界面编排（打开绘制面板等）留在页面组件。
 */
export function useMapPaint() {
  const mapStore = useMapStore()
  const projectStore = useProjectStore()

  function nextImageResourceName(): string {
    const used = new Set(
      mapStore.mapData.resources
        .filter(r => r.resourceType === 'image')
        .map(r => r.name),
    )
    let name = '绘制背景'
    let seq = 2
    while (used.has(name)) name = `绘制背景${seq++}`
    return name
  }

  async function saveMapImage(
    blob: Blob,
    width: number,
    height: number,
    layerId: number,
    mode: 'bitmap' | 'vector' = 'vector',
  ): Promise<void> {
    const root = projectStore.root
    const mapName = mapStore.mapData.name
    if (!root || !mapName) throw new Error('项目或地图未就绪')

    const name = nextImageResourceName()
    const relativePath = `assets/maps/${mapName}/images/${name}.png`

    await invoke('create_dir', { path: `${root}/assets/maps/${mapName}/images` })
    await invoke('write_binary', {
      path: `${root}/${relativePath}`,
      data: Array.from(new Uint8Array(await blob.arrayBuffer())),
    })

    mapStore.addResource({
      name,
      path: relativePath,
      resourceType: 'image',
      tileWidth: width,
      tileHeight: height,
      collisionType: '图像',
      collisionEnabled: false,
    })
    // 扁平模型：保存的背景图作为新的图片图层，插在当前图层上方
    // 编辑模式沿用当前工具栏选择（默认矢量，与角色编辑器一致），切层时按图层恢复
    const layerIndex = mapStore.mapData.layers.findIndex(l => l.id === layerId)
    mapStore.addImageAt(layerIndex >= 0 ? layerIndex : mapStore.mapData.layers.length - 1, {
      imagePath: relativePath,
      position: [0, 0],
      rotation: 0,
      scale: 1,
      scaleX: 1,
      scaleY: 1,
      opacity: 1,
      width,
      height,
      collisionType: '图像',
      collisionEnabled: false,
      background: true,
      paintMode: mode,
    }, name)
  }

  return { saveMapImage }
}
