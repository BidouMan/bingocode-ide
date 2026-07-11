import json
import sys
import time
import os
import random
import math
import threading
import queue
from PIL import Image
from models.map_model import MapModel

# 添加项目根目录到Python路径（确保在任何目录运行都能找到models模块）
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 设置标准输出为无缓冲模式
sys.stdout = os.fdopen(sys.stdout.fileno(), "w", buffering=1)

_PRESSED_KEYS = set()
_PRESSED_KEYS_PREV = set()
_WAIT_TIMERS = {}
_EVENT_LISTENERS = {}
_SHOW_FPS = False
_PAUSED = False
_STOPPED = False
_SHOW_ALL_COLLISION = False
_PENDING_RESPONSES = []  # 监听线程→主线程的待发响应
_USER_INPUT_QUEUE = queue.Queue()  # 用户 input() 输入队列
_PERF_STATS = {"last_time": time.time(), "frame_count": 0}
_GROUPS = {}
_MOUSE_STATE = {"down": False, "last_down": False, "x": 0, "y": 0}  # 用字典包装鼠标状态
_SPRITES = {}  # 存储所有精灵实例
_SAY_TIMERS = {}  # say 定时消失计时器
_CURRENT_MAP = None  # 当前加载的地图数据
_MAP_DIR = None  # 当前地图所在目录
_MAP_SPRITES = {}  # 地图瓦片精灵
_MAP_MODEL = None  # 当前地图模型实例

# 相机和视口设置
_CAMERA_X = 320  # 相机X坐标（屏幕中心）
_CAMERA_Y = 240  # 相机Y坐标（屏幕中心）
_CAMERA_ZOOM = 1.0  # 相机缩放比例
_SCREEN_WIDTH = 640  # 屏幕宽度
_SCREEN_HEIGHT = 480  # 屏幕高度
_FOLLOW_TARGET = None  # 摄像机跟随目标

# 渲染缓存
_RENDERED_TILES = set()  # 已渲染的瓦片缓存
_IMAGE_SIZE_CACHE = {}   # 图像尺寸缓存，避免重复磁盘IO
_FRAME_UPDATES = []      # 每帧精灵更新缓冲，帧末合并发送


class _MouseType:
    @property
    def x(self):
        return _MOUSE_STATE["x"]

    @property
    def y(self):
        return _MOUSE_STATE["y"]

    def __repr__(self):
        return "mouse"


mouse = _MouseType()  # 🚀 定义全局变量 mouse

__all__ = [
    "Sprite",
    "Timer",
    "run",
    "key_down",
    "key_pressed",
    "wait",
    "broadcast",
    "receive",
    "pause",
    "resume",
    "is_paused",
    "stop",
    "show_fps",
    "mouse_down",
    "mouse_pressed",
    "mouse",
    "load_map",
    "follow",
    "play_sound",
    "show_collision",
    "random_int",
    "random_float",
    "draw_text",
    "stop_sound",
    "shake",
    "start_game",
    "register_generator",
    "unregister_generator",
    "GameStop",
    "stop_game",
]


class Timer:
    def __init__(self, seconds, loop=True, autostart=False):
        self._interval = seconds
        self._loop = loop
        self._running = False
        self._last_time = 0
        if autostart:
            self.start()

    def start(self):
        self._running = True
        self._last_time = time.time()

    def stop(self):
        self._running = False

    def is_timeout(self):
        if not self._running:
            return False
        now = time.time()
        if now - self._last_time >= self._interval:
            self._last_time = now
            if not self._loop:
                self._running = False
            return True
        return False


class Sprite:
    # 类属性：碰撞检测时间控制
    _last_collision_time = 0

    def __init__(self, filename):
        # 1. 基础属性初始化
        self.id = str(id(self))
        self._x = 320
        self._y = 240
        self._scale = 100
        self._angle = 0
        self._rotation_style = "all"
        self._current_scale_x = 1.0
        self.hitbox_scale = 1.0
        self.on_ground = False
        self.vy = 0
        self._prev_bottom_y = 0
        self._jump_cut = False
        self._drop_through = False
        self._drop_through_timer = 0
        self._groups = []
        self._visible = True
        self._is_deleted = False
        self._layer = 0
        self._speed = 0
        self._on_hit_callbacks = []
        self._auto_destroy = False

        # 3. 渲染预设缓存（必须在 early return 之前初始化，避免 deleted 精灵崩溃）
        self._cached_image = None
        self._cached_hitbox = None
        self._visual_offset_x = 0
        self._visual_offset_y = 0
        self._show_hitbox = _SHOW_ALL_COLLISION

        # 🚀 2. 资源解析逻辑升级
        # 尝试寻找解压后的角色文件夹 (例如 assets/sprites/洛克人)
        self.sprite_dir = os.path.join("assets", "sprites", filename)

        # 注意：角色资源必须由用户在资源管理器中添加后才会存在于项目目录
        # 不再自动从引擎内置素材解压
        self.config = self._load_sprite_config()

        if self.config:
            # 如果是 BGS 角色包格式
            self.current_costume_index = 0

            # 检查 frames 或 costumes 字段
            if "frames" in self.config:
                first_frame = self.config["frames"][0]
                self.image = os.path.join(self.sprite_dir, first_frame)
            elif "costumes" in self.config:
                first_frame = self.config["costumes"][0]["file"]
                self.image = os.path.join(self.sprite_dir, first_frame)
        else:
            self.image = self._resolve_path(filename, "sprites")
            self.sprite_dir = None
            self.config = None

        if not os.path.exists(self.image):
            print(f"❌ 角色 '{filename}' 不存在，请先在资源管理器中添加")
            self._is_deleted = True
            stop()
            return

        # 4. 初始计算碰撞箱和图片信息
        self._setup_hitbox()

        # 5. 向 IDE 发送创建指令
        create_data = {
            # 关键：转为绝对路径确保 IDE 渲染器能跨目录找到文件
            "image": os.path.abspath(self.image),
            "x": self._x,
            "y": self._y,
            "angle": self._angle,
            "scale": self._scale / 100.0,
            "scale_x": 1.0,
            "scale_y": 1.0,
            "type": "image",
            "layer": 1000,  # 默认在图层之上（地图图层 z=0~N）
            "vox": self._visual_offset_x,
            "voy": self._visual_offset_y,
            "raw_cw": self._content_w,
            "raw_ch": self._content_h,
        }

        # 添加精灵配置信息，用于动画播放
        if self.sprite_dir and self.config:
            create_data["sprite_dir"] = os.path.abspath(self.sprite_dir)
            create_data["config"] = self.config

        self._send_command("CREATE", create_data)

        # 将精灵添加到全局集合
        _SPRITES[self.id] = self

        # 立即调用_setup_hitbox，确保内容尺寸已计算
        self._setup_hitbox()

        # 立即调用_get_hitbox_rect，确保碰撞盒信息已计算
        self._get_hitbox_rect()

    # ---------- 运动模块 ----------
    def _resolve_collision(self, axis):
        """
        处理碰撞检测和位移修正
        axis: 'x' 或 'y'，指定要处理的轴
        """
        global _CURRENT_MAP, _MAP_MODEL

        if not _CURRENT_MAP:
            return

        tile_size = _CURRENT_MAP.get("tile_size", 16)

        # 获取精灵的碰撞盒
        sprite_rect = self._get_hitbox_rect()
        if not sprite_rect:
            return

        # 计算角色的half_width和half_height
        half_width = (sprite_rect[2] - sprite_rect[0]) / 2
        half_height = (sprite_rect[3] - sprite_rect[1]) / 2

        # 检测所有图层中的实心图块
        for layer in _CURRENT_MAP.get("layers", []):
            # --- 图像图层碰撞检测（优先于瓦片碰撞） ---
            if layer.get("type") == "image" and "images" in layer:
                for image in layer["images"]:
                    collision_enabled = image.get("collisionEnabled", image.get("collision_enabled", False))
                    if not collision_enabled:
                        continue

                    col_type = image.get("collisionType", image.get("collision_type", "图像"))
                    is_one_way = col_type == "跳板"

                    pos = image.get("position", [0, 0])
                    scale = image.get("scale", 1.0)
                    scale_x = image.get("scaleX", image.get("scale_x", scale))
                    scale_y = image.get("scaleY", image.get("scale_y", scale))

                    # 计算图像碰撞包围盒（世界坐标）
                    collision_shape = image.get("collision_shape", None)
                    if (
                        collision_shape
                        and "points" in collision_shape
                        and len(collision_shape["points"]) >= 2
                    ):
                        points = collision_shape["points"]
                        world_points = [
                            (
                                pos[0] + p[0] * abs(scale_x),
                                pos[1] + p[1] * abs(scale_y),
                            )
                            for p in points
                        ]
                        img_left = min(p[0] for p in world_points)
                        img_top = min(p[1] for p in world_points)
                        img_right = max(p[0] for p in world_points)
                        img_bottom = max(p[1] for p in world_points)
                    else:
                        img_w = image.get("width", image.get("_cache_w", 0))
                        img_h = image.get("height", image.get("_cache_h", 0))
                        if img_w <= 0 or img_h <= 0:
                            continue
                        img_left = pos[0]
                        img_top = pos[1]
                        img_right = img_left + img_w * abs(scale_x)
                        img_bottom = img_top + img_h * abs(scale_y)

                    if is_one_way and axis == "x":
                        continue

                    if is_one_way and self._drop_through:
                        continue

                    check_overlap_x = min(img_right, sprite_rect[2]) - max(
                        img_left, sprite_rect[0]
                    )
                    if axis == "x":
                        check_top = sprite_rect[1] + 8
                        check_bottom = sprite_rect[3] - 8
                        if check_top >= check_bottom:
                            continue
                        check_overlap_y = min(img_bottom, check_bottom) - max(
                            img_top, check_top
                        )
                    else:
                        check_left = sprite_rect[0] - 2
                        check_right = sprite_rect[2] + 2
                        check_overlap_x = min(img_right, check_right) - max(
                            img_left, check_left
                        )
                        check_overlap_y = min(img_bottom, sprite_rect[3]) - max(
                            img_top, sprite_rect[1]
                        )

                    if check_overlap_x > 0 and check_overlap_y > 0:
                        if is_one_way and axis == "y":
                            if self._prev_bottom_y <= img_top:
                                rect = self._get_hitbox_rect()
                                if rect:
                                    self._y = img_top - (rect[3] - self._y) - 0.05
                                    self.on_ground = True
                                    self.vy = 0
                                return
                            continue

                        if axis == "x":
                            dist_to_right = abs(sprite_rect[0] - img_right)
                            dist_to_left = abs(sprite_rect[2] - img_left)
                            if dist_to_right < dist_to_left:
                                center_to_left = self._x - sprite_rect[0]
                                self._x = img_right + center_to_left + 0.05
                            else:
                                center_to_right = sprite_rect[2] - self._x
                                self._x = img_left - center_to_right - 0.05
                            return

                        elif axis == "y":
                            if sprite_rect[3] <= img_top + tile_size:
                                rect = self._get_hitbox_rect()
                                if rect:
                                    self._y = img_top - (rect[3] - self._y) - 0.05
                                    self.on_ground = True
                                    self.vy = 0
                            elif sprite_rect[1] >= img_bottom - tile_size:
                                rect = self._get_hitbox_rect()
                                if rect:
                                    self._y = img_bottom + (self._y - rect[1]) + 0.05
                            return

            tiles = layer.get("tiles", {})

            # 计算精灵覆盖的图块范围
            # 进一步收缩 X 轴探测盒，彻底不给它碰到地板和天花板的机会
            if axis == "x":
                check_rect = [
                    sprite_rect[0],
                    sprite_rect[1] + 8,  # 缩进加大到8像素
                    sprite_rect[2],
                    sprite_rect[3] - 8,  # 缩进加大到8像素
                ]
                min_tile_x = math.floor(check_rect[0] / tile_size)
                max_tile_x = math.floor(check_rect[2] / tile_size)
                min_tile_y = math.floor(check_rect[1] / tile_size)
                max_tile_y = math.floor(check_rect[3] / tile_size)
            else:
                # Y轴探测使用完整碰撞盒
                # 策略：稍微加宽 Y 轴的探测范围（左右各多出 2 像素）
                # 这样即使 X 轴修正把角色往外推了一点点，也不会导致"踩空"
                min_tile_x = math.floor((sprite_rect[0] - 2) / tile_size)
                max_tile_x = math.floor((sprite_rect[2] + 2) / tile_size)

                # 保持原有的 Y 范围不变
                min_tile_y = math.floor(sprite_rect[1] / tile_size)
                max_tile_y = math.floor(sprite_rect[3] / tile_size)

            # 检查范围内的每个图块（需要 _MAP_MODEL 提供瓦片碰撞数据）
            collision_found = False
            if _MAP_MODEL:
                for tile_x in range(min_tile_x, max_tile_x + 1):
                    for tile_y in range(min_tile_y, max_tile_y + 1):
                        tile_pos = (tile_x, tile_y)
                        if tile_pos in tiles:
                            tile_id = tiles[tile_pos]
                            if tile_id > 0:
                                # 使用Tiled标准：通过firstgid范围查找瓦片集
                                tile_id_int = int(tile_id)
                                resource_index, tile_index = _find_tileset_for_gid(
                                    tile_id_int, _CURRENT_MAP["tile_sets"]
                                )

                                # 获取图块碰撞状态
                                collision_enabled = _MAP_MODEL.get_tile_collision(
                                    resource_index, tile_index
                                )
                                if collision_enabled:
                                    col_type = _MAP_MODEL.get_tile_collision_type(
                                        resource_index, tile_index
                                    )
                                    is_one_way = col_type == "跳板"

                                    if is_one_way and axis == "x":
                                        continue

                                    if is_one_way and self._drop_through:
                                        continue

                                    collision_shape = _MAP_MODEL.get_tile_collision_shape(
                                        resource_index, tile_index
                                    )

                                    if collision_shape and "points" in collision_shape:
                                        points = collision_shape["points"]
                                        world_points = [
                                            (
                                                tile_x * tile_size + p[0],
                                                tile_y * tile_size + p[1],
                                            )
                                            for p in points
                                        ]
                                        tile_left = min(p[0] for p in world_points)
                                        tile_top = min(p[1] for p in world_points)
                                        tile_right = max(p[0] for p in world_points)
                                        tile_bottom = max(p[1] for p in world_points)
                                    else:
                                        tile_left = tile_x * tile_size
                                        tile_top = tile_y * tile_size
                                        tile_right = tile_left + tile_size
                                        tile_bottom = tile_top + tile_size

                                    overlap_left = max(sprite_rect[0], tile_left)
                                    overlap_top = max(sprite_rect[1], tile_top)
                                    overlap_right = min(sprite_rect[2], tile_right)
                                    overlap_bottom = min(sprite_rect[3], tile_bottom)

                                    overlap_x = overlap_right - overlap_left
                                    overlap_y = overlap_bottom - overlap_top
                                    if overlap_x > 0 and overlap_y > 0:
                                        if is_one_way and axis == "y":
                                            if self._prev_bottom_y <= tile_top:
                                                rect = self._get_hitbox_rect()
                                                if rect:
                                                    self._y = (
                                                        tile_top
                                                        - (rect[3] - self._y)
                                                        - 0.05
                                                    )
                                                    self.on_ground = True
                                                    self.vy = 0
                                                return
                                            continue

                                        if axis == "x":
                                            dist_to_right = abs(sprite_rect[0] - tile_right)
                                            dist_to_left = abs(sprite_rect[2] - tile_left)

                                            if dist_to_right < dist_to_left:
                                                center_to_left = self._x - sprite_rect[0]
                                                self._x = tile_right + center_to_left + 0.05
                                            else:
                                                center_to_right = sprite_rect[2] - self._x
                                                self._x = tile_left - center_to_right - 0.05
                                            return

                                        elif axis == "y":
                                            if sprite_rect[3] <= tile_top + tile_size:
                                                rect = self._get_hitbox_rect()
                                                if rect:
                                                    self._y = (
                                                        tile_top
                                                        - (rect[3] - self._y)
                                                        - 0.05
                                                    )
                                                    self.on_ground = True
                                                    self.vy = 0
                                            elif sprite_rect[1] >= tile_bottom - tile_size:
                                                rect = self._get_hitbox_rect()
                                                if rect:
                                                    self._y = (
                                                        tile_bottom
                                                        + (self._y - rect[1])
                                                        + 0.05
                                                    )
                                                    self.vy = 0
                                            return

        # 地图边界碰撞检测
        bounds = _CURRENT_MAP.get(
            "world_bounds", {"left": 0, "top": 0, "right": 640, "bottom": 480}
        )

        # 获取精灵的碰撞盒
        sprite_rect = self._get_hitbox_rect()
        if sprite_rect:
            # 计算精灵的半宽和半高
            half_width = (sprite_rect[2] - sprite_rect[0]) / 2
            half_height = (sprite_rect[3] - sprite_rect[1]) / 2

            # 检查地图边界（使用 world_bounds，支持负坐标）
            if axis == "x":
                # 左边界
                if sprite_rect[0] < bounds["left"]:
                    center_to_left = self._x - sprite_rect[0]
                    self._x = bounds["left"] + center_to_left + 0.05
                # 右边界
                elif sprite_rect[2] > bounds["right"]:
                    center_to_right = sprite_rect[2] - self._x
                    self._x = bounds["right"] - center_to_right - 0.05
            elif axis == "y":
                # 上边界
                if sprite_rect[1] < bounds["top"]:
                    center_to_top = self._y - sprite_rect[1]
                    self._y = bounds["top"] + center_to_top + 0.05
                # 下边界
                elif sprite_rect[3] > bounds["bottom"]:
                    center_to_bottom = sprite_rect[3] - self._y
                    self._y = bounds["bottom"] - center_to_bottom - 0.05

    def goto(self, x, y):
        """移到指定坐标"""
        self.set_xy(x, y)

    def set_xy(self, x, y):
        """设置坐标"""
        hitbox = self._get_hitbox_rect()
        if hitbox:
            self._prev_bottom_y = hitbox[3]
        self._x = x
        self._y = y
        self._resolve_collision("x")
        self._resolve_collision("y")
        self._update_transform()

    def set_x(self, x):
        self._x = x
        self._resolve_collision("x")
        self._update_transform()

    def set_y(self, y):
        hitbox = self._get_hitbox_rect()
        if hitbox:
            self._prev_bottom_y = hitbox[3]
        self._y = y
        self._resolve_collision("y")
        self._update_transform()

    def add_x(self, delta_x):
        """将 x 坐标增加（或减少）一定数值"""
        self._x += delta_x
        self._resolve_collision("x")
        self._update_transform()

    def add_y(self, delta_y):
        """将 y 坐标增加（或减少）一定数值"""
        hitbox = self._get_hitbox_rect()
        if hitbox:
            self._prev_bottom_y = hitbox[3]
        self._y += delta_y
        self._resolve_collision("y")
        self._update_transform()

    def _handle_step_move(self, dx, dy):
        """处理单步移动和碰撞检测"""
        was_on_floor = self.on_ground
        old_x = self._x
        old_y = self._y

        hitbox = self._get_hitbox_rect()
        if hitbox:
            self._prev_bottom_y = hitbox[3]

        self._x += dx
        self._resolve_collision("x")

        if was_on_floor:
            self.on_ground = True

        self._y += dy
        self._resolve_collision("y")

    def jump(self, power=10):
        """角色跳跃

        Args:
            power: 跳跃力度（默认10，越大跳得越高）
        """
        self.vy = -power
        self.on_ground = False
        self._jump_cut = False

    def cut_jump(self):
        """截断跳跃（松开跳跃键时调用），使角色提前下落"""
        if self.vy < 0:
            self._jump_cut = True
        self._jump_buffered = False

    def drop_through(self):
        """从跳板下穿：角色站在跳板上时，按下键可穿过跳板下落"""
        if self.on_ground:
            self._drop_through = True
            self._drop_through_timer = 10
            self.on_ground = False
            self.vy = 2

    def set_speed(self, speed):
        """设置持续速度，引擎每帧自动沿当前方向移动"""
        self._speed = speed

    def on_hit(self, group, callback=None):
        """注册碰撞回调。callback(bullet, other) 或默认双方删除"""
        self._on_hit_callbacks.append((group, callback))

    def broadcast(self, event_name):
        """发送广播（触发所有接收该事件的回调）"""
        for callback in _EVENT_LISTENERS.get(event_name, []):
            callback()

    def move(self, distance):
        """朝着当前 angle 方向移动 distance 像素"""
        radians = math.radians(self._angle)

        # 计算移动分量
        dx = distance * math.cos(radians)
        dy = distance * math.sin(radians)

        # 设置最大步长（防止隧道效应）
        MAX_STEP = 16.0  # 最大步长为16像素，与图块大小一致

        # 计算总位移长度
        total_distance = math.sqrt(dx * dx + dy * dy)

        # 如果位移很小，直接移动
        if total_distance <= MAX_STEP:
            self._handle_step_move(dx, dy)
        else:
            # 将大位移拆分成多个小位移
            steps = int(math.ceil(total_distance / MAX_STEP))
            step_dx = dx / steps
            step_dy = dy / steps

            # 执行步进移动
            for _ in range(steps):
                self._handle_step_move(step_dx, step_dy)

        # 更新变换
        self._update_transform()

    def goto_rand(self):
        """移到随机位置"""
        self._x = random.randint(0, 640)
        self._y = random.randint(0, 480)
        self._update_transform()

    def set_angle(self, angle):
        """设置旋转角度"""
        self._angle = angle
        self._update_transform()

    def look_at(self, target):
        """
        让当前角色看向另一个角色或鼠标 (自动旋转角度)
        """
        if self._is_deleted:
            return

        # 1. 🚀 获取目标位置 (mx, my)
        if target is mouse:
            tx, ty = _MOUSE_STATE["x"], _MOUSE_STATE["y"]
        elif isinstance(target, Sprite):
            if target._is_deleted:
                return
            # 获取目标的视觉中心
            t_rect = target._get_hitbox_rect()
            tx, ty = (t_rect[0] + t_rect[2]) / 2.0, (t_rect[1] + t_rect[3]) / 2.0
        else:
            # 如果不是 mouse 也不是 Sprite，不执行旋转
            return

        # 2. 🚀 获取自身的视觉中心
        # 必须从视觉中心发出射线，指向才不会歪
        s_rect = self._get_hitbox_rect()
        sx, sy = (s_rect[0] + s_rect[2]) / 2.0, (s_rect[1] + s_rect[3]) / 2.0

        # 3. 计算坐标差并求角度
        dx = tx - sx
        dy = ty - sy

        # 使用 atan2 计算弧度，再转换为角度
        radians = math.atan2(dy, dx)
        angle = math.degrees(radians)

        # 4. 应用角度
        self.set_angle(angle % 360)

    def edge_bounce(self):
        """基于 Hitbox 的精准反弹，自动识别世界边界"""
        if _CURRENT_MAP:
            bounds = _CURRENT_MAP.get("world_bounds", {"left": 0, "top": 0, "right": 640, "bottom": 480})
        else:
            bounds = {"left": 0, "top": 0, "right": 640, "bottom": 480}

        STAGE_LEFT = bounds["left"]
        STAGE_TOP = bounds["top"]
        STAGE_RIGHT = bounds["right"]
        STAGE_BOTTOM = bounds["bottom"]
        rect = self._get_hitbox_rect()
        hit = False

        # 左右判断
        if rect[2] > STAGE_RIGHT:
            self._x -= rect[2] - STAGE_RIGHT
            self._angle = 180 - self._angle
            hit = True
        elif rect[0] < STAGE_LEFT:
            self._x += STAGE_LEFT - rect[0]
            self._angle = 180 - self._angle
            hit = True

        # 上下判断
        if rect[3] > STAGE_BOTTOM:
            self._y -= rect[3] - STAGE_BOTTOM
            self._angle = -self._angle
            hit = True
        elif rect[1] < STAGE_TOP:
            self._y += STAGE_TOP - rect[1]
            self._angle = -self._angle
            hit = True

        if hit:
            self._angle %= 360
            self._update_transform()

    # ----------- 外观模块 ----------
    def set_scale(self, value):
        self._scale = min(max(5.0, float(value)), 1000.0)
        self._update_transform()

    def add_scale(self, value):
        """
        在当前缩放比例的基础上增加 value (单位为百分比)
        例如：add_scale(10) 会让角色变大 10%
        """
        # 🚀 直接利用 property 逻辑，简单稳健
        self.scale += value

    def set_rotation_mode(self, style):
        """
        style:
        'all': 任意旋转 (默认)
        'left_right': 左右翻转 (角度不改变图片旋转，只决定水平镜像)
        'none': 不可旋转 (图片始终正向)
        """
        self._rotation_style = style
        # 立即触发一次更新以应用新样式
        self._update_transform()

    def show(self):
        """显示角色"""
        if self._is_deleted:
            return  # 已经删除的不能显示
        self._visible = True
        self._send_command("UPDATE", {"id": self.id, "visible": True})

    def hide(self):
        """隐藏角色（仅仅是看不见，物体还在内存里）"""
        self._visible = False
        self._send_command("UPDATE", {"id": self.id, "visible": False})

    def say(self, text, seconds=0):
        """
        让角色说话。新话会替换旧话。
        say("你好")      → 永久显示
        say("得分+1", 2) → 2秒后自动消失
        """
        self._send_command("SAY", {"text": str(text)})
        if seconds > 0:
            def _hide():
                self._send_command("SAY", {"text": ""})
            timer = Timer(seconds, loop=False, autostart=True)
            _SAY_TIMERS[self.id] = (timer, _hide)

    def play(self, animation_name, transition_time=0.1):
        """
        播放指定名称的动画
        参数: animation_name - 动画名称（如 'idle', 'walk' 等）
              transition_time - 平滑过渡时间（秒），默认0.1秒
        """
        if not self.config:
            return

        # 如果当前已经在播放这个动画，就不需要重复设置
        if (
            hasattr(self, "_current_animation")
            and self._current_animation == animation_name
        ):
            return

        # 获取动画配置
        animation_config = None
        if "segments" in self.config:
            for segment in self.config["segments"]:
                if segment.get("name") == animation_name:
                    animation_config = segment
                    break
        elif "animations" in self.config:
            animation_config = self.config["animations"].get(animation_name)

        if not animation_config:
            return

        # 获取动画参数
        start = animation_config.get("start", 1)
        end = animation_config.get("end", 1)
        fps = animation_config.get("fps", 10)
        loop = animation_config.get("loop", True)

        # 如果当前没有动画在播放，直接设置新动画
        if not hasattr(self, "animation_state") or not self.animation_state:
            self.animation_state = {
                "start": start - 1,
                "end": end - 1,
                "fps": fps,
                "loop": loop,
                "current_frame": start - 1,
                "last_frame_time": time.time(),
                "frame_duration": 1.0 / fps,
                "is_playing": True,
            }
            self._current_animation = animation_name
            self._update_animation_frame()
            return

        # 直接切换动画状态，不使用复杂的过渡逻辑
        # 这样动画切换会更加流畅，没有延迟
        self.animation_state = {
            "start": start - 1,
            "end": end - 1,
            "fps": fps,
            "loop": loop,
            "current_frame": start - 1,
            "last_frame_time": time.time(),
            "frame_duration": 1.0 / fps,
            "is_playing": True,
        }
        self._update_animation_frame()

        # 记录当前播放的动画名称
        self._current_animation = animation_name

    # ---------- 侦测模块 ----------
    def is_touch_edge(self):
        """
        精准边界检测：判定角色的实际视觉边缘是否越过了 640*480 的舞台
        """
        # 1. 获取缩放和偏移后的真实包围盒 [left, top, right, bottom]
        rect = self._get_hitbox_rect()

        # 2. 舞台固定尺寸
        STAGE_W = 640
        STAGE_H = 480

        # 3. 只要任何一边超出了舞台，就返回 True
        if (
            rect[0] < 0  # 左边出界
            or rect[2] > STAGE_W  # 右边出界
            or rect[1] < 0  # 上边出界
            or rect[3] > STAGE_H
        ):  # 下边出界
            return True

        return False

    def is_out_side(self):
        """
        完全出界检测：只有当角色整体（所有像素）都离开舞台时才返回 True
        舞台尺寸固定为 640 * 480
        """
        # 获取当前精准包围盒 [left, top, right, bottom]
        rect = self._get_hitbox_rect()

        STAGE_W = 640
        STAGE_H = 480

        # 逻辑判断：
        # rect[2] < 0: 右边缘比舞台左边还要小（在左侧完全出界）
        # rect[0] > STAGE_W: 左边缘比舞台右边还要大（在右侧完全出界）
        # rect[3] < 0: 下边缘比舞台顶边还要小（在上方完全出界）
        # rect[1] > STAGE_H: 上边缘比舞台底边还要大（在下方完全出界）
        if rect[2] < 0 or rect[0] > STAGE_W or rect[3] < 0 or rect[1] > STAGE_H:
            return True

        return False

    def is_touch(self, target):
        """判断是否碰到另一个 Sprite、鼠标或带有指定标签的图块"""
        if self._is_deleted or not self._visible:
            return False

        # 🚀 1. 统一获取当前的精准包围盒 [left, top, right, bottom]
        # 这个方法已经包含了 _visual_offset 和 scale 的所有校准
        r1 = self._get_hitbox_rect()
        if not r1:
            return False

        if target is mouse:
            mx, my = _MOUSE_STATE["x"], _MOUSE_STATE["y"]
            # 🚀 2. 判定鼠标点 (mx, my) 是否在内容矩形 r1 内
            return r1[0] <= mx <= r1[2] and r1[1] <= my <= r1[3]

        # 🚀 3. 如果目标是字符串，进行标签碰撞检测
        if isinstance(target, str):
            tag = target
            # 获取精灵的位置
            sprite_x, sprite_y = self.x, self.y

            # 获取地图数据
            if _CURRENT_MAP:
                tile_size = _CURRENT_MAP.get("tile_size", 16)

                # 计算精灵包围盒覆盖的图块范围
                min_tile_x = math.floor(r1[0] // tile_size)
                max_tile_x = math.floor(r1[2] // tile_size)
                min_tile_y = math.floor(r1[1] // tile_size)
                max_tile_y = math.floor(r1[3] // tile_size)

                # 遍历所有图层
                for layer in _CURRENT_MAP.get("layers", []):
                    tiles = layer.get("tiles", {})

                    # 检查每个图块
                    for (tile_x, tile_y), tile_id in tiles.items():
                        if tile_id > 0:
                            # 检查图块是否在精灵包围盒内
                            if (
                                min_tile_x <= tile_x <= max_tile_x
                                and min_tile_y <= tile_y <= max_tile_y
                            ):
                                # 使用Tiled标准：通过firstgid范围查找瓦片集
                                resource_index, tile_index = _find_tileset_for_gid(
                                    tile_id, _CURRENT_MAP["tile_sets"]
                                )

                                # 获取图块标签
                                if _MAP_MODEL:
                                    tile_tag = _MAP_MODEL.get_tile_tag(
                                        resource_index, tile_index
                                    )
                                    if tile_tag == tag:
                                        return True
            return False

        # 🚀 4. 原有的 Sprite 间碰撞逻辑
        if target is None or not hasattr(target, "_visible") or not target._visible:
            return False
        if hasattr(target, "_is_deleted") and target._is_deleted:
            return False

        if not isinstance(target, Sprite):
            return False

        r2 = target._get_hitbox_rect()
        if not r2:
            return False

        # AABB 碰撞公式保持不变
        return not (r1[2] < r2[0] or r1[0] > r2[2] or r1[3] < r2[1] or r1[1] > r2[3])

    def touch_group(self, group_name):
        """
        判断是否撞到了某个组里的任意成员。
        如果撞到了，返回那个成员；没撞到返回 None。
        """
        if group_name not in _GROUPS:
            return None

        for other in _GROUPS[group_name]:
            # 排除自己
            if other is self:
                continue
            # 这里的 is_touching 是我们之前写的 Pillow AABB 算法
            if self.is_touch(other):
                return other
        return None

    def add_to_group(self, group_name):
        """将角色归类，比如 'enemies', 'bullets'"""
        if group_name not in _GROUPS:
            _GROUPS[group_name] = []
        if self not in _GROUPS[group_name]:
            _GROUPS[group_name].append(self)
            self._groups.append(group_name)

    def delete(self):
        """彻底删除（视觉移除 + 物理移除 + 内存清理）"""
        self._is_deleted = True
        self._send_command("DELETE", {"id": self.id})
        # 从全局组里彻底踢出去
        if hasattr(self, "_groups"):
            for g in self._groups:
                if self in _GROUPS.get(g, []):
                    _GROUPS[g].remove(self)
        # 从全局精灵集合中移除
        if self.id in _SPRITES:
            del _SPRITES[self.id]
        # 清理 say 计时器
        if self.id in _SAY_TIMERS:
            del _SAY_TIMERS[self.id]

    def distance_to(self, target):
        """
        计算当前角色视觉中心点到目标（Sprite 或 mouse）的距离
        """
        if self._is_deleted:
            return 999999

        # 🚀 1. 优先处理鼠标，因为它不是 Sprite 实例
        if target is mouse:
            # 使用精准的视觉中心点
            rect = self._get_hitbox_rect()
            cx, cy = (rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0
            dx = cx - _MOUSE_STATE["x"]
            dy = cy - _MOUSE_STATE["y"]
            return math.sqrt(dx * dx + dy * dy)

        # 🚀 2. 处理其他 Sprite 角色
        if not isinstance(target, Sprite) or target._is_deleted:
            return 999999

        # 为了保持精准，建议角色间测距也使用视觉中心
        r1 = self._get_hitbox_rect()
        r2 = target._get_hitbox_rect()

        cx1, cy1 = (r1[0] + r1[2]) / 2.0, (r1[1] + r1[3]) / 2.0
        cx2, cy2 = (r2[0] + r2[2]) / 2.0, (r2[1] + r2[3]) / 2.0

        dx = cx1 - cx2
        dy = cy1 - cy2
        return math.sqrt(dx**2 + dy**2)

    def is_on_floor(self):
        """
        检测角色脚底下方 1-2 像素处是否存在带有碰撞的图块
        返回: True 如果在地面上，False 否则
        """
        if self._is_deleted or not _CURRENT_MAP:
            return False

        # 获取角色的碰撞盒
        rect = self._get_hitbox_rect()
        if not rect:
            return False

        # 获取角色脚底位置（底部边缘）
        bottom_y = rect[3]
        # 检测脚底下方 1-2 像素处的位置
        check_y = bottom_y + 1.5

        # 获取地图的瓦片大小
        tile_size = _CURRENT_MAP.get("tile_size", 16)

        # 计算需要检查的图块范围（角色宽度范围内的所有图块）
        # 策略：稍微加宽 Y 轴的探测范围（左右各多出 2 像素）
        # 这样即使 X 轴修正把角色往外推了一点点，也不会导致"踩空"
        min_tile_x = math.floor((rect[0] - 2) / tile_size)
        max_tile_x = math.floor((rect[2] + 2) / tile_size)
        check_tile_y = math.floor(check_y // tile_size)

        # 遍历所有图层
        for layer in _CURRENT_MAP.get("layers", []):
            # --- 图像图层地面检测 ---
            if layer.get("type") == "image" and "images" in layer:
                for image in layer["images"]:
                    collision_enabled = image.get("collisionEnabled", image.get("collision_enabled", False))
                    if not collision_enabled:
                        continue

                    col_type = image.get("collisionType", image.get("collision_type", "图像"))
                    is_one_way = col_type == "跳板"

                    pos = image.get("position", [0, 0])
                    scale = image.get("scale", 1.0)
                    scale_x = image.get("scaleX", image.get("scale_x", scale))
                    scale_y = image.get("scaleY", image.get("scale_y", scale))

                    collision_shape = image.get("collision_shape", None)
                    if (
                        collision_shape
                        and "points" in collision_shape
                        and len(collision_shape["points"]) >= 2
                    ):
                        points = collision_shape["points"]
                        world_points = [
                            (
                                pos[0] + p[0] * abs(scale_x),
                                pos[1] + p[1] * abs(scale_y),
                            )
                            for p in points
                        ]
                        img_left = min(p[0] for p in world_points)
                        img_top = min(p[1] for p in world_points)
                        img_right = max(p[0] for p in world_points)
                        img_bottom = max(p[1] for p in world_points)
                    else:
                        img_w = image.get("width", image.get("_cache_w", 0))
                        img_h = image.get("height", image.get("_cache_h", 0))
                        if img_w <= 0 or img_h <= 0:
                            continue
                        img_left = pos[0]
                        img_top = pos[1]
                        img_right = img_left + img_w * abs(scale_x)
                        img_bottom = img_top + img_h * abs(scale_y)

                    if is_one_way and self._prev_bottom_y > img_top:
                        continue

                    if is_one_way and self._drop_through:
                        continue

                    if (
                        rect[0] - 2 <= img_right
                        and rect[2] + 2 >= img_left
                        and check_y >= img_top
                        and check_y <= img_bottom
                    ):
                        return True

            tiles = layer.get("tiles", {})

            # 检查角色宽度范围内的每个图块
            for tile_x in range(min_tile_x, max_tile_x + 1):
                tile_pos = (tile_x, check_tile_y)
                if tile_pos in tiles:
                    tile_id = tiles[tile_pos]
                    if tile_id > 0:
                        # 使用Tiled标准：通过firstgid范围查找瓦片集
                        tile_id_int = int(tile_id)
                        resource_index, tile_index = _find_tileset_for_gid(
                            tile_id_int, _CURRENT_MAP["tile_sets"]
                        )

                        # 获取图块碰撞状态
                        if _MAP_MODEL:
                            collision_enabled = _MAP_MODEL.get_tile_collision(
                                resource_index, tile_index
                            )
                            if collision_enabled:
                                col_type = _MAP_MODEL.get_tile_collision_type(
                                    resource_index, tile_index
                                )
                                is_one_way = col_type == "跳板"

                                # 获取图块的碰撞形状
                                collision_shape = _MAP_MODEL.get_tile_collision_shape(
                                    resource_index, tile_index
                                )

                                # 计算图块的碰撞盒
                                tile_size = _CURRENT_MAP.get("tile_size", 16)
                                if collision_shape and "points" in collision_shape:
                                    # 使用自定义碰撞形状
                                    points = collision_shape["points"]
                                    # 转换为世界坐标
                                    world_points = [
                                        (
                                            tile_x * tile_size + p[0],
                                            check_tile_y * tile_size + p[1],
                                        )
                                        for p in points
                                    ]
                                    # 计算自定义形状的边界盒
                                    tile_left = min(p[0] for p in world_points)
                                    tile_top = min(p[1] for p in world_points)
                                    tile_right = max(p[0] for p in world_points)
                                    tile_bottom = max(p[1] for p in world_points)
                                else:
                                    # 使用默认矩形碰撞盒
                                    tile_left = tile_x * tile_size
                                    tile_top = check_tile_y * tile_size
                                    tile_right = tile_left + tile_size
                                    tile_bottom = tile_top + tile_size

                                if is_one_way and self._prev_bottom_y > tile_top:
                                    continue

                                if is_one_way and self._drop_through:
                                    continue

                                # 检查角色脚底是否在图块的碰撞盒内
                                if (
                                    rect[0] - 2 <= tile_right
                                    and rect[2] + 2 >= tile_left
                                    and check_y >= tile_top
                                    and check_y <= tile_bottom
                                ):
                                    return True

        return False

    # ----------- 属性赋值 ----------
    @property
    def x(self):
        return self._x

    @x.setter
    def x(self, value):
        self.set_x(value)

    @property
    def y(self):
        return self._y

    @y.setter
    def y(self, value):
        self.set_y(value)

    @property
    def angle(self):
        return self._angle

    @angle.setter
    def angle(self, value):
        self.set_angle(value)

    @property
    def scale(self):
        return self._scale

    @scale.setter
    def scale(self, value):
        self.set_scale(value)

    @property
    def layer(self):
        return self._layer

    @layer.setter
    def layer(self, value):
        """学生可以手动设置层级，例如 hero.layer = 10"""
        self._layer = value
        self._send_command("UPDATE", {"id": self.id, "layer": value})

    # ---------- 内部调用 ----------
    def _load_sprite_config(self):
        """内部工具：尝试读取文件夹下的 config.json"""
        config_path = os.path.join(self.sprite_dir, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"❌ 警告：读取角色配置 {config_path} 失败: {e}")
        return None

    def _resolve_path(self, filename, category):
        """通用路径解析：工程根目录优先，其次是 assets/分类/，自动补全图片扩展名"""
        if os.path.exists(filename):
            return filename

        # 预留支持：assets/sprites/ 或 assets/sounds/ 等
        guessed_path = os.path.join("assets", category, filename)
        if os.path.exists(guessed_path):
            return guessed_path

        # 尝试常见图片扩展名（如 "火球子弹" → "火球子弹.png"）
        for ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"):
            if os.path.exists(guessed_path + ext):
                return guessed_path + ext

        return filename  # 实在找不到就返回原名，让错误显现出来

    def _setup_hitbox(self):
        """通用型高性能采样：支持任何尺寸图片，自动定位内容重心"""

        if hasattr(self, "_content_w") and self._cached_image == self.image:
            return self._cached_hitbox

        try:
            with Image.open(self.image) as img:
                self._orig_w, self._orig_h = img.size
                # 转换为 RGBA 确保 getbbox 能正常工作
                bbox = img.convert("RGBA").getbbox()

                if bbox:
                    l, t, r, b = bbox
                    self._content_w = r - l
                    self._content_h = b - t
                    self._content_bbox = bbox  # 保存非透明区域边界

                    self._visual_offset_x = (l + r) / 2.0 - self._orig_w / 2.0
                    self._visual_offset_y = (t + b) / 2.0 - self._orig_h / 2.0

                else:
                    self._content_w, self._content_h = self._orig_w, self._orig_h
                    self._visual_offset_x = self._visual_offset_y = 0

                self._cached_hitbox = [0, 0, self._content_w, self._content_h]
                self._cached_image = self.image
        except:
            self._content_w = self._content_h = 50
            self._visual_offset_x = self._visual_offset_y = 0
            self._orig_w = self._orig_h = 50
            self._content_bbox = (0, 0, 50, 50)
            self._cached_hitbox = [0, 0, 50, 50]
            self._cached_image = self.image

        return self._cached_hitbox

    def _get_hitbox_rect(self):
        """获取当前角色在舞台上的真实内容包围盒 [left, top, right, bottom]
        同一帧内重复调用使用缓存，减少计算量
        """
        self._setup_hitbox()  # 确保内容宽高和偏移量已算出

        # 获取非透明区域边界
        if not hasattr(self, "_content_bbox"):
            return None

        bbox = self._content_bbox
        if not bbox:
            return None

        # 帧级缓存：同一帧内位置不变时复用结果
        if hasattr(self, "_cached_rect_frame") and self._cached_rect_frame == _PERF_STATS["frame_count"]:
            if (abs(self._cached_rect_x - self._x) < 0.01 and 
                abs(self._cached_rect_y - self._y) < 0.01 and
                self._cached_rect_scale == self._scale):
                return self._cached_rect

        # 计算缩放系数
        s = self._scale / 100.0

        # 图片的视觉中心
        img_w, img_h = self._orig_w, self._orig_h
        center_x, center_y = self._x, self._y

        # 【核心对齐公式】
        # 以图片中心为基准，计算非透明内容相对于中心点的偏移，再应用缩放
        content_left = center_x + (bbox[0] - img_w / 2) * s
        content_top = center_y + (bbox[1] - img_h / 2) * s
        content_right = center_x + (bbox[2] - img_w / 2) * s
        content_bottom = center_y + (bbox[3] - img_h / 2) * s

        rect = [content_left, content_top, content_right, content_bottom]

        # 更新帧级缓存
        self._cached_rect = rect
        self._cached_rect_frame = _PERF_STATS["frame_count"]
        self._cached_rect_x = self._x
        self._cached_rect_y = self._y
        self._cached_rect_scale = self._scale

        return rect

    def _update_transform(self):
        """统一处理旋转、缩放和镜像逻辑"""
        display_angle = self._angle
        # 计算基础缩放比例（百分比转为小数）
        base_scale = self._scale / 100.0

        # 默认情况下，Y轴只受 size 影响
        final_scale_y = base_scale
        # X轴受 size 和 镜像状态 共同影响
        final_scale_x = base_scale * self._current_scale_x

        if self._rotation_style == "left_right":
            norm_angle = self._angle % 360
            if 90 < norm_angle < 270:
                self._current_scale_x = -1.0
            elif (0 <= norm_angle < 90) or (270 < norm_angle <= 360):
                self._current_scale_x = 1.0

            # 重新计算镜像后的 X 缩放
            final_scale_x = base_scale * self._current_scale_x
            display_angle = 0

        elif self._rotation_style == "none":
            display_angle = 0
            final_scale_x = base_scale

        # 🚀 缓存比对：如果上次发送值相同，跳过发送以减少管道压力
        current_key = (
            round(self._x, 1), round(self._y, 1), round(display_angle, 1),
            round(base_scale, 4), round(final_scale_x, 4), round(final_scale_y, 4),
            self._visible, self._layer,
            os.path.abspath(self.image) if hasattr(self, "image") and self.image else None,
        )
        if getattr(self, "_last_update_key", None) == current_key:
            return
        self._last_update_key = current_key

        # 🚀 发送指令：确保携带 scale_y 和图像信息
        update_data = {
            "x": self._x,
            "y": self._y,
            "angle": display_angle,
            "scale": base_scale,
            "scale_x": final_scale_x,
            "scale_y": final_scale_y,
            # 添加碰撞盒信息，用于可视化调试
            "hitbox": self._get_hitbox_rect()
            if self._show_hitbox and hasattr(self, "_get_hitbox_rect")
            else None,
            "vox": self._visual_offset_x,
            "voy": self._visual_offset_y,
            "cw": self._content_w,
            "ch": self._content_h,
        }

        # 添加图像信息（如果有）
        if hasattr(self, "image") and self.image:
            update_data["image"] = os.path.abspath(self.image)

        # 加入帧缓冲，帧末合并发送以减少管道写入次数
        update_data["id"] = self.id
        _FRAME_UPDATES.append(update_data)

    def _update_animation_frame(self):
        """更新动画帧"""
        if not hasattr(self, "animation_state") or not self.animation_state:
            return

        # 检查是否在过渡状态
        if hasattr(self, "_is_transitioning") and self._is_transitioning:
            # 计算过渡进度
            now = time.time()
            elapsed = now - self._transition_start_time
            progress = min(elapsed / self._transition_duration, 1.0)

            if progress < 0.5:
                # 前半段显示源动画的帧
                current_frame = self._source_animation["current_frame"]
            else:
                # 后半段显示目标动画的帧
                current_frame = self._target_animation["current_frame"]

            # 如果过渡完成，结束过渡状态
            if progress >= 1.0:
                self.animation_state = self._target_animation
                del self._source_animation
                del self._target_animation
                del self._transition_duration
                del self._is_transitioning
        else:
            # 正常动画播放
            current_frame = self.animation_state["current_frame"]

        # 获取帧文件路径
        if self.config and "frames" in self.config:
            if current_frame < len(self.config["frames"]):
                frame_file = self.config["frames"][current_frame]
                self.image = os.path.join(self.sprite_dir, frame_file)

                # 更新变换和图像
                self._update_transform()

    # ----------- 超级核心 -----------
    def _send_command(self, cmd_type, data_dict):
        """核心:所有指令都是通过它发送出去并执行的"""
        packet = {"type": cmd_type, "id": self.id, "data": data_dict}
        # stdout 已经是行缓冲模式（buffering=1），print 自动带换行会刷缓冲
        print(json.dumps(packet))


def _input_sync_listener():
    global _PRESSED_KEYS, _MOUSE_STATE, _PAUSED, _SHOW_FPS, _SHOW_ALL_COLLISION
    while True:
        try:
            # 🚀 确保是阻塞式读取
            line = sys.stdin.readline()
            if not line:
                time.sleep(0.01)
                continue

            clean_line = line.strip()

            if clean_line.startswith("K_DOWN:"):
                key = clean_line.split(":", 1)[1]
                _PRESSED_KEYS.add(key)
            elif clean_line.startswith("K_UP:"):
                key = clean_line.split(":", 1)[1]
                _PRESSED_KEYS.discard(key)

                # 🚀 新增鼠标事件处理
            elif clean_line.startswith("M_DOWN:"):
                old_value = _MOUSE_STATE["down"]
                _MOUSE_STATE["down"] = True

            elif clean_line.startswith("M_UP:"):
                old_value = _MOUSE_STATE["down"]
                _MOUSE_STATE["down"] = False

            elif clean_line.startswith("M_MOVE:"):
                # 解析 M_MOVE:320.5,240.0
                pos_str = clean_line.split(":", 1)[1]
                mx_s, my_s = pos_str.split(",")
                _MOUSE_STATE["x"] = float(mx_s)
                _MOUSE_STATE["y"] = float(my_s)

            # ─── 调试命令 ───
            elif clean_line == "PAUSE:":
                _PAUSED = True
                _PENDING_RESPONSES.append(json.dumps({"type": "PAUSE_STATE", "data": {"paused": True}}))
            elif clean_line == "RESUME:":
                _PAUSED = False
                _PENDING_RESPONSES.append(json.dumps({"type": "PAUSE_STATE", "data": {"paused": False}}))
            elif clean_line == "SHOW_FPS:1":
                _SHOW_FPS = True
                _PENDING_RESPONSES.append(json.dumps({"type": "FPS_UPDATE", "data": {"fps": round(_PERF_STATS.get("last_fps", 0), 1)}}))
            elif clean_line == "SHOW_FPS:0":
                _SHOW_FPS = False
                _PENDING_RESPONSES.append(json.dumps({"type": "FPS_UPDATE", "data": {"fps": 0}}))
            elif clean_line == "SHOW_COLLISION:1":
                _SHOW_ALL_COLLISION = True
                for sprite in _SPRITES.values():
                    sprite._show_hitbox = True
            elif clean_line == "SHOW_COLLISION:0":
                _SHOW_ALL_COLLISION = False
                for sprite in _SPRITES.values():
                    sprite._show_hitbox = False
            else:
                # 不是控制命令 → 投喂给用户代码的 input()
                _USER_INPUT_QUEUE.put(clean_line)
        except:
            time.sleep(0.01)


# 确保线程启动 (代码末尾)
threading.Thread(target=_input_sync_listener, daemon=True).start()


def _custom_input(prompt=""):
    """替代内置 input()，从 _USER_INPUT_QUEUE 读取，不跟 stdin 监听线程抢数据。"""
    if prompt:
        # 把提示文字输出到 stdout，前端控制台会显示
        print(prompt, end="", flush=True)
    # 通知前端弹出输入框
    print("__BINGO_WAITING_INPUT__", flush=True)
    try:
        return _USER_INPUT_QUEUE.get(timeout=300)
    except queue.Empty:
        return ""


def mouse_down():
    """判断鼠标是否按下"""
    # 🚀 不需要 global 声明，因为只读取不赋值
    return _MOUSE_STATE["down"]


def mouse_pressed():
    """单次检测：只有在按下的那一帧返回 True"""
    # 如果当前按下，且上一帧没按，说明是刚刚按下的
    return _MOUSE_STATE["down"] and not _MOUSE_STATE["last_down"]


def key_down(key):
    """供用户调用：if key_down('a')"""
    return str(key).lower() in _PRESSED_KEYS


def key_pressed(key):
    """只有按下的那一帧返回 True"""
    return str(key).lower() in _PRESSED_KEYS and str(key).lower() not in _PRESSED_KEYS_PREV


def wait(seconds):
    """每 N 秒返回一次 True"""
    now = time.time()
    if seconds not in _WAIT_TIMERS or now - _WAIT_TIMERS[seconds] >= seconds:
        _WAIT_TIMERS[seconds] = now
        return True
    return False


def broadcast(event_name):
    """发送全局广播"""
    for callback in _EVENT_LISTENERS.get(event_name, []):
        callback()


def receive(event_name, callback):
    """注册全局广播接收"""
    if event_name not in _EVENT_LISTENERS:
        _EVENT_LISTENERS[event_name] = []
    _EVENT_LISTENERS[event_name].append(callback)


def pause():
    """暂停游戏（loop 仍运行，但精灵停止移动）"""
    global _PAUSED
    _PAUSED = True


def resume():
    """继续游戏"""
    global _PAUSED
    _PAUSED = False


def is_paused():
    """检查是否暂停"""
    return _PAUSED


def stop():
    """停止游戏（退出 run 循环）"""
    global _STOPPED
    _STOPPED = True


def show_fps(visible=True):
    """学生调用的接口"""
    global _SHOW_FPS
    _SHOW_FPS = visible
    packet = {"type": "UI_COMMAND", "data": {"visible": visible}}
    print(json.dumps(packet))


def random_int(min_val, max_val):
    """在 min_val 和 max_val 之间取随机整数（包含两端）"""
    return random.randint(int(min_val), int(max_val))


def random_float(min_val=0.0, max_val=1.0):
    """在 min_val 和 max_val 之间取随机浮点数"""
    return random.uniform(float(min_val), float(max_val))


def shake(intensity=5, duration=0.3):
    """屏幕震动效果"""
    packet = {
        "type": "SCREEN_SHAKE",
        "data": {"intensity": intensity, "duration": duration},
    }
    print(json.dumps(packet))


def stop_sound(sound_name=None):
    """停止音效。不传参数则停止所有音效。"""
    packet = {
        "type": "STOP_SOUND",
        "data": {"sound": sound_name} if sound_name else {},
    }
    print(json.dumps(packet))


def draw_text(x, y, *args):
    """在屏幕指定位置绘制文字，参数自动拼接为字符串
    draw_text(100, 50, "分数:", score)
    """
    text = "".join(str(a) for a in args)
    packet = {
        "type": "DRAW_TEXT",
        "data": {"id": f"text_{x}_{y}", "text": text, "x": x, "y": y},
    }
    print(json.dumps(packet))


def play_sound(sound_name, loop=False):
    sounds_dir = os.path.join("assets", "sounds")
    sound_path = None
    if os.path.exists(os.path.join(sounds_dir, sound_name)):
        sound_path = os.path.join(sounds_dir, sound_name)
    else:
        for ext in (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".wma"):
            candidate = os.path.join(sounds_dir, sound_name + ext)
            if os.path.exists(candidate):
                sound_path = candidate
                break
    # 递归搜索子目录（如 effects/、loop/）
    if not sound_path:
        for root, dirs, files in os.walk(sounds_dir):
            for f in files:
                if f == sound_name or f.rsplit(".", 1)[0] == sound_name:
                    sound_path = os.path.join(root, f)
                    break
            if sound_path:
                break
    if not sound_path:
        return
    packet = {
        "type": "PLAY_SOUND",
        "data": {
            "sound": sound_path,
            "loop": loop,
        },
    }
    print(json.dumps(packet))


def show_collision(sprite):
    if isinstance(sprite, Sprite):
        sprite._show_hitbox = True


# ---------- 内部函数 ----------


def _send_fps_to_ide(fps):
    """内部统计并发送 FPS 数值"""
    packet = {"type": "FPS_UPDATE", "data": {"fps": round(fps, 1)}}
    print(json.dumps(packet))


def get_main_player():
    """获取主玩家（第一个创建的精灵）"""
    for sprite in _SPRITES.values():
        return sprite
    return None


def _send_camera_update(x, y, world_bounds=None):
    """发送摄像机更新指令到IDE"""
    data = {
        "x": x,
        "y": y,
    }
    if world_bounds:
        data["limit_left"] = world_bounds["left"]
        data["limit_right"] = world_bounds["right"]
        data["limit_top"] = world_bounds["top"]
        data["limit_bottom"] = world_bounds["bottom"]
    camera_packet = {
        "type": "CAMERA_UPDATE",
        "data": data,
    }
    print(json.dumps(camera_packet))


def _flush_frame_updates():
    """将帧缓冲中的精灵更新合并为一条 JSON 发送，大幅减少管道写入次数"""
    global _FRAME_UPDATES
    if not _FRAME_UPDATES:
        return
    packet = {"type": "UPDATE_BATCH", "data": {"updates": _FRAME_UPDATES}}
    print(json.dumps(packet))
    _FRAME_UPDATES = []


def follow(sprite):
    """
    设置摄像机跟随指定精灵

    Args:
        sprite: 要跟随的精灵对象
    """
    global _FOLLOW_TARGET
    _FOLLOW_TARGET = sprite


def load_map(map_name):
    """
    加载并显示地图

    Args:
        map_name: 地图名称（不含扩展名）
    """
    global _CURRENT_MAP, _MAP_SPRITES, _MAP_MODEL, _MAP_DIR

    # 清理之前的地图
    _clear_map()

    try:
        # 从项目根目录的assets/maps文件夹读取地图文件
        # 尝试加载二进制文件（通过检查.info文件），如果不存在再回退到JSON文件
        # 使用当前工作目录（项目根目录）
        map_dir = os.path.join(os.getcwd(), "assets", "maps", map_name)
        _MAP_DIR = map_dir
        json_file = os.path.join(map_dir, "map.json")

        # 如果地图目录不存在，尝试自动解压 .bgm 文件
        if not os.path.exists(map_dir):
            _try_extract_bgm(map_name)

        print(f"✅ [BingoEngine] 加载地图: {map_name}")

        if not os.path.exists(json_file):
            print(f"❌ [BingoEngine] 地图文件不存在: {json_file}")
            return False

        with open(json_file, "r", encoding="utf-8") as f:
            save_data = json.load(f)

        # 解析行业标准格式（带 firstgid 和压缩瓦片数据）
        tilesets_raw = save_data.get("tilesets", save_data.get("tileSets", []))
        tilesets = []
        for ts in tilesets_raw:
            tilesets.append({
                "name": ts.get("name", ""),
                "image_path": ts.get("image", ts.get("image_path", "")),
                "tile_width": ts.get("tileWidth", ts.get("tile_width", 16)),
                "tile_height": ts.get("tileHeight", ts.get("tile_height", 16)),
                "firstgid": ts.get("firstgid", 1),
                "collisionType": ts.get("collisionType", ts.get("collision_type", "图像")),
                "collisionEnabled": ts.get("collisionEnabled", ts.get("collision_enabled", False)),
                "tiles": ts.get("tiles", []),
            })

        # 解析图层数据
        layers_raw = save_data.get("layers", [])
        layers = []
        for layer_raw in layers_raw:
            layer_type = layer_raw.get("type", "drawing")
            if layer_type in ("tilelayer", "drawing"):
                tiles = {}
                data_str = layer_raw.get("data")
                if data_str:
                    # 解压 base64+zlib 瓦片数据（GID格式，含firstgid偏移）
                    tiles = _decompress_tiles(data_str, save_data["width"], save_data["height"])
                elif "tiles" in layer_raw:
                    # 兼容旧格式（稀疏字典）
                    raw_tiles = layer_raw["tiles"]
                    for key, val in raw_tiles.items():
                        if isinstance(key, str) and "," in key:
                            parts = key.split(",")
                            tiles[(int(parts[0]), int(parts[1]))] = val
                        else:
                            tiles[key] = val
                layers.append({
                    "name": layer_raw.get("name", "图层"),
                    "type": "drawing",
                    "visible": layer_raw.get("visible", True),
                    "locked": layer_raw.get("locked", False),
                    "tiles": tiles,
                    "images": layer_raw.get("images", []),
                })
            elif layer_type == "imagelayer":
                # 兼容两种格式：images（带位置）和 resources（资源引用，无位置）
                images = layer_raw.get("images", [])
                if not images:
                    # 将 resources 转换为 images 格式（资源默认放在 0,0）
                    for res in layer_raw.get("resources", []):
                        images.append({
                            "imagePath": res.get("path", ""),
                            "image_path": res.get("path", ""),
                            "position": [0, 0],
                            "rotation": 0,
                            "scale": 1,
                            "scaleX": 1,
                            "scaleY": 1,
                            "opacity": 1,
                            "width": res.get("tileWidth", 64),
                            "height": res.get("tileHeight", 64),
                            "collisionType": res.get("collisionType", "none"),
                            "collisionEnabled": res.get("collisionEnabled", False),
                        })
                layers.append({
                    "name": layer_raw.get("name", "图像层"),
                    "type": "image",
                    "visible": layer_raw.get("visible", True),
                    "locked": layer_raw.get("locked", False),
                    "tiles": {},
                    "images": images,
                })

        # 用图层中资源的碰撞信息补全 tileset（用户可能在 PropertyPanel 中设置了 tileset 级的碰撞）
        resource_collision_map = {}
        for layer_raw in layers_raw:
            for res in layer_raw.get("resources", []):
                rname = res.get("name", "")
                if rname and res.get("collisionEnabled", False):
                    resource_collision_map[rname] = {
                        "collisionType": res.get("collisionType", "图像"),
                        "collisionEnabled": True,
                    }
        for ts in tilesets:
            rname = ts.get("name", "")
            if rname in resource_collision_map:
                ts["collisionType"] = resource_collision_map[rname]["collisionType"]
                ts["collisionEnabled"] = True

        map_data = {
            "name": save_data.get("name", ""),
            "width": save_data["width"],
            "height": save_data["height"],
            "tile_size": save_data.get("tileSize", save_data.get("tile_size", 16)),
            "gravity": save_data.get("gravity", False),
            "layers": layers,
            "tile_sets": tilesets,
        }

        _CURRENT_MAP = map_data
        _MAP_MODEL = MapModel(tilesets)

        tile_size = _CURRENT_MAP.get("tile_size", 16)
        map_width_px = _CURRENT_MAP["width"] * tile_size
        map_height_px = _CURRENT_MAP["height"] * tile_size

        # 计算地图的世界像素边界（world_bounds）
        all_tile_positions = []
        all_image_bounds = []
        for layer in _CURRENT_MAP.get("layers", []):
            for (x, y), tile_id in layer.get("tiles", {}).items():
                if tile_id > 0:
                    all_tile_positions.append((x, y))
            if layer.get("type") == "image" and "images" in layer:
                for image in layer["images"]:
                    pos = image.get("position", [0, 0])
                    w = image.get("width", tile_size)
                    h = image.get("height", tile_size)
                    all_image_bounds.append((pos[0], pos[1], pos[0] + w, pos[1] + h))

        if all_tile_positions:
            min_gx = min(p[0] for p in all_tile_positions)
            max_gx = max(p[0] for p in all_tile_positions)
            min_gy = min(p[1] for p in all_tile_positions)
            max_gy = max(p[1] for p in all_tile_positions)
            tile_bounds_left = min_gx * tile_size
            tile_bounds_top = min_gy * tile_size
            tile_bounds_right = (max_gx + 1) * tile_size
            tile_bounds_bottom = (max_gy + 1) * tile_size
        else:
            tile_bounds_left = 0
            tile_bounds_top = 0
            tile_bounds_right = 640
            tile_bounds_bottom = 480

        all_left = [tile_bounds_left] + [b[0] for b in all_image_bounds]
        all_top = [tile_bounds_top] + [b[1] for b in all_image_bounds]
        all_right = [tile_bounds_right] + [b[2] for b in all_image_bounds]
        all_bottom = [tile_bounds_bottom] + [b[3] for b in all_image_bounds]

        # world_bounds 必须包含 (0,0) 到 (640,480) 的区域
        # 因为编辑器中游戏窗口参考框从 (0,0) 开始
        # 摄像机需要能显示这个区域
        world_bounds = {
            "left": min(min(all_left), 0),
            "top": min(min(all_top), 0),
            "right": max(max(all_right), 640),
            "bottom": max(max(all_bottom), 480),
        }
        _CURRENT_MAP["world_bounds"] = world_bounds

        scene_update_packet = {
            "type": "SCENE_UPDATE",
            "data": {
                "width": map_width_px,
                "height": map_height_px,
                "world_bounds": world_bounds,
            },
        }
        print(json.dumps(scene_update_packet))

        # 渲染地图
        _render_map()
        return True

    except Exception as e:
        print(f"❌ [BingoEngine] 加载地图时出错: {e}")
        import traceback

        traceback.print_exc()
        return False


def _decompress_tiles(base64_data, width, height):
    """解压 base64+zlib 瓦片数据为稀疏字典
    格式：每瓦片4字节uint32小端序，存储GID（含firstgid偏移）
    """
    import base64
    import zlib
    compressed = base64.b64decode(base64_data)
    decompressed = zlib.decompress(compressed)
    flat_array = list(decompressed)
    tiles = {}
    for y in range(height):
        for x in range(width):
            idx = (y * width + x) * 4
            if idx + 3 < len(flat_array):
                # uint32小端序
                gid = flat_array[idx] | (flat_array[idx + 1] << 8) | (flat_array[idx + 2] << 16) | (flat_array[idx + 3] << 24)
                if gid > 0:
                    tiles[(x, y)] = gid
    return tiles


def _find_tileset_for_gid(gid, tile_sets):
    """通过GID查找所属瓦片集索引和本地瓦片索引（Tiled标准）
    使用二分查找优化（tile_sets按firstgid升序排列）
    返回 (tileset_index, local_tile_index)，未找到返回 (0, 0)
    """
    if not tile_sets:
        return 0, gid
    # 二分查找：找到最后一个 firstgid <= gid 的瓦片集
    lo, hi = 0, len(tile_sets) - 1
    result = 0
    while lo <= hi:
        mid = (lo + hi) // 2
        firstgid = tile_sets[mid].get("firstgid", 1)
        if gid >= firstgid:
            result = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return result, gid - tile_sets[result].get("firstgid", 1)


def _try_extract_bgm(map_name):
    """自动解压 .bgm 地图包到 assets/maps/ 目录"""
    import zipfile
    engine_dir = os.path.dirname(os.path.abspath(__file__))
    bgm_path = os.path.join(engine_dir, "assets", "maps", "packages", f"{map_name}.bgm")
    if not os.path.exists(bgm_path):
        return False
    try:
        target_dir = os.path.join(os.getcwd(), "assets", "maps", map_name)
        os.makedirs(target_dir, exist_ok=True)
        with zipfile.ZipFile(bgm_path, 'r') as zf:
            zf.extractall(target_dir)
        print(f"✅ [BingoEngine] 自动解压 .bgm: {map_name} → {target_dir}")
        return True
    except Exception as e:
        print(f"❌ [BingoEngine] 解压 .bgm 失败: {e}")
        return False


def _clear_map():
    """清理地图资源"""
    global _CURRENT_MAP, _MAP_SPRITES, _RENDERED_TILES, _MAP_DIR

    # 删除地图瓦片精灵
    for sprite_id in list(_MAP_SPRITES.keys()):
        packet = {"type": "DELETE", "id": sprite_id}
        print(json.dumps(packet))
        del _MAP_SPRITES[sprite_id]

    _CURRENT_MAP = None
    _MAP_DIR = None
    _MAP_SPRITES = {}
    _RENDERED_TILES.clear()


def _handle_physics_collision():
    """处理物理碰撞检测和位移修正"""
    global _CURRENT_MAP, _SPRITES, _MAP_MODEL

    if not _CURRENT_MAP:
        return

    # 遍历所有精灵
    for sprite in _SPRITES.values():
        if sprite._is_deleted:
            continue

        if sprite._drop_through:
            sprite._drop_through_timer -= 1
            if sprite._drop_through_timer <= 0:
                sprite._drop_through = False

        sprite.on_ground = False

        hitbox = sprite._get_hitbox_rect()
        if hitbox:
            sprite._prev_bottom_y = hitbox[3]

        if _CURRENT_MAP.get("gravity", False):
            if sprite.vy < 0:
                if sprite._jump_cut:
                    gravity = 2.8
                else:
                    gravity = 0.5
            else:
                gravity = 1.1
            sprite.vy = min(sprite.vy + gravity, 10)
        else:
            gravity = 0

        sprite._y += sprite.vy
        sprite._resolve_collision("y")
        sprite._resolve_collision("x")
        if sprite.on_ground:
            sprite.vy = 0
            sprite._jump_cut = False

        sprite._update_transform()


def _render_map():
    """渲染地图 - 优化版本"""
    global _CURRENT_MAP, _MAP_SPRITES, _RENDERED_TILES, _MAP_DIR

    if not _CURRENT_MAP:
        return

    tile_size = _CURRENT_MAP["tile_size"]

    batch_commands = []

    # 遍历所有图层
    for layer_idx, layer in enumerate(_CURRENT_MAP["layers"]):
        if not layer["visible"]:
            continue

        # 处理图像图层
        if layer.get("type") == "image" and "images" in layer:
            for image_idx, image in enumerate(layer["images"]):
                # 生成唯一的图像ID
                sprite_id = f"image_{layer_idx}_{image_idx}"

                # 获取图像位置
                position = image.get("position", [0, 0])
                screen_x = position[0]
                screen_y = position[1]

                # 获取图像旋转、缩放和透明度
                rotation = image.get("rotation", 0)
                scale = image.get("scale", 1.0)
                scale_x = image.get("scale_x", scale)
                scale_y = image.get("scale_y", scale)
                opacity = image.get("opacity", 1.0)

                # 获取图像路径并转换为绝对路径（兼容 camelCase 和 snake_case）
                image_path = image.get("imagePath", image.get("image_path", ""))
                if image_path:
                    # 如果是相对路径，转换为绝对路径
                    if not os.path.isabs(image_path):
                        # 尝试相对于地图文件所在目录的路径
                        map_dir = _MAP_DIR if _MAP_DIR else os.getcwd()
                        absolute_path = os.path.join(map_dir, image_path)
                        if os.path.exists(absolute_path):
                            image_path = absolute_path
                        else:
                            # 尝试相对于项目根目录的路径
                            project_root = os.path.dirname(
                                os.path.dirname(os.path.abspath(__file__))
                            )
                            absolute_path = os.path.join(project_root, image_path)
                            if os.path.exists(absolute_path):
                                image_path = absolute_path
                            else:
                                # 尝试相对于当前工作目录的路径
                                absolute_path = os.path.join(os.getcwd(), image_path)
                                if os.path.exists(absolute_path):
                                    image_path = absolute_path

                # 获取图像原始尺寸（使用缓存避免重复磁盘IO）
                original_width, original_height = 1, 1
                if image_path:
                    cache_key = image_path
                    if cache_key in _IMAGE_SIZE_CACHE:
                        original_width, original_height = _IMAGE_SIZE_CACHE[cache_key]
                    else:
                        try:
                            from PIL import Image

                            with Image.open(image_path) as img:
                                original_width, original_height = img.size
                            _IMAGE_SIZE_CACHE[cache_key] = (original_width, original_height)
                        except:
                            pass

                # 直接使用左上角坐标，因为update_map_image方法会处理中心点计算
                center_x = screen_x
                center_y = screen_y

                # 缓存图像原始尺寸到 image dict（用于运行时碰撞检测）
                image["_cache_w"] = original_width
                image["_cache_h"] = original_height

                # 添加到批量渲染列表
                image_data = {
                    "id": sprite_id,
                    "x": center_x,
                    "y": center_y,
                    "angle": rotation,
                    "scale": scale,
                    "scale_x": scale_x,
                    "scale_y": scale_y,
                    "opacity": opacity,
                    "type": "image",
                    "image_path": image_path,
                    "layer": layer_idx,
                }

                batch_commands.append(image_data)

        # 处理绘制图层的瓦片
        if "tiles" in layer:
            # 遍历图层中的所有瓦片（静态图层烘焙模式下渲染所有瓦片）
            for (x, y), tile_id in layer["tiles"].items():
                if tile_id <= 0:
                    continue

                tile_id_int = int(tile_id)

                # 使用Tiled标准：通过firstgid范围查找瓦片集
                resource_index, actual_tile_index = _find_tileset_for_gid(
                    tile_id_int, _CURRENT_MAP["tile_sets"]
                )

                if resource_index >= len(_CURRENT_MAP["tile_sets"]):
                    continue

                sprite_id = f"tile_{layer_idx}_{x}_{y}"
                tile_key = (layer_idx, x, y)

                # 获取瓦片集的具体瓦片大小（图块实际大小）
                tile_set_size = tile_size  # 默认使用地图的全局tile_size
                if resource_index < len(_CURRENT_MAP["tile_sets"]):
                    tile_set = _CURRENT_MAP["tile_sets"][resource_index]
                    tile_set_size = tile_set.get("tile_width", tile_size)

                # 计算瓦片在世界坐标中的位置 - 左上角定位
                # 与编辑器画布一致：setPos(x * tile_size, y * tile_size)
                world_x = x * tile_size
                world_y = y * tile_size

                # 添加到批量渲染列表
                tile_data = {
                    "id": sprite_id,
                    "x": world_x,
                    "y": world_y,
                    "angle": 0,
                    "scale": 1.0,
                    "scale_x": 1.0,
                    "scale_y": 1.0,
                    "type": "tile",
                    "tile_id": actual_tile_index + 1,  # 恢复为从1开始的索引
                    "tile_set_index": resource_index,
                    "layer": layer_idx,
                    "tile_size": tile_set_size,
                }

                batch_commands.append(tile_data)
                _RENDERED_TILES.add(tile_key)

    # 批量渲染：一次性发送所有可见瓦片和图像的渲染指令
    if batch_commands:
        # 处理瓦片集信息，确保包含完整的图片路径
        processed_tile_sets = []
        if _CURRENT_MAP.get("tile_sets"):
            for tile_set in _CURRENT_MAP["tile_sets"]:
                processed_tile_set = tile_set.copy()
                # 确保image_path字段存在（兼容二进制格式）
                if "image_path" in processed_tile_set:
                    # 转换图像路径为绝对路径
                    image_path = processed_tile_set["image_path"]
                    if not os.path.isabs(image_path):
                        # 尝试相对于项目根目录的路径
                        project_root = os.path.dirname(
                            os.path.dirname(os.path.abspath(__file__))
                        )
                        absolute_path = os.path.join(project_root, image_path)
                        if os.path.exists(absolute_path):
                            image_path = absolute_path
                        else:
                            # 尝试相对于当前工作目录的路径
                            absolute_path = os.path.join(os.getcwd(), image_path)
                            if os.path.exists(absolute_path):
                                image_path = absolute_path
                    processed_tile_set["image_path"] = image_path
                    processed_tile_set["image"] = image_path
                processed_tile_sets.append(processed_tile_set)

        # 使用地图的全局tile_size作为数据包的tile_size（格子大小）
        # 这样图块始终在原来的格子位置上
        packet_tile_size = tile_size

        packet = {
            "type": "CREATE_BATCH",
            "data": {
                "tiles": batch_commands,
                "tile_sets": processed_tile_sets,
                "tile_size": packet_tile_size,
            },
        }
        print(json.dumps(packet))

        # 更新已渲染的精灵字典
        for tile_data in batch_commands:
            _MAP_SPRITES[tile_data["id"]] = tile_data


def run():
    global _PERF_STATS, _MOUSE_STATE, _SPRITES, _PENDING_RESPONSES
    _MOUSE_STATE["down"] = False
    main_module = sys.modules["__main__"]
    if not hasattr(main_module, "loop"):
        return

    _PHYSICS_DT = 1.0 / 60.0
    _MAX_FRAME_TIME = 0.05
    _MAX_PHYSICS_STEPS = 3

    _PERF_STATS["last_time"] = time.time()
    accumulator = 0.0
    prev_time = time.perf_counter()

    while True:
        if _STOPPED:
            break

        now = time.perf_counter()
        frame_time = min(now - prev_time, _MAX_FRAME_TIME)
        prev_time = now
        accumulator += frame_time

        steps = 0
        while accumulator >= _PHYSICS_DT and steps < _MAX_PHYSICS_STEPS:
            if not _PAUSED:
                for sprite in _SPRITES.values():
                    if hasattr(sprite, "_is_transitioning") and sprite._is_transitioning:
                        source_state = sprite._source_animation
                        if source_state.get("is_playing", True):
                            t = time.time()
                            if t - source_state["last_frame_time"] >= source_state["frame_duration"]:
                                source_state["current_frame"] += 1
                                if source_state["current_frame"] > source_state["end"]:
                                    if source_state.get("loop", True):
                                        source_state["current_frame"] = source_state["start"]
                                    else:
                                        source_state["current_frame"] = source_state["end"]
                                        source_state["is_playing"] = False
                                source_state["last_frame_time"] = t

                        target_state = sprite._target_animation
                        if target_state.get("is_playing", True):
                            t = time.time()
                            if t - target_state["last_frame_time"] >= target_state["frame_duration"]:
                                target_state["current_frame"] += 1
                                if target_state["current_frame"] > target_state["end"]:
                                    if target_state.get("loop", True):
                                        target_state["current_frame"] = target_state["start"]
                                    else:
                                        target_state["current_frame"] = target_state["end"]
                                        target_state["is_playing"] = False
                                target_state["last_frame_time"] = t

                        sprite._update_animation_frame()
                    elif hasattr(sprite, "animation_state") and sprite.animation_state:
                        sprite_state = sprite.animation_state
                        if not sprite_state.get("is_playing", True):
                            continue
                        t = time.time()
                        if t - sprite_state["last_frame_time"] >= sprite_state["frame_duration"]:
                            sprite_state["current_frame"] += 1
                            if sprite_state["current_frame"] > sprite_state["end"]:
                                if sprite_state.get("loop", True):
                                    sprite_state["current_frame"] = sprite_state["start"]
                                else:
                                    sprite_state["current_frame"] = sprite_state["end"]
                                    sprite_state["is_playing"] = False
                            sprite_state["last_frame_time"] = t
                            sprite._update_animation_frame()

            main_module.loop()

            for sid in list(_SAY_TIMERS.keys()):
                timer, hide_fn = _SAY_TIMERS[sid]
                if timer.is_timeout():
                    hide_fn()
                    del _SAY_TIMERS[sid]

            if not _PAUSED:
                for sprite in list(_SPRITES.values()):
                    if sprite._is_deleted:
                        continue
                    # 运动
                    if sprite._speed > 0:
                        sprite.move(sprite._speed)
                    # 自动销毁
                    if sprite._auto_destroy and sprite.is_out_side():
                        sprite.delete()
                    # 碰撞回调
                    if sprite._on_hit_callbacks:
                        for group_name, callback in list(sprite._on_hit_callbacks):
                            for other in list(_GROUPS.get(group_name, [])):
                                if other is sprite or other._is_deleted:
                                    continue
                                if sprite.is_touch(other):
                                    if callback:
                                        callback(sprite, other)
                                    else:
                                        sprite.delete()
                                        other.delete()
                                    break

                if _CURRENT_MAP:
                    _handle_physics_collision()

            accumulator -= _PHYSICS_DT
            steps += 1

        if accumulator > _PHYSICS_DT * _MAX_PHYSICS_STEPS:
            accumulator = 0.0

        if _FOLLOW_TARGET:
            global _CAMERA_X, _CAMERA_Y
            old_camera_x = _CAMERA_X
            old_camera_y = _CAMERA_Y

            if _CURRENT_MAP:
                bounds = _CURRENT_MAP.get(
                    "world_bounds", {"left": 0, "top": 0, "right": 640, "bottom": 480}
                )
            else:
                bounds = {"left": 0, "top": 0, "right": 640, "bottom": 480}
            view_w, view_h = 640, 480

            _CAMERA_X = max(
                bounds["left"] + view_w / 2,
                min(_FOLLOW_TARGET.x, bounds["right"] - view_w / 2),
            )
            _CAMERA_Y = max(
                bounds["top"] + view_h / 2,
                min(_FOLLOW_TARGET.y, bounds["bottom"] - view_h / 2),
            )

            _send_camera_update(_CAMERA_X, _CAMERA_Y, bounds if _CURRENT_MAP else None)

            if _CURRENT_MAP:
                tile_size = _CURRENT_MAP.get("tile_size", 16)
                if (
                    abs(_CAMERA_X - old_camera_x) >= tile_size // 2
                    or abs(_CAMERA_Y - old_camera_y) >= tile_size // 2
                ):
                    _render_map()

        # 合并发送本帧所有精灵更新
        _flush_frame_updates()

        _MOUSE_STATE["last_down"] = _MOUSE_STATE["down"]
        _PRESSED_KEYS_PREV = _PRESSED_KEYS.copy()

        _PERF_STATS["frame_count"] += 1
        t = time.time()
        duration = t - _PERF_STATS["last_time"]
        if duration >= 0.5:
            fps = _PERF_STATS["frame_count"] / duration
            _PERF_STATS["last_fps"] = round(fps, 1)
            if _SHOW_FPS:
                _send_fps_to_ide(fps)
            _PERF_STATS["frame_count"] = 0
            _PERF_STATS["last_time"] = t

        # 刷出监听线程的待发响应
        while _PENDING_RESPONSES:
            print(_PENDING_RESPONSES.pop(0))

        # 帧率限制：混合等待策略。time.sleep() 睡大部分时间省电，
        # 末尾用精确自旋补齐 macOS time.sleep() 的精度不足
        target_frame_time = 1.0 / 60.0
        elapsed = time.perf_counter() - now
        remaining = target_frame_time - elapsed
        if remaining > 0.003:
            # 用 sleep 睡大部分时间（省电），留约 1.5ms 给自旋
            time.sleep(remaining - 0.0015)
            # 精确自旋补齐剩余时间
            while time.perf_counter() - now < target_frame_time:
                pass
        elif remaining > 0:
            # 剩余时间很少，直接自旋（避免 sleep 精度问题）
            while time.perf_counter() - now < target_frame_time:
                pass


# ========== 新增：Generator 调度模式 ==========

_generators = []  # 所有活跃的 generator

def register_generator(gen):
    """注册一个 generator 到调度器"""
    _generators.append(gen)

def unregister_generator(gen):
    """从调度器移除一个 generator"""
    if gen in _generators:
        _generators.remove(gen)

class GameStop(Exception):
    """游戏停止异常"""
    pass

def stop_game():
    """停止游戏（抛出异常中断 generator）"""
    raise GameStop()

def start_game(project_dir=None, target_file=None):
    """
    新版游戏启动函数：使用 generator 调度模式

    Args:
        project_dir: 项目目录路径，用于自动发现 .py 文件
        target_file: 指定要运行的文件路径
    """
    global _STOPPED, _PERF_STATS, _MOUSE_STATE, _PENDING_RESPONSES

    _STOPPED = False
    _MOUSE_STATE["down"] = False

    # 如果提供了项目目录，使用脚本发现模块
    if project_dir:
        from script_runner import discover_and_merge
        script_content = discover_and_merge(project_dir, target_file)
        if not script_content:
            print("❌ 没有找到 Python 文件")
            return

        # 执行脚本，注册 generator
        exec_globals = {
            "__name__": "__main__",
            "Sprite": Sprite,
            "Timer": Timer,
            "input": _custom_input,
            "key_down": key_down,
            "key_pressed": key_pressed,
            "mouse": mouse,
            "mouse_down": mouse_down,
            "mouse_pressed": mouse_pressed,
            "wait": wait,
            "load_map": load_map,
            "play_sound": play_sound,
            "stop_sound": stop_sound,
            "draw_text": draw_text,
            "shake": shake,
            "follow": follow,
            "show_fps": show_fps,
            "show_collision": show_collision,
            "random_int": random_int,
            "random_float": random_float,
            "broadcast": broadcast,
            "receive": receive,
            "pause": pause,
            "resume": resume,
            "is_paused": is_paused,
            "stop": stop_game,
            "register_generator": register_generator,
        }
        exec(script_content, exec_globals)

    # 主循环
    _PERF_STATS["last_time"] = time.time()
    _PHYSICS_DT = 1.0 / 60.0
    _MAX_FRAME_TIME = 0.05
    _MAX_PHYSICS_STEPS = 3
    accumulator = 0.0
    prev_time = time.perf_counter()

    while True:
        now = time.perf_counter()
        frame_time = min(now - prev_time, _MAX_FRAME_TIME)
        prev_time = now
        accumulator += frame_time

        # 物理步进
        steps = 0
        while accumulator >= _PHYSICS_DT and steps < _MAX_PHYSICS_STEPS:
            if not _PAUSED:
                # 动画更新
                for sprite in _SPRITES.values():
                    if hasattr(sprite, "animation_state") and sprite.animation_state:
                        _update_sprite_animation(sprite)

                # 执行所有 generator（每帧一次迭代）
                for gen in list(_generators):
                    try:
                        next(gen)
                    except StopIteration:
                        _generators.remove(gen)
                    except GameStop:
                        _generators.clear()
                        return
                    except Exception as e:
                        print(f"❌ Generator 错误: {e}")
                        _generators.remove(gen)

                # 精灵运动和碰撞
                for sprite in list(_SPRITES.values()):
                    if sprite._is_deleted:
                        continue
                    if sprite._speed > 0:
                        sprite.move(sprite._speed)
                    if sprite._auto_destroy and sprite.is_out_side():
                        sprite.delete()
                    if sprite._on_hit_callbacks:
                        for group_name, callback in list(sprite._on_hit_callbacks):
                            for other in list(_GROUPS.get(group_name, [])):
                                if other is sprite or other._is_deleted:
                                    continue
                                if sprite.is_touch(other):
                                    if callback:
                                        callback(sprite, other)
                                    else:
                                        sprite.delete()
                                        other.delete()
                                    break

                if _CURRENT_MAP:
                    _handle_physics_collision()

            accumulator -= _PHYSICS_DT
            steps += 1

        if accumulator > _PHYSICS_DT * _MAX_PHYSICS_STEPS:
            accumulator = 0.0

        # 相机跟随
        if _FOLLOW_TARGET:
            global _CAMERA_X, _CAMERA_Y
            old_camera_x = _CAMERA_X
            old_camera_y = _CAMERA_Y

            if _CURRENT_MAP:
                bounds = _CURRENT_MAP.get("world_bounds", {"left": 0, "top": 0, "right": 640, "bottom": 480})
            else:
                bounds = {"left": 0, "top": 0, "right": 640, "bottom": 480}
            view_w, view_h = 640, 480

            _CAMERA_X = max(bounds["left"] + view_w / 2, min(_FOLLOW_TARGET.x, bounds["right"] - view_w / 2))
            _CAMERA_Y = max(bounds["top"] + view_h / 2, min(_FOLLOW_TARGET.y, bounds["bottom"] - view_h / 2))

            _send_camera_update(_CAMERA_X, _CAMERA_Y, bounds if _CURRENT_MAP else None)

            if _CURRENT_MAP:
                tile_size = _CURRENT_MAP.get("tile_size", 16)
                if abs(_CAMERA_X - old_camera_x) >= tile_size // 2 or abs(_CAMERA_Y - old_camera_y) >= tile_size // 2:
                    _render_map()

        # 帧合并发送
        _flush_frame_updates()

        # 状态更新
        _MOUSE_STATE["last_down"] = _MOUSE_STATE["down"]
        _PRESSED_KEYS_PREV = _PRESSED_KEYS.copy()

        # FPS 统计
        _PERF_STATS["frame_count"] += 1
        t = time.time()
        duration = t - _PERF_STATS["last_time"]
        if duration >= 0.5:
            fps = _PERF_STATS["frame_count"] / duration
            _PERF_STATS["last_fps"] = round(fps, 1)
            if _SHOW_FPS:
                _send_fps_to_ide(fps)
            _PERF_STATS["frame_count"] = 0
            _PERF_STATS["last_time"] = t

        # 刷出监听线程的待发响应
        while _PENDING_RESPONSES:
            print(_PENDING_RESPONSES.pop(0))

        # 帧率限制
        target_frame_time = 1.0 / 60.0
        elapsed = time.perf_counter() - now
        remaining = target_frame_time - elapsed
        if remaining > 0.003:
            time.sleep(remaining - 0.0015)
            while time.perf_counter() - now < target_frame_time:
                pass
        elif remaining > 0:
            while time.perf_counter() - now < target_frame_time:
                pass

def _update_sprite_animation(sprite):
    """更新精灵动画帧"""
    if not hasattr(sprite, "animation_state") or not sprite.animation_state:
        return

    sprite_state = sprite.animation_state
    if not sprite_state.get("is_playing", True):
        return

    t = time.time()
    if t - sprite_state["last_frame_time"] >= sprite_state["frame_duration"]:
        sprite_state["current_frame"] += 1
        if sprite_state["current_frame"] > sprite_state["end"]:
            if sprite_state.get("loop", True):
                sprite_state["current_frame"] = sprite_state["start"]
            else:
                sprite_state["current_frame"] = sprite_state["end"]
                sprite_state["is_playing"] = False
        sprite_state["last_frame_time"] = t
        sprite._update_animation_frame()