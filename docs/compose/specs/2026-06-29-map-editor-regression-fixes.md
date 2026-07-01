# 地图编辑器退步修复 + 功能补全计划

## 退步修复清单

### R1: 图层资源隔离 (CRITICAL)
**原版**: 每个图层有独立的 `layer_resources[layer_id] = [resource_info]`，资源面板只显示当前图层的资源
**当前**: 全局 `mapResources` 所有图层共享
**修复方案**:
- map.ts: `mapResources` 改为 `Record<number, MapResource[]>` 按图层ID索引
- ResourceListPanel: 只显示当前 activeLayer 的资源
- 上传资源时只添加到当前图层
- tileId 编码需要考虑图层本地索引到全局索引的映射

### R2: layerResourcesMap 恢复使用 (与 R1 关联)
**原版**: `layerResourcesMap: {layer_id: [start, end]}` 存储在 .info 文件中
**当前**: 类型定义了但从未使用
**修复方案**:
- 导出时序列化 layerResourcesMap
- 导入时根据 layerResourcesMap 分配资源到各图层
- MapData 接口保持 layerResourcesMap 字段

### R3: 增量渲染优化
**原版**: changed_area 跟踪 + 16ms 防抖，只重绘变化的瓦片
**当前**: renderAllLayers() 全量重绘
**修复方案**:
- MapCanvas: 添加 changedTiles 集合跟踪变化
- watch 改为只重绘变化的瓦片而非全量
- 大批量操作（如 flood fill）后才全量重绘

### R4: JSON 文件格式优化
**原版**: 4文件二进制（紧凑快速）
**当前**: JSON in zip（冗余）
**修复方案**: 保持 JSON 格式但优化序列化
- tiles 改为二维数组代替 Record<string, number>（更紧凑）
- 保留二进制导出兼容

## 缺失功能补全清单

### F1: 图像图层渲染 (CRITICAL)
**原版**: ImageLayer 支持 position/rotation/scale/opacity
**当前**: 只渲染 drawing 图层
**修复方案**:
- MapCanvas: renderAllLayers 中增加 image 图层渲染
- 创建 PIXI.Sprite 从资源路径加载图片
- 应用 transform (position/scale/rotation)
- 应用 opacity

### F2: 变换工具 (Transform Tool)
**原版**: 292行 Photoshop 风格 8 点手柄
**当前**: 无
**修复方案**:
- MapCanvas: 添加 TransformBox 组件
- 8 个控制点手柄（4角+4边中点）
- 拖拽缩放（Shift 等比）
- 右键旋转
- 更新 ImageData 的 transform 属性

### F3: 拖拽资源到画布
**原版**: QDrag MIME 类型拖拽
**当前**: 无
**修复方案**:
- ResourceListPanel: 添加 draggable 属性
- MapCanvas: 监听 drop 事件
- 放置时根据图层类型：
  - drawing 图层：在光标位置放置瓦片
  - image 图层：创建 ImageData 对象

### F4: 资源文件生命周期管理
**原版**: _is_resource_file_used_by_other_layers / _safe_delete_resource_file
**当前**: 无安全检查直接删除
**修复方案**:
- 删除资源前检查其他图层是否引用
- 只有无引用时才从磁盘删除文件

### F5: 每图层资源面板更新
**原版**: 切换图层时资源面板自动刷新
**当前**: 资源面板不随图层切换更新
**修复方案**:
- watch activeLayerIndex 变化时刷新资源列表
- 资源面板显示当前图层的资源
