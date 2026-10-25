// 模块级共享缓存：MainLayout 同时挂着两个 GameCanvas 实例（预览窗 + 全屏 v-show 窗），
// 若各实例自持缓存，同一文件会重复走 IPC 加载且渲染 store 的贴图计数器被翻倍登记，
// 「加载资源中」覆盖层的进度与完成判定随之失真（表现为覆盖层随动画节奏闪烁）
export const sharedTextureCache: Map<string, any> = new Map()
export const sharedTilesetFrameCache: Map<string, Map<number, any>> = new Map()
export const sharedFrameTextureCache: Map<string, any> = new Map()
// 同一路径加载中的 Promise：同帧并发请求（两个实例 / 预载+首渲染）只算一次计数
export const sharedInFlightTextures: Map<string, Promise<any>> = new Map()

/**
 * 清空全部游戏纹理缓存：每次运行开始时必须调用。
 *
 * 缓存以文件路径为 key，而磁盘文件在两次运行之间可能变化——
 * 角色改名顶替旧名、删除后重建同名角色、重新上传同名文件、绘制保存覆盖原图等，
 * 都会出现「同路径、不同内容」。若跨运行复用缓存，会渲染出已删除旧资源的贴图。
 * 因此缓存只在单次运行内复用（动画换帧/多精灵共享），运行开始一律重新加载。
 */
export function invalidateGameTextures() {
  sharedTextureCache.clear()
  sharedTilesetFrameCache.clear()
  sharedFrameTextureCache.clear()
  sharedInFlightTextures.clear()
}
