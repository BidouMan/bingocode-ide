"""引擎全局可变状态（唯一存放处）。

为什么集中在这里：引擎拆分为多个模块后，各模块通过 `import engine_state as st`
共享同一份状态。**注意：不要用 `from engine_state import _X`**——那是值拷贝，
别的模块重新赋值后不会同步，会导致 stop()/pause() 之类静默失效。

新增状态时的规则：
- 需要跨模块读写的 → 放这里，并写清楚含义与生命周期；
- 只在某一个模块内部使用的 → 放那个模块顶部，不要加到这里（避免变成垃圾场）。
"""

import queue
import threading
import time

# ---------------- 输入（input_api.py 写入，主循环读取） ----------------
_PRESSED_KEYS = set()
_PRESSED_KEYS_FRAME = set()
_PRESSED_KEYS_PREV = set()
# 松开事件：监听线程累积到 _RELEASED_KEYS，每个物理步开始快照到 _RELEASED_FRAME，
# 供 key_up() 读取；这样不会因为事件到达时机跨帧而漏掉"刚松开"的那一帧
_RELEASED_KEYS = set()
_RELEASED_FRAME = set()
# 用字典包装鼠标状态：released 由输入线程累积，released_frame 是每个物理步的快照（供 mouse_up）
_MOUSE_STATE = {"down": False, "last_down": False, "down_step_prev": False, "released": False, "released_frame": False, "x": 0, "y": 0}
# 点击（角色被点击）状态：
#   press_seq    —— 输入线程在按下那一刻 +1，一次真实按下只有一个序号
#   active_seq   —— 本物理步有效的那次按下序号（-1 = 本步没有新的点击）
#   resolved_seq / target_id —— 缓存这次按下点中的最上层角色，供 is_clicked / on_clicked 共用
#   dispatched_seq —— 已派发过 on_clicked 的按下序号，保证一次按下只回调一次
_CLICK_STATE = {"press_seq": 0, "active_seq": -1, "resolved_seq": -1, "target_id": None, "dispatched_seq": -1}
_PENDING_RESPONSES = []  # 监听线程→主线程的待发响应
_USER_INPUT_QUEUE = queue.Queue()  # 用户 input() 输入队列

# ---------------- 时间 / 定时器 ----------------
_WAIT_TIMERS = {}  # key=(code_id, lineno) -> 上次触发时的游戏时间（每个调用位置独立）
_GAME_TIME = 0.0  # 游戏时间（秒）：只在未暂停时随物理步累加，Timer / time_passed 统一使用
# 固定物理步长（60Hz）与单个渲染帧最多补算的物理步数；
# run() 与 start_game() 共用这套常量，避免两条主循环各写一份而逐渐走偏
_PHYSICS_DT = 1.0 / 60.0
_MAX_FRAME_TIME = 0.05
_MAX_PHYSICS_STEPS = 3
_PERF_STATS = {"last_time": time.time(), "frame_count": 0}

# 性能模式：只降低画面刷新与数据发送频率，逻辑步进恒为 60Hz。
# 逻辑帧率一旦跟着变，学生写的 x += 5、重力、speed 等「每帧一次」的代码就会整体变速，
# 这不符合游戏引擎的基本约定，所以这里绝不动 _PHYSICS_DT。
_PERF_MODE = False


def set_perf_mode(on):
    """性能模式开关：仅影响渲染相关，不改变游戏逻辑速度。"""
    global _PERF_MODE
    _PERF_MODE = bool(on)


# ---------------- 事件广播 / 游戏控制 ----------------
_EVENT_LISTENERS = {}
# 广播事件的两帧缓冲：broadcast() 写入 _EVENT_PENDING，下一步开始提升到 _EVENT_ACTIVE，
# 供 receive() 查询；持续一帧后自动清空，保证同一帧内代码顺序不影响结果
_EVENT_PENDING = set()
_EVENT_ACTIVE = set()
_PAUSED = False
_STOPPED = False
# 启动闸门：引擎初始化完成（GAME_READY）后先停在这里，等前端「启动加载页」收起
# 并通过 stdin 发来 START: 才放开主循环。否则加载页还盖着时角色已经在走了。
_GAME_START_GATE = threading.Event()

# ---------------- 精灵 / 物理 ----------------
_SPRITES = {}  # 存储所有精灵实例
_GROUPS = {}
_SAY_TIMERS = {}  # say 定时消失计时器

# ---------------- 地图 ----------------
_CURRENT_MAP = None  # 当前加载的地图数据
_MAP_DIR = None  # 当前地图所在目录
_MAP_SPRITES = {}  # 地图瓦片精灵
_MAP_MODEL = None  # 当前地图模型实例
_RENDERED_TILES = set()  # 已渲染的瓦片缓存

# ---------------- 相机 / 屏幕 ----------------
_CAMERA_X = 320  # 相机X坐标（屏幕中心）
_CAMERA_Y = 240  # 相机Y坐标（屏幕中心）
_CAMERA_ZOOM = 1.0  # 相机缩放比例
_SCREEN_WIDTH = 640  # 屏幕宽度
_SCREEN_HEIGHT = 480  # 屏幕高度
_FOLLOW_TARGET = None  # 摄像机跟随目标
_AUTO_CAMERA_TARGET = None  # 由地图相机设置自动跟随的主玩家（区别于代码 camera_follow()）

# ---------------- 显示 / 缓存 ----------------
_SHOW_FPS = False
_SHOW_ALL_COLLISION = False
_FRAME_UPDATES = []  # 每帧精灵更新缓冲，帧末合并发送
_FRAME_SEQ = 0  # 物理步序号，性能模式下用于隔帧发送
_IMAGE_SIZE_CACHE = {}  # 图像尺寸缓存，避免重复磁盘IO
_IMAGE_BBOX_CACHE = {}  # 图片内容框缓存：同一张图批量创建角色时免去重复读盘+像素采样

# ---------------- 异步脚本（generator 调度） ----------------
_generators = []  # 所有活跃的 generator

# ---------------- 其它 ----------------
_SOUND_WARNED = set()
