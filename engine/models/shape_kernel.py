# -*- coding: utf-8 -*-
"""Shape 几何内核：凸多边形 / 复合形状的 overlap、sweep、raycast、inflate。

设计目标（为后续静态烘焙、Contact 掩码、move_and_slide 打底）：
  1. 几何只有一份：世界坐标顶点；旋转/缩放后的形状在构造时直接烘成顶点，不再降级成 AABB。
  2. 输出统一为「法线 + 深度 / 时间」，调用方不需要自己推导方向。
  3. 所有二维形状最终都归约为「一组凸多边形」：
     - 矩形 / 圆形 / 胶囊 / 任意多边形 → ConvexPolygon
     - 凹多边形 → CompoundShape（耳切三角化）
  4. 坐标系与引擎一致：x 向右、y 向下；顺时针顶点为正向（shoelace > 0）。

法线约定：
  - Manifold.normal：从 b 指向 a 的单位法线（把 a 沿此方向推出 depth 即可分离）。
  - SweepHit.normal：撞击瞬间从 b 指向 a 的接触法线（与移动方向相反）。
  - RayHit.normal：命中表面的外法线（指向射线来源一侧）。

本模块只做纯几何，不依赖 bingo_engine，方便单独测试。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Sequence, Tuple, Union

Vec2 = Tuple[float, float]

__all__ = [
    "Vec2", "AABB", "Manifold", "SweepHit", "RayHit",
    "ConvexPolygon", "CompoundShape", "Shape",
    "polygon_shape", "rect_shape", "aabb_shape", "capsule_shape",
    "transformed_polygon_shape",
    "overlap", "overlap_all", "intersects", "sweep", "raycast", "inflate",
    "bounds", "point_inside", "closest_point",
]

_EPS = 1e-9
_EPS_SAT = 1e-7

# Miter 限制（仅用于收缩）：交点最多离原顶点 4*|amount|，避免极端尖角。
# 正向膨胀改用圆弧采样，不使用 miter，保证严格外扩 amount。
_MITER_LIMIT = 4.0


# ---------------------------------------------------------------------------
# 基础向量运算
# ---------------------------------------------------------------------------

def _add(a: Vec2, b: Vec2) -> Vec2:
    return (a[0] + b[0], a[1] + b[1])


def _sub(a: Vec2, b: Vec2) -> Vec2:
    return (a[0] - b[0], a[1] - b[1])


def _mul(a: Vec2, s: float) -> Vec2:
    return (a[0] * s, a[1] * s)


def _dot(a: Vec2, b: Vec2) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _cross(a: Vec2, b: Vec2) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _length(a: Vec2) -> float:
    return math.hypot(a[0], a[1])


def _normalize(a: Vec2) -> Vec2:
    length = math.hypot(a[0], a[1])
    if length < _EPS:
        return (0.0, 0.0)
    return (a[0] / length, a[1] / length)


def _signed_area(points: Sequence[Vec2]) -> float:
    """世界坐标（y 向下）下的有向面积：> 0 表示顺时针。"""
    area = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        area += x1 * y2 - x2 * y1
    return area * 0.5


def _ensure_clockwise(points: Sequence[Vec2]) -> Tuple[Vec2, ...]:
    pts = tuple(points)
    if _signed_area(pts) < 0:
        return tuple(reversed(pts))
    return pts


def _clean_points(points: Iterable[Sequence[float]]) -> Tuple[Vec2, ...]:
    """转 float、去掉连续重复点与退化点。"""
    out: List[Vec2] = []
    for p in points:
        if p is None or len(p) < 2:
            continue
        x, y = float(p[0]), float(p[1])
        if not math.isfinite(x) or not math.isfinite(y):
            continue
        if out and abs(out[-1][0] - x) < _EPS and abs(out[-1][1] - y) < _EPS:
            continue
        out.append((x, y))
    # 首尾重复也去掉
    while len(out) > 1 and abs(out[0][0] - out[-1][0]) < _EPS and abs(out[0][1] - out[-1][1]) < _EPS:
        out.pop()
    return tuple(out)


def _project(points: Sequence[Vec2], axis: Vec2) -> Tuple[float, float]:
    lo = math.inf
    hi = -math.inf
    for p in points:
        v = _dot(p, axis)
        if v < lo:
            lo = v
        if v > hi:
            hi = v
    return lo, hi


def _bbox(points: Sequence[Vec2]) -> Tuple[float, float, float, float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


# ---------------------------------------------------------------------------
# 形状表示
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AABB:
    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    def intersects(self, other: "AABB") -> bool:
        return not (
            self.right < other.left or self.left > other.right
            or self.bottom < other.top or self.top > other.bottom
        )

    def contains_point(self, p: Vec2) -> bool:
        return self.left <= p[0] <= self.right and self.top <= p[1] <= self.bottom


@dataclass(frozen=True)
class Manifold:
    """两个形状的穿透信息。normal 从 b 指向 a，把 a 沿 normal 移动 depth 即分离。"""
    normal: Vec2
    depth: float

    def push_a(self) -> Vec2:
        return _mul(self.normal, self.depth)


@dataclass(frozen=True)
class SweepHit:
    """线性扫掠的首次接触。time ∈ [0,1]，point 为 a 上的接触点。"""
    time: float
    normal: Vec2
    point: Vec2


@dataclass(frozen=True)
class RayHit:
    distance: float
    point: Vec2
    normal: Vec2


class ConvexPolygon:
    """世界坐标凸多边形（顺时针）。构造时缓存法线、包围盒与中心。"""

    __slots__ = ("points", "normals", "bbox", "center", "area")

    def __init__(self, points: Iterable[Sequence[float]]):
        cleaned = _clean_points(points)
        if len(cleaned) < 3:
            raise ValueError("ConvexPolygon 至少需要 3 个有效顶点")
        pts = _ensure_clockwise(cleaned)
        if len(pts) > 3 and not _is_convex(pts):
            raise ValueError("ConvexPolygon 顶点不是凸多边形，请用 make_shape 自动分解")
        self.points: Tuple[Vec2, ...] = pts
        self.normals: Tuple[Vec2, ...] = _outward_normals(pts)
        self.bbox: AABB = AABB(*_bbox(pts))
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        self.center: Vec2 = (cx, cy)
        self.area: float = _signed_area(pts)

    # 便捷方法：让调用方可以写 shape.overlap(other) / shape.inflate(1)
    def overlap(self, other: "Shape") -> Optional[Manifold]:
        return overlap(self, other)

    def sweep(self, other: "Shape", delta: Vec2) -> Optional[SweepHit]:
        return sweep(self, other, delta)

    def raycast(self, origin: Vec2, direction: Vec2,
                max_distance: float = math.inf) -> Optional[RayHit]:
        return raycast(self, origin, direction, max_distance)

    def inflate(self, amount: float) -> "Shape":
        return inflate(self, amount)

    def translated(self, delta: Vec2) -> "ConvexPolygon":
        return ConvexPolygon([_add(p, delta) for p in self.points])

    def __repr__(self) -> str:
        return "ConvexPolygon(%d pts, bbox=%r)" % (len(self.points), self.bbox)


class CompoundShape:
    """由多个凸多边形组成的复合形状（凹多边形 / 多碰撞体）。"""

    __slots__ = ("parts", "bbox")

    def __init__(self, parts: Iterable[ConvexPolygon]):
        self.parts: Tuple[ConvexPolygon, ...] = tuple(p for p in parts if p is not None)
        if not self.parts:
            raise ValueError("CompoundShape 至少需要 1 个凸多边形")
        bs = [p.bbox for p in self.parts]
        self.bbox = AABB(
            min(b.left for b in bs), min(b.top for b in bs),
            max(b.right for b in bs), max(b.bottom for b in bs),
        )

    def overlap(self, other: "Shape") -> Optional[Manifold]:
        return overlap(self, other)

    def sweep(self, other: "Shape", delta: Vec2) -> Optional[SweepHit]:
        return sweep(self, other, delta)

    def raycast(self, origin: Vec2, direction: Vec2,
                max_distance: float = math.inf) -> Optional[RayHit]:
        return raycast(self, origin, direction, max_distance)

    def inflate(self, amount: float) -> "Shape":
        return inflate(self, amount)

    def __repr__(self) -> str:
        return "CompoundShape(%d parts, bbox=%r)" % (len(self.parts), self.bbox)


Shape = Union[ConvexPolygon, CompoundShape]


# ---------------------------------------------------------------------------
# 构造辅助
# ---------------------------------------------------------------------------

def _outward_normals(points: Sequence[Vec2]) -> Tuple[Vec2, ...]:
    """顺时针多边形的外法线：edge (dx,dy) → normalize(dy,-dx)。"""
    normals: List[Vec2] = []
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < _EPS:
            normals.append((0.0, 0.0))
        else:
            normals.append((dy / length, -dx / length))
    return tuple(normals)


def _is_convex(points: Sequence[Vec2]) -> bool:
    """顺时针顶点序列：所有叉积 >= 0。"""
    n = len(points)
    if n < 3:
        return False
    for i in range(n):
        a = points[i]
        b = points[(i + 1) % n]
        c = points[(i + 2) % n]
        if _cross(_sub(b, a), _sub(c, b)) < -1e-7:
            return False
    return True


def polygon_shape(points: Sequence[Sequence[float]]) -> Shape:
    """任意多边形：凸的直接返回 ConvexPolygon，凹的耳切三角化后返回 CompoundShape。"""
    cleaned = _clean_points(points)
    if len(cleaned) < 3:
        raise ValueError("polygon_shape 至少需要 3 个有效顶点")
    pts = _ensure_clockwise(cleaned)
    if _is_convex(pts):
        return ConvexPolygon(pts)
    return CompoundShape(_ear_clip(pts))


def rect_shape(x: float, y: float, w: float, h: float) -> ConvexPolygon:
    """轴对齐矩形（世界坐标左上角 + 宽高）。"""
    return ConvexPolygon([(x, y), (x + w, y), (x + w, y + h), (x, y + h)])


def _ensure_rect(w: float, h: float) -> Tuple[float, float]:
    if w < 0:
        w = -w
    if h < 0:
        h = -h
    return w, h


def aabb_shape(left: float, top: float, right: float, bottom: float) -> ConvexPolygon:
    w, h = _ensure_rect(right - left, bottom - top)
    return rect_shape(min(left, right), min(top, bottom), w, h)


def capsule_shape(a: Vec2, b: Vec2, radius: float, arc_segments: int = 8) -> ConvexPolygon:
    """胶囊：两端圆 + 直边，采样成凸多边形。

    arc_segments 为每侧半圆的段数（默认 8，足够 16px 网格上的角色判定）。
    采样点通过凸包收口，保证不会因为采样顺序产生自交。
    """
    r = abs(float(radius))
    if r < _EPS:
        return ConvexPolygon([a, b, ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)])
    seg = max(2, int(arc_segments))
    axis = _sub(b, a)
    if _length(axis) < _EPS:
        # 退化成一个圆
        pts = []
        for i in range(seg * 2):
            ang = (i / (seg * 2.0)) * math.tau
            pts.append((a[0] + math.cos(ang) * r, a[1] + math.sin(ang) * r))
        return ConvexPolygon(_convex_hull(pts))
    ang = math.atan2(axis[1], axis[0])
    pts: List[Vec2] = []
    # 端点 a 的圆（避开直边方向的重复点）
    for i in range(seg + 1):
        theta = ang + math.pi / 2 + (i / seg) * math.pi
        pts.append((a[0] + math.cos(theta) * r, a[1] + math.sin(theta) * r))
    # 端点 b 的圆
    for i in range(seg + 1):
        theta = ang - math.pi / 2 + (i / seg) * math.pi
        pts.append((b[0] + math.cos(theta) * r, b[1] + math.sin(theta) * r))
    return ConvexPolygon(_convex_hull(pts))


def transformed_polygon_shape(
    local_points: Sequence[Sequence[float]],
    position: Vec2 = (0.0, 0.0),
    rotation_degrees: float = 0.0,
    scale: Union[float, Tuple[float, float]] = 1.0,
) -> Shape:
    """本地多边形 → 世界坐标形状（旋转/缩放直接烘进顶点，绝不降级 AABB）。"""
    sx, sy = (scale, scale) if isinstance(scale, (int, float)) else scale
    rad = math.radians(float(rotation_degrees))
    cos_a, sin_a = math.cos(rad), math.sin(rad)
    pts: List[Vec2] = []
    for p in local_points:
        lx, ly = float(p[0]) * sx, float(p[1]) * sy
        wx = position[0] + lx * cos_a - ly * sin_a
        wy = position[1] + lx * sin_a + ly * cos_a
        pts.append((wx, wy))
    return polygon_shape(pts)


def _convex_hull(points: Sequence[Vec2]) -> List[Vec2]:
    """Andrew 单调链：返回顺时针凸包（世界坐标 y 向下）。"""
    pts = sorted(set(points))
    if len(pts) <= 2:
        return list(pts)

    def build() -> List[Vec2]:
        lower: List[Vec2] = []
        for p in pts:
            while len(lower) >= 2 and _cross(_sub(lower[-1], lower[-2]), _sub(p, lower[-1])) <= 0:
                lower.pop()
            lower.append(p)
        upper: List[Vec2] = []
        for p in reversed(pts):
            while len(upper) >= 2 and _cross(_sub(upper[-1], upper[-2]), _sub(p, upper[-1])) <= 0:
                upper.pop()
            upper.append(p)
        return lower[:-1] + upper[:-1]

    hull = build()
    # 单调链在标准数学坐标下返回逆时针；y 向下时需翻转成顺时针
    return list(reversed(hull))


def _ear_clip(points: Sequence[Vec2]) -> List[ConvexPolygon]:
    """顺时针凹多边形耳切三角化。"""
    pts: List[Vec2] = list(points)
    tris: List[ConvexPolygon] = []
    guard = 0
    while len(pts) > 3 and guard < len(points) * len(points) + 16:
        guard += 1
        n = len(pts)
        found = False
        for i in range(n):
            a = pts[(i - 1) % n]
            b = pts[i]
            c = pts[(i + 1) % n]
            if _cross(_sub(b, a), _sub(c, b)) <= 1e-7:
                continue
            ear = True
            for j in range(n):
                if j in ((i - 1) % n, i, (i + 1) % n):
                    continue
                if _point_in_triangle(pts[j], a, b, c):
                    ear = False
                    break
            if not ear:
                continue
            try:
                tris.append(ConvexPolygon([a, b, c]))
            except ValueError:
                continue
            del pts[i]
            found = True
            break
        if not found:
            break
    if len(pts) >= 3:
        try:
            tris.append(ConvexPolygon(pts))
        except ValueError:
            pass
    if not tris:
        raise ValueError("多边形无法三角化（可能自交或退化）")
    return tris


def _point_in_triangle(p: Vec2, a: Vec2, b: Vec2, c: Vec2) -> bool:
    d1 = _cross(_sub(b, a), _sub(p, a))
    d2 = _cross(_sub(c, b), _sub(p, b))
    d3 = _cross(_sub(a, c), _sub(p, c))
    has_neg = d1 < -_EPS or d2 < -_EPS or d3 < -_EPS
    has_pos = d1 > _EPS or d2 > _EPS or d3 > _EPS
    return not (has_neg and has_pos)


# ---------------------------------------------------------------------------
# 遍历 / 分派
# ---------------------------------------------------------------------------

def _parts(shape: Shape) -> Tuple[ConvexPolygon, ...]:
    if isinstance(shape, CompoundShape):
        return shape.parts
    if isinstance(shape, ConvexPolygon):
        return (shape,)
    raise TypeError("不支持的形状类型: %r" % type(shape))


def bounds(shape: Shape) -> AABB:
    if isinstance(shape, (ConvexPolygon, CompoundShape)):
        return shape.bbox
    raise TypeError("不支持的形状类型: %r" % type(shape))


def _center(shape: Shape) -> Vec2:
    b = bounds(shape)
    return ((b.left + b.right) * 0.5, (b.top + b.bottom) * 0.5)


# ---------------------------------------------------------------------------
# overlap
# ---------------------------------------------------------------------------

def _convex_overlap(a: ConvexPolygon, b: ConvexPolygon) -> Optional[Manifold]:
    if not a.bbox.intersects(b.bbox):
        return None

    best_depth = math.inf
    best_axis: Optional[Vec2] = None

    for axis in a.normals + b.normals:
        if abs(axis[0]) < _EPS and abs(axis[1]) < _EPS:
            continue
        amin, amax = _project(a.points, axis)
        bmin, bmax = _project(b.points, axis)
        overlap_depth = min(amax, bmax) - max(amin, bmin)
        if overlap_depth <= _EPS_SAT:
            return None
        if overlap_depth < best_depth:
            best_depth = overlap_depth
            best_axis = axis

    if best_axis is None:
        return None

    # 统一方向：从 b 指向 a
    axis = best_axis
    if _dot(_sub(a.center, b.center), axis) < 0:
        axis = (-axis[0], -axis[1])
    return Manifold(axis, best_depth)


def overlap_all(a: Shape, b: Shape) -> List[Manifold]:
    """返回所有凸块之间的穿透信息（Contact 掩码阶段按部件记录用）。"""
    if not bounds(a).intersects(bounds(b)):
        return []
    out: List[Manifold] = []
    for pa in _parts(a):
        for pb in _parts(b):
            m = _convex_overlap(pa, pb)
            if m is not None:
                out.append(m)
    return out


def overlap(a: Shape, b: Shape) -> Optional[Manifold]:
    """返回穿透最深的一组法线 + 深度；不相交返回 None。"""
    if not bounds(a).intersects(bounds(b)):
        return None
    best: Optional[Manifold] = None
    for pa in _parts(a):
        for pb in _parts(b):
            m = _convex_overlap(pa, pb)
            if m is None:
                continue
            if best is None or m.depth > best.depth:
                best = m
    return best


def intersects(a: Shape, b: Shape) -> bool:
    if not bounds(a).intersects(bounds(b)):
        return False
    for pa in _parts(a):
        for pb in _parts(b):
            if _convex_overlap(pa, pb) is not None:
                return True
    return False


# ---------------------------------------------------------------------------
# sweep：A 沿 delta 线性平移，求首次接触
# ---------------------------------------------------------------------------

def _convex_sweep(a: ConvexPolygon, b: ConvexPolygon, delta: Vec2) -> Optional[SweepHit]:
    if _length(delta) < _EPS:
        return None
    if not _aabb_sweep_intersects(a.bbox, b.bbox, delta):
        return None

    enter_time = -math.inf
    exit_time = math.inf
    enter_axis: Optional[Vec2] = None

    for axis in a.normals + b.normals:
        if abs(axis[0]) < _EPS and abs(axis[1]) < _EPS:
            continue
        amin, amax = _project(a.points, axis)
        bmin, bmax = _project(b.points, axis)
        speed = _dot(axis, delta)
        if abs(speed) < _EPS:
            # 该轴上始终分离
            if amax <= bmin + _EPS_SAT or bmax <= amin + _EPS_SAT:
                return None
            continue
        # a 区间沿轴以 speed 平移；求与 b 区间重叠的时间窗口
        t1 = (bmin - amax) / speed
        t2 = (bmax - amin) / speed
        if t1 > t2:
            t1, t2 = t2, t1
        if t1 > enter_time:
            enter_time = t1
            enter_axis = axis
        if t2 < exit_time:
            exit_time = t2
        if enter_time > exit_time:
            return None

    if enter_axis is None:
        return None
    if exit_time < 0.0 or enter_time > 1.0 + _EPS_SAT:
        return None
    time = max(0.0, enter_time)
    if time > 1.0:
        time = 1.0

    normal = enter_axis
    # 接触法线应与移动方向相反（把 a 往回推）
    if _dot(normal, delta) > 0:
        normal = (-normal[0], -normal[1])
    # 退化：法线与移动方向垂直时，按两形状中心方向定向
    if abs(_dot(normal, delta)) < _EPS:
        if _dot(_sub(a.center, b.center), normal) < 0:
            normal = (-normal[0], -normal[1])

    move = _mul(delta, time)
    # 接触点：a 在 -normal 方向上的支撑点
    support = min(a.points, key=lambda p: _dot(p, normal))
    point = _add(support, move)
    return SweepHit(time, normal, point)


def _aabb_sweep_intersects(a: AABB, b: AABB, delta: Vec2) -> bool:
    """扫掠 A 的包围盒（A 平移 delta）是否可能碰到 B；用于快速剔除。"""
    t_min = 0.0
    t_max = 1.0
    for lo_a, hi_a, lo_b, hi_b, d in (
        (a.left, a.right, b.left, b.right, delta[0]),
        (a.top, a.bottom, b.top, b.bottom, delta[1]),
    ):
        if abs(d) < _EPS:
            if hi_a < lo_b or hi_b < lo_a:
                return False
            continue
        t1 = (lo_b - hi_a) / d
        t2 = (hi_b - lo_a) / d
        if t1 > t2:
            t1, t2 = t2, t1
        t_min = max(t_min, t1)
        t_max = min(t_max, t2)
        if t_min > t_max:
            return False
    return True


def sweep(a: Shape, b: Shape, delta: Vec2) -> Optional[SweepHit]:
    """a 沿 delta 平移时与 b 的首次接触；没有接触返回 None。

    只处理线性平移（不含旋转）。若起始时已经重叠，返回 time=0，
    调用方应先做 depenetration（P5 move_and_slide 会统一处理）。
    """
    if not _aabb_sweep_intersects(bounds(a), bounds(b), delta):
        return None
    best: Optional[SweepHit] = None
    for pa in _parts(a):
        for pb in _parts(b):
            hit = _convex_sweep(pa, pb, delta)
            if hit is None:
                continue
            if best is None or hit.time < best.time:
                best = hit
    return best


# ---------------------------------------------------------------------------
# raycast
# ---------------------------------------------------------------------------

def _convex_raycast(poly: ConvexPolygon, origin: Vec2, direction: Vec2,
                    max_distance: float) -> Optional[RayHit]:
    # 包围盒粗筛
    if not _ray_aabb_hit(origin, direction, max_distance, poly.bbox):
        return None

    t_enter = -math.inf
    t_exit = math.inf
    enter_normal: Optional[Vec2] = None
    exit_normal: Optional[Vec2] = None

    n = len(poly.points)
    for i in range(n):
        p = poly.points[i]
        normal = poly.normals[i]
        num = _dot(normal, _sub(origin, p))
        den = _dot(normal, direction)
        if abs(den) < _EPS:
            # 射线平行于该边：在外侧则不可能命中
            if num > _EPS:
                return None
            continue
        t = -num / den
        if den < 0:
            # 从外侧进入该半平面
            if t > t_enter:
                t_enter = t
                enter_normal = normal
        else:
            if t < t_exit:
                t_exit = t
                exit_normal = normal

    if t_enter > t_exit:
        return None
    if t_exit < 0.0:
        return None
    if t_enter > max_distance:
        return None

    if t_enter >= 0.0:
        distance = t_enter
        normal = enter_normal or exit_normal or (0.0, 0.0)
    else:
        # 起点在形状内部：返回出射面
        distance = t_exit
        normal = exit_normal or (0.0, 0.0)
    if distance > max_distance:
        return None
    return RayHit(distance, _add(origin, _mul(direction, distance)), normal)


def _ray_aabb_hit(origin: Vec2, direction: Vec2, max_distance: float, box: AABB) -> bool:
    t_min = 0.0
    t_max = max_distance
    for lo, hi, o, d in (
        (box.left, box.right, origin[0], direction[0]),
        (box.top, box.bottom, origin[1], direction[1]),
    ):
        if abs(d) < _EPS:
            if o < lo or o > hi:
                return False
            continue
        t1 = (lo - o) / d
        t2 = (hi - o) / d
        if t1 > t2:
            t1, t2 = t2, t1
        t_min = max(t_min, t1)
        t_max = min(t_max, t2)
        if t_min > t_max:
            return False
    return True


def raycast(shape: Shape, origin: Vec2, direction: Vec2,
            max_distance: float = math.inf) -> Optional[RayHit]:
    """射线与形状的最近命中；direction 内部会归一化。"""
    dir_len = _length(direction)
    if dir_len < _EPS:
        return None
    unit = (direction[0] / dir_len, direction[1] / dir_len)
    best: Optional[RayHit] = None
    for part in _parts(shape):
        hit = _convex_raycast(part, origin, unit, max_distance)
        if hit is None:
            continue
        if best is None or hit.distance < best.distance:
            best = hit
    return best


# ---------------------------------------------------------------------------
# inflate
# ---------------------------------------------------------------------------

def _line_intersection(p1: Vec2, d1: Vec2, p2: Vec2, d2: Vec2) -> Optional[Vec2]:
    den = _cross(d1, d2)
    if abs(den) < 1e-9:
        return None
    diff = _sub(p2, p1)
    t = _cross(diff, d2) / den
    return _add(p1, _mul(d1, t))


def _inflate_convex(poly: ConvexPolygon, amount: float) -> ConvexPolygon:
    if abs(amount) < _EPS:
        return poly
    if amount > 0:
        return _round_offset(poly, amount)
    return _miter_shrink(poly, amount)


def _round_offset(poly: ConvexPolygon, amount: float) -> ConvexPolygon:
    """正向膨胀：把每个顶点换成半径 amount 的圆弧采样点。

    直接 miter（两条偏移线求交）在 90° 角会得到 1.414*amount 的尖点，
    再靠 clamp 收回来又会让整条边缩水；圆弧采样才是真正的「膨胀 amount」。
    """
    pts = poly.points
    normals = poly.normals
    n = len(pts)
    result: List[Vec2] = []
    max_step = math.pi / 4.0
    for i in range(n):
        center = pts[i]
        a0 = math.atan2(normals[(i - 1) % n][1], normals[(i - 1) % n][0])
        a1 = math.atan2(normals[i][1], normals[i][0])
        sweep = (a1 - a0) % math.tau
        # 凸多边形外角必定在 (0, π)；浮点抖动时退化为单点
        if sweep > math.pi:
            sweep -= math.tau
        steps = max(1, int(math.ceil(abs(sweep) / max_step)))
        for k in range(steps + 1):
            ang = a0 + sweep * (k / steps)
            result.append((center[0] + math.cos(ang) * amount,
                           center[1] + math.sin(ang) * amount))
    try:
        return ConvexPolygon(result)
    except ValueError:
        return _miter_shrink(poly, amount)


def _miter_shrink(poly: ConvexPolygon, amount: float) -> ConvexPolygon:
    """负向收缩 / 兜底：沿用边偏移 + 交点，尖角限制在 4*|amount| 内。"""
    pts = poly.points
    n = len(pts)
    result: List[Vec2] = []
    limit = abs(amount) * _MITER_LIMIT
    for i in range(n):
        prev = (i - 1) % n
        p_prev = pts[prev]
        p_cur = pts[i]
        n_prev = poly.normals[prev]
        n_cur = poly.normals[i]

        line_p1 = _add(p_prev, _mul(n_prev, amount))
        line_p2 = _add(p_cur, _mul(n_cur, amount))
        d_prev = _sub(p_cur, p_prev)
        d_cur = _sub(pts[(i + 1) % n], p_cur)
        new_p = _line_intersection(line_p1, d_prev, line_p2, d_cur)

        if new_p is None:
            # 平行边（理论上是直线共线）：直接沿法线外推
            new_p = _add(p_cur, _mul(_normalize(_add(n_prev, n_cur)), amount))

        if limit > _EPS:
            delta = _sub(new_p, p_cur)
            dist = _length(delta)
            if dist > limit:
                new_p = _add(p_cur, _mul(delta, limit / dist))
        result.append(new_p)

    try:
        return ConvexPolygon(result)
    except ValueError:
        # 收缩过度导致退化时，退回按中心缩放
        cx, cy = poly.center
        scale = 1.0
        w = poly.bbox.width
        h = poly.bbox.height
        base = min(w, h) * 0.5
        if base > _EPS:
            scale = max(0.01, (base + amount) / base)
        scaled = [((x - cx) * scale + cx, (y - cy) * scale + cy) for x, y in pts]
        return ConvexPolygon(scaled)


def inflate(shape: Shape, amount: float) -> Shape:
    """沿外法线整体膨胀 amount（负数为收缩）；保持凸块结构不变。"""
    if isinstance(shape, CompoundShape):
        return CompoundShape(_inflate_convex(p, amount) for p in shape.parts)
    return _inflate_convex(shape, amount)


# ---------------------------------------------------------------------------
# 便捷判断
# ---------------------------------------------------------------------------

def point_inside(shape: Shape, point: Vec2) -> bool:
    for part in _parts(shape):
        if _point_in_convex(part.points, point):
            return True
    return False


def _point_in_convex(points: Sequence[Vec2], point: Vec2) -> bool:
    n = len(points)
    for i in range(n):
        a = points[i]
        b = points[(i + 1) % n]
        if _cross(_sub(b, a), _sub(point, a)) < -_EPS:
            return False
    return True


def closest_point(shape: Shape, point: Vec2) -> Vec2:
    """形状表面（或内部）离 point 最近的点，用于命中点/距离查询。"""
    best: Optional[Vec2] = None
    best_d2 = math.inf
    for part in _parts(shape):
        if _point_in_convex(part.points, point):
            return point
        pts = part.points
        n = len(pts)
        for i in range(n):
            a = pts[i]
            b = pts[(i + 1) % n]
            q = _closest_on_segment(point, a, b)
            d2 = (q[0] - point[0]) ** 2 + (q[1] - point[1]) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best = q
    return best if best is not None else point


def _closest_on_segment(p: Vec2, a: Vec2, b: Vec2) -> Vec2:
    ab = _sub(b, a)
    length_sq = _dot(ab, ab)
    if length_sq < _EPS:
        return a
    t = _dot(_sub(p, a), ab) / length_sq
    t = max(0.0, min(1.0, t))
    return _add(a, _mul(ab, t))
