/**
 * 地图保存 Worker：把耗时的 serializeMap（pako 压缩）放到后台线程，
 * 避免大图 / 多图层保存时阻塞编辑器主线程（参考 Unreal / Unity 的后台保存）。
 */
import { serializeMap } from './mapSerializer'

self.onmessage = (event: MessageEvent<{ id: number; mapData: any }>) => {
  const { id, mapData } = event.data
  try {
    const saveData = serializeMap(mapData)
    self.postMessage({ id, ok: true, json: JSON.stringify(saveData) })
  } catch (err) {
    self.postMessage({ id, ok: false, error: String(err) })
  }
}
