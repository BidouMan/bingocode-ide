# MEMORY spillover — 碰撞系统
_Extracted from MEMORY.md "Discovered durable knowledge" → 碰撞系统 (stable reference; collision work settled, 2026-10-13)._

## 碰撞系统

- **碰撞计算 100% 在 Python 引擎**: `engine/bingo_engine.py` 是碰撞唯一实现处（`_setup_hitbox()`、`_get_hitbox_rect()`、`_resolve_collision(axis)`）；Rust（src-tauri）无碰撞代码；前端（useEngine.ts → render.ts hitboxes Map → GameCanvas.vue）仅传输 hitbox 数组并可视化调试，不参与碰撞计算。修碰撞 bug 只需改 bingo_engine.py。[ses_edb115532ffe]
- **碰撞解算为轴分离式**: 各移动入口先 `_resolve_collision("x")` 再 `_resolve_collision("y")`。hitbox 格式 `[left, top, right, bottom]`（`hitbox[3]`=bottom 用于 `_prev_bottom_y` 地面检测）。支持三种碰撞体：瓦片矩形、自定义多边形（`collision_shape.points`）、地图边界。[ses_edb115532ffe]
- **命中盒不处理真实旋转（仅翻转）**: `_get_hitbox_rect()` 只按 `_current_scale_x`(±1) 水平镜像，不读 `self._angle`。默认旋转样式 `"all"` 下 angle=180 是渲染器真实旋转，命中盒不随之镜像 → 内容 bbox 不对称的精灵朝左时视觉可穿墙（左穿右不穿症状）。`set_rotation_mode('left_right')` 路径（angle→flip）命中盒与渲染器一致。[ses_edb115532ffe]
- **主循环物理排序**: 固定步长 1/60s（`run()` :2297-2478）。每物理步：用户 `loop()`（add_x 等在此解一次 X）→ `_handle_physics_collision()` :2056-2098 对所有精灵加重力后**先 Y 后 X** 各解一次 → **X 碰撞每帧双次解算，中间隔 Y 位移**。重力：上升 0.5（jump_cut 2.8）、下落 1.1、vy 钳 ≤10。frame_count 每 ~0.5s 重置（`duration>=0.5` :2451）。[ses_edb115532ffe]
