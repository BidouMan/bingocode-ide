"""地图运行时：加载/清理地图、瓦片渲染、地图物理碰撞、感应区（sensor）事件。

什么时候来这里改：load_map 失败、地图不显示、瓦片图层/视差、地图碰撞、sensor 进出触发。
标记与射线查询不在这里，见 markers.py。"""
import json
import os
import sys
from models.coords import set_user_origin_y, to_world_x, to_world_y
from models.map_model import MapModel
from models.shape_kernel import CompoundShape, ConvexPolygon, intersects, point_inside, polygon_shape
from models.static_index import SENSOR_EXIT_EPS, StaticEntry, build_world
from collision_geometry import _collision_polygon_parts, _image_collision_world_polygons, _shape_convex_parts
from game_control import _safe_call
from markers import MapMarkerRef, _map_marker_list, get_marker, get_markers
import engine_state as st


def _shape_one_way(raw):
    """形状的单向碰撞参数 → (one_way, dir_x, dir_y, margin)。

    dir 是「触发碰撞的运动方向」（世界坐标，y 向下）：
      (0, 1)  下落时挡住 = 只能从上方踩住（默认）
      (0, -1) 上升时挡住 = 只能从下方顶住
      (1, 0)  向右走时挡住 = 从左侧挡住
      (-1, 0) 向左走时挡住 = 从右侧挡住

    旧存档没有 oneWay 字段时，兼容 collisionType == "跳板"（等价于方向向下、margin 0）。
    结果缓存到 poly 上，避免每帧重复解析。
    """
    cached = raw.get("_one_way")
    if cached is not None:
        return cached

    flag = raw.get("oneWay")
    if flag is None:
        flag = raw.get("collisionType") == "跳板"

    if not flag:
        result = (False, 0.0, 1.0, 0.0)
    else:
        try:
            dx = float(raw.get("oneWayDirX") or 0.0)
            dy = float(raw.get("oneWayDirY") or 0.0)
        except (TypeError, ValueError):
            dx, dy = 0.0, 0.0
        if dx == 0.0 and dy == 0.0:
            dx, dy = 0.0, 1.0
        # 只支持轴对齐：取绝对值大的分量，另一轴归零
        if abs(dx) >= abs(dy):
            dx = 1.0 if dx > 0 else -1.0
            dy = 0.0
        else:
            dx = 0.0
            dy = 1.0 if dy > 0 else -1.0
        try:
            margin = max(0.0, float(raw.get("oneWayMargin") or 0.0))
        except (TypeError, ValueError):
            margin = 0.0
        result = (True, dx, dy, margin)

    raw["_one_way"] = result
    return result


def _build_static_world(map_data, map_model):
    """把地图里的静态碰撞几何烘焙成 solid / sensor 双索引。

    只在地图加载时执行一次：
      - 形状层：按 kind 进入阻挡索引 / 感应索引；tag 单独建查找表
      - 图像碰撞：静态图像的碰撞体，进入阻挡索引
      - 图块碰撞：实心图块，进入阻挡索引

    烘焙失败（极少见的坏数据）时返回 None，碰撞路径会回退到全表扫描，不影响运行。
    """
    entries = []
    # 图块标签：tag → 格子集合（与碰撞无关，只给 is_touch 用）
    tile_tags = {}
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
                one_way, ow_dx, ow_dy, ow_margin = _shape_one_way(poly)
                entries.append(StaticEntry(
                    shape=shape,
                    source="shape",
                    kind=poly.get("kind", "solid"),
                    tag=poly.get("tag", "") or "",
                    # 单向形状对外仍报告「跳板」，保持 raycast 等 API 的既有语义
                    collision_type="跳板" if one_way else poly.get("collisionType", "墙体"),
                    one_way=one_way,
                    one_way_dir=(ow_dx, ow_dy),
                    one_way_margin=ow_margin,
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
                image_type = image.get("collisionType", "图像")
                entries.append(StaticEntry(
                    shape=shape,
                    source="image",
                    kind="solid",
                    collision_type=image_type,
                    # 图像沿用的「跳板」类型：等价于只能从上方踩住
                    one_way=(image_type == "跳板"),
                    one_way_dir=(0.0, 1.0),
                    one_way_margin=0.0,
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

            # 图块标签与碰撞无关：没有碰撞的图块也能挂「水」这类标签，
            # 所以要在碰撞判断之前收集（同一格子出现在多个图层时去重）
            tile_tag = map_model.get_tile_tag(resource_index, tile_index)
            if tile_tag:
                tile_tags.setdefault(tile_tag, set()).add((tile_x, tile_y))

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

            tile_type = map_model.get_tile_collision_type(resource_index, tile_index)
            entries.append(StaticEntry(
                shape=shape,
                source="tile",
                kind="solid",
                collision_type=tile_type,
                # 图块的「跳板」类型：等价于只能从上方踩住，沿用原来的 0.5px 容差
                one_way=(tile_type == "跳板"),
                one_way_dir=(0.0, 1.0),
                one_way_margin=0.5,
                layer_index=layer_index,
                ref=(tile_x, tile_y),
            ))

    return build_world(entries, tile_tags)


def load_map(map_name):
    """
    加载并显示地图

    Args:
        map_name: 地图名称（不含扩展名）
    """

    # 清理之前的地图
    _clear_map()

    try:
        # 从项目根目录的assets/maps文件夹读取地图文件
        # 尝试加载二进制文件（通过检查.info文件），如果不存在再回退到JSON文件
        # 使用当前工作目录（项目根目录）
        map_dir = os.path.join(os.getcwd(), "assets", "maps", map_name)
        st._MAP_DIR = map_dir
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
                        one_way, ow_dx, ow_dy, ow_margin = _shape_one_way(poly_raw)
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
                            # 单向碰撞：方向 + 厚度（旧存档的「跳板」在这里统一成方向向下）
                            "oneWay": one_way,
                            "oneWayDirX": ow_dx,
                            "oneWayDirY": ow_dy,
                            "oneWayMargin": ow_margin,
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

        st._CURRENT_MAP = map_data
        st._MAP_MODEL = MapModel(tilesets)

        # P3：静态几何烘焙一次，后续碰撞/感应/射线查询共用
        try:
            st._CURRENT_MAP["static_world"] = _build_static_world(st._CURRENT_MAP, st._MAP_MODEL)
        except Exception as exc:  # 坏数据不应让整张地图打不开
            st._CURRENT_MAP["static_world"] = None
            print("static index build failed: %s" % exc, file=sys.stderr)

        tile_size = st._CURRENT_MAP.get("tile_size", 16)
        map_width_px = st._CURRENT_MAP["width"] * tile_size
        map_height_px = st._CURRENT_MAP["height"] * tile_size

        # 用户坐标原点跟随地图高度：y=0 永远在地图底部。
        # 单屏地图（高 480）与旧行为完全一致；更高的地图不再出现负 y。
        set_user_origin_y(map_height_px)

        # 计算地图的世界像素边界（world_bounds）
        all_tile_positions = []
        all_image_bounds = []
        for layer in st._CURRENT_MAP.get("layers", []):
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
        st._CURRENT_MAP["world_bounds"] = world_bounds

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
        if not st._CURRENT_MAP:
            return False
        static_world = st._CURRENT_MAP.get("static_world")
        if static_world is None:
            return False
        wx = to_world_x(float(x))
        wy = to_world_y(float(y))
        for entry in static_world.solid.query_point(wx, wy):
            if point_inside(entry.shape, (wx, wy)):
                return True
        return False

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

    # 删除地图瓦片精灵
    for sprite_id in list(st._MAP_SPRITES.keys()):
        packet = {"type": "DELETE", "id": sprite_id}
        print(json.dumps(packet))
        del st._MAP_SPRITES[sprite_id]

    # 地图卸载：撤销自动相机跟随目标（代码 camera_follow() 的仍保留）
    if st._AUTO_CAMERA_TARGET is not None and st._FOLLOW_TARGET is st._AUTO_CAMERA_TARGET:
        st._FOLLOW_TARGET = None
    st._AUTO_CAMERA_TARGET = None

    st._CURRENT_MAP = None
    st._MAP_DIR = None
    st._MAP_SPRITES = {}
    st._RENDERED_TILES.clear()
    # 卸载地图后用户坐标原点退回单屏舞台
    set_user_origin_y(st._SCREEN_HEIGHT)


def _handle_physics_collision():
    """处理物理碰撞检测和位移修正"""

    if not st._CURRENT_MAP:
        return

    # 地图属性「禁止下滑」：开启时站在斜坡上不下滑（缺省视为开启）
    stop_on_slope = st._CURRENT_MAP.get("stopOnSlope", True)

    # 遍历所有精灵
    for sprite in st._SPRITES.values():
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
                if sprite._smart_jump_key not in st._PRESSED_KEYS_FRAME:
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

        if st._CURRENT_MAP.get("gravity", False) and sprite._gravity:
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

    只查感应索引（solid 不参与），每个标签带缓冲带地判定：
      - 进入：外扩 SENSOR_EPS 后相交
      - 离开：外扩更大的 SENSOR_EXIT_EPS 后仍不相交
      - 从无到有 → 触发一次 on_sensor_enter；从有到无 → 触发一次 on_sensor_exit
    缓冲带让「站在阈值附近轻微抖动」不会反复触发进入/离开。
    """
    if not st._CURRENT_MAP:
        return
    static_world = st._CURRENT_MAP.get("static_world")
    if static_world is None:
        return

    for sprite in list(st._SPRITES.values()):
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

        # 感应索引宽相：查询盒按「离开判定」的最大外扩量放大，
        # 保证还处在缓冲带里的感应形状仍能进候选（用于判断是否真正离开）
        entries = static_world.sensors.query_rect(
            rect[0] - SENSOR_EXIT_EPS, rect[1] - SENSOR_EXIT_EPS,
            rect[2] + SENSOR_EXIT_EPS, rect[3] + SENSOR_EXIT_EPS,
        )

        active = sprite._sensor_active_tags
        touched = set()
        if entries:
            shape = sprite._get_collision_shape()
            for entry in entries:
                tag = entry.tag
                if tag not in wanted or tag in touched:
                    continue
                # 已在区域内：用更大的外扩形状判断是否还留在缓冲带内
                probe = entry.exit_probe_shape if tag in active else entry.probe_shape
                if intersects(shape, probe):
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

    if not st._CURRENT_MAP:
        return

    tile_size = st._CURRENT_MAP["tile_size"]

    batch_commands = []

    # 遍历所有图层
    for layer_idx, layer in enumerate(st._CURRENT_MAP["layers"]):
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
                        map_dir = st._MAP_DIR if st._MAP_DIR else os.getcwd()
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
                    if cache_key in st._IMAGE_SIZE_CACHE:
                        original_width, original_height = st._IMAGE_SIZE_CACHE[cache_key]
                    else:
                        try:
                            from PIL import Image

                            with Image.open(image_path) as img:
                                original_width, original_height = img.size
                            st._IMAGE_SIZE_CACHE[cache_key] = (original_width, original_height)
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
                    tile_id_int, st._CURRENT_MAP["tile_sets"]
                )

                if resource_index >= len(st._CURRENT_MAP["tile_sets"]):
                    continue

                sprite_id = f"tile_{layer_idx}_{x}_{y}"
                tile_key = (layer_idx, x, y)

                # 获取瓦片集的具体瓦片大小（图块实际大小）
                tile_set_size = tile_size  # 默认使用地图的全局tile_size
                if resource_index < len(st._CURRENT_MAP["tile_sets"]):
                    tile_set = st._CURRENT_MAP["tile_sets"][resource_index]
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
                st._RENDERED_TILES.add(tile_key)

    # 批量渲染：一次性发送所有可见瓦片和图像的渲染指令
    if batch_commands:
        # 处理瓦片集信息，确保包含完整的图片路径
        processed_tile_sets = []
        if st._CURRENT_MAP.get("tile_sets"):
            for tile_set in st._CURRENT_MAP["tile_sets"]:
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
            st._MAP_SPRITES[tile_data["id"]] = tile_data
