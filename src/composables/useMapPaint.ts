import { invoke } from '@tauri-apps/api/core'
import { useMapStore } from '../stores/map'
import { useProjectStore } from '../stores/project'

/**
 * 地图绘制业务逻辑：绘制页输出 PNG → 地图目录 + 地图级图像素材 + 图层实例。
 * 页面切换等 UI 逻辑仍留在 MainLayout。
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
    mapStore.addImageInstance(layerId, {
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
    })
  }

  return { saveMapImage }
}
