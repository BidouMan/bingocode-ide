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
from models.shape_kernel import (
    ConvexPolygon, CompoundShape, polygon_shape, aabb_shape, capsule_shape, intersects,
    overlap as shape_overlap,
    sweep as shape_sweep,
    point_inside,
    raycast as shape_raycast,
)
from models.static_index import StaticEntry, build_world, SENSOR_EPS
from models.coords import (
    to_world_x,
    to_world_y,
    to_user_x,
    to_user_y,
    to_world_dx,
    to_world_dy,
    to_user_dy,
    to_world_angle,
    to_user_angle,
    set_user_origin_y,
    screen_to_user_y,
)

# 添加项目根目录到Python路径（确保在任何目录运行都能找到models模块）
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 设置标准输出为无缓冲模式
sys.stdout = os.fdopen(sys.stdout.fileno(), "w", buffering=1)

_PRESSED_KEYS = set()
_PRESSED_KEYS_FRAME = set()
_PRESSED_KEYS_PREV = set()
# 松开事件：监听线程累积到 _RELEASED_KEYS，每个物理步开始快照到 _RELEASED_FRAME，
# 供 key_up() 读取；这样不会因为事件到达时机跨帧而漏掉"刚松开"的那一帧
_RELEASED_KEYS = set()
_RELEASED_FRAME = set()
_WAIT_TIMERS = {}  # key=(code_id, lineno) -> 上次触发时的游戏时间（每个调用位置独立）
_GAME_TIME = 0.0  # 游戏时间（秒）：只在未暂停时随物理步累加，Timer / time_passed 统一使用
_EVENT_LISTENERS = {}
# 广播事件的两帧缓冲：broadcast() 写入 _EVENT_PENDING，下一步开始提升到 _EVENT_ACTIVE，
# 供 receive() 查询；持续一帧后自动清空，保证同一帧内代码顺序不影响结果
_EVENT_PENDING = set()
_EVENT_ACTIVE = set()
_SHOW_FPS = False
_PAUSED = False
_STOPPED = False
_SHOW_ALL_COLLISION = False
_PENDING_RESPONSES = []  # 监听线程→主线程的待发响应
_USER_INPUT_QUEUE = queue.Queue()  # 用户 input() 输入队列
_PERF_STATS = {"last_time": time.time(), "frame_count": 0}
# 固定物理步长（60Hz）与单个渲染帧最多补算的物理步数；
# run() 与 start_game() 共用这套常量，避免两条主循环各写一份而逐渐走偏
_PHYSICS_DT = 1.0 / 60.0
_MAX_FRAME_TIME = 0.05
_MAX_PHYSICS_STEPS = 3
_GROUPS = {}
# 用字典包装鼠标状态：released 由输入线程累积，released_frame 是每个物理步的快照（供 mouse_up）
_MOUSE_STATE = {"down": False, "last_down": False, "released": False, "released_frame": False, "x": 0, "y": 0}
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
_AUTO_CAMERA_TARGET = None  # 由地图相机设置自动跟随的主玩家（区别于代码 camera_follow()）

# 渲染缓存
_RENDERED_TILES = set()  # 已渲染的瓦片缓存
_IMAGE_SIZE_CACHE = {}   # 图像尺寸缓存，避免重复磁盘IO
_IMAGE_BBOX_CACHE = {}   # 图片内容框缓存：同一张图批量创建角色时免去重复读盘+像素采样
_FRAME_UPDATES = []      # 每帧精灵更新缓冲，帧末合并发送


def _image_bbox_info(path):
    """读取图片尺寸与非透明内容框（按路径+修改时间缓存，批量创建角色不必反复读盘）

    返回 (原宽, 原高, 内容框, 内容宽, 内容高, 横向视觉偏移, 纵向视觉偏移)；
    图片读不出来返回 None（调用方按 50x50 兜底）。
    """
    try:
        st = os.stat(path)
        key = (os.path.abspath(path), st.st_mtime_ns, st.st_size)
    except OSError:
        return None

    info = _IMAGE_BBOX_CACHE.get(key)
    if info is not None:
        return info

    try:
        with Image.open(path) as img:
            orig_w, orig_h = img.size
            # 转换为 RGBA 确保 getbbox 能正常工作
            bbox = img.convert("RGBA").getbbox()
    except Exception:
        return None

    if bbox:
        l, t, r, b = bbox
        content_w, content_h = r - l, b - t
        vox = (l + r) / 2.0 - orig_w / 2.0
        voy = (t + b) / 2.0 - orig_h / 2.0
    else:
        content_w, content_h = orig_w, orig_h
        vox = voy = 0

    info = (orig_w, orig_h, bbox, content_w, content_h, vox, voy)
    _IMAGE_BBOX_CACHE[key] = info
    return info


def _playable_bounds():
    """游戏可玩区域 = 地图矩形（width×tile_size × height×tile_size）

    边界碰撞与边界类 API 必须都用这一套边界。不能用 world_bounds：
    它包含绘制图层四周的出血区与超出地图的素材（40×30 的地图可能算出 1280×960），
    角色会被挡在屏幕外，看起来就像"走出去了"。
    没有地图时退回 640×480 舞台。
    """
    if _CURRENT_MAP:
        ts = _CURRENT_MAP.get("tile_size", 16)
        return {
            "left": 0,
            "top": 0,
            "right": _CURRENT_MAP["width"] * ts,
            "bottom": _CURRENT_MAP["height"] * ts,
        }
    return {"left": 0, "top": 0, "right": _SCREEN_WIDTH, "bottom": _SCREEN_HEIGHT}


# ---------- 图像实例碰撞几何（图像模式） ----------

def _polygon_signed_area(points):
    """鞋带公式，返回有符号面积"""
    area = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return area / 2.0


def _is_convex_polygon(points):
    """判断多边形是否为凸（用于决定是否需要三角剖分）"""
    n = len(points)
    if n < 3:
        return False
    sign = 0
    for i in range(n):
        ax, ay = points[i]
        bx, by = points[(i + 1) % n]
        cx, cy = points[(i + 2) % n]
        cross = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
        if abs(cross) < 1e-9:
            continue
        s = 1 if cross > 0 else -1
        if sign == 0:
            sign = s
        elif s != sign:
            return False
    return sign != 0


def _point_in_triangle(px, py, ax, ay, bx, by, cx, cy):
    d1 = (px - bx) * (ay - by) - (ax - bx) * (py - by)
    d2 = (px - cx) * (by - cy) - (bx - cx) * (py - cy)
    d3 = (px - ax) * (cy - ay) - (cx - ax) * (py - ay)
    has_neg = d1 < -1e-9 or d2 < -1e-9 or d3 < -1e-9
    has_pos = d1 > 1e-9 or d2 > 1e-9 or d3 > 1e-9
    return not (has_neg and has_pos)


def _triangulate_polygon(points):
    """耳切法把凹多边形拆成三角形；失败时回退扇形三角化"""
    pts = [list(p) for p in points]
    if len(pts) < 3:
        return None
    if _polygon_signed_area(pts) < 0:
        pts.reverse()

    indices = list(range(len(pts)))
    tris = []
    guard = 0
    max_guard = len(pts) * len(pts) + 16
    while len(indices) > 3 and guard < max_guard:
        guard += 1
        ear_found = False
        n = len(indices)
        for i in range(n):
            i0 = indices[(i - 1) % n]
            i1 = indices[i]
            i2 = indices[(i + 1) % n]
            ax, ay = pts[i0]
            bx, by = pts[i1]
            cx, cy = pts[i2]
            cross = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
            if cross <= 1e-9:
                continue
            contains_other = False
            for j in indices:
                if j == i0 or j == i1 or j == i2:
                    continue
                if _point_in_triangle(pts[j][0], pts[j][1], ax, ay, bx, by, cx, cy):
                    contains_other = True
                    break
            if contains_other:
                continue
            tris.append([pts[i0], pts[i1], pts[i2]])
            indices.pop(i)
            ear_found = True
            break
        if not ear_found:
            break

    if len(indices) == 3:
        tris.append([pts[indices[0]], pts[indices[1]], pts[indices[2]]])

    if not tris:
        # 回退：扇形三角化（至少保证有碰撞体）
        tris = [[pts[0], pts[i], pts[i + 1]] for i in range(1, len(pts) - 1)]
    return tris


def _normalize_image_collision_points(raw_points, img_w, img_h, allow_pixel_coords=True):
    """单组碰撞点 → 去重、可选兼容历史像素坐标后的归一化点列

    新格式 collisions 的坐标恒为归一化值（允许超出 0~1，表示碰撞体在画面外），
    因此只有旧 collisionShape 才启用像素坐标启发式。
    """
    points = []
    for p in raw_points or []:
        if not isinstance(p, (list, tuple)) or len(p) < 2:
            continue
        try:
            x, y = float(p[0]), float(p[1])
        except (TypeError, ValueError):
            continue
        if not points or abs(x - points[-1][0]) > 1e-6 or abs(y - points[-1][1]) > 1e-6:
            points.append([x, y])
    if len(points) >= 2:
        if abs(points[0][0] - points[-1][0]) < 1e-6 and abs(points[0][1] - points[-1][1]) < 1e-6:
            points.pop()

    # 兼容历史像素坐标（绝对值 > 1.5 视为像素）
    if allow_pixel_coords and points and any(abs(x) > 1.5 or abs(y) > 1.5 for x, y in points):
        points = [[x / img_w, y / img_h] for x, y in points]
    return points


def _collision_polygon_parts(points):
    """碰撞层多边形 → SAT 判定用的凸多边形集合（凹多边形做耳切三角化）

    SAT 只对凸多边形严格成立：凹多边形直接投影会在凹陷空区判定出假碰撞，
    表现为角色还悬在斜面上方就被拦住（看起来像整层碰撞"位移"了）。
    """
    pts = [[float(p[0]), float(p[1])] for p in points]
    convex = [[(x, y) for x, y in pts]]
    if _is_convex_polygon(pts):
        return convex
    tris = _triangulate_polygon(pts) or []
    parts = [[(float(x), float(y)) for x, y in tri] for tri in tris if len(tri) >= 3]
    return parts or convex


def _shape_convex_parts(poly):
    """形状层多边形 → 凸块形状列表（凹多边形耳切三角化），结果缓存到 poly。

    不能直接 ConvexPolygon(points)：自定义工具画出的凹多边形会抛 ValueError，
    旧实现会静默丢掉整块形状（既不阻挡也不触发感应）。
    """
    cached = poly.get("_shape_parts")
    if cached is not None:
        return cached

    parts = []
    for source in poly.get("parts") or [poly.get("points") or []]:
        for convex_points in _collision_polygon_parts(source):
            if len(convex_points) < 3:
                continue
            try:
                parts.append(ConvexPolygon(convex_points))
            except (ValueError, TypeError):
                continue
    poly["_shape_parts"] = parts
    return parts


def _image_collision_local_polygons(image):
    """图像实例碰撞形状 → 图片本地归一化凸多边形列表（缓存到运行时字典）

    新格式支持一张图多个碰撞体（collisions 数组，坐标允许超出 0~1）；
    旧存档仅有单个 collisionShape，按单碰撞体读取。
    """
    cached = image.get("_collision_local_polys")
    if cached is not None:
        return cached

    img_w = float(image.get("width") or 0) or 1.0
    img_h = float(image.get("height") or 0) or 1.0

    raw_sets = []
    collisions = image.get("collisions")
    has_collisions_field = isinstance(collisions, (list, tuple))
    if has_collisions_field:
        for col in collisions:
            if isinstance(col, dict):
                raw_sets.append((col.get("points") or [], False))
    else:
        shape = image.get("collisionShape") or image.get("collision_shape")
        if isinstance(shape, dict):
            raw_sets.append((shape.get("points") or [], True))

    polys = []
    for raw_points, allow_pixel in raw_sets:
        points = _normalize_image_collision_points(raw_points, img_w, img_h, allow_pixel)
        if len(points) < 3 or abs(_polygon_signed_area(points)) < 1e-8:
            continue
        if _is_convex_polygon(points):
            polys.append(points)
        else:
            tris = _triangulate_polygon(points)
            polys.extend(tris if tris else [points])

    if not polys:
        if has_collisions_field:
            # 新格式已明确给出碰撞体集合：空/无有效项 = 没有碰撞，不回退整图
            polys = []
        else:
            # 旧存档没有碰撞形状时按整张图片处理
            polys = [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0]]]

    image["_collision_local_polys"] = polys
    return polys


def _image_collision_world_polygons(image):
    """把归一化本地多边形转换到世界坐标（中心缩放 + 旋转 + 平移）"""
    local_polys = _image_collision_local_polygons(image)

    pos = image.get("position") or [0, 0]
    try:
        px, py = float(pos[0]), float(pos[1])
    except (TypeError, ValueError, IndexError):
        px, py = 0.0, 0.0

    img_w = float(image.get("width") or 64) or 64.0
    img_h = float(image.get("height") or 64) or 64.0
    try:
        scale = float(image.get("scale", 1.0) or 1.0)
    except (TypeError, ValueError):
        scale = 1.0
    try:
        sx = abs(float(image.get("scaleX", image.get("scale_x", scale)) or scale))
    except (TypeError, ValueError):
        sx = abs(scale)
    try:
        sy = abs(float(image.get("scaleY", image.get("scale_y", scale)) or scale))
    except (TypeError, ValueError):
        sy = abs(scale)
    if sx <= 0:
        sx = abs(scale) or 1.0
    if sy <= 0:
        sy = abs(scale) or 1.0

    try:
        rotation = float(image.get("rotation", 0) or 0)
    except (TypeError, ValueError):
        rotation = 0.0

    # 同一帧内 x/y 两次碰撞检测、is_on_ground 会重复调用；
    # 变换未变化时直接复用世界多边形，避免每帧重复分配
    cache_key = (px, py, img_w, img_h, sx, sy, rotation)
    if image.get("_collision_world_key") == cache_key:
        return image.get("_collision_world_polys") or []

    rad = math.radians(rotation)
    cos_a, sin_a = math.cos(rad), math.sin(rad)

    # 前端 anchor=0.5：position 是未旋转包围盒左上角，旋转围绕中心
    cx = px + img_w * sx / 2.0
    cy = py + img_h * sy / 2.0

    world_polys = []
    for poly in local_polys:
        out = []
        for p in poly:
            lx = (p[0] - 0.5) * img_w * sx
            ly = (p[1] - 0.5) * img_h * sy
            out.append((cx + lx * cos_a - ly * sin_a, cy + lx * sin_a + ly * cos_a))
        world_polys.append(out)

    image["_collision_world_key"] = cache_key
    image["_collision_world_polys"] = world_polys
    return world_polys


def _polygon_center(points):
    n = len(points)
    return (sum(p[0] for p in points) / n, sum(p[1] for p in points) / n)


def _project_points(points, axis):
    ax, ay = axis
    vals = [p[0] * ax + p[1] * ay for p in points]
    return min(vals), max(vals)


def _rect_corners(rect):
    return [(rect[0], rect[1]), (rect[2], rect[1]), (rect[2], rect[3]), (rect[0], rect[3])]


def _sign(value):
    """位移方向：正数返回 1，负数返回 -1，零返回 0（碰撞按方向解算用）"""
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _aabb_polygon_mtv(rect, polygon):
    """SAT：返回把矩形推出多边形的最小平移向量 (mtv_x, mtv_y)；不相交返回 None"""
    axes = [(1.0, 0.0), (0.0, 1.0)]
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        ex, ey = x2 - x1, y2 - y1
        length = math.hypot(ex, ey)
        if length < 1e-9:
            continue
        axes.append((-ey / length, ex / length))

    rect_points = _rect_corners(rect)
    rect_cx, rect_cy = _polygon_center(rect_points)
    poly_cx, poly_cy = _polygon_center(polygon)

    min_overlap = float("inf")
    best_axis = None
    best_sign = 1.0
    for axis in axes:
        rmin, rmax = _project_points(rect_points, axis)
        pmin, pmax = _project_points(polygon, axis)
        overlap = min(rmax, pmax) - max(rmin, pmin)
        if overlap <= 1e-7:
            return None
        if overlap < min_overlap:
            min_overlap = overlap
            best_axis = axis
            rc = rect_cx * axis[0] + rect_cy * axis[1]
            pc = poly_cx * axis[0] + poly_cy * axis[1]
            best_sign = 1.0 if rc >= pc else -1.0

    if best_axis is None:
        return None
    return (best_axis[0] * min_overlap * best_sign, best_axis[1] * min_overlap * best_sign)


def _point_in_polygon(x, y, polygon):
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xin = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < xin:
                inside = not inside
    return inside


def _polygon_hits_horizontal(polygon, x0, x1, y):
    """多边形是否与水平检测带 [x0,x1] × y 相交（用于 is_on_ground）"""
    n = len(polygon)
    for i in range(n):
        x1p, y1p = polygon[i]
        x2p, y2p = polygon[(i + 1) % n]
        if (y1p > y) != (y2p > y):
            xin = (x2p - x1p) * (y - y1p) / (y2p - y1p) + x1p
            if x0 <= xin <= x1:
                return True
    # 采样判断脚下是否已经陷入碰撞体内部
    samples = 5
    for k in range(samples + 1):
        x = x0 + (x1 - x0) * k / samples
        if _point_in_polygon(x, y, polygon):
            return True
    return False


class _MouseType:
    @property
    def x(self):
        return to_user_x(_MOUSE_STATE["x"])

    @property
    def y(self):
        # 鼠标是屏幕坐标：固定在屏幕左下角，不随地图高度变化
        return screen_to_user_y(_MOUSE_STATE["y"])

    @property
    def pos(self):
        """一次性获取鼠标坐标 (x, y)，可直接拆包：x, y = mouse.pos"""
        return self.x, self.y

    def __repr__(self):
        return "mouse"


mouse = _MouseType()  # 🚀 定义全局变量 mouse


class _MarkerRef:
    """挂点引用（get_marker 返回）：读取时实时求值世界坐标。

    支持动画帧切换（帧级覆盖）、父的旋转/缩放/镜像变换；
    可直接用于 goto() / follow()，也可读 .x / .y。
    """

    def __init__(self, sprite, name):
        self._sprite = sprite
        self.name = name

    @property
    def x(self):
        pos = self._sprite._marker_world_xy(self.name)
        return to_user_x(pos[0]) if pos else 0.0

    @property
    def y(self):
        pos = self._sprite._marker_world_xy(self.name)
        # 用户空间：y 向上为正
        return to_user_y(pos[1]) if pos else 0.0

    def __repr__(self):
        return "marker('%s')" % self.name


def _resolve_target_xy(target):
    """把标记引用 / 地图标记 / Sprite 解析为世界坐标 (x, y)；无法解析返回 None"""
    if isinstance(target, _MarkerRef):
        return target._sprite._marker_world_xy(target.name)
    if isinstance(target, MapMarkerRef):
        # 地图标记本身保存的就是世界坐标
        return target.world_xy
    if isinstance(target, Sprite):
        if target._is_deleted:
            return None
        # 必须读世界坐标：target.x/y 是用户空间，会翻转 y
        return (target._x, target._y)
    return None

def _parse_direction_world(direction):
    """方向参数 → 世界坐标单位向量 (x 右、y 下)。

    支持：
      - 字符串："left"/"right"/"up"/"down"（以及 左/右/上/下）
      - 数字：用户角度（0=右，90=上，180=左，270=下；逆时针为正）
    无效返回 None。
    """
    if isinstance(direction, str):
        key = direction.strip().lower()
        table = {
            "left": (-1.0, 0.0), "right": (1.0, 0.0),
            "up": (0.0, -1.0), "down": (0.0, 1.0),
            "左": (-1.0, 0.0), "右": (1.0, 0.0),
            "上": (0.0, -1.0), "下": (0.0, 1.0),
        }
        return table.get(key)
    if isinstance(direction, (int, float)):
        rad = math.radians(float(direction))
        return (math.cos(rad), -math.sin(rad))
    return None

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


class Timer:
    def __init__(self, seconds, loop=True):
        self._interval = float(seconds)
        self._loop = loop
        self._running = False
        self._last_time = 0.0
        # 创建即自动开始（与文档、教程写法一致）；需要手动控制就先 stop() 再 start()
        self.start()

    def start(self):
        """开始/重新开始计时（会重置计时起点）"""
        self._running = True
        self._last_time = _GAME_TIME

    def stop(self):
        """停止计时（再次 start() 后重新计时）"""
        self._running = False

    def is_timeout(self):
        """时间到了返回 True；循环计时器会自动重新计时"""
        if not self._running:
            return False
        if _GAME_TIME - self._last_time >= self._interval:
            self._last_time = _GAME_TIME
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
        # 角色素材名（Sprite("角色1") 里的名字），供相机跟随按名字查找
        self.sprite_name = filename
        self._x = 320
        self._y = 240
        self._scale = 100
        self._angle = 0
        self._rotation_style = "all"
        self._current_scale_x = 1.0
        self.hitbox_scale = 1.0
        self._on_ground = False
        # 接触掩码（P4）：本帧 x/y 解算中碰到的方向，按位记录
        self._contacts = 0
        self._vy = 0
        self._prev_bottom_y = 0
        # 本步移动前的内容盒上沿：与 _prev_bottom_y 一起判断「从上方落地 / 从下方撞头」
        self._prev_top_y = 0
        self._jump_cut = False
        # smart_jump：active=正在由 smart_jump 控制的跳跃；called=本帧是否被调用过
        # 目标写法是 if key_down("w"): smart_jump()，按键松开后就不会再被调用，
        # 引擎据此判断松手并自动停止跳跃
        self._smart_jump_active = False
        self._smart_jump_called = False
        # 记录这次起跳对应的按键；松开该键时引擎自动停止跳跃
        self._smart_jump_key = None
        self._drop_through = False
        self._drop_through_timer = 0
        self._groups = []
        self._visible = True
        self._is_deleted = False
        self._layer = 0
        self._speed = 0
        # 本物理步学生代码执行前的 x：用于区分主动移动与斜面碰撞推挤下滑
        self._frame_start_x = 0.0
        self._on_hit_callbacks = []
        # 感应区进出回调：[(tag, callback)]；_sensor_active_tags 记录当前仍在区域内的标签，
        # 用于「只在从无到有 / 从有到无时各触发一次」
        self._sensor_enter_callbacks = []
        self._sensor_exit_callbacks = []
        self._sensor_active_tags = set()
        self._auto_destroy = False
        # 位置跟随目标（get_marker 挂点引用 / 另一个 Sprite）：None = 不跟随
        self._follow_ref = None
        # 跟随镜像继承（±1）：父翻面武器跟着翻（Godot 子节点语义）
        # 脱离跟随（unfollow）后保留最后一次取值，使挂件保持脱离瞬间的朝向
        self._follow_flip = 1.0
        # follow(target, flip=False) 可关闭镜像继承（如鼠标瞄准武器）
        self._follow_flip_on = True
        # 本帧实际显示的镜像倍率（含自身翻转与跟随继承），供挂点求值/链式跟随读取
        self._display_flip = 1.0

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
        self._is_bsf = False
        # 禁用碰撞（编辑器「禁用碰撞」开关；仅 .bsf manifest 提供，缺省开启）
        self._collision_disabled = False
        # 受重力影响（编辑器「重力」开关 / 代码 sprite.gravity；缺省受重力）
        self._gravity = True
        self.config = self._load_sprite_config()
        # .bgs 的 config.json 直接携带 gravity 字段（.bsf 已在 normalize 时读取）
        if self.config and not self._is_bsf:
            self._gravity = bool(self.config.get("gravity", True))

        if self.config:
            # 如果是 BGS 角色包格式
            self.current_costume_index = 0

            if self._is_bsf:
                # .bsf：唯一贴图是 sheet.png，帧切换只改 UV 区域（frame_rect）
                # 初始帧 = manifest.defaultFrame（编辑器选中帧），缺省第一帧
                self.image = self._bsf_sheet
            # 检查 frames 或 costumes 字段
            elif "frames" in self.config:
                frames_list = self.config["frames"]
                # 默认渲染帧（编辑器选中帧持久化字段），无效/缺省回退第一帧
                df = self.config.get("defaultFrame")
                if isinstance(df, str) and df in frames_list:
                    self.current_costume_index = frames_list.index(df)
                elif isinstance(df, int) and 0 <= df < len(frames_list):
                    self.current_costume_index = df
                first_frame = frames_list[self.current_costume_index]
                self.image = os.path.join(self.sprite_dir, first_frame)
            elif "costumes" in self.config:
                first_frame = self.config["costumes"][0]["file"]
                self.image = os.path.join(self.sprite_dir, first_frame)
        else:
            self.image = self._resolve_path(filename, "sprites")
            self.sprite_dir = None
            self.config = None

        if not os.path.exists(self.image):
            print(f"[警告] 角色 '{filename}' 不存在，请先在资源管理器中添加")
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
            "layer": self._layer,  # 默认 0：数字越大越靠前，学生设 1/2 即可盖住别人
            "vox": self._visual_offset_x,
            "voy": self._visual_offset_y,
            "raw_cw": self._content_w,
            "raw_ch": self._content_h,
        }

        # .bsf：CREATE 即携带首帧在 sheet 中的 UV 区域
        if self._is_bsf:
            create_data["frame_rect"] = self._bsf_frame_rect()

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
    def _collision_layer_correction(self, layer, axis, layer_index=None):
        """形状层（世界坐标多边形）对当前精灵的轴分离位移量；没有碰撞返回 None"""
        sprite_rect = self._get_hitbox_rect()
        if not sprite_rect:
            return None

        # 静态索引宽相：只有包围盒可能相交的形状才进入精确 SAT。
        # 解算顺序仍完全沿用 layer["polygons"]，结果与全表扫描一致。
        candidate_ids = None
        static_world = _CURRENT_MAP.get("static_world") if _CURRENT_MAP else None
        if static_world is not None and layer_index is not None:
            entries = static_world.solid.query_rect(
                sprite_rect[0], sprite_rect[1], sprite_rect[2], sprite_rect[3]
            )
            candidate_ids = {
                e.ref for e in entries
                if e.source == "shape" and e.layer_index == layer_index and e.ref is not None
            }
            if not candidate_ids:
                return None

        sprite_shape = self._get_collision_shape()
        best = None
        for poly in layer.get("polygons", []):
            if candidate_ids is not None and poly.get("id") not in candidate_ids:
                continue
            if poly.get("disabled"):
                continue
            # 感应形状只做区域检测，不参与阻挡解算
            if poly.get("kind", "solid") == "sensor":
                continue
            points = poly.get("points") or []
            if len(points) < 3:
                continue

            col_type = poly.get("collisionType", "墙体")
            is_one_way = col_type == "跳板"
            if is_one_way and axis == "x":
                continue
            if is_one_way and self._drop_through:
                continue

            if is_one_way:
                poly_top = min(p[1] for p in points)
                poly_bottom = max(p[1] for p in points)
                if self._prev_bottom_y > poly_top:
                    continue
                if axis == "y":
                    # 必须先和平台横向重叠，否则远处的跳板会把角色"吸"上去
                    if (
                        sprite_rect[2] <= min(p[0] for p in points)
                        or sprite_rect[0] >= max(p[0] for p in points)
                    ):
                        continue
                    # 单向平台只需落回顶面：薄多边形用 SAT 求 MTV 会残留穿透，
                    # 下一帧就会被误判成"从下方穿过"而整块掉下去
                    # 必须真正与平台竖直方向交叠：角色整体在平台下方时不能被"吸"上去
                    if sprite_rect[3] > poly_top and sprite_rect[1] < poly_bottom:
                        cand = poly_top - sprite_rect[3] - 0.05
                        if best is None or abs(cand) > abs(best):
                            best = cand
                    continue

            # 凸块形状缓存：凹多边形已拆成凸块，SAT 只能对凸多边形判定
            part_shapes = _shape_convex_parts(poly)

            part_best = None
            for part_shape in part_shapes:
                # 角色用真实判定形状（胶囊/多边形），不再用 AABB
                manifold = shape_overlap(sprite_shape, part_shape)
                if manifold is None:
                    continue
                mtv = (manifold.normal[0] * manifold.depth,
                       manifold.normal[1] * manifold.depth)
                if not self._mtv_axis_dominant(mtv, axis):
                    continue
                part_correction = mtv[0] if axis == "x" else mtv[1]
                if abs(part_correction) < 1e-6:
                    continue
                if part_best is None or abs(part_correction) > abs(part_best):
                    part_best = part_correction
            if part_best is None:
                continue
            if best is None or abs(part_best) > abs(best):
                best = part_best

        return best

    def _image_collision_correction(self, layer, axis):
        """计算图像图层对当前精灵的轴分离位移量；没有碰撞返回 None

        图像实例的碰撞形状是图片本地归一化多边形，运行时按缩放/旋转转换到世界坐标；
        凹多边形已在加载时三角剖分，用 SAT 求最小穿透并按移动轴取分量。
        """
        sprite_rect = self._get_hitbox_rect()
        if not sprite_rect:
            return None

        best = None
        for image in layer.get("images", []):
            collision_enabled = image.get(
                "collisionEnabled", image.get("collision_enabled", False)
            )
            if not collision_enabled:
                continue

            col_type = image.get("collisionType", image.get("collision_type", "图像"))
            is_one_way = col_type == "跳板"
            if is_one_way and axis == "x":
                continue
            if is_one_way and self._drop_through:
                continue

            world_polys = _image_collision_world_polygons(image)
            if not world_polys:
                continue

            # 单向平台：只在下落且脚底在平台顶面之上时生效
            if is_one_way:
                poly_top = min(p[1] for poly in world_polys for p in poly)
                poly_bottom = max(p[1] for poly in world_polys for p in poly)
                if self._prev_bottom_y > poly_top:
                    continue
                if axis == "y":
                    # 必须和平台横向重叠，避免远处跳板把角色吸上去
                    poly_left = min(p[0] for poly in world_polys for p in poly)
                    poly_right = max(p[0] for poly in world_polys for p in poly)
                    if sprite_rect[2] <= poly_left or sprite_rect[0] >= poly_right:
                        continue
                    # 单向平台只落到顶面，避免 SAT 对薄碰撞形状残留穿透
                    # 必须真正与平台竖直方向交叠：角色整体在平台下方时不能被吸上去
                    if sprite_rect[3] > poly_top and sprite_rect[1] < poly_bottom:
                        cand = poly_top - sprite_rect[3] - 0.05
                        if best is None or abs(cand) > abs(best):
                            best = cand
                    continue

            shape_parts = image.get("_collision_world_shapes")
            if shape_parts is None:
                shape_parts = []
                for poly in world_polys:
                    if len(poly) < 3:
                        continue
                    try:
                        shape_parts.append(ConvexPolygon(poly))
                    except (ValueError, TypeError):
                        continue
                image["_collision_world_shapes"] = shape_parts

            sprite_shape = self._get_collision_shape()
            for part_shape in shape_parts:
                manifold = shape_overlap(sprite_shape, part_shape)
                if manifold is None:
                    continue
                mtv = (manifold.normal[0] * manifold.depth,
                       manifold.normal[1] * manifold.depth)
                if not self._mtv_axis_dominant(mtv, axis):
                    continue
                correction = mtv[0] if axis == "x" else mtv[1]
                if abs(correction) < 1e-6:
                    continue
                if best is None or abs(correction) > abs(best):
                    best = correction

        return best

    # 接触掩码位：分别表示「左侧 / 右侧 / 头顶 / 脚下」有阻挡
    _CONTACT_LEFT = 1
    _CONTACT_RIGHT = 2
    _CONTACT_UP = 4
    _CONTACT_DOWN = 8

    # 多边形/图像碰撞在 y 轴上可接受的推挤距离上限（像素）。
    # 超过这个距离说明角色是嵌进了墙体侧面，不是正常落地/撞头，应交给 x 轴处理；
    # 斜坡每帧的抬升只有几像素，远小于这个值，所以上坡不受影响。
    _MAX_CONTACT_SNAP = 12.0
    # 站在地面时能自动抬脚走上去的最大台阶高度（像素）
    _MAX_STEP_UP = 8.0
    # 多边形 MTV 的「主导轴」系数：只有 MTV 在该轴上的分量不小于另一轴 0.5 倍时，
    # 才认为这个轴是该面的真实朝向（0.5 ≈ 允许 63° 以内的斜坡）。
    # 手画碰撞层的「竖直墙」常常歪几度，三角形边缘的 MTV 是斜的，
    # 硬取它的 y 分量会把贴墙下落的角色一帧帧往上顶（表现为挂在墙上慢慢下滑）。
    _MTV_DOMINANT_RATIO = 0.5

    def _mtv_axis_dominant(self, mtv, axis):
        """MTV 是否主要沿指定轴（x 轴看 x 分量、y 轴看 y 分量）"""
        main = abs(mtv[0]) if axis == "x" else abs(mtv[1])
        other = abs(mtv[1]) if axis == "x" else abs(mtv[0])
        return main >= other * self._MTV_DOMINANT_RATIO

    def _accept_axis_correction(self, correction, direction):
        """是否采纳本轴的推挤修正：只接受与运动方向相反的推挤

        direction = 0 表示本步没有主动移动，保留旧的「最近边推出」兜底行为
        """
        if direction == 0 or correction is None:
            return True
        return (correction > 0) != (direction > 0)

    def _contact_bit(self, axis, correction):
        """推挤方向 → 接触位。

        correction > 0 表示把角色往右/下推：说明阻挡在左侧/头顶。
        """
        if axis == "x":
            return self._CONTACT_LEFT if correction > 0 else self._CONTACT_RIGHT
        return self._CONTACT_DOWN if correction < 0 else self._CONTACT_UP

    def _contact_bit_from_normal(self, normal):
        """法线方向 → 接触位（法线从阻挡指向角色）。"""
        if abs(normal[0]) >= abs(normal[1]):
            return self._contact_bit("x", normal[0])
        return self._contact_bit("y", normal[1])

    # depenetration：最多迭代次数 / 推出后额外留出的皮肤厚度
    _DEPEN_MAX_ITERATIONS = 4
    _DEPEN_SKIN = 0.01

    def _depenetrate(self):
        """把角色从静态实心几何里推出；返回是否发生过推出。

        用于角色生成/传送/上一帧修正残留导致嵌墙的场景：
          - 只查 solid 索引，感应与单向平台不参与（单向平台不能从下方顶人）
          - 每轮取穿透最深的一组，沿法线推出 depth + 少量皮肤
          - 迭代若干轮，处理同时嵌在两个障碍里的极端情况
        """
        if self._collision_disabled or not _CURRENT_MAP:
            return False
        static_world = _CURRENT_MAP.get("static_world")
        if static_world is None:
            return False

        moved = False
        for _ in range(self._DEPEN_MAX_ITERATIONS):
            rect = self._get_hitbox_rect()
            if not rect:
                break
            entries = static_world.solid.query_rect(rect[0], rect[1], rect[2], rect[3])
            if not entries:
                break
            sprite_shape = self._get_collision_shape()
            best = None
            for entry in entries:
                # 单向平台只从上方承载，不能当作实心块把角色顶出去
                if entry.collision_type == "跳板":
                    continue
                manifold = shape_overlap(sprite_shape, entry.shape)
                if manifold is None or manifold.depth <= 1e-4:
                    continue
                if best is None or manifold.depth > best.depth:
                    best = manifold
            if best is None:
                break
            push = best.depth + self._DEPEN_SKIN
            self._x += best.normal[0] * push
            self._y += best.normal[1] * push
            self._contacts |= self._contact_bit_from_normal(best.normal)
            moved = True
        return moved

    # 单步最大位移：超过就拆分，避免一步穿过薄墙（与 move() 的 16px 子步一致）
    _MAX_MOVE_STEP = 16.0

    def move_and_slide(self, dx, dy, axis_order="xy", resolve_x=True, resolve_y=True,
                       depenetrate=True):
        """唯一位移入口：先 depenetrate，再按轴移动并解算碰撞。

        axis_order:
          - "xy"：先横向后纵向（角色代码 move()/add_x 等）
          - "yx"：先纵向后横向（重力物理步，与旧行为一致）
        resolve_x/resolve_y=False 时对应轴不移动也不解算（set_x/add_x 等单轴操作）。
        位移超过 _MAX_MOVE_STEP 时自动拆成多个子步，避免隧道效应。
        """
        if self._collision_disabled or not _CURRENT_MAP:
            if resolve_x:
                self._x += dx
            if resolve_y:
                self._y += dy
            return

        total = math.hypot(dx, dy)
        steps = 1 if total <= self._MAX_MOVE_STEP else int(math.ceil(total / self._MAX_MOVE_STEP))
        step_dx = dx / steps
        step_dy = dy / steps
        for _ in range(steps):
            self._move_and_slide_step(
                step_dx, step_dy, axis_order, resolve_x, resolve_y, depenetrate
            )

    def _move_and_slide_step(self, dx, dy, axis_order, resolve_x, resolve_y, depenetrate):
        """move_and_slide 的单个子步（保证每次位移不超过 _MAX_MOVE_STEP）。"""
        if depenetrate:
            self._depenetrate()

        # 记录移动前的内容盒上下沿，供单向平台「从上方落地 / 从下方撞头」判断
        hitbox = self._get_hitbox_rect()
        if hitbox:
            self._prev_bottom_y = hitbox[3]
            self._prev_top_y = hitbox[1]

        if axis_order == "yx":
            if resolve_y:
                self._y += dy
                self._resolve_collision("y", _sign(dy))
            if resolve_x:
                self._x += dx
                self._resolve_collision("x", _sign(dx))
        else:
            if resolve_x:
                self._x += dx
                self._resolve_collision("x", _sign(dx))
            if resolve_y:
                self._y += dy
                self._resolve_collision("y", _sign(dy))

    def _resolve_collision(self, axis, direction=0):
        """
        处理碰撞检测和位移修正
        axis: 'x' 或 'y'，指定要处理的轴
        direction: 本步在该轴上的移动方向（世界坐标正负）；0 = 本步没有主动移动

        轴向解算只接受「与运动方向相反」的推挤（Godot move_and_slide 的思路）：
        往右走只处理迎面撞上来的墙，往上升只处理头顶，往下降只处理脚下。
        同方向的推挤说明角色本来就已经嵌在地形里，硬推开会把人瞬移到墙的另一侧，
        或者把贴着墙面上升的角色「吸」到墙顶。

        P4：不再「碰到第一个就 return」。本轴所有来源（形状层 / 图像 / 图块 / 边界）
        的接触都会记录进 _contacts 掩码，然后只应用一个最合理的修正：
          - 有主动移动：取与运动方向相反、幅度最大的推挤（最近的阻挡面）
          - direction=0（传送兜底）：取幅度最小的推挤（最近边）
        """
        global _CURRENT_MAP, _MAP_MODEL

        # 禁用碰撞：完全不参与地形/边界阻挡（碰到检测仍按碰撞盒工作）
        if self._collision_disabled:
            return

        if not _CURRENT_MAP:
            return

        tile_size = _CURRENT_MAP.get("tile_size", 16)

        # 获取精灵的碰撞盒
        sprite_rect = self._get_hitbox_rect()
        if not sprite_rect:
            return

        # 本轴接触收集：delta 是最终要施加的位移，correction 只用于判断接触方向
        best_delta = None
        best_mag = 0.0
        best_effect = None
        encounter_mask = 0

        def consider(delta, correction_for_side, effect=None):
            nonlocal best_delta, best_mag, best_effect, encounter_mask
            if delta is None or abs(delta) < 1e-7:
                return
            # 接触掩码记录「实际碰到了哪一侧」，不受运动方向过滤影响
            encounter_mask |= self._contact_bit(axis, correction_for_side)
            if not self._accept_axis_correction(delta, direction):
                return
            magnitude = abs(delta)
            if best_delta is None:
                better = True
            elif direction == 0:
                better = magnitude < best_mag
            else:
                better = magnitude > best_mag
            if better:
                best_delta = delta
                best_mag = magnitude
                best_effect = effect

        # 检测所有图层中的实心图块
        for layer_index, layer in enumerate(_CURRENT_MAP.get("layers", [])):
            # --- 形状层（世界坐标判定形状） ---
            if layer.get("type") == "shape":
                correction = self._collision_layer_correction(layer, axis, layer_index)
                if correction is None:
                    continue
                # y 轴只处理迎面（落地/撞头），且抬升距离不能大得离谱
                if axis == "y" and abs(correction) > self._MAX_CONTACT_SNAP:
                    continue
                margin = 0.05 if correction > 0 else -0.05
                effect = None
                if axis == "y":
                    if correction < 0 and direction > 0:
                        effect = "ground"
                    elif correction > 0 and direction < 0:
                        effect = "ceiling"
                consider(correction + margin, correction, effect)
                continue

            # --- 图像图层碰撞检测（优先级高于瓦片碰撞） ---
            # 图像实例使用真实多边形碰撞：SAT 求最小穿透，再按移动轴取分量
            if layer.get("type") == "image" and "images" in layer:
                correction = self._image_collision_correction(layer, axis)
                if correction is None:
                    continue
                if axis == "y" and abs(correction) > self._MAX_CONTACT_SNAP:
                    continue
                margin = 0.05 if correction > 0 else -0.05
                effect = None
                if axis == "y":
                    if correction < 0 and direction > 0:
                        effect = "ground"
                    elif correction > 0 and direction < 0:
                        effect = "ceiling"
                consider(correction + margin, correction, effect)
                continue

            tiles = layer.get("tiles", {})

            # 计算精灵覆盖的图块范围
            # X 轴探测盒上下各缩进 1 像素：脚正好贴地/头正好贴天花板时不算横向碰撞，
            # 同时避免缩进过大导致「只压到墙边一条」时 x 轴看不见墙
            if axis == "x":
                check_rect = [
                    sprite_rect[0],
                    sprite_rect[1] + 1,
                    sprite_rect[2],
                    sprite_rect[3] - 1,
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
            if _MAP_MODEL:
                for tile_x in range(min_tile_x, max_tile_x + 1):
                    for tile_y in range(min_tile_y, max_tile_y + 1):
                        tile_pos = (tile_x, tile_y)
                        if tile_pos not in tiles:
                            continue
                        tile_id = tiles[tile_pos]
                        if tile_id <= 0:
                            continue
                        # 使用Tiled标准：通过firstgid范围查找瓦片集
                        tile_id_int = int(tile_id)
                        resource_index, tile_index = _find_tileset_for_gid(
                            tile_id_int, _CURRENT_MAP["tile_sets"]
                        )

                        # 获取图块碰撞状态
                        if not _MAP_MODEL.get_tile_collision(resource_index, tile_index):
                            continue
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
                            # 编辑器保存的是归一化坐标(0~1)，需乘以 tile_size 转为像素
                            world_points = [
                                (
                                    tile_x * tile_size + p[0] * tile_size,
                                    tile_y * tile_size + p[1] * tile_size,
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
                        if overlap_x <= 0 or overlap_y <= 0:
                            continue

                        if is_one_way and axis == "y":
                            if self._prev_bottom_y <= tile_top:
                                rect = self._get_hitbox_rect()
                                if rect:
                                    delta = tile_top - rect[3] - 0.05
                                    consider(delta, delta, "ground")
                            continue

                        if axis == "x":
                            # 台阶自动上台：站在地面时，抬升不超过 _MAX_STEP_UP 的台阶直接踩上去
                            step_up = sprite_rect[3] - tile_top
                            if self._on_ground and 0 < step_up <= self._MAX_STEP_UP:
                                self._y = tile_top - (sprite_rect[3] - self._y) - 0.05
                                # 抬脚后必须刷新碰撞盒，否则一排相邻台阶会被连续抬多次
                                sprite_rect = self._get_hitbox_rect() or sprite_rect
                                continue

                            dist_to_right = abs(sprite_rect[0] - tile_right)
                            dist_to_left = abs(sprite_rect[2] - tile_left)

                            if dist_to_right < dist_to_left:
                                correction = tile_right - sprite_rect[0] + 0.05
                            else:
                                correction = tile_left - sprite_rect[2] - 0.05
                            consider(correction, correction)

                        elif axis == "y":
                            rect = self._get_hitbox_rect()
                            if not rect:
                                continue

                            if direction > 0:
                                # 下落：脚原本在顶面之上才算落地。
                                # 从侧面蹭到墙/墙顶时这里直接跳过，交给 x 轴推出，
                                # 避免把正在上升的角色「吸」到墙顶并误判成着地
                                if self._prev_bottom_y > tile_top + 0.5:
                                    continue
                                delta = tile_top - rect[3] - 0.05
                                consider(delta, delta, "ground")
                            elif direction < 0:
                                # 上升：头原本在底面之下才算撞天花板。
                                # 从侧面蹭到墙时跳过，跳跃不会被墙角打断
                                if self._prev_top_y < tile_bottom - 0.5:
                                    continue
                                delta = tile_bottom - rect[1] + 0.05
                                consider(delta, delta, "ceiling")
                            else:
                                # 本步没有上下移动（兜底）：按最近边推出，但不判定落地
                                overlap_up = tile_bottom - rect[1]
                                overlap_down = rect[3] - tile_top
                                if overlap_up < overlap_down:
                                    delta = tile_bottom - rect[1] + 0.05
                                else:
                                    delta = tile_top - rect[3] - 0.05
                                consider(delta, delta)

        # 应用本轴最合理的唯一修正
        self._contacts |= encounter_mask
        if best_delta is not None:
            if axis == "x":
                self._x += best_delta
            else:
                self._y += best_delta
                # 向上推出 = 落到平台/地面；向下推出 = 撞到天花板。
                # direction == 0（本步没有上下移动，例如 move() 的水平移动）
                # 只做位置修正，不能判着地、更不能清零 vy，
                # 否则贴墙下落时每帧被顶一下，就会变成「挂在墙上慢慢下滑」。
                if best_effect == "ground":
                    self._on_ground = True
                    self._vy = 0
                elif best_effect == "ceiling":
                    self._vy = 0

        # 地图边界碰撞检测
        # 只有开启「边界碰撞」才把地图像素矩形当隐形墙钳制；
        # 关闭时保持自由移动，edge_bounce/is_touch_edge/is_out_side/
        # 子弹出界销毁等边界 API 才能正常工作
        if not _CURRENT_MAP.get("boundaryCollision", _CURRENT_MAP.get("gravity", False)):
            return

        bounds = _playable_bounds()
        rect = self._get_hitbox_rect() or sprite_rect
        if not rect:
            return

        # 检查地图边界（使用地图矩形，与边界碰撞/边界 API 同一套）
        if axis == "x":
            # 左边界
            if rect[0] < bounds["left"]:
                self._x += bounds["left"] - rect[0] + 0.05
                self._contacts |= self._CONTACT_LEFT
            # 右边界
            elif rect[2] > bounds["right"]:
                self._x += bounds["right"] - rect[2] - 0.05
                self._contacts |= self._CONTACT_RIGHT
        elif axis == "y":
            # 上边界
            if rect[1] < bounds["top"]:
                self._y += bounds["top"] - rect[1] + 0.05
                self._contacts |= self._CONTACT_UP
            # 下边界
            elif rect[3] > bounds["bottom"]:
                self._y += bounds["bottom"] - rect[3] - 0.05
                self._contacts |= self._CONTACT_DOWN

    def goto(self, x, y=None):
        """移到指定坐标；也接受标记引用或另一个角色（注册点对齐）

        w.goto(320, 240)                   # 用户坐标：左下角原点，y 向上为正
        w.goto(player.get_marker())        # 对准角色的「标记」
        w.goto(enemy)
        """
        if y is None:
            pos = _resolve_target_xy(x)
            if pos is None:
                print("[警告] goto 参数无效：需要 (x, y)、标记或角色")
                return
            # 标记/角色解析出来的是世界坐标，直接写入，避免二次翻转
            self._set_xy_world(pos[0], pos[1])
            return
        self.set_xy(x, y)

    def get_marker(self, name="标记"):
        """获取标记引用（.bsf 角色在编辑器「标记」图层标注的锚点）

        返回值可直接给 goto()/follow() 用，也可读 .x/.y（用户坐标：左下角原点，y 向上）：
            w.goto(player.get_marker())        # 第一个标记「标记」
            w.follow(player.get_marker('标记2'))
        """
        if not getattr(self, "_is_bsf", False):
            print("[警告] 标记仅 .bsf 角色支持（先在角色编辑器「标记」图层添加）")
            return None
        if self._marker_world_xy(name) is None:
            known = sorted((getattr(self, "_bsf_markers", None) or {}).keys())
            hint = ("已有标记: " + ", ".join(known)) if known else "该角色还没有标记"
            print(f"[警告] 角色没有名为 '{name}' 的标记（{hint}）")
            return None
        return _MarkerRef(self, name)

    def follow(self, target, flip=True):
        """持续跟随目标的位置（每帧自动更新，只跟位置不跟朝向）

        target = get_marker() 返回的标记引用，或另一个 Sprite：
            w.follow(player.get_marker())
            w.follow(enemy)
        默认继承目标的左右镜像（父翻面武器跟着翻，Godot 子节点观感）；
        鼠标瞄准类武器可关：w.follow(m, flip=False)。
        朝向/缩放仍可独立控制（如 w.look_at(mouse) 瞄准）；
        目标被删除时自动停止跟随。w.unfollow() 手动解除（保留脱离时的朝向）。
        """
        if isinstance(target, (_MarkerRef, Sprite)):
            self._follow_ref = target
            self._follow_flip_on = bool(flip)
            self._follow_flip = 1.0  # 下一帧 _update_follows 重算
        else:
            print("[警告] follow 参数无效：需要标记或角色")

    def unfollow(self):
        """停止跟随（保留脱离瞬间的朝向，不恢复为正向）"""
        self._follow_ref = None
        # 故意不重置 _follow_flip：它保存着最后一次继承来的镜像，
        # 留着才能让挂件停在脱离时的朝向；再次 follow() 会重新初始化

    # ---------- 坐标（用户空间：原点在地图左下角，y 向上为正） ----------
    def set_xy(self, x, y):
        """设置坐标（用户坐标：地图左下角为 (0,0)，y 向上为正）"""
        self._set_xy_world(to_world_x(x), to_world_y(y))

    def _set_xy_world(self, x, y):
        """按世界坐标传送（不做任何转换）。

        传送不是「移动」，没有运动方向：
          - 先记录旧的上下沿，保留单向平台原有的落点判断
          - 写入目标坐标后先 depenetrate，再按最近边兜底解算
        """
        hitbox = self._get_hitbox_rect()
        if hitbox:
            self._prev_bottom_y = hitbox[3]
            self._prev_top_y = hitbox[1]
        self._x = x
        self._y = y
        if not self._collision_disabled and _CURRENT_MAP:
            self._depenetrate()
            self._resolve_collision("x")
            self._resolve_collision("y")
        self._update_transform()

    def set_x(self, x):
        """设置 x 坐标（用户坐标：正数向右）"""
        target = to_world_x(x)
        self.move_and_slide(target - self._x, 0.0, axis_order="xy", resolve_y=False)
        self._update_transform()

    def set_y(self, y):
        """设置 y 坐标（用户坐标：正数向上）"""
        target = to_world_y(y)
        self.move_and_slide(0.0, target - self._y, axis_order="yx", resolve_x=False)
        self._update_transform()

    def add_x(self, delta_x):
        """将 x 坐标增加（或减少）一定数值（用户坐标：正数向右）"""
        dx = to_world_dx(delta_x)
        self.move_and_slide(dx, 0.0, axis_order="xy", resolve_y=False)
        self._update_transform()

    def add_y(self, delta_y):
        """将 y 坐标增加（或减少）一定数值（用户坐标：正数向上）"""
        dy = to_world_dy(delta_y)
        self.move_and_slide(0.0, dy, axis_order="yx", resolve_x=False)
        self._update_transform()

    def jump(self, power=10):
        """角色跳跃

        Args:
            power: 跳跃力度（默认10，越大跳得越高）
        """
        self._vy = -power
        self._on_ground = False
        self._jump_cut = False

    def stop_jump(self):
        """停止跳跃：角色正在上升时调用，停止继续上升并提前落下

        只在上升阶段生效（上升重力从 0.5 变为 2.8），自己不会让角色起跳；
        没有"松手"动作的场景（敌人 AI、撞天花板等）也能直接调用。
        """
        if self._vy < 0:
            self._jump_cut = True
        self._jump_buffered = False

    def cut_jump(self):
        """旧名字，保留兼容；等价于 stop_jump()"""
        self.stop_jump()

    def smart_jump(self, power=10):
        """大小跳：按下起跳，按住跳得高，松手就落下

        用法（必须写在 if key_down(...) 里面，每帧调用一次）：

            while True:
                if key_down("w"):
                    hero.smart_jump(12)

        引擎通过「本帧有没有被调用」判断按键状态：松开后这个函数不再被调用，
        引擎会自动帮你停止跳跃，所以不需要自己写 stop_jump。

        Args:
            power: 最大跳跃力度（默认 10，越大跳得越高）
        """
        self._smart_jump_called = True
        if not self._smart_jump_active and self._on_ground:
            # 刚按下且站在地面上：起跳
            self.jump(power)
            self._smart_jump_active = True
            # 记住本步刚按下的键：无论学生把 smart_jump 写在 if key_down 还是
            # if key_pressed 里，松手判断都按这个键的真实状态来，不会误截断
            newly = _PRESSED_KEYS_FRAME - _PRESSED_KEYS_PREV
            self._smart_jump_key = next(iter(newly), None)

    def drop_down(self):
        """从跳板掉下去：角色站在跳板上时调用，穿过脚下的跳板下落"""
        if self._on_ground:
            self._drop_through = True
            self._drop_through_timer = 10
            self._on_ground = False
            self._vy = 2

    def drop_through(self):
        """旧名字，保留兼容；等价于 drop_down()"""
        self.drop_down()

    def set_speed(self, speed):
        """设置持续速度，引擎每帧自动沿当前方向移动"""
        self._speed = speed

    def on_touch_group(self, group, callback=None):
        """碰到指定组的成员时自动处理（注册一次即可，引擎每帧自动检测）

        - 不传 callback：碰到后默认双方都删除
        - 传 callback：执行 callback(自己, 碰到的角色)，删不删由函数决定
        """
        self._on_hit_callbacks.append((group, callback))

    # 兼容旧项目代码，旧名不再出现在文档与补全中
    def on_hit(self, group, callback=None):
        return self.on_touch_group(group, callback)

    def on_sensor_enter(self, tag, callback):
        """进入某个感应形状时执行 callback(自己, 标签)（注册一次即可，引擎每帧自动检测）

        只有形状层里设成「感应」或「阻挡 + 感应」、并且填了同名标签的形状才会触发；
        同一个标签从无到有时只触发一次，站在里面不会每帧重复触发。
        """
        if not callable(callback):
            print("[提示] on_sensor_enter 需要传一个函数，例如：hero.on_sensor_enter(\"水\", 碰到水)")
            return
        self._sensor_enter_callbacks.append((tag, callback))

    def on_sensor_exit(self, tag, callback):
        """离开某个感应形状时执行 callback(自己, 标签)（每个标签只触发一次）"""
        if not callable(callback):
            print("[提示] on_sensor_exit 需要传一个函数，例如：hero.on_sensor_exit(\"水\", 离开水)")
            return
        self._sensor_exit_callbacks.append((tag, callback))

    def broadcast(self, event_name):
        """发送广播（触发所有接收该事件的回调；单个回调出错不会中断游戏）"""
        broadcast(event_name)

    def receive(self, event_name):
        """这一帧有没有收到指定广播（广播是全局的，写在哪个角色上结果一样）"""
        return receive(event_name)

    def on_receive(self, event_name, callback=None):
        """防误用提示：on_receive 是注册用的全局函数，不是角色的方法"""
        if not getattr(self, "_receive_hint_shown", False):
            print("[提示] on_receive 是全局函数，不是角色的方法。注册写法：on_receive(\"事件名\", 函数)，写在循环外面；只想检查有没有收到广播，用 if 角色.receive(\"事件名\")")
            self._receive_hint_shown = True
        return None

    def move(self, distance):
        """朝着当前 angle 方向移动 distance 像素"""
        radians = math.radians(self._angle)

        # 计算移动分量
        dx = distance * math.cos(radians)
        dy = distance * math.sin(radians)

        # 大位移的拆步与碰撞全部交给唯一入口 move_and_slide
        self.move_and_slide(dx, dy, axis_order="xy")

        # 更新变换
        self._update_transform()

    def goto_rand(self):
        """移到地图内的随机位置"""
        bounds = _playable_bounds()
        self._set_xy_world(
            random.randint(int(bounds["left"]), int(bounds["right"])),
            random.randint(int(bounds["top"]), int(bounds["bottom"])),
        )

    def set_angle(self, angle):
        """设置旋转角度（用户坐标：逆时针为正，0=右 90=上 180=左 270=下）"""
        self._angle = to_world_angle(angle)
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
            # 用目标的位置点（轴心）而不是旋转后包围盒中心：
            # 对方也在旋转时，包围盒中心会绕着它的轴心摆动，瞄准点会跟着抖
            tx, ty = target._x, target._y
        else:
            # 如果不是 mouse 也不是 Sprite，不执行旋转
            return

        # 2. 🚀 以自身旋转轴心为射线起点
        # 非 .bsf 角色：轴心 = 内容重心 = 世界坐标 (x, y)，与旧实现（包围盒中心）完全等价
        # .bsf 角色：轴心 = manifest pivot，而 pivot 可能明显偏离内容重心。
        # 此时若仍用「包围盒中心」作起点，该中心会随 angle 绕轴心旋转，形成
        # angle → 中心 → angle 的自反馈，近目标处相邻两帧角度来回跳变
        # （看起来像两个不同朝向的角色），故起点固定为不随旋转变化的轴心。
        sx, sy = self._x, self._y

        # 3. 计算坐标差并求角度
        dx = tx - sx
        dy = ty - sy

        # 目标几乎和自己的轴心重合时，方向没有意义：鼠标/对方在原地轻微一动，
        # atan2 结果就在 0° 和 180° 之间乱跳，画面看起来像疯狂抖动。
        # 此时保持上一帧的朝向，不再重新瞄准。
        if dx * dx + dy * dy < 0.25:
            return

        # 使用 atan2 计算弧度，再转换为角度
        radians = math.atan2(dy, dx)
        angle = math.degrees(radians)

        # 4. 应用角度（atan2 在世界空间算出，已是世界角度，直接写入避免二次翻转）
        self._angle = angle % 360
        self._update_transform()

    def edge_bounce(self):
        """基于 Hitbox 的精准反弹，自动识别地图边界"""
        bounds = _playable_bounds()

        STAGE_LEFT = bounds["left"]
        STAGE_TOP = bounds["top"]
        STAGE_RIGHT = bounds["right"]
        STAGE_BOTTOM = bounds["bottom"]
        rect = self._get_hitbox_rect()
        if not rect:
            return
        hit = False
        # move() 内的 _resolve_collision 会把越界精灵钳制回边界内 0.05px，
        # 所以不能只判 overflow——还要判"贴边"；方向判断避免沿边缘滑动时误触发
        EPS = 0.5
        cos_a = math.cos(math.radians(self._angle))
        sin_a = math.sin(math.radians(self._angle))

        # 左右判断
        if rect[2] >= STAGE_RIGHT - EPS and cos_a > 0:
            self._x -= rect[2] - STAGE_RIGHT
            self._angle = 180 - self._angle
            hit = True
        elif rect[0] <= STAGE_LEFT + EPS and cos_a < 0:
            self._x += STAGE_LEFT - rect[0]
            self._angle = 180 - self._angle
            hit = True

        # 上下判断
        if rect[3] >= STAGE_BOTTOM - EPS and sin_a > 0:
            self._y -= rect[3] - STAGE_BOTTOM
            self._angle = -self._angle
            hit = True
        elif rect[1] <= STAGE_TOP + EPS and sin_a < 0:
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

    def _apply_visible(self, visible):
        """设置可见状态并同步帧缓冲：本帧已排队的更新若仍带旧状态，
        会在 hide()/show() 之后才刷出，把角色又画出来，这里一并改写"""
        self._visible = visible
        for update in _FRAME_UPDATES:
            if update.get("id") == self.id:
                update["visible"] = visible
        self._send_command("UPDATE", {"id": self.id, "visible": visible})

    def show(self):
        """显示角色"""
        if self._is_deleted:
            return  # 已经删除的不能显示
        self._apply_visible(True)

    def hide(self):
        """隐藏角色（仅仅是看不见，物体还在内存里）"""
        self._apply_visible(False)

    def say(self, text, seconds=0):
        """
        让角色说话。新话会替换旧话。
        say("你好")      → 永久显示
        say("得分+1", 2) → 2秒后自动消失
        """
        self._send_command("SAY", {"text": str(text)})
        # 新气泡先取消旧的隐藏计时器，防止旧计时器提前隐藏新话
        _SAY_TIMERS.pop(self.id, None)
        if seconds > 0:
            def _hide():
                self._send_command("SAY", {"text": ""})
            timer = Timer(seconds, loop=False)
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
        # .bsf：优先按 clip 原始帧序列播放（支持非连续帧 / 重复帧）
        if getattr(self, "_is_bsf", False) and animation_name in getattr(self, "_bsf_clips", {}):
            clip = self._bsf_clips[animation_name]
            name_to_idx = {f.get("name"): i for i, f in enumerate(self._bsf_frames)}
            idxs = [name_to_idx[n] for n in clip.get("frames", []) if n in name_to_idx]
            if idxs:
                animation_config = {
                    "start": 1,
                    "end": len(idxs),
                    "fps": clip.get("fps", 10),
                    "loop": clip.get("loop", True),
                    "frame_indices": idxs,
                }
        if not animation_config and "segments" in self.config:
            for segment in self.config["segments"]:
                if segment.get("name") == animation_name:
                    animation_config = segment
                    break
        if not animation_config and "animations" in self.config:
            animation_config = self.config["animations"].get(animation_name)

        if not animation_config:
            # 排查友好：名字打错/片段缺失时不再静默失败，列出可用动画名
            if getattr(self, "_is_bsf", False):
                available = [c.get("name") for c in getattr(self, "_bsf_clips", {}).values()]
            else:
                available = [s.get("name") for s in (self.config.get("segments") or [])]
            print(f"[警告] 角色 '{self.config.get('name', '未知')}' 没有动画 '{animation_name}'，可用动画: {available}")
            return

        # 获取动画参数
        start = animation_config.get("start", 1)
        end = animation_config.get("end", 1)
        fps = animation_config.get("fps", 10)
        loop = animation_config.get("loop", True)
        frame_indices = animation_config.get("frame_indices")

        # 如果当前没有动画在播放，直接设置新动画
        if not hasattr(self, "animation_state") or not self.animation_state:
            self.animation_state = {
                "start": start - 1,
                "end": end - 1,
                "fps": fps,
                "loop": loop,
                "frame_indices": frame_indices,
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
            "frame_indices": frame_indices,
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
        精准边界检测：判定角色的实际视觉边缘是否接触或越过地图边界
        """
        # 1. 获取缩放和偏移后的真实包围盒 [left, top, right, bottom]
        rect = self._get_hitbox_rect()
        if not rect:
            return False

        # 2. 地图矩形边界（与物理钳制同一套边界，没有地图时退回 640×480 舞台）
        bounds = _playable_bounds()
        # 边界碰撞会把越界精灵拉回边界内 0.05px，
        # 只判 overflow 会永远 False——贴边（容差内）也算碰到
        EPS = 0.5

        # 3. 任何一边接触或超出地图边界，就返回 True
        if (
            rect[0] <= bounds["left"] + EPS  # 左边贴边/出界
            or rect[2] >= bounds["right"] - EPS  # 右边贴边/出界
            or rect[1] <= bounds["top"] + EPS  # 上边贴边/出界
            or rect[3] >= bounds["bottom"] - EPS  # 下边贴边/出界
        ):
            return True

        return False

    def is_out_side(self):
        """
        完全出界检测：只有当角色整体（所有像素）都离开地图边界时才返回 True
        """
        # 获取当前精准包围盒 [left, top, right, bottom]
        rect = self._get_hitbox_rect()
        if not rect:
            return False

        bounds = _playable_bounds()

        # 逻辑判断：
        # rect[2] < left: 右边缘比地图左边还要小（在左侧完全出界）
        # rect[0] > right: 左边缘比地图右边还要大（在右侧完全出界）
        # rect[3] < top: 下边缘比地图顶边还要小（在上方完全出界）
        # rect[1] > bottom: 上边缘比地图底边还要大（在下方完全出界）
        if (
            rect[2] < bounds["left"]
            or rect[0] > bounds["right"]
            or rect[3] < bounds["top"]
            or rect[1] > bounds["bottom"]
        ):
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
            # 用真实判定形状：胶囊/多边形的斜角区域不再误判为碰到
            return point_inside(self._get_collision_shape(), (mx, my))

        # 🚀 3. 如果目标是字符串，进行标签碰撞检测
        if isinstance(target, str):
            tag = target
            # 获取精灵的位置（世界坐标：内部逻辑不经过用户空间）
            sprite_x, sprite_y = self._x, self._y

            # 获取地图数据
            if _CURRENT_MAP:
                tile_size = _CURRENT_MAP.get("tile_size", 16)

                # 计算精灵包围盒覆盖的图块范围（按判定外扩量放大，
                # 避免贴着图块边缘停住时因皮肤间隙漏判该图块的标签）
                min_tile_x = math.floor((r1[0] - SENSOR_EPS) // tile_size)
                max_tile_x = math.floor((r1[2] + SENSOR_EPS) // tile_size)
                min_tile_y = math.floor((r1[1] - SENSOR_EPS) // tile_size)
                max_tile_y = math.floor((r1[3] + SENSOR_EPS) // tile_size)

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

                # 形状层：按真实多边形判定，不再用格子范围（tag 可挂在任意能力类型上）
                # P3：优先走烘焙好的 tag 查找表，避免每次 is_touch 全表扫描
                if tag:
                    static_world = _CURRENT_MAP.get("static_world")
                    if static_world is not None:
                        sprite_shape = self._get_collision_shape()
                        for entry in static_world.tag_entries(tag):
                            # 统一用外扩 SENSOR_EPS 的判定形状：贴着墙面/地面也算碰到
                            if intersects(sprite_shape, entry.probe_shape):
                                return True
                    else:
                        # 索引构建失败时的兼容路径：保持原全表扫描
                        for layer in _CURRENT_MAP.get("layers", []):
                            if layer.get("type") != "shape":
                                continue
                            for poly in layer.get("polygons", []):
                                if poly.get("disabled"):
                                    continue
                                if (poly.get("tag") or "") != tag:
                                    continue
                                points = poly.get("points") or []
                                if len(points) < 3:
                                    continue
                                for part in poly.get("parts") or [points]:
                                    if len(part) < 3:
                                        continue
                                    if _aabb_polygon_mtv(r1, part):
                                        return True
            return False

        # 🚀 4. 原有的 Sprite 间碰撞逻辑
        if target is None or not hasattr(target, "_visible") or not target._visible:
            return False
        if hasattr(target, "_is_deleted") and target._is_deleted:
            return False

        if not isinstance(target, Sprite):
            return False

        # 角色间碰撞使用真实判定形状（.bsf 胶囊/多边形不再降级 AABB）
        shape1 = self._get_collision_shape()
        shape2 = target._get_collision_shape()
        return shape_overlap(shape1, shape2) is not None

    def is_touch_group(self, group_name):
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

    # 兼容旧项目代码，旧名不再出现在文档与补全中
    def touch_group(self, group_name):
        return self.is_touch_group(group_name)

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
        计算当前角色到目标（Sprite 或 mouse）的像素距离

        用角色的位置点（.bgs = 内容重心，.bsf = 编辑器标注的轴心）来测距，
        与 goto()/look_at() 完全一致。不能用旋转后包围盒的中心：
        轴心标在脚底等位置时，包围盒中心会随旋转绕轴心摆动，
        角色明明已经站在鼠标上，距离却总是几十像素，导致判断失灵。
        """
        if self._is_deleted:
            return 999999

        # 🚀 1. 优先处理鼠标，因为它不是 Sprite 实例
        if target is mouse:
            dx = self._x - _MOUSE_STATE["x"]
            dy = self._y - _MOUSE_STATE["y"]
            return math.hypot(dx, dy)

        # 🚀 2. 处理其他 Sprite 角色
        if not isinstance(target, Sprite) or target._is_deleted:
            return 999999

        dx = self._x - target._x
        dy = self._y - target._y
        return math.hypot(dx, dy)

    # 前方阻挡探测距离（像素）：is_blocked 默认向前探这么远
    _BLOCK_PROBE = 2.0

    def is_blocked(self, direction="down", distance=None):
        """前方是否有实心地形阻挡（俯视迷宫常用）。

        direction: "left"/"right"/"up"/"down"（或 左/右/上/下），也接受用户角度数字
        distance: 探测距离，默认 2 像素；想查更远可以传更大值

        只查静态实心地形（形状层 solid/both、图像碰撞、实心图块），
        感应区域不算阻挡；跳板只有向下且从上方靠近时才算阻挡。

        用法：
            if not hero.is_blocked("right"):
                hero.add_x(4)
        """
        if self._is_deleted or self._collision_disabled or not _CURRENT_MAP:
            return False
        world_dir = _parse_direction_world(direction)
        if world_dir is None:
            return False
        probe = self._BLOCK_PROBE if distance is None else max(0.0, float(distance))
        if probe <= 0.0:
            return False

        rect = self._get_hitbox_rect()
        if not rect:
            return False
        dx = world_dir[0] * probe
        dy = world_dir[1] * probe

        static_world = _CURRENT_MAP.get("static_world")
        if static_world is not None:
            query_left = min(rect[0], rect[0] + dx)
            query_top = min(rect[1], rect[1] + dy)
            query_right = max(rect[2], rect[2] + dx)
            query_bottom = max(rect[3], rect[3] + dy)
            sprite_shape = self._get_collision_shape()
            for entry in static_world.solid.query_rect(
                query_left, query_top, query_right, query_bottom
            ):
                if entry.collision_type == "跳板":
                    # 跳板只在下落方向、且角色在平台上方时阻挡
                    if world_dir[1] <= 0 or self._drop_through:
                        continue
                    if rect[3] > entry.bbox.top + 0.5:
                        continue
                if shape_sweep(sprite_shape, entry.shape, (dx, dy)) is not None:
                    return True

        # 边界碰撞开启时，地图矩形也算阻挡
        if _CURRENT_MAP.get("boundaryCollision", _CURRENT_MAP.get("gravity", False)):
            bounds = _playable_bounds()
            if world_dir[0] < 0 and rect[0] + dx < bounds["left"]:
                return True
            if world_dir[0] > 0 and rect[2] + dx > bounds["right"]:
                return True
            if world_dir[1] < 0 and rect[1] + dy < bounds["top"]:
                return True
            if world_dir[1] > 0 and rect[3] + dy > bounds["bottom"]:
                return True
        return False

    def is_on_wall(self):
        """左右两侧是否贴着墙（基于本帧接触掩码）。"""
        if self._is_deleted:
            return False
        return bool(self._contacts & (self._CONTACT_LEFT | self._CONTACT_RIGHT))

    def is_on_ceiling(self):
        """头顶是否撞到实体地形（基于本帧接触掩码）。

        典型用法：跳跃撞到天花板时停止上升
            if hero.is_on_ceiling():
                hero.stop_jump()
        也从地图上边界（开启「限制边界」时）产生接触。
        """
        if self._is_deleted:
            return False
        return bool(self._contacts & self._CONTACT_UP)

    def is_on_ground(self):
        """是否站在地面上（由物理落地接触决定）

        只有角色真正落在有碰撞的地形上才返回 True：上升中、从下方穿过跳板、
        从平台侧面擦过都返回 False。与 jump()/smart_jump()/drop_down() 内部判定一致。
        """
        if self._is_deleted:
            return False
        return self._on_ground

    def is_on_floor(self):
        """旧名字，保留兼容；等价于 is_on_ground()"""
        return self.is_on_ground()

    # ----------- 属性赋值 ----------
    @property
    def x(self):
        """水平位置（用户坐标：正数向右）"""
        return to_user_x(self._x)

    @x.setter
    def x(self, value):
        self.set_x(value)

    @property
    def y(self):
        """垂直位置（用户坐标：正数向上）"""
        return to_user_y(self._y)

    @y.setter
    def y(self, value):
        self.set_y(value)

    @property
    def pos(self):
        """一次性获取角色坐标 (x, y)，可直接拆包：x, y = hero.pos（只读）"""
        return self.x, self.y

    @property
    def vy(self):
        """垂直速度（用户坐标：正数向上，负数向下）"""
        return to_user_dy(self._vy)

    @vy.setter
    def vy(self, value):
        self._vy = to_world_dy(value)

    @property
    def gravity(self):
        """是否受地图重力影响（默认 True）。设为 False 后不下坠，撞墙/落地等碰撞照常"""
        return self._gravity

    @gravity.setter
    def gravity(self, value):
        self._gravity = bool(value)

    @property
    def angle(self):
        """朝向角度（用户坐标：逆时针为正）"""
        return to_user_angle(self._angle)

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
        """内部尝试读取角色文件夹下的 config.json（.bgs）或 manifest.json（.bsf）。

        兼容带扩展名的引用：`Sprite("角色1.png")` 而角色已转正为 `角色1/` 目录
        （编辑器给单图角色加中心点/碰撞/挂点时会把 png 升级成 .bsf 目录）。
        """
        stem_dir = os.path.splitext(self.sprite_dir)[0]
        candidates = [self.sprite_dir] if stem_dir == self.sprite_dir else [self.sprite_dir, stem_dir]
        for sprite_dir in candidates:
            if not sprite_dir:
                continue
            # 先切到候选目录：_normalize_bsf_manifest 用 self.sprite_dir 定位 sheet.png
            prev_dir = self.sprite_dir
            self.sprite_dir = sprite_dir
            config = self._load_config_in_dir(sprite_dir)
            if config:
                return config
            self.sprite_dir = prev_dir
        return None

    def _load_config_in_dir(self, sprite_dir):
        """读取指定目录下的 config.json（.bgs）或 manifest.json（.bsf）"""
        config_path = os.path.join(sprite_dir, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[警告] 读取角色配置 {config_path} 失败: {e}")

        # .bsf 解压目录：sheet 图集格式（manifest.json + sheet.png）
        manifest_path = os.path.join(sprite_dir, "manifest.json")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                frames = manifest.get("frames")
                if manifest.get("format") == "bsf" and isinstance(frames, list) and frames:
                    return self._normalize_bsf_manifest(manifest)
                print(f"[警告] manifest.json 不是合法的 .bsf v2 文件: {manifest_path}")
            except Exception as e:
                print(f"[警告] 读取角色 manifest {manifest_path} 失败: {e}")
        return None

    def _normalize_bsf_manifest(self, manifest):
        """把 .bsf manifest 规范化为引擎内部 config，同时缓存 BSF 专用字段。

        返回的 config 保持旧字段兼容：
        - frames: 帧名列表（旧代码按文件名拼路径的分支对 BSF 不生效，走 _is_bsf 分支）
        - segments: 由 clips 合成的近似连续区间（兜底；play() 优先走原始 clip 帧序列）
        """
        self._is_bsf = True
        self._bsf_manifest = manifest
        self._bsf_frames = manifest["frames"]
        canvas = manifest.get("canvas") or {}
        self._bsf_pivot = manifest.get("pivot") or {
            "x": (canvas.get("w") or 0) / 2.0,
            "y": (canvas.get("h") or 0) / 2.0,
        }
        # 自定义碰撞形状（可选）：无/非法 = 自动碰撞（内容包围盒）
        self._bsf_collision = manifest.get("collision")
        # 禁用碰撞（可选）：True = 该角色不参与地形/边界物理阻挡，仍可被碰到检测
        self._collision_disabled = bool(
            manifest.get("collisionDisabled", manifest.get("collision_disabled", False))
        )
        # 受重力影响（可选）：False = 重力地图里也不下坠，撞墙/落地等碰撞照常
        self._gravity = bool(manifest.get("gravity", True))
        # 挂点（可选）：名字 → {x, y}（画布坐标）；帧级覆盖在 frames[i].markers
        self._bsf_markers = manifest.get("markers") or {}
        self._bsf_clips = {
            c.get("name"): c
            for c in manifest.get("clips", [])
            if isinstance(c, dict) and c.get("name")
        }
        self._bsf_frame_index = 0
        # 默认渲染帧（编辑器选中帧持久化字段 defaultFrame）：无效/缺省回退第一帧
        default_frame = manifest.get("defaultFrame")
        if isinstance(default_frame, str):
            for i, f in enumerate(self._bsf_frames):
                if f.get("name") == default_frame:
                    self._bsf_frame_index = i
                    break
        elif isinstance(default_frame, int) and 0 <= default_frame < len(self._bsf_frames):
            self._bsf_frame_index = default_frame
        self._bsf_sheet = os.path.join(
            self.sprite_dir, manifest.get("sheet") or "sheet.png"
        )

        name_to_idx = {f.get("name"): i for i, f in enumerate(self._bsf_frames)}
        segments = []
        for clip in manifest.get("clips", []):
            if not isinstance(clip, dict):
                continue
            idxs = [name_to_idx[n] for n in clip.get("frames", []) if n in name_to_idx]
            if not idxs:
                continue
            segments.append({
                "name": clip.get("name"),
                "start": min(idxs) + 1,
                "end": max(idxs) + 1,
                "fps": clip.get("fps", 10),
                "loop": clip.get("loop", True),
            })

        return {
            "name": manifest.get("name") or os.path.basename(self.sprite_dir),
            "frames": [
                f.get("name") or "frame_%03d" % (i + 1)
                for i, f in enumerate(self._bsf_frames)
            ],
            "segments": segments,
            "bsf": True,
        }

    def _bsf_frame_rect(self, index=None):
        """当前（或指定）帧在 sheet.png 中的 UV 区域 [x, y, w, h]"""
        idx = self._bsf_frame_index if index is None else index
        rect = self._bsf_frames[idx]["rect"]
        return [rect["x"], rect["y"], rect["w"], rect["h"]]

    def _marker_world_xy(self, name):
        """挂点画布坐标 → 世界坐标（应用父的旋转/缩放/镜像）；不存在返回 None。

        与 _update_transform 同一显示语义：left_right 镜像走 scale_x、
        display_angle 在 none/left_right 下为 0；帧级覆盖 frames[i].markers 优先。
        """
        if not getattr(self, "_is_bsf", False) or self._is_deleted:
            return None
        idx = getattr(self, "_bsf_frame_index", 0)
        frame = self._bsf_frames[idx] if 0 <= idx < len(self._bsf_frames) else {}
        m = None
        if isinstance(frame, dict):
            m = (frame.get("markers") or {}).get(name)
        if m is None:
            m = (getattr(self, "_bsf_markers", None) or {}).get(name)
        if not isinstance(m, dict) or "x" not in m or "y" not in m:
            return None
        pivot = frame.get("pivot") or self._bsf_pivot
        try:
            dx = float(m["x"]) - float(pivot["x"])
            dy = float(m["y"]) - float(pivot["y"])
        except (TypeError, ValueError):
            return None
        # 显示缩放/镜像（与 _update_transform 一致；_display_flip 含跟随继承）
        base_scale = self._scale / 100.0
        sx = base_scale * getattr(self, "_display_flip", self._current_scale_x)
        sy = base_scale
        style = self._rotation_style
        if style == "left_right":
            display_angle = 0.0
        elif style == "none":
            display_angle = 0.0
            sx = base_scale
        else:
            display_angle = float(self._angle)
        rad = math.radians(display_angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        # 局部 → 缩放/镜像 → 旋转 → 平移（PixiJS 变换顺序）
        wx = self._x + dx * sx * cos_a - dy * sy * sin_a
        wy = self._y + dx * sx * sin_a + dy * sy * cos_a
        return (wx, wy)

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
        if getattr(self, "_is_bsf", False):
            return self._setup_hitbox_bsf()

        if hasattr(self, "_content_w") and self._cached_image == self.image:
            return self._cached_hitbox

        info = _image_bbox_info(self.image)
        if info is None:
            self._content_w = self._content_h = 50
            self._visual_offset_x = self._visual_offset_y = 0
            self._orig_w = self._orig_h = 50
            self._content_bbox = (0, 0, 50, 50)
            self._cached_hitbox = [0, 0, 50, 50]
            self._cached_image = self.image
        else:
            (self._orig_w, self._orig_h, self._content_bbox,
             self._content_w, self._content_h,
             self._visual_offset_x, self._visual_offset_y) = info
            self._cached_hitbox = [0, 0, self._content_w, self._content_h]
            self._cached_image = self.image

        return self._cached_hitbox

    def _setup_hitbox_bsf(self):
        """.bsf 帧定位：直接用 manifest 的 rect/offset/pivot 计算，无需读像素（O(1)）。

        坐标语义（与旧 .bgs 的"内容重心=x/y"对齐）：
        - 引擎 (x, y) = manifest.pivot（角色所在点，见 bsf-api §4）
        - 纹理 = 帧 rect（紧致裁剪），vox/voy = pivot 相对帧纹理中心的偏移
        - 自定义碰撞（manifest collision，画布坐标）存在时覆盖 _content_bbox，
          缺省回退帧内容框（= 自动碰撞）；胶囊/多边形同时记录真实顶点，
          运行时由 _get_collision_shape 用 Shape 内核按真实轮廓判定
        """
        idx = getattr(self, "_bsf_frame_index", 0)
        if (
            hasattr(self, "_content_w")
            and getattr(self, "_cached_bsf_frame", None) == idx
            and self._cached_image == self.image
        ):
            return self._cached_hitbox

        frame = self._bsf_frames[idx]
        rect = frame["rect"]
        offset = frame.get("offset") or {"x": 0, "y": 0}
        # 帧级 pivot 覆盖优先（编辑器「仅当前帧」修改），缺省回退 manifest 统一值
        pivot = frame.get("pivot") or self._bsf_pivot
        rw, rh = rect["w"], rect["h"]

        # 前端 anchor=0.5：纹理坐标系下 (0,0)-(rw,rh) 即当前帧内容
        self._orig_w, self._orig_h = rw, rh
        self._content_w, self._content_h = rw, rh
        # pivot 落在世界 (x, y) ⇒ pivot 相对纹理中心的偏移即 PixiJS pivot
        self._visual_offset_x = pivot["x"] - (offset["x"] + rw / 2.0)
        self._visual_offset_y = pivot["y"] - (offset["y"] + rh / 2.0)
        # 碰撞框：自定义形状（帧覆盖 > 统一值）优先，否则帧内容框（自动碰撞）
        collision = frame.get("collision") or getattr(self, "_bsf_collision", None)
        bbox = self._collision_canvas_bbox(collision)
        if bbox is None:
            self._content_bbox = (0, 0, rw, rh)
            self._local_collision_points = None
        else:
            x0, y0, x1, y1 = bbox
            self._content_bbox = (
                x0 - offset["x"], y0 - offset["y"],
                x1 - offset["x"], y1 - offset["y"],
            )
            # 真正的判定形状顶点（画布坐标 → 帧图片局部坐标），供 Shape 内核使用
            canvas_points = self._collision_canvas_points(collision)
            if canvas_points:
                self._local_collision_points = tuple(
                    (px - offset["x"], py - offset["y"]) for px, py in canvas_points
                )
            else:
                self._local_collision_points = None

        self._cached_hitbox = [0, 0, rw, rh]
        self._cached_image = self.image
        self._cached_bsf_frame = idx
        # 帧切换后让 _get_hitbox_rect 的帧级缓存失效
        # （_get_collision_shape 的缓存键已含帧号与 bsf 帧索引，无需额外清理）
        self._cached_rect_frame = None
        return self._cached_hitbox

    def _collision_canvas_points(self, collision):
        """自定义碰撞形状 → 画布坐标顶点列表；无有效形状返回 None。

        rect:    四个角
        capsule: 竖直胶囊采样成多边形（Godot CapsuleShape2D 语义）
        polygon: 原始点集
        """
        if not isinstance(collision, dict):
            return None
        ctype = collision.get("type")
        try:
            if ctype == "rect":
                cx, cy = float(collision.get("cx", 0)), float(collision.get("cy", 0))
                w = max(1.0, float(collision.get("w", 1)))
                h = max(1.0, float(collision.get("h", 1)))
                return [
                    (cx - w / 2.0, cy - h / 2.0),
                    (cx + w / 2.0, cy - h / 2.0),
                    (cx + w / 2.0, cy + h / 2.0),
                    (cx - w / 2.0, cy + h / 2.0),
                ]
            if ctype == "capsule":
                cx, cy = float(collision.get("cx", 0)), float(collision.get("cy", 0))
                r = max(0.5, float(collision.get("radius", 1)))
                total_h = max(2.0 * r, float(collision.get("height", 2.0 * r)))
                half_seg = max(0.0, total_h / 2.0 - r)
                capsule = capsule_shape((cx, cy - half_seg), (cx, cy + half_seg), r, 8)
                return list(capsule.points)
            if ctype == "polygon":
                pts = []
                for p in collision.get("points") or []:
                    if isinstance(p, (list, tuple)) and len(p) >= 2:
                        pts.append((float(p[0]), float(p[1])))
                return pts if len(pts) >= 3 else None
        except (TypeError, ValueError):
            return None
        return None

    def _collision_canvas_bbox(self, collision):
        """自定义碰撞形状 → 画布坐标系 AABB (x0, y0, x1, y1)；无有效形状返回 None。

        rect: 中心+尺寸（Godot RectangleShape2D 语义）
        capsule: 竖直取向，height 含两端圆帽总高（Godot CapsuleShape2D 语义）→ 外接矩形
        polygon: 点集范围（与地图碰撞编辑器运行时降级为 AABB 的先例一致）
        """
        if not isinstance(collision, dict):
            return None
        ctype = collision.get("type")
        try:
            if ctype == "rect":
                cx, cy = float(collision.get("cx", 0)), float(collision.get("cy", 0))
                w = max(1.0, float(collision.get("w", 1)))
                h = max(1.0, float(collision.get("h", 1)))
                return (cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0)
            if ctype == "capsule":
                cx, cy = float(collision.get("cx", 0)), float(collision.get("cy", 0))
                r = max(0.5, float(collision.get("radius", 1)))
                total_h = max(2.0 * r, float(collision.get("height", 2.0 * r)))
                return (cx - r, cy - total_h / 2.0, cx + r, cy + total_h / 2.0)
            if ctype == "polygon":
                pts = collision.get("points") or []
                xs, ys = [], []
                for p in pts:
                    if isinstance(p, (list, tuple)) and len(p) >= 2:
                        xs.append(float(p[0]))
                        ys.append(float(p[1]))
                if len(xs) >= 3:
                    return (min(xs), min(ys), max(xs), max(ys))
        except (TypeError, ValueError):
            return None
        return None

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

        # 帧级缓存：同一帧内位置/旋转不变时复用结果
        if hasattr(self, "_cached_rect_frame") and self._cached_rect_frame == _PERF_STATS["frame_count"]:
            if (abs(self._cached_rect_x - self._x) < 0.01 and
                abs(self._cached_rect_y - self._y) < 0.01 and
                self._cached_rect_scale == self._scale and
                getattr(self, "_cached_rect_flip", 1) == getattr(self, "_display_flip", getattr(self, "_current_scale_x", 1)) and
                getattr(self, "_cached_rect_angle", 0) == getattr(self, "_angle", 0)):
                return self._cached_rect

        s = self._scale / 100.0
        # 显示镜像倍率（含跟随继承；非跟随者等于 _current_scale_x）
        flip_x = getattr(self, "_display_flip", getattr(self, "_current_scale_x", 1))

        # 有效旋转角度：与 _update_transform 逻辑一致
        rot_style = getattr(self, "_rotation_style", "all around")
        if rot_style == "left_right" or rot_style == "none":
            effective_angle = 0  # 这两种风格不产生实际旋转，镜像由 flip_x 处理
        else:
            effective_angle = self._angle

        img_w, img_h = self._orig_w, self._orig_h
        center_x, center_y = self._x, self._y

        # 内容重心相对图片中心的偏移（与前端 PixiJS pivot 一致）
        vox = getattr(self, "_visual_offset_x", 0.0)
        voy = getattr(self, "_visual_offset_y", 0.0)

        # PixiJS 变换管线：world = position + R(angle) × S(scale) × (local − pivot)
        # local 相对图片中心（anchor=0.5），scale 含翻转（scaleX=s×flip, scaleY=s）
        rad = math.radians(effective_angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)

        corners = [
            (bbox[0], bbox[1]), (bbox[2], bbox[1]),
            (bbox[2], bbox[3]), (bbox[0], bbox[3]),
        ]

        world_xs, world_ys = [], []
        for bx, by in corners:
            # local 相对图片中心
            lx = bx - img_w / 2.0
            ly = by - img_h / 2.0
            # 减去 pivot（内容重心）
            px = lx - vox
            py = ly - voy
            # 缩放（含水平翻转）
            sx = px * s * flip_x
            sy = py * s
            # 旋转
            rx = sx * cos_a - sy * sin_a
            ry = sx * sin_a + sy * cos_a
            # 平移到世界坐标
            world_xs.append(center_x + rx)
            world_ys.append(center_y + ry)

        rect = [min(world_xs), min(world_ys), max(world_xs), max(world_ys)]

        # 更新帧级缓存
        self._cached_rect = rect
        self._cached_rect_frame = _PERF_STATS["frame_count"]
        self._cached_rect_x = self._x
        self._cached_rect_y = self._y
        self._cached_rect_scale = self._scale
        self._cached_rect_flip = flip_x
        self._cached_rect_angle = effective_angle

        return rect

    def _get_collision_shape(self):
        """当前角色的真实判定形状（世界坐标，Shape 内核对象）。

        与渲染解耦：
          - .bsf 有 manifest collision（rect / capsule / polygon）时用真实顶点
          - 没有自定义碰撞时用帧内容框（自动碰撞）
          - 普通图片用非透明内容框
        形状随位置/缩放/翻转/旋转一起烘焙，不再降级成世界 AABB。
        """
        self._setup_hitbox()

        # 局部顶点：优先自定义碰撞，否则内容框
        points = None
        if getattr(self, "_is_bsf", False) and getattr(self, "_local_collision_points", None):
            points = tuple(self._local_collision_points)
        elif hasattr(self, "_content_bbox") and self._content_bbox:
            b = self._content_bbox
            points = ((b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3]))

        if not points or len(points) < 3:
            rect = self._get_hitbox_rect()
            if not rect:
                # 没有内容框（空图片等极端情况）：给一个零尺寸形状，避免崩溃/误判
                return aabb_shape(self._x, self._y, self._x, self._y)
            return aabb_shape(rect[0], rect[1], rect[2], rect[3])

        s = self._scale / 100.0
        flip_x = getattr(self, "_display_flip", getattr(self, "_current_scale_x", 1))
        rot_style = getattr(self, "_rotation_style", "all around")
        if rot_style == "left_right" or rot_style == "none":
            effective_angle = 0
        else:
            effective_angle = self._angle

        # 帧级缓存：位置/形态不变时复用
        cache_key = (
            _PERF_STATS["frame_count"],
            getattr(self, "_bsf_frame_index", 0),
            self.image,
        )
        if (
            getattr(self, "_cached_shape", None) is not None
            and getattr(self, "_cached_shape_key", None) == cache_key
            and abs(self._cached_shape_x - self._x) < 0.01
            and abs(self._cached_shape_y - self._y) < 0.01
            and self._cached_shape_scale == self._scale
            and getattr(self, "_cached_shape_flip", 1) == flip_x
            and getattr(self, "_cached_shape_angle", 0) == effective_angle
        ):
            return self._cached_shape

        img_w, img_h = self._orig_w, self._orig_h
        vox = getattr(self, "_visual_offset_x", 0.0)
        voy = getattr(self, "_visual_offset_y", 0.0)
        rad = math.radians(effective_angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)

        world_points = []
        for bx, by in points:
            lx = bx - img_w / 2.0
            ly = by - img_h / 2.0
            px = lx - vox
            py = ly - voy
            sx = px * s * flip_x
            sy = py * s
            rx = sx * cos_a - sy * sin_a
            ry = sx * sin_a + sy * cos_a
            world_points.append((self._x + rx, self._y + ry))

        try:
            shape = polygon_shape(world_points)
        except (ValueError, TypeError):
            rect = self._get_hitbox_rect()
            shape = (aabb_shape(rect[0], rect[1], rect[2], rect[3]) if rect
                     else aabb_shape(self._x, self._y, self._x, self._y))

        self._cached_shape = shape
        self._cached_shape_key = cache_key
        self._cached_shape_x = self._x
        self._cached_shape_y = self._y
        self._cached_shape_scale = self._scale
        self._cached_shape_flip = flip_x
        self._cached_shape_angle = effective_angle
        return shape

    def _update_transform(self):
        """统一处理旋转、缩放和镜像逻辑"""
        display_angle = self._angle
        # 计算基础缩放比例（百分比转为小数）
        base_scale = self._scale / 100.0

        # 默认情况下，Y轴只受 size 影响
        final_scale_y = base_scale
        # X轴受 size、自身镜像状态、跟随镜像继承共同影响（Godot 子节点语义）
        final_scale_x = base_scale * self._current_scale_x * self._follow_flip

        if self._rotation_style == "left_right":
            norm_angle = self._angle % 360
            if 90 < norm_angle < 270:
                self._current_scale_x = -1.0
            elif (0 <= norm_angle < 90) or (270 < norm_angle <= 360):
                self._current_scale_x = 1.0

            # 重新计算镜像后的 X 缩放（含跟随继承）
            final_scale_x = base_scale * self._current_scale_x * self._follow_flip
            display_angle = 0

        elif self._rotation_style == "none":
            display_angle = 0
            # "none" = 永不旋转永不翻转（含跟随继承），Scratch「不旋转」语义
            final_scale_x = base_scale

        # 本帧显示镜像倍率：供挂点世界坐标求值与链式跟随读取
        self._display_flip = final_scale_x / base_scale if base_scale else 1.0

        # 🚀 缓存比对：如果上次发送值相同，跳过发送以减少管道压力
        current_key = (
            round(self._x, 1), round(self._y, 1), round(display_angle, 1),
            round(base_scale, 4), round(final_scale_x, 4), round(final_scale_y, 4),
            self._visible, self._layer, self._show_hitbox,
            os.path.abspath(self.image) if hasattr(self, "image") and self.image else None,
            # .bsf 路径不变，帧切换必须进入缓存键否则动画不下发
            getattr(self, "_bsf_frame_index", None) if getattr(self, "_is_bsf", False) else None,
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
            # 层级必须随每帧更新一起下发，否则学生会看到 layer 被默认值覆盖
            "layer": self._layer,
            # 可见状态必须随每帧更新下发：批量更新里缺省 visible 会被前端默认成 True，
            # 导致 hide() 之后角色视觉上又冒出来（但引擎内部仍隐藏、碰撞检测不到）
            "visible": self._visible,
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

        # .bsf：帧切换携带新的 UV 区域（image 始终是 sheet.png）
        if getattr(self, "_is_bsf", False) and getattr(self, "_bsf_frames", None):
            update_data["frame_rect"] = self._bsf_frame_rect()

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

        # .bsf：clip 内序号映射到 sheet 帧索引，只切 UV 区域不换文件
        if getattr(self, "_is_bsf", False) and self._bsf_frames:
            indices = self.animation_state.get("frame_indices")
            if indices and 0 <= current_frame < len(indices):
                frame_idx = indices[current_frame]
            else:
                frame_idx = max(0, min(current_frame, len(self._bsf_frames) - 1))
            if frame_idx != getattr(self, "_bsf_frame_index", 0):
                self._bsf_frame_index = frame_idx
                self._setup_hitbox()  # 重新计算当前帧的 vox/voy（O(1)，来自 manifest）
                self._update_transform()
            return

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
                # 只有确实按下过的键才算松开，避免启动前的多余松开事件触发 key_up
                if key in _PRESSED_KEYS:
                    _RELEASED_KEYS.add(key)
                _PRESSED_KEYS.discard(key)

                # 🚀 新增鼠标事件处理
            elif clean_line.startswith("M_DOWN:"):
                old_value = _MOUSE_STATE["down"]
                _MOUSE_STATE["down"] = True

            elif clean_line.startswith("M_UP:"):
                old_value = _MOUSE_STATE["down"]
                _MOUSE_STATE["down"] = False
                # 只有确实按下过的才算松开，避免启动前的多余松开事件触发 mouse_up
                if old_value:
                    _MOUSE_STATE["released"] = True

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
                    sprite._last_update_key = None
            elif clean_line == "SHOW_COLLISION:0":
                _SHOW_ALL_COLLISION = False
                for sprite in _SPRITES.values():
                    sprite._show_hitbox = False
                    sprite._last_update_key = None
            else:
                # 不是控制命令 → 投喂给用户代码的 input()
                _USER_INPUT_QUEUE.put(clean_line)
        except:
            time.sleep(0.01)


# 确保线程启动 (代码末尾)
threading.Thread(target=_input_sync_listener, daemon=True).start()


def _custom_input(prompt=""):
    """替代内置 input()，从 _USER_INPUT_QUEUE 读取，不跟 stdin 监听线程抢数据。"""
    import sys
    try:
        # 提示文字不加换行，光标停在同一行（与代码模式一致）
        sys.stdout.write(prompt + "__BINGO_WAITING_INPUT__\n")
        sys.stdout.flush()
        return _USER_INPUT_QUEUE.get(timeout=300)
    except EOFError:
        # Windows 上 taskkill /F 强制终止进程时，stdin 管道关闭会触发 EOFError
        return ""
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


def mouse_up():
    """单次检测：只有在松开鼠标左键的那一帧返回 True"""
    return _MOUSE_STATE["released_frame"]


def key_down(key):
    """供用户调用：if key_down('a')"""
    return str(key).lower() in _PRESSED_KEYS_FRAME


def key_pressed(key):
    """只有按下的那一帧返回 True"""
    k = str(key).lower()
    return k in _PRESSED_KEYS_FRAME and k not in _PRESSED_KEYS_PREV


def key_up(key):
    """只有松开的那一帧返回 True"""
    return str(key).lower() in _RELEASED_FRAME


def _sync_input_frame():
    """物理步开始前同步输入状态快照

    输入线程是异步改 _PRESSED_KEYS / _RELEASED_KEYS 的，这里统一快照一份给本步的
    学生代码，保证 key_down / key_pressed / key_up 三个 API 看到的是同一时刻的状态
    """
    _PRESSED_KEYS_PREV.clear()
    _PRESSED_KEYS_PREV.update(_PRESSED_KEYS_FRAME)
    _PRESSED_KEYS_FRAME.clear()
    _PRESSED_KEYS_FRAME.update(_PRESSED_KEYS)
    _RELEASED_FRAME.clear()
    _RELEASED_FRAME.update(_RELEASED_KEYS)
    _RELEASED_KEYS.clear()

    # 鼠标松开同样用「事件累积 + 本步快照」，避免异步事件落在两步之间被漏掉
    _MOUSE_STATE["released_frame"] = _MOUSE_STATE["released"]
    _MOUSE_STATE["released"] = False


def _time_passed_impl(seconds, frame):
    key = (id(frame.f_code), frame.f_lineno)
    now = _GAME_TIME
    last = _WAIT_TIMERS.get(key)
    if last is None:
        _WAIT_TIMERS[key] = now
        return False
    if now - last >= seconds:
        _WAIT_TIMERS[key] = now
        return True
    return False


def time_passed(seconds):
    """每个调用位置独立计时：经过 N 秒后第一次返回 True，之后每隔 N 秒返回一次"""
    return _time_passed_impl(seconds, sys._getframe(1))


def wait(seconds):
    """旧名字，保留兼容；等价于 time_passed(seconds)"""
    return _time_passed_impl(seconds, sys._getframe(1))


def _promote_event_frame():
    """物理步开始：把上一步发出的广播提升为本步可见"""
    _EVENT_ACTIVE.clear()
    _EVENT_ACTIVE.update(_EVENT_PENDING)
    _EVENT_PENDING.clear()


def broadcast(event_name):
    """发送全局广播（单个回调出错不会中断游戏主循环）"""
    # 登记给 receive() 轮询：下一物理步可见，持续一帧
    _EVENT_PENDING.add(event_name)
    for callback in list(_EVENT_LISTENERS.get(event_name, [])):
        try:
            callback()
        except GameStop:
            raise
        except Exception as e:
            print(f"[错误] 广播「{event_name}」的处理函数出错: {e}")


def receive(event_name):
    """这一帧有没有收到指定广播（广播发出后的下一帧返回一次 True）"""
    return event_name in _EVENT_ACTIVE


def on_receive(event_name, callback):
    """当收到指定的广播时，执行 callback（Scratch「当接收到」帽子积木同款）"""
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


def random_float(min_val=0.0, max_val=1.0, decimals=2):
    """在 min_val 和 max_val 之间取随机浮点数

    Args:
        decimals: 保留小数位数，默认 2 位（对中小学生更友好）；传 None 返回完整精度
    """
    value = random.uniform(float(min_val), float(max_val))
    return value if decimals is None else round(value, decimals)


def shake(intensity=5, duration=0.3):
    """屏幕震动效果"""
    packet = {
        "type": "SCREEN_SHAKE",
        "data": {"intensity": intensity, "duration": duration},
    }
    print(json.dumps(packet))


def _resolve_sound_path(sound_name):
    """在项目 assets/sounds 下查找音效，返回绝对路径；找不到返回 None"""
    if not sound_name:
        return None
    # 允许直接传绝对路径或带路径的文件名
    if os.path.exists(sound_name):
        return os.path.abspath(sound_name)

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
    return os.path.abspath(sound_path) if sound_path else None


_SOUND_WARNED = set()


def stop_sound(sound_name=None):
    """停止音效。不传参数则停止所有音效。"""
    sound = _resolve_sound_path(sound_name) or sound_name
    packet = {
        "type": "STOP_SOUND",
        "data": {"sound": sound} if sound else {},
    }
    print(json.dumps(packet))


def show_text(x, y, *args):
    """在屏幕指定位置显示文字，参数自动拼接为字符串
    show_text(100, 50, "分数:", score)
    """
    text = "".join(str(a) for a in args)
    packet = {
        "type": "DRAW_TEXT",
        "data": {"id": f"text_{x}_{y}", "text": text, "x": x, "y": y},
    }
    print(json.dumps(packet))


def play_sound(sound_name, loop=False):
    sound_path = _resolve_sound_path(sound_name)
    if not sound_path:
        # 只提示一次，避免循环里每帧刷屏
        if sound_name not in _SOUND_WARNED:
            _SOUND_WARNED.add(sound_name)
            print(f"[提示] 找不到音效 '{sound_name}'，请先在资源管理器中导入音效")
        return
    packet = {
        "type": "PLAY_SOUND",
        "data": {
            # 前端 convertFileSrc 需要绝对路径
            "sound": sound_path,
            "loop": loop,
        },
    }
    print(json.dumps(packet))


def show_collision(sprite):
    if isinstance(sprite, Sprite):
        sprite._show_hitbox = True
        # 重置脏缓存，强制下一帧发送包含 hitbox 的 UPDATE
        sprite._last_update_key = None
        # 通知前端开启碰撞盒渲染开关
        print(json.dumps({"type": "SHOW_COLLISION", "data": {"visible": True}}))


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


def _camera_config():
    """当前地图的相机设置（缺省为空字典 = 仅支持代码 camera_follow()）"""
    if not _CURRENT_MAP:
        return {}
    cfg = _CURRENT_MAP.get("camera") or {}
    return cfg if isinstance(cfg, dict) else {}


def _resolve_camera_target(name):
    """按角色变量名解析相机跟随目标。

    依次尝试：用户脚本里的同名变量 → 角色素材名（Sprite("角色1")）→ 1 号角色。
    找不到时回退主玩家，避免相机不跟随（课堂容错）。
    """
    name = str(name or "").strip()
    if name:
        main = sys.modules.get("__main__")
        obj = getattr(main, name, None) if main else None
        if isinstance(obj, Sprite) and not getattr(obj, "_is_deleted", False):
            return obj
        for sprite in _SPRITES.values():
            if getattr(sprite, "sprite_name", "") == name and not getattr(sprite, "_is_deleted", False):
                return sprite
    return get_main_player()


def _update_camera_follow():
    """每帧更新相机。

    支持两种来源：
    - 地图属性里的相机设置（勾选「相机跟随」后自动跟随指定角色/1 号角色，可设偏移/平滑/边界限制）；
    - 代码调用 camera_follow() 手动跟随（优先级高于自动跟随）。
    """
    global _CAMERA_X, _CAMERA_Y, _FOLLOW_TARGET, _AUTO_CAMERA_TARGET
    cfg = _camera_config()
    enabled = bool(cfg.get("enabled"))

    if enabled:
        # 只在没有目标时解析一次（代码 camera_follow() 或已解析的目标不会被覆盖）
        if _FOLLOW_TARGET is None:
            target = _resolve_camera_target(cfg.get("target", ""))
            if target is not None:
                _FOLLOW_TARGET = target
                _AUTO_CAMERA_TARGET = target
    elif _AUTO_CAMERA_TARGET is not None and _FOLLOW_TARGET is _AUTO_CAMERA_TARGET:
        # 关闭相机跟随：撤销自动目标，不影响代码 camera_follow()
        _FOLLOW_TARGET = None
        _AUTO_CAMERA_TARGET = None

    if _FOLLOW_TARGET is None:
        return
    if getattr(_FOLLOW_TARGET, "_is_deleted", False):
        # 目标被删除：停止跟随（地图开启自动跟随时下一帧会重新锁定主玩家）
        _FOLLOW_TARGET = None
        _AUTO_CAMERA_TARGET = None
        return

    offset_x = float(cfg.get("offsetX", 0) or 0)
    offset_y = float(cfg.get("offsetY", 0) or 0)
    smooth = max(0.0, min(0.95, float(cfg.get("smoothing", 0) or 0)))
    limit = bool(cfg.get("limitBounds", True))

    if _CURRENT_MAP:
        # 相机活动范围 = 地图自身的像素矩形（不建议用 world_bounds：
        # 它包含图片出血/超出地图的素材，会把相机带到地图/游戏窗口之外）
        ts = _CURRENT_MAP.get("tile_size", 16)
        bounds = {
            "left": 0,
            "top": 0,
            "right": _CURRENT_MAP["width"] * ts,
            "bottom": _CURRENT_MAP["height"] * ts,
        }
    else:
        bounds = {"left": 0, "top": 0, "right": 640, "bottom": 480}

    old_camera_x = _CAMERA_X
    old_camera_y = _CAMERA_Y

    # 摄像机是世界空间的量，必须读世界坐标；_FOLLOW_TARGET.x/y 是用户空间会翻转 y
    tx = _FOLLOW_TARGET._x + offset_x
    ty = _FOLLOW_TARGET._y + offset_y
    if limit:
        view_w, view_h = 640, 480
        tx = max(bounds["left"] + view_w / 2, min(tx, bounds["right"] - view_w / 2))
        ty = max(bounds["top"] + view_h / 2, min(ty, bounds["bottom"] - view_h / 2))

    if smooth > 0.001:
        factor = max(0.05, 1.0 - smooth)
        _CAMERA_X += (tx - _CAMERA_X) * factor
        _CAMERA_Y += (ty - _CAMERA_Y) * factor
    else:
        _CAMERA_X = tx
        _CAMERA_Y = ty

    _send_camera_update(_CAMERA_X, _CAMERA_Y, bounds if (_CURRENT_MAP and limit) else None)

    if _CURRENT_MAP:
        tile_size = _CURRENT_MAP.get("tile_size", 16)
        if abs(_CAMERA_X - old_camera_x) >= tile_size / 2 or abs(_CAMERA_Y - old_camera_y) >= tile_size / 2:
            _render_map()


def _flush_frame_updates():
    """将帧缓冲中的精灵更新合并为一条 JSON 发送，大幅减少管道写入次数"""
    global _FRAME_UPDATES
    if not _FRAME_UPDATES:
        return
    packet = {"type": "UPDATE_BATCH", "data": {"updates": _FRAME_UPDATES}}
    print(json.dumps(packet))
    _FRAME_UPDATES = []


def _update_follows():
    """每帧同步所有跟随者的位置与镜像继承（flush 前调用）。

    只写 x/y 与镜像（不碰 angle/scale）——朝向永远归用户控制；
    镜像继承目标的显示翻转（父翻面武器跟着翻，Godot 子节点观感，
    follow(target, flip=False) 可关）；目标被删除时自动停止跟随。
    """
    for sprite in list(_SPRITES.values()):
        if sprite._is_deleted or sprite._follow_ref is None:
            continue
        ref = sprite._follow_ref
        pos = _resolve_target_xy(ref)
        if pos is None:
            # 目标已被删除：等同 unfollow，保留最后一次镜像继承的朝向
            sprite._follow_ref = None
            continue
        # 镜像继承：取目标的本帧显示翻转（链式跟随时含祖辈继承）
        flip = 1.0
        if sprite._follow_flip_on:
            parent = ref._sprite if isinstance(ref, _MarkerRef) else ref
            flip = getattr(parent, "_display_flip", 1.0)
        sprite._follow_flip = flip
        sprite._x, sprite._y = pos
        # 缓存比对在 _update_transform 内部，位置/镜像未变则不发包
        sprite._update_transform()


def camera_follow(sprite):
    """
    设置摄像机跟随指定精灵

    Args:
        sprite: 要跟随的精灵对象
    """
    global _FOLLOW_TARGET, _AUTO_CAMERA_TARGET
    _FOLLOW_TARGET = sprite
    # 代码手动跟随优先于地图里的自动跟随
    _AUTO_CAMERA_TARGET = None


def _build_static_world(map_data, map_model):
    """把地图里的静态碰撞几何烘焙成 solid / sensor 双索引。

    只在地图加载时执行一次：
      - 形状层：按 kind 进入阻挡索引 / 感应索引；tag 单独建查找表
      - 图像碰撞：静态图像的碰撞体，进入阻挡索引
      - 图块碰撞：实心图块，进入阻挡索引

    烘焙失败（极少见的坏数据）时返回 None，碰撞路径会回退到全表扫描，不影响运行。
    """
    entries = []
    tile_size = float(map_data.get("tile_size", 16) or 16)

    for layer_index, layer in enumerate(map_data.get("layers", [])):
        layer_type = layer.get("type")

        if layer_type == "shape":
            for poly in layer.get("polygons", []):
                if poly.get("disabled"):
                    continue
                # 凹多边形按耳切拆成凸块（直接构造 ConvexPolygon 会失败并丢掉整块形状）
                shape_parts = _shape_convex_parts(poly)
                if not shape_parts:
                    continue
                shape = shape_parts[0] if len(shape_parts) == 1 else CompoundShape(shape_parts)
                entries.append(StaticEntry(
                    shape=shape,
                    source="shape",
                    kind=poly.get("kind", "solid"),
                    tag=poly.get("tag", "") or "",
                    collision_type=poly.get("collisionType", "墙体"),
                    layer_index=layer_index,
                    ref=poly.get("id"),
                    origin=poly,
                ))
            continue

        if layer_type == "image":
            for image_index, image in enumerate(layer.get("images") or []):
                if not image.get("collisionEnabled", image.get("collision_enabled", False)):
                    continue
                try:
                    polys = _image_collision_world_polygons(image)
                except (TypeError, ValueError, KeyError):
                    continue
                convex = []
                for part in polys:
                    if len(part) < 3:
                        continue
                    try:
                        convex.append(ConvexPolygon(part))
                    except (ValueError, TypeError):
                        continue
                if not convex:
                    continue
                shape = convex[0] if len(convex) == 1 else CompoundShape(convex)
                entries.append(StaticEntry(
                    shape=shape,
                    source="image",
                    kind="solid",
                    collision_type=image.get("collisionType", "图像"),
                    layer_index=layer_index,
                    ref=image_index,
                    origin=image,
                ))
            continue

        if layer_type != "drawing":
            continue

        for (tile_x, tile_y), tile_id in (layer.get("tiles") or {}).items():
            try:
                tile_id_int = int(tile_id)
            except (TypeError, ValueError):
                continue
            if tile_id_int <= 0:
                continue
            resource_index, tile_index = _find_tileset_for_gid(
                tile_id_int, map_data.get("tile_sets", [])
            )
            if not map_model.get_tile_collision(resource_index, tile_index):
                continue

            shape = None
            collision_shape = map_model.get_tile_collision_shape(resource_index, tile_index)
            if isinstance(collision_shape, dict) and collision_shape.get("points"):
                # 编辑器保存的是归一化坐标(0~1)，乘以 tile_size 转世界像素
                world_points = [
                    (
                        tile_x * tile_size + float(p[0]) * tile_size,
                        tile_y * tile_size + float(p[1]) * tile_size,
                    )
                    for p in collision_shape["points"]
                    if isinstance(p, (list, tuple)) and len(p) >= 2
                ]
                if len(world_points) >= 3:
                    try:
                        shape = polygon_shape(world_points)
                    except (ValueError, TypeError):
                        shape = None

            if shape is None:
                left = tile_x * tile_size
                top = tile_y * tile_size
                shape = ConvexPolygon([
                    (left, top),
                    (left + tile_size, top),
                    (left + tile_size, top + tile_size),
                    (left, top + tile_size),
                ])

            entries.append(StaticEntry(
                shape=shape,
                source="tile",
                kind="solid",
                collision_type=map_model.get_tile_collision_type(resource_index, tile_index),
                layer_index=layer_index,
                ref=(tile_x, tile_y),
            ))

    return build_world(entries)


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

        if not os.path.exists(json_file):
            print(f"[错误] 地图文件不存在: {json_file}")
            return False

        with open(json_file, "r", encoding="utf-8") as f:
            save_data = json.load(f)

        # 新存档的素材库在地图顶层；旧存档仍然散落在各图层的 resources 里
        top_resources = save_data.get("resources")
        if not isinstance(top_resources, list):
            top_resources = None

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
                    "render": layer_raw.get("render", True),
                    "locked": layer_raw.get("locked", False),
                    "tiles": tiles,
                    "images": layer_raw.get("images", []),
                })
            elif layer_type == "imagelayer":
                # 兼容两种格式：images（带位置）和 resources（资源引用，无位置）
                images = layer_raw.get("images", [])
                # 只在旧存档（没有顶层素材库）时回退到层内 resources，
                # 避免新版层内镜像让每个空图像层都重复生成素材实例
                if not images and top_resources is None:
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
                    "render": layer_raw.get("render", True),
                    "locked": layer_raw.get("locked", False),
                    "tiles": {},
                    "images": images,
                })
            elif layer_type in ("collisionlayer", "shapelayer"):
                # 形状层：世界坐标判定形状，与图像/图块解耦
                raw_shapes = layer_raw.get("shapes")
                if raw_shapes is None:
                    # 旧存档只有 polygons 字段，读取时统一成形状
                    raw_shapes = layer_raw.get("polygons", [])
                polygons = []
                for poly_raw in raw_shapes:
                    pts = []
                    for p in poly_raw.get("points") or []:
                        if isinstance(p, (list, tuple)) and len(p) >= 2:
                            try:
                                pts.append((float(p[0]), float(p[1])))
                            except (TypeError, ValueError):
                                continue
                    if len(pts) >= 3:
                        polygons.append({
                            # 稳定 id：静态索引宽相按 id 回到原始 polygon 走原有解算
                            "id": poly_raw.get("id") or ("shape_%d" % len(polygons)),
                            "points": pts,
                            # 凸块：凹多边形预先三角化，供 SAT 碰撞判定使用
                            "parts": _collision_polygon_parts(pts),
                            "collisionType": poly_raw.get("collisionType", "墙体"),
                            # 能力类型：solid=阻挡，sensor=感应，both=两者
                            "kind": poly_raw.get("kind", "solid"),
                            "tag": poly_raw.get("tag", "") or "",
                            "disabled": bool(poly_raw.get("disabled", False)),
                        })
                layers.append({
                    "name": layer_raw.get("name", "形状"),
                    "type": "shape",
                    "visible": layer_raw.get("visible", True),
                    "render": layer_raw.get("render", True),
                    "locked": layer_raw.get("locked", False),
                    "tiles": {},
                    "images": [],
                    "polygons": polygons,
                })

        # 用素材的碰撞信息补全 tileset（用户可能在 PropertyPanel 中设置了 tileset 级的碰撞）
        resource_collision_map = {}
        if top_resources is not None:
            resource_entries = top_resources
        else:
            resource_entries = [
                res
                for layer_raw in layers_raw
                for res in layer_raw.get("resources", [])
            ]
        for res in resource_entries:
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
            # 边界碰撞：勾选后角色被地图像素矩形挡住，不能离开可玩区域
            # 旧存档没有该字段时沿用重力地图原来的行为（重力=钳制）
            "boundaryCollision": bool(
                save_data.get("boundaryCollision", save_data.get("gravity", False))
            ),
            # 禁止下滑：勾选后角色站在斜坡上不下滑；旧存档缺省视为开启
            "stopOnSlope": bool(save_data.get("stopOnSlope", True)),
            "layers": layers,
            "tile_sets": tilesets,
            # 地图相机设置（属性面板里的相机跟随/偏移/平滑/边界限制）
            "camera": save_data.get("camera") or {},
            # 场景标记（编辑器里放的坐标图钉），供 get_marker / get_markers 查询
            "markers": save_data.get("markers") or [],
        }

        _CURRENT_MAP = map_data
        _MAP_MODEL = MapModel(tilesets)

        # P3：静态几何烘焙一次，后续碰撞/感应/射线查询共用
        try:
            _CURRENT_MAP["static_world"] = _build_static_world(_CURRENT_MAP, _MAP_MODEL)
        except Exception as exc:  # 坏数据不应让整张地图打不开
            _CURRENT_MAP["static_world"] = None
            print("static index build failed: %s" % exc, file=sys.stderr)

        tile_size = _CURRENT_MAP.get("tile_size", 16)
        map_width_px = _CURRENT_MAP["width"] * tile_size
        map_height_px = _CURRENT_MAP["height"] * tile_size

        # 用户坐标原点跟随地图高度：y=0 永远在地图底部。
        # 单屏地图（高 480）与旧行为完全一致；更高的地图不再出现负 y。
        set_user_origin_y(map_height_px)

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
        return _MapHandle(map_name)

    except Exception as e:
        print(f"[错误] 加载地图时出错: {e}")
        import traceback

        traceback.print_exc()
        return False


class MapMarkerRef:
    """地图标记引用（get_marker 返回）

    可以直接当坐标用：读 .x / .y / .pos，也可以拆包 x, y = m，
    或者直接 player.goto(m)。坐标为用户坐标（左下角原点，y 向上）。
    """

    __slots__ = ("_raw",)

    def __init__(self, raw):
        self._raw = raw

    @property
    def name(self):
        return str(self._raw.get("name", ""))

    @property
    def type(self):
        """标记类型（属性面板里设置：出生点 / 敌人 / 道具 ...）"""
        return str(self._raw.get("type", "") or "")

    @property
    def x(self):
        return to_user_x(float(self._raw.get("x", 0) or 0))

    @property
    def y(self):
        return to_user_y(float(self._raw.get("y", 0) or 0))

    @property
    def pos(self):
        """一次性获取坐标 (x, y)，可直接拆包：x, y = m.pos"""
        return self.x, self.y

    @property
    def world_xy(self):
        """世界坐标（y 向下），供 goto / 内部放置使用"""
        return (
            float(self._raw.get("x", 0) or 0),
            float(self._raw.get("y", 0) or 0),
        )

    # 让标记可以直接当坐标用：x, y = m / m[0] / player.goto(m)
    def __iter__(self):
        yield self.x
        yield self.y

    def __len__(self):
        return 2

    def __getitem__(self, index):
        if index in (0, -2):
            return self.x
        if index in (1, -1):
            return self.y
        raise IndexError("标记只有 x、y 两个坐标")

    def __repr__(self):
        return "<标记 '%s' (%s, %s)>" % (self.name, round(self.x), round(self.y))


def _map_marker_list():
    """当前地图的全部标记（世界坐标原始数据）"""
    return (_CURRENT_MAP or {}).get("markers") or []


def get_marker(name):
    """按名称获取地图标记（编辑器里在地图上放的坐标图钉）

    Args:
        name: 标记名称（属性面板里的「名称」）

    Returns:
        标记引用，可读 .x / .y（用户坐标）或 .pos，也可直接 goto(marker)；找不到返回 None

    用法：
        map = load_map("地图1")
        pos = map.get_marker("出生点")
        player.goto(pos)          # 直接把角色放到标记位置
        x, y = pos                # 也可以拆包
    """
    markers = _map_marker_list()
    for raw in markers:
        if str(raw.get("name", "")) == str(name):
            return MapMarkerRef(raw)
    if not _CURRENT_MAP:
        print("[提示] 还没有加载地图，先用 load_map('地图名') 加载")
    elif markers:
        known = [str(m.get("name", "")) for m in markers[:8]]
        more = "…" if len(markers) > 8 else ""
        print(f"[警告] 没有名为 '{name}' 的标记（已有标记：{'、'.join(known)}{more}）")
    else:
        print("[警告] 这张地图还没有标记，先在地图编辑器里点「标记」放一个")
    return None


def get_markers(marker_type):
    """按类型获取地图标记列表（类型在属性面板里设置，如 出生点 / 敌人 / 道具）

    Args:
        marker_type: 标记类型名称

    Returns:
        同类型的所有标记（列表），没有时返回空列表，可直接 for 遍历

    用法：
        for m in get_markers("敌人"):
            enemy = Sprite("史莱姆")
            enemy.goto(m)
    """
    return [
        MapMarkerRef(raw)
        for raw in _map_marker_list()
        if str(raw.get("type", "")) == str(marker_type)
    ]


class RaycastHit:
    """raycast() 的命中结果（没打中时 raycast 返回 None）。

    坐标为用户坐标（左下角原点、y 向上），与角色 x/y 一致：
        hit.x / hit.y / hit.pos / hit.distance / hit.normal
    """
    __slots__ = ("distance", "_wx", "_wy", "_nx", "_ny", "tag", "collision_type", "source")

    def __init__(self, distance, world_point, world_normal, entry):
        self.distance = float(distance)
        self._wx = float(world_point[0])
        self._wy = float(world_point[1])
        self._nx = float(world_normal[0])
        self._ny = float(world_normal[1])
        self.tag = getattr(entry, "tag", "") or ""
        self.collision_type = getattr(entry, "collision_type", "") or ""
        self.source = getattr(entry, "source", "") or ""

    @property
    def x(self):
        return to_user_x(self._wx)

    @property
    def y(self):
        return to_user_y(self._wy)

    @property
    def pos(self):
        return self.x, self.y

    @property
    def normal_x(self):
        """命中表面法线的水平分量（用户坐标）"""
        return self._nx

    @property
    def normal_y(self):
        """命中表面法线的垂直分量（用户坐标，向上为正）"""
        return -self._ny

    @property
    def normal(self):
        return self.normal_x, self.normal_y

    def __bool__(self):
        return True

    def __repr__(self):
        return "<raycast 命中 (%s, %s)，距离 %s>" % (
            round(self.x), round(self.y), round(self.distance, 1)
        )


def raycast(x, y, direction, distance=1000):
    """从用户坐标 (x, y) 射出一条射线，返回最近命中的实心地形。

    direction: "left"/"right"/"up"/"down"（或 左/右/上/下），
               也可以是用户角度数字（0=右，90=上，180=左，270=下）
    distance:  射线长度（像素），默认 1000

    Returns:
        RaycastHit（.x/.y/.pos/.distance/.normal）或 None（没打中）

    用法：
        hit = raycast(hero.x, hero.y, "right", 200)
        if hit:
            print(hit.distance, hit.tag)
    """
    if not _CURRENT_MAP:
        return None
    static_world = _CURRENT_MAP.get("static_world")
    if static_world is None:
        return None
    world_dir = _parse_direction_world(direction)
    if world_dir is None:
        return None
    max_distance = max(0.0, float(distance))
    if max_distance <= 0.0:
        return None

    ox = to_world_x(float(x))
    oy = to_world_y(float(y))
    end_x = ox + world_dir[0] * max_distance
    end_y = oy + world_dir[1] * max_distance
    candidates = static_world.solid.query_rect(
        min(ox, end_x), min(oy, end_y), max(ox, end_x), max(oy, end_y)
    )
    best = None
    for entry in candidates:
        hit = shape_raycast(entry.shape, (ox, oy), world_dir, max_distance)
        if hit is None:
            continue
        if best is None or hit.distance < best[0]:
            best = (hit.distance, hit, entry)
    if best is None:
        return None
    return RaycastHit(best[0], best[1].point, best[1].normal, best[2])


class _MapHandle:
    """load_map() 返回的地图对象（加载失败时返回 False）

    Args:
        name: 地图名称

    用法（与角色统一，用 .get_marker() 取标记）：
        map = load_map("地图1")
        pos = map.get_marker("出生点")
        player.goto(pos)
    """

    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name

    def get_marker(self, name="标记"):
        """按名称获取这张地图上的标记（同 get_marker(name)）"""
        return get_marker(name)

    def get_markers(self, marker_type=None):
        """按类型获取标记列表；不传类型则返回全部标记"""
        if marker_type is None:
            return [MapMarkerRef(raw) for raw in _map_marker_list()]
        return get_markers(marker_type)

    def is_solid(self, x, y):
        """这个用户坐标点上是否有实心地形（形状层 solid/both、图像碰撞、实心图块）。

        感应区域不算；跳板算实心地形。
        """
        if not _CURRENT_MAP:
            return False
        static_world = _CURRENT_MAP.get("static_world")
        if static_world is None:
            return False
        wx = to_world_x(float(x))
        wy = to_world_y(float(y))
        for entry in static_world.solid.query_point(wx, wy):
            if point_inside(entry.shape, (wx, wy)):
                return True
        return False

    def raycast(self, x, y, direction, distance=1000):
        """同全局 raycast(x, y, direction, distance)"""
        return raycast(x, y, direction, distance)

    def __bool__(self):
        # 加载成功返回的对象在 if 判断里视为真（由原来的 True 兼容而来）
        return True

    def __repr__(self):
        return "map(%r)" % self.name


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
        return True
    except Exception as e:
        print(f"[错误] 解压 .bgm 失败: {e}")
        return False


def _clear_map():
    """清理地图资源"""
    global _CURRENT_MAP, _MAP_SPRITES, _RENDERED_TILES, _MAP_DIR, _FOLLOW_TARGET, _AUTO_CAMERA_TARGET

    # 删除地图瓦片精灵
    for sprite_id in list(_MAP_SPRITES.keys()):
        packet = {"type": "DELETE", "id": sprite_id}
        print(json.dumps(packet))
        del _MAP_SPRITES[sprite_id]

    # 地图卸载：撤销自动相机跟随目标（代码 camera_follow() 的仍保留）
    if _AUTO_CAMERA_TARGET is not None and _FOLLOW_TARGET is _AUTO_CAMERA_TARGET:
        _FOLLOW_TARGET = None
    _AUTO_CAMERA_TARGET = None

    _CURRENT_MAP = None
    _MAP_DIR = None
    _MAP_SPRITES = {}
    _RENDERED_TILES.clear()
    # 卸载地图后用户坐标原点退回单屏舞台
    set_user_origin_y(_SCREEN_HEIGHT)


def _handle_physics_collision():
    """处理物理碰撞检测和位移修正"""
    global _CURRENT_MAP, _SPRITES, _MAP_MODEL

    if not _CURRENT_MAP:
        return

    # 地图属性「禁止下滑」：开启时站在斜坡上不下滑（缺省视为开启）
    stop_on_slope = _CURRENT_MAP.get("stopOnSlope", True)

    # 遍历所有精灵
    for sprite in _SPRITES.values():
        if sprite._is_deleted:
            continue

        # P4：每帧重置接触掩码，再按本帧 x/y 解算结果重新记录
        sprite._contacts = 0

        # 禁用碰撞：不参与重力、落地与墙体修正（照常渲染与按代码移动）
        if sprite._collision_disabled:
            sprite._on_ground = False
            sprite._update_transform()
            continue

        if sprite._drop_through:
            sprite._drop_through_timer -= 1
            if sprite._drop_through_timer <= 0:
                sprite._drop_through = False

        # smart_jump：松手后自动停止跳跃
        # 优先按"起跳时记录的键"判断（支持 if key_down 和 if key_pressed 两种写法）；
        # 没有记录到键时退回"本步是否被调用"的判断
        if sprite._smart_jump_active:
            if sprite._smart_jump_key is not None:
                if sprite._smart_jump_key not in _PRESSED_KEYS_FRAME:
                    if sprite._vy < 0:
                        sprite.stop_jump()
                    sprite._smart_jump_active = False
                    sprite._smart_jump_key = None
            elif not sprite._smart_jump_called:
                if sprite._vy < 0:
                    sprite.stop_jump()
                sprite._smart_jump_active = False
        sprite._smart_jump_called = False

        sprite._on_ground = False

        if _CURRENT_MAP.get("gravity", False) and sprite._gravity:
            if sprite._vy < 0:
                if sprite._jump_cut:
                    gravity = 2.8
                else:
                    gravity = 0.5
            else:
                gravity = 1.1
            sprite._vy = min(sprite._vy + gravity, 10)
        else:
            gravity = 0

        x_before = sprite._x
        # 唯一入口：先纵向再横向（与旧物理步顺序一致），内部会先 depenetrate
        sprite.move_and_slide(0.0, sprite._vy, axis_order="yx")
        # 禁止下滑：本步学生代码与自动移动都没动过 x 时，
        # 落地状态下撤销重力+碰撞推挤带来的水平漂移（即 Godot floor_stop_on_slope 语义）
        if stop_on_slope and sprite._on_ground and x_before == sprite._frame_start_x:
            sprite._x = x_before
        if sprite._on_ground:
            sprite._vy = 0
            sprite._jump_cut = False

        sprite._update_transform()


def _process_sensor_events():
    """轮询注册了感应回调的角色，触发「进入 / 离开」事件。

    只查感应索引（solid 不参与），每个标签的判定形状统一按 SENSOR_EPS 外扩：
      - 从无到有 → 触发一次 on_sensor_enter
      - 从有到无 → 触发一次 on_sensor_exit
    外扩让「刚好贴着边界 / 贴着感应区休息」也算在内，不会因浮点误差漏判或抖动。
    """
    if not _CURRENT_MAP:
        return
    static_world = _CURRENT_MAP.get("static_world")
    if static_world is None:
        return

    for sprite in list(_SPRITES.values()):
        if sprite._is_deleted:
            continue
        enter_callbacks = sprite._sensor_enter_callbacks
        exit_callbacks = sprite._sensor_exit_callbacks
        if not (enter_callbacks or exit_callbacks):
            continue

        wanted = {tag for tag, _ in enter_callbacks}
        wanted.update(tag for tag, _ in exit_callbacks)
        if not wanted:
            continue

        rect = sprite._get_hitbox_rect()
        if not rect:
            continue

        # 感应索引宽相：查询盒按外扩量放大，保证贴着边界的感应形状也进候选
        entries = static_world.sensors.query_rect(
            rect[0] - SENSOR_EPS, rect[1] - SENSOR_EPS,
            rect[2] + SENSOR_EPS, rect[3] + SENSOR_EPS,
        )

        active = sprite._sensor_active_tags
        touched = set()
        if entries:
            shape = sprite._get_collision_shape()
            for entry in entries:
                tag = entry.tag
                if tag not in wanted or tag in touched:
                    continue
                if intersects(shape, entry.probe_shape):
                    touched.add(tag)

        for tag in touched - active:
            for t, callback in list(enter_callbacks):
                if t == tag:
                    _safe_call(callback, sprite, tag)
        for tag in active - touched:
            for t, callback in list(exit_callbacks):
                if t == tag:
                    _safe_call(callback, sprite, tag)
        sprite._sensor_active_tags = touched


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
        # 渲染开关：编辑器里「渲染」未勾选时，游戏运行窗口不绘制该图层
        if not layer.get("render", True):
            continue

        # 形状层只参与物理与感应判定，不参与渲染
        if layer.get("type") == "shape":
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
                # 缩放读取需兼容 camelCase（编辑器保存格式）——与碰撞检测路径（约269行）一致
                rotation = image.get("rotation", 0)
                scale = image.get("scale", 1.0)
                scale_x = image.get("scaleX", image.get("scale_x", scale))
                scale_y = image.get("scaleY", image.get("scale_y", scale))
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


# ---------- 物理步共用实现 ----------
# 旧式 run()（def loop()）与 while True generator 模式过去各写了一份物理步，
# 任何碰撞/感应功能都要改两处，极易漏改。现在统一走这两个函数：
#   _begin_physics_step：推进时间、更新动画、记录步初位置
#   学生代码（loop() / generator）
#   _end_physics_step：气泡计时、自动移动、触碰回调、地形碰撞、感应事件

def _safe_call(callback, *args):
    """执行用户回调；回调内出错只打印错误，不中断游戏（与 broadcast 行为一致）。

    GameStop 必须继续向上抛：学生代码里调用 stop() 时依赖它结束 generator。
    """
    try:
        callback(*args)
    except GameStop:
        raise
    except Exception as e:
        print(f"[错误] 回调出错: {e}")


def _begin_physics_step():
    """物理步开始（未暂停时）：推进游戏时间、更新动画、记录本步初始 x。"""
    global _GAME_TIME
    if _PAUSED:
        return
    _GAME_TIME += _PHYSICS_DT
    for sprite in _SPRITES.values():
        if getattr(sprite, "animation_state", None):
            _update_sprite_animation(sprite)
    if _CURRENT_MAP is not None:
        for sprite in _SPRITES.values():
            # 禁止下滑功能据此区分主动移动与斜面推挤下滑
            sprite._frame_start_x = sprite._x


def _end_physics_step():
    """物理步收尾（未暂停时）：气泡计时、自动移动、触碰回调、地形碰撞、感应事件。"""
    if _PAUSED:
        return

    # say 计时器：到期自动隐藏气泡
    for sid in list(_SAY_TIMERS.keys()):
        timer, hide_fn = _SAY_TIMERS[sid]
        if timer.is_timeout():
            hide_fn()
            del _SAY_TIMERS[sid]

    for sprite in list(_SPRITES.values()):
        if sprite._is_deleted:
            continue
        # 持续速度自动移动
        if sprite._speed > 0:
            sprite.move(sprite._speed)
        # 自动销毁
        if sprite._auto_destroy and sprite.is_out_side():
            sprite.delete()
        # 分组触碰回调
        if sprite._on_hit_callbacks:
            for group_name, callback in list(sprite._on_hit_callbacks):
                for other in list(_GROUPS.get(group_name, [])):
                    if other is sprite or other._is_deleted:
                        continue
                    if sprite.is_touch(other):
                        if callback:
                            _safe_call(callback, sprite, other)
                        else:
                            # 不传回调：默认双方都删除
                            sprite.delete()
                            other.delete()
                        break

    if _CURRENT_MAP:
        _handle_physics_collision()
        _process_sensor_events()


def run():
    global _PERF_STATS, _MOUSE_STATE, _SPRITES, _PENDING_RESPONSES, _GAME_TIME, _WAIT_TIMERS
    _MOUSE_STATE["down"] = False
    _MOUSE_STATE["released"] = False
    _MOUSE_STATE["released_frame"] = False
    _GAME_TIME = 0.0
    _WAIT_TIMERS.clear()
    _EVENT_PENDING.clear()
    _EVENT_ACTIVE.clear()
    main_module = sys.modules["__main__"]
    if not hasattr(main_module, "loop"):
        return

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
            # 暂停时也要同步输入快照：用户代码需要靠按键检测来调用 resume()
            _sync_input_frame()
            _promote_event_frame()

            _begin_physics_step()
            main_module.loop()
            _end_physics_step()

            accumulator -= _PHYSICS_DT
            steps += 1

        if accumulator > _PHYSICS_DT * _MAX_PHYSICS_STEPS:
            accumulator = 0.0

        # 相机跟随（地图属性设置 / 代码 camera_follow()）
        _update_camera_follow()

        # 同步位置跟随（挂点/角色），再合并发送本帧所有精灵更新
        _update_follows()
        _flush_frame_updates()

        _MOUSE_STATE["last_down"] = _MOUSE_STATE["down"]

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
    global _STOPPED, _PERF_STATS, _MOUSE_STATE, _PENDING_RESPONSES, _GAME_TIME, _WAIT_TIMERS

    _STOPPED = False
    _MOUSE_STATE["down"] = False
    _MOUSE_STATE["released"] = False
    _MOUSE_STATE["released_frame"] = False
    _GAME_TIME = 0.0
    _WAIT_TIMERS.clear()
    _EVENT_PENDING.clear()
    _EVENT_ACTIVE.clear()

    # 如果提供了项目目录，使用脚本发现模块
    if project_dir:
        from script_runner import discover_and_merge
        try:
            script_content = discover_and_merge(project_dir, target_file)
        except SyntaxError as e:
            print(f"[错误] {e}")
            return
        if not script_content:
            print("[错误] 没有找到 Python 文件")
            return

        # 执行脚本，注册 generator
        exec_globals = {
            "__name__": "__main__",
            "Sprite": Sprite,
            "Timer": Timer,
            "input": _custom_input,
            "key_down": key_down,
            "key_pressed": key_pressed,
            "key_up": key_up,
            "mouse": mouse,
            "mouse_down": mouse_down,
            "mouse_pressed": mouse_pressed,
            "mouse_up": mouse_up,
            "time_passed": time_passed,
            "wait": wait,  # 兼容旧项目
            "load_map": load_map,
            "play_sound": play_sound,
            "stop_sound": stop_sound,
            "show_text": show_text,
            "shake": shake,
            "camera_follow": camera_follow,
            "show_fps": show_fps,
            "show_collision": show_collision,
            "random_int": random_int,
            "random_float": random_float,
            "broadcast": broadcast,
            "receive": receive,
            "on_receive": on_receive,
            "pause": pause,
            "resume": resume,
            "is_paused": is_paused,
            "stop": stop_game,
            "register_generator": register_generator,
        }
        exec(script_content, exec_globals)

    # 主循环
    _PERF_STATS["last_time"] = time.time()
    accumulator = 0.0
    prev_time = time.perf_counter()

    while True:
        # 用户可能用 `from bingo_engine import *` 拿到只设置 _STOPPED 的 stop()，
        # 与 exec_globals 里抛 GameStop 的版本并存，两种都要能真正结束游戏
        if _STOPPED:
            return

        now = time.perf_counter()
        frame_time = min(now - prev_time, _MAX_FRAME_TIME)
        prev_time = now
        accumulator += frame_time

        # 物理步进
        steps = 0
        while accumulator >= _PHYSICS_DT and steps < _MAX_PHYSICS_STEPS:
            # 暂停时也要同步输入快照：学生代码需要靠按键检测来调用 resume()
            _sync_input_frame()
            _promote_event_frame()

            _begin_physics_step()

            # 执行所有 generator（每帧一次迭代）
            # 暂停时照常执行：文档约定「程序还在跑」，否则 resume() 永远不会被调用
            for gen in list(_generators):
                try:
                    next(gen)
                except StopIteration:
                    _generators.remove(gen)
                except GameStop:
                    _generators.clear()
                    return
                except Exception as e:
                    print(f"[错误] Generator 错误: {e}")
                    _generators.remove(gen)

            if not _PAUSED:
                # 所有 generator 结束且无活跃行为时自动退出主循环，
                # 让 Python 进程正常结束，IDE 才能收到 engine:finished 复位运行按钮
                if not _generators and not _SAY_TIMERS:
                    _has_active = any(
                        (s._speed > 0) or
                        (getattr(s, "animation_state", None) and s.animation_state.get("is_playing", False)) or
                        bool(s._on_hit_callbacks) or
                        bool(s._sensor_enter_callbacks) or
                        bool(s._sensor_exit_callbacks) or
                        s._follow_ref is not None
                        for s in _SPRITES.values() if not s._is_deleted
                    )
                    if not _has_active:
                        return

            _end_physics_step()

            accumulator -= _PHYSICS_DT
            steps += 1

        if accumulator > _PHYSICS_DT * _MAX_PHYSICS_STEPS:
            accumulator = 0.0

        # 相机跟随（地图属性设置 / 代码 camera_follow()）
        _update_camera_follow()

        # 同步位置跟随（挂点/角色），再帧合并发送
        _update_follows()
        _flush_frame_updates()

        # 状态更新
        _MOUSE_STATE["last_down"] = _MOUSE_STATE["down"]

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