# 游戏引擎性能分析与优化计划

## 当前性能评估

### Python 引擎端瓶颈

| # | 问题 | 位置 | 影响 |
|---|---|---|---|
| 1 | 每物理tick 5次 `_SPRITES` 遍历 | `run()` L2286-2313 | 峰值15次遍历/帧 |
| 2 | `list(_SPRITES.values())` 副本 | L2286,2291,2297 | 每tick 3次O(n)分配 |
| 3 | `_find_tileset_for_gid` 线性扫描 | L1909-1917 | 每个碰撞瓦片O(tilesets) |
| 4 | `_render_map` PIL Image.open()磁盘IO | L2076 | 每次镜头移动读磁盘 |
| 5 | `_resolve_collision` 多次 `_get_hitbox_rect` | L239-481 | 每轴最多7次调用 |
| 6 | 镜头移动8px即全量重渲染 | L2343-2347 | 大规模JSON payload |

### PixiJS 前端瓶颈

| # | 问题 | 位置 | 影响 |
|---|---|---|---|
| 7 | syncTiles 每帧全量排序+属性赋值 | L262-327 | 1000瓦片4-7ms |
| 8 | syncSprites 重复纹理请求 | L240 | 加载期间每帧请求 |
| 9 | syncSayTexts 无变化也重设text | L373 | 30气泡0.5-2ms |
| 10 | mousemove 无节流+强制布局 | L490 | 100次/秒10-50ms |
| 11 | usesEngine() 每次输入都扫描代码 | L480-486 | 500行代码0.2ms/次 |
| 12 | handleResize 无防抖 | L97-104 | 调整大小时同步渲染 |

## 优化计划

### 高优先级（低风险，立刻性能提升）

1. **usesEngine() 结果缓存** — 避免每次输入事件扫描代码内容
2. **mousemove RAF节流** — 每帧最多处理一次鼠标移动
3. **文字脏检查** — text/say 仅在实际变化时设置
4. **syncHitboxes 脏检查** — 碰撞盒不变时不重绘
5. **ResizeObserver 防抖** — 100ms防抖限制同步渲染
6. **syncTiles 属性脏检查** — 仅值变化时更新
7. **Python `_get_hitbox_rect` 调用合并** — 减少重复计算

### 中优先级（中等风险）

8. **`_find_tileset_for_gid` 二分查找** — O(n)→O(log n)
9. **Python `_SPRITES` 遍历合并** — 减少到2次
10. **PIL图像尺寸缓存** — 避免重复磁盘IO

## 验证方式

```bash
# 运行pixi.js性能测试（统计数据）
cd engine && python3 -c "import bingo_engine as eng; ..."

# 检查FPS输出
# 人工观察游戏运行稳定性
```
