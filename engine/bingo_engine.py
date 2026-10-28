"""BingoCodeIDE 游戏引擎入口（门面文件，不再承载具体实现）。

本文件只做三件事：
1. 运行时引导：把项目根目录加入 sys.path、把 stdout 设为无缓冲（子进程 JSON 协议依赖即时输出）；
2. 重新导出公共 API：保证 `from bingo_engine import *`、`start_game()` 里的 exec_globals、
   Rust 侧 `from bingo_engine import start_game` 与旧版行为完全一致；
3. 暴露 run() / start_game() 两个入口（真正实现在 game_loop.py）。

改功能前先看目录：AGENTS.md 的「引擎模块地图」（或 engine/ENGINE_MAP.md）。
import 顺序有约束：本文件的引导代码必须位于导入其它 engine 模块之前。
"""

import os
import sys

# 添加项目根目录到Python路径（确保在任何目录运行都能找到models模块）
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 设置标准输出为无缓冲模式
sys.stdout = os.fdopen(sys.stdout.fileno(), "w", buffering=1)

# 各实现模块（暴露为 bingo_engine.xxx 便于调试/定位，不要在用户脚本里使用）
import audio  # noqa: E402,F401
import camera  # noqa: E402,F401
import collision_geometry  # noqa: E402,F401
import effects  # noqa: E402,F401
import engine_state  # noqa: E402,F401
import game_control  # noqa: E402,F401
import game_loop  # noqa: E402,F401
import input_api  # noqa: E402,F401
import map_runtime  # noqa: E402,F401
import markers  # noqa: E402,F401
import sprite  # noqa: E402,F401
import sprite_animation  # noqa: E402,F401
import sprite_assets  # noqa: E402,F401
import sprite_physics  # noqa: E402,F401
import timing  # noqa: E402,F401

# ---------------- 公共 API 重新导出 ----------------
from audio import play_sound, stop_sound  # noqa: E402
from camera import camera_follow  # noqa: E402
from effects import random_float, random_int, shake, show_collision, show_text  # noqa: E402
from game_control import (  # noqa: E402
    GameStop,
    broadcast,
    is_paused,
    on_receive,
    pause,
    receive,
    resume,
    show_fps,
    stop,
    stop_game,
)
from game_loop import (  # noqa: E402
    register_generator,
    run,
    start_game,
    unregister_generator,
)
from input_api import (  # noqa: E402
    key_down,
    key_pressed,
    key_up,
    mouse,
    mouse_down,
    mouse_pressed,
    mouse_up,
)
from map_runtime import load_map  # noqa: E402
from markers import get_marker, get_markers, raycast  # noqa: E402
from sprite import Sprite  # noqa: E402
from timing import Timer, time_passed, wait  # noqa: E402

__all__ = [
    "Sprite",
    "Timer",
    "run",
    "key_down",
    "key_pressed",
    "key_up",
    "time_passed",
    "wait",  # 兼容旧项目，文档与补全中不再展示
    "broadcast",
    "receive",
    "on_receive",
    "pause",
    "resume",
    "is_paused",
    "stop",
    "show_fps",
    "mouse_down",
    "mouse_pressed",
    "mouse_up",
    "mouse",
    "load_map",
    "get_marker",
    "get_markers",
    "raycast",
    "camera_follow",
    "play_sound",
    "show_collision",
    "random_int",
    "random_float",
    "show_text",
    "stop_sound",
    "shake",
    "start_game",
    "register_generator",
    "unregister_generator",
    "GameStop",
    "stop_game",
]
