# 引擎模块地图（改引擎代码前先看这里）

> 目标：让 agent / 开发者**用 1~2 次打开文件**就定位到该改的地方，不要整目录 grep。
> 目录结构改动时请同步更新本文件（以及 AGENTS.md 里的简版表）。

## 0. 一句话定位

| 你想做的事 | 打开 |
| --- | --- |
| 用户脚本能调用的 API（Sprite/Timer/load_map…） | 见第 3 节「公共 API → 文件」 |
| 帧循环、启动、暂停语义、generator 调度 | [game_loop.py](game_loop.py) |
| 角色卡墙/斜坡/单向平台/贴地判断 | [sprite_physics.py](sprite_physics.py) |
| 角色图片/bsf/bgs 载入、碰撞盒、挂点坐标 | [sprite_assets.py](sprite_assets.py) |
| 角色动画播放、说话气泡 | [sprite_animation.py](sprite_animation.py) |
| 角色公开方法（move/jump/follow/属性） | 见第 4 节「Sprite 方法 → 文件」 |
| 地图加载、瓦片渲染、地图碰撞、感应区 | [map_runtime.py](map_runtime.py) |
| 地图标记 get_marker(s)、raycast | [markers.py](markers.py) |
| 镜头跟随、相机更新包 | [camera.py](camera.py) |
| 键鼠输入、input() 桥接 | [input_api.py](input_api.py) |
| 音效、文字、震动、随机数 | [audio.py](audio.py) / [effects.py](effects.py) |
| 暂停/停止/事件广播/FPS 显示 | [game_control.py](game_control.py) |
| 计时器与游戏时间 | [timing.py](timing.py) |
| 碰撞几何纯算法（三角化/MTV/内容框） | [collision_geometry.py](collision_geometry.py) |
| 共享可变状态（`_SPRITES`/`_STOPPED`…） | [engine_state.py](engine_state.py) |
| Python 子进程入口 / 导出面 | [bingo_engine.py](bingo_engine.py) |

## 1. 分层与依赖方向（必须保持单向）

```
bingo_engine.py            门面：sys.path 引导 + stdout 无缓冲 + 重导出 + __all__
└── game_loop.py           入口层：run() / start_game() / 物理步调度 / generator
    ├── camera.py          相机（会调用 map_runtime._render_map）
    ├── map_runtime.py     地图加载/渲染/地图物理/感应区
    │   ├── markers.py     标记查询 + raycast
    │   ├── collision_geometry.py   纯几何
    │   └── game_control.py         事件广播 + GameStop + _safe_call
    ├── effects.py         屏幕表现（依赖 sprite 做类型判断）
    ├── sprite.py          Sprite 主类，继承三个 Mixin
    │   ├── sprite_physics.py    物理/碰撞（依赖 collision_geometry、map_runtime._find_tileset_for_gid）
    │   ├── sprite_assets.py     素材装载/碰撞盒/挂点
    │   └── sprite_animation.py  动画/说话（依赖 timing.Timer）
    ├── input_api.py / timing.py / game_control.py / audio.py
    └── engine_state.py    所有跨模块共享的可变状态（最底层，不 import 任何人）
```

规则：**箭头只能向下**。如果新功能需要反向依赖（例如 collision_geometry 想读精灵），
把数据当参数传进去，或在该函数内做局部导入（见 `sprite_physics.is_touch` 里对 `Sprite` 的处理）。

## 2. 模块表

| 文件 | 约行数 | 职责 | 常改什么 |
| --- | --- | --- | --- |
| `bingo_engine.py` | ~115 | 门面：引导、重导出、`__all__` | 新增公共 API 时补导出 |
| `game_loop.py` | ~365 | `run()`/`start_game()`、物理步、每帧调度、generator 注册、FPS 上报、动画推进 | 帧率、步长、启动/重启、调度顺序 |
| `sprite.py` | ~800 | `Sprite` 主类 + 公开方法 + 属性 + 类常量 | 用户 API、属性语义 |
| `sprite_physics.py` | ~880 | 碰撞解算、`move_and_slide`、`is_touch`/`is_blocked`/贴地 | 卡墙、穿模、斜坡、抖动 |
| `sprite_assets.py` | ~610 | bsf/bgs/单图解析、hitbox、标记点、变换同步 | 图片错位、碰撞盒偏移、挂点坐标 |
| `sprite_animation.py` | ~170 | `play()`、`say()`、逐帧推进 | 动画不播/卡帧、气泡时长 |
| `map_runtime.py` | ~890 | `load_map`/清理/瓦片渲染/地图物理/感应区 | 地图不显示、图层、碰撞层、sensor |
| `markers.py` | ~275 | 地图标记与挂点查询、`raycast` | 标记取不到、射线打不中 |
| `camera.py` | ~185 | `camera_follow`、跟随目标解析、每帧更新合并发送 | 镜头抖动、边界限制 |
| `input_api.py` | ~175 | `mouse`、`key_*`、`mouse_*`、`input()`、监听线程 | 按键漏帧、鼠标坐标 |
| `timing.py` | ~60 | `Timer`、`time_passed`、`wait` | 暂停时计时、计时不准 |
| `game_control.py` | ~122 | 暂停/继续/停止、`broadcast/receive`、`GameStop`、`_safe_call` | 广播时序、停止无效 |
| `audio.py` | ~65 | `play_sound`/`stop_sound`/路径解析 | 音效找不到、循环播放 |
| `effects.py` | ~51 | `show_text`/`shake`/`random_*`/`show_collision` | 文字、震动、随机数 |
| `collision_geometry.py` | ~430 | 多边形三角化、MTV、图片内容框、可玩边界 | 纯几何 bug（可单测） |
| `engine_state.py` | ~80 | 共享可变状态（唯一存放处） | 新增跨模块状态 |

## 3. 公共 API → 文件

（`__all__` 全量；用户脚本 `from bingo_engine import *` 拿到的就是这些）

| API | 文件 |
| --- | --- |
| `Sprite` | `sprite.py` |
| `Timer`, `time_passed`, `wait` | `timing.py` |
| `run`, `start_game`, `register_generator`, `unregister_generator` | `game_loop.py` |
| `key_down`, `key_pressed`, `key_up` | `input_api.py` |
| `mouse`, `mouse_down`, `mouse_pressed`, `mouse_up` | `input_api.py` |
| `broadcast`, `receive`, `on_receive` | `game_control.py` |
| `pause`, `resume`, `is_paused`, `stop`, `stop_game`, `show_fps`, `GameStop` | `game_control.py` |
| `load_map` | `map_runtime.py` |
| `get_marker`, `get_markers`, `raycast` | `markers.py` |
| `camera_follow` | `camera.py` |
| `play_sound`, `stop_sound` | `audio.py` |
| `show_text`, `show_collision`, `shake`, `random_int`, `random_float` | `effects.py` |

> 注意：`start_game()` 里的 `exec_globals`（用户脚本可见的名字）也是手工维护的一张表，
> 新增公共 API 时**两处都要加**：`bingo_engine.py` 的 `__all__` + `game_loop.py` 的 `exec_globals`。

## 4. Sprite 方法 → 文件

| 文件 | 方法（44 / 19 / 13 / 3 个） |
| --- | --- |
| `sprite.py` | `__init__`、`goto`、`get_marker`、`follow`、`unfollow`、`set_xy`、`set_x/y`、`add_x/y`、`jump`、`stop_jump`、`cut_jump`、`smart_jump`、`drop_down`、`drop_through`、`set_speed`、`on_touch_group`、`on_hit`、`on_sensor_enter/exit`、`broadcast`、`receive`、`on_receive`、`move`、`goto_rand`、`set_angle`、`look_at`、`edge_bounce`、`set_scale`、`add_scale`、`set_rotation_mode`、`show`、`hide`、`say`*(见动画)*、`touch_group`、`add_to_group`、`delete`、`distance_to`、属性 `x/y/pos/vy/gravity/angle/scale/layer`、`_set_xy_world`、`_apply_visible`、`_send_command` |
| `sprite_physics.py` | `_collision_layer_correction`、`_image_collision_correction`、`_mtv_axis_dominant`、`_accept_axis_correction`、`_contact_bit(_from_normal)`、`_depenetrate`、`move_and_slide`、`_move_and_slide_step`、`_resolve_collision`、`is_touch`、`is_touch_edge`、`is_touch_group`、`is_out_side`、`is_blocked`、`is_on_wall/ceiling/ground/floor` |
| `sprite_assets.py` | `_load_sprite_config`、`_load_config_in_dir`、`_normalize_bsf_manifest`、`_bsf_frame_rect`、`_marker_world_xy`、`_resolve_path`、`_setup_hitbox`、`_setup_hitbox_bsf`、`_collision_canvas_points/bbox`、`_get_hitbox_rect`、`_get_collision_shape`、`_update_transform` |
| `sprite_animation.py` | `play`、`say`、`_update_animation_frame` |

`Sprite` 的类常量（`_CONTACT_*`、`_MAX_MOVE_STEP`、`_MAX_STEP_UP` 等）全部保留在 `sprite.py` 的类头上。

## 5. 改代码的硬规则

1. **共享状态只走 `engine_state`**：模块顶部 `import engine_state as st`，用 `st._SPRITES` 读写。
   禁止 `from engine_state import _X`（值拷贝，重新赋值不同步）。
   新增状态时先问：需要跨模块读写吗？是 → 放 `engine_state.py`；否 → 放本模块顶部。
2. **依赖只能是单向的**（见第 1 节）。需要反向引用时用函数内局部导入，并写注释说明原因。
3. **不要新建 `engine/` 子目录**：Tauri 打包配置只收录 `engine/*.py`（平铺）与 `engine/models/*.py`，
   新建子目录会**只在打包版缺失**，开发期看不出来。
4. **门面只做重导出**：具体逻辑写进对应模块，不要让 `bingo_engine.py` 继续变胖。
5. **改动用户可见行为时**：同步检查 `__all__`、`exec_globals`、`docs/` 下的用户文档。
6. **跨平台**：引擎代码与平台无关；涉及路径的改动保持 `os.path`/相对路径写法。

## 6. 改完后怎么快速验证

```bash
cd engine
./venv/bin/python -m py_compile *.py           # 语法
./venv/bin/python -c "import bingo_engine as be; print(len(be.__all__), 'Sprite 方法', len([n for n in dir(be.Sprite) if not n.startswith('_')]))"
pnpm tauri dev                                  # 真正跑一个项目（两条主循环都要覆盖）
```

- 旧 `while True` 模式：`examples/while_true_demo`
- generator 模式：任意项目点击运行
- 排查卡顿/跳帧时优先看 `game_loop.py` 的 `_begin_physics_step` / `_end_physics_step`
