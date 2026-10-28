"""挂点与地图标记查询 + 射线检测。

什么时候来这里改：Sprite.get_marker / 地图 get_marker / get_markers / raycast 的行为。
依赖：只依赖 engine_state 与 models，不依赖 sprite / map_runtime（避免循环导入）。"""
import math
from models.coords import to_user_x, to_user_y, to_world_x, to_world_y
from models.shape_kernel import raycast as shape_raycast
import engine_state as st


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
    return (st._CURRENT_MAP or {}).get("markers") or []


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
    if not st._CURRENT_MAP:
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
    if not st._CURRENT_MAP:
        return None
    static_world = st._CURRENT_MAP.get("static_world")
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
