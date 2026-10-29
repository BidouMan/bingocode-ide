"""图像/碰撞几何纯函数（无业务状态，可单测）。

什么时候来这里改：碰撞多边形三角化、MTV 分离轴、图片内容框/像素碰撞、可玩区域边界。
规则：这里只放纯几何计算，不要读写游戏状态（缓存除外），不要 print 协议。"""
import math
import os
from PIL import Image
from models.shape_kernel import ConvexPolygon
import engine_state as st


def _image_bbox_info(path):
    """读取图片尺寸与非透明内容框（按路径+修改时间缓存，批量创建角色不必反复读盘）

    返回 (原宽, 原高, 内容框, 内容宽, 内容高, 横向视觉偏移, 纵向视觉偏移)；
    图片读不出来返回 None（调用方按 50x50 兜底）。
    """
    try:
        stat_info = os.stat(path)
        key = (os.path.abspath(path), stat_info.st_mtime_ns, stat_info.st_size)
    except OSError:
        return None

    info = st._IMAGE_BBOX_CACHE.get(key)
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
    st._IMAGE_BBOX_CACHE[key] = info
    return info


def _playable_bounds():
    """游戏可玩区域 = 地图矩形（width×tile_size × height×tile_size）

    边界碰撞与边界类 API 必须都用这一套边界。不能用 world_bounds：
    它包含绘制图层四周的出血区与超出地图的素材（40×30 的地图可能算出 1280×960），
    角色会被挡在屏幕外，看起来就像"走出去了"。
    没有地图时退回 640×480 舞台。
    """
    if st._CURRENT_MAP:
        ts = st._CURRENT_MAP.get("tile_size", 16)
        return {
            "left": 0,
            "top": 0,
            "right": st._CURRENT_MAP["width"] * ts,
            "bottom": st._CURRENT_MAP["height"] * ts,
        }
    return {"left": 0, "top": 0, "right": st._SCREEN_WIDTH, "bottom": st._SCREEN_HEIGHT}


def _screen_bounds():
    """当前画面在世界坐标中的矩形（固定 640×480 的窗口，中心跟着相机走）

    与 _playable_bounds（地图矩形）不是一回事：地图再大，玩家也只能看到窗口这一块。
    判断「看不看得见」（如 is_out_screen 出屏删除）必须用这一套；
    edge_bounce / 边界碰撞这类「地图范围」限制仍用 _playable_bounds。
    """
    half_w = st._SCREEN_WIDTH / 2.0
    half_h = st._SCREEN_HEIGHT / 2.0
    return {
        "left": st._CAMERA_X - half_w,
        "top": st._CAMERA_Y - half_h,
        "right": st._CAMERA_X + half_w,
        "bottom": st._CAMERA_Y + half_h,
    }


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
