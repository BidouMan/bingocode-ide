"""Sprite 物理与碰撞（Mixin）：解算、move_and_slide、贴地/顶墙判断、is_touch 系列。

什么时候来这里改：角色卡进地形、穿过瓦片、斜坡/单向平台、碰撞抖动、接触方向判断。
类结构：SpritePhysicsMixin 由 sprite.Sprite 继承，方法内可直接用 self 的字段。"""
import math
from models.shape_kernel import ConvexPolygon, intersects, overlap as shape_overlap, point_inside, sweep as shape_sweep
from models.static_index import SENSOR_EPS
from collision_geometry import _aabb_polygon_mtv, _image_collision_world_polygons, _playable_bounds, _screen_bounds, _shape_convex_parts, _sign
from input_api import mouse
from map_runtime import _find_tileset_for_gid
from markers import _parse_direction_world, raycast as _raycast
import engine_state as st


class SpritePhysicsMixin:
    """Sprite 物理与碰撞实现（由 sprite.Sprite 继承；方法内 self 即 Sprite 实例）。"""

    # ---------- 运动模块 ----------
    def _collision_layer_correction(self, layer, axis, layer_index=None):
        """形状层（世界坐标多边形）对当前精灵的轴分离位移量；没有碰撞返回 None"""
        sprite_rect = self._get_hitbox_rect()
        if not sprite_rect:
            return None

        # 静态索引宽相：只有包围盒可能相交的形状才进入精确 SAT。
        # 解算顺序仍完全沿用 layer["polygons"]，结果与全表扫描一致。
        candidate_ids = None
        static_world = st._CURRENT_MAP.get("static_world") if st._CURRENT_MAP else None
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


    def _depenetrate(self):
        """把角色从静态实心几何里推出；返回是否发生过推出。

        用于角色生成/传送/上一帧修正残留导致嵌墙的场景：
          - 只查 solid 索引，感应与单向平台不参与（单向平台不能从下方顶人）
          - 每轮取穿透最深的一组，沿法线推出 depth + 少量皮肤
          - 迭代若干轮，处理同时嵌在两个障碍里的极端情况
        """
        if self._collision_disabled or not st._CURRENT_MAP:
            return False
        static_world = st._CURRENT_MAP.get("static_world")
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


    def move_and_slide(self, dx, dy, axis_order="xy", resolve_x=True, resolve_y=True,
                       depenetrate=True):
        """唯一位移入口：先 depenetrate，再按轴移动并解算碰撞。

        axis_order:
          - "xy"：先横向后纵向（角色代码 move()/add_x 等）
          - "yx"：先纵向后横向（重力物理步，与旧行为一致）
        resolve_x/resolve_y=False 时对应轴不移动也不解算（set_x/add_x 等单轴操作）。
        位移超过 _MAX_MOVE_STEP 时自动拆成多个子步，避免隧道效应。
        """
        if self._collision_disabled or not st._CURRENT_MAP:
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

        # 禁用碰撞：完全不参与地形/边界阻挡（碰到检测仍按碰撞盒工作）
        if self._collision_disabled:
            return

        if not st._CURRENT_MAP:
            return

        tile_size = st._CURRENT_MAP.get("tile_size", 16)

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

        # 检测所有图层中的形状层与图像碰撞（图块在下方统一走 static_world）
        for layer_index, layer in enumerate(st._CURRENT_MAP.get("layers", [])):
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

        # --- 图块碰撞 ---
        # 几何统一取自 static_world（与 depenetrate / sweep_test / raycast 同源），
        # 不再直接读 MapModel：否则同一块图块在两处各算一套，解算与推出可能互相打架。
        if axis == "x":
            # X 轴探测盒上下各缩进 1 像素：脚正好贴地/头正好贴天花板时不算横向碰撞，
            # 同时避免缩进过大导致「只压到墙边一条」时 x 轴看不见墙
            probe_rect = [
                sprite_rect[0],
                sprite_rect[1] + 1,
                sprite_rect[2],
                sprite_rect[3] - 1,
            ]
        else:
            # Y 轴探测盒左右各多 2 像素：x 轴修正把角色往外推一点点后也不会「踩空」
            probe_rect = [
                sprite_rect[0] - 2,
                sprite_rect[1],
                sprite_rect[2] + 2,
                sprite_rect[3],
            ]

        def apply_tile(tile_left, tile_top, tile_right, tile_bottom, is_one_way):
            """单个图块的轴向修正（索引路径与 MapModel 回退路径共用）。"""
            nonlocal sprite_rect
            if is_one_way and axis == "x":
                return
            if is_one_way and self._drop_through:
                return

            overlap_left = max(sprite_rect[0], tile_left)
            overlap_top = max(sprite_rect[1], tile_top)
            overlap_right = min(sprite_rect[2], tile_right)
            overlap_bottom = min(sprite_rect[3], tile_bottom)
            if overlap_right - overlap_left <= 0 or overlap_bottom - overlap_top <= 0:
                return

            if is_one_way and axis == "y":
                # 单向平台：只有从上方落下来才踩得住
                if self._prev_bottom_y <= tile_top:
                    rect = self._get_hitbox_rect()
                    if rect:
                        delta = tile_top - rect[3] - 0.05
                        consider(delta, delta, "ground")
                return

            if axis == "x":
                # 台阶自动上台：站在地面时，抬升不超过 _MAX_STEP_UP 的台阶直接踩上去
                step_up = sprite_rect[3] - tile_top
                if self._on_ground and 0 < step_up <= self._MAX_STEP_UP:
                    self._y = tile_top - (sprite_rect[3] - self._y) - 0.05
                    # 抬脚后必须刷新碰撞盒，否则一排相邻台阶会被连续抬多次
                    sprite_rect = self._get_hitbox_rect() or sprite_rect
                    return

                dist_to_right = abs(sprite_rect[0] - tile_right)
                dist_to_left = abs(sprite_rect[2] - tile_left)
                if dist_to_right < dist_to_left:
                    correction = tile_right - sprite_rect[0] + 0.05
                else:
                    correction = tile_left - sprite_rect[2] - 0.05
                consider(correction, correction)
                return

            # y 轴
            rect = self._get_hitbox_rect()
            if not rect:
                return

            if direction > 0:
                # 下落：脚原本在顶面之上才算落地。
                # 从侧面蹭到墙/墙顶时这里直接跳过，交给 x 轴推出，
                # 避免把正在上升的角色「吸」到墙顶并误判成着地
                if self._prev_bottom_y > tile_top + 0.5:
                    return
                delta = tile_top - rect[3] - 0.05
                consider(delta, delta, "ground")
            elif direction < 0:
                # 上升：头原本在底面之下才算撞天花板。
                # 从侧面蹭到墙时跳过，跳跃不会被墙角打断
                if self._prev_top_y < tile_bottom - 0.5:
                    return
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

        static_world = st._CURRENT_MAP.get("static_world")
        if static_world is not None:
            for entry in static_world.solid.query_rect(*probe_rect):
                if entry.source != "tile":
                    continue
                bbox = entry.bbox
                apply_tile(
                    bbox.left, bbox.top, bbox.right, bbox.bottom,
                    entry.collision_type == "跳板",
                )
        elif st._MAP_MODEL:
            # 索引构建失败时的兼容路径：仍按 MapModel 直接查图块（行为与旧版一致）
            min_tile_x = math.floor(probe_rect[0] / tile_size)
            max_tile_x = math.floor(probe_rect[2] / tile_size)
            min_tile_y = math.floor(probe_rect[1] / tile_size)
            max_tile_y = math.floor(probe_rect[3] / tile_size)
            for layer in st._CURRENT_MAP.get("layers", []):
                tiles = layer.get("tiles") or {}
                for tile_x in range(min_tile_x, max_tile_x + 1):
                    for tile_y in range(min_tile_y, max_tile_y + 1):
                        tile_id = tiles.get((tile_x, tile_y))
                        if not tile_id or tile_id <= 0:
                            continue
                        resource_index, tile_index = _find_tileset_for_gid(
                            int(tile_id), st._CURRENT_MAP["tile_sets"]
                        )
                        if not st._MAP_MODEL.get_tile_collision(resource_index, tile_index):
                            continue
                        is_one_way = (
                            st._MAP_MODEL.get_tile_collision_type(resource_index, tile_index)
                            == "跳板"
                        )
                        collision_shape = st._MAP_MODEL.get_tile_collision_shape(
                            resource_index, tile_index
                        )
                        if collision_shape and "points" in collision_shape:
                            # 编辑器保存的是归一化坐标(0~1)，需乘以 tile_size 转为像素
                            world_points = [
                                (
                                    tile_x * tile_size + p[0] * tile_size,
                                    tile_y * tile_size + p[1] * tile_size,
                                )
                                for p in collision_shape["points"]
                            ]
                            apply_tile(
                                min(p[0] for p in world_points),
                                min(p[1] for p in world_points),
                                max(p[0] for p in world_points),
                                max(p[1] for p in world_points),
                                is_one_way,
                            )
                        else:
                            apply_tile(
                                tile_x * tile_size,
                                tile_y * tile_size,
                                (tile_x + 1) * tile_size,
                                (tile_y + 1) * tile_size,
                                is_one_way,
                            )

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
        # 关闭时保持自由移动，edge_bounce/is_touch_edge/
        # 子弹出界销毁等边界 API 才能正常工作
        if not st._CURRENT_MAP.get("boundaryCollision", st._CURRENT_MAP.get("gravity", False)):
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


    def is_out_screen(self):
        """
        完全出屏检测：只有当角色整体（所有像素）都离开 640×480 的游戏画面时才返回 True

        用的是「画面」而不是「地图」：地图比画面大时，角色飞出一屏就会被判出屏，
        不会一直飞到地图另一头才销毁；开启相机跟随时，画面中心跟着角色移动。
        """
        # 获取当前精准包围盒 [left, top, right, bottom]
        rect = self._get_hitbox_rect()
        if not rect:
            return False

        bounds = _screen_bounds()

        # 逻辑判断：
        # rect[2] < left: 右边缘比画面左边还小（在画面左侧完全出屏）
        # rect[0] > right: 左边缘比画面右边还大（在画面右侧完全出屏）
        # rect[3] < top: 下边缘比画面顶边还小（在画面上方完全出屏）
        # rect[1] > bottom: 上边缘比画面底边还大（在画面下方完全出屏）
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
        # 局部导入：sprite 模块要继承本 Mixin，模块级导入会形成循环
        from sprite import Sprite

        if self._is_deleted or not self._visible:
            return False

        # 🚀 1. 统一获取当前的精准包围盒 [left, top, right, bottom]
        # 这个方法已经包含了 _visual_offset 和 scale 的所有校准
        r1 = self._get_hitbox_rect()
        if not r1:
            return False

        if target is mouse:
            mx, my = st._MOUSE_STATE["x"], st._MOUSE_STATE["y"]
            # 用真实判定形状：胶囊/多边形的斜角区域不再误判为碰到
            return point_inside(self._get_collision_shape(), (mx, my))

        # 🚀 3. 如果目标是字符串，进行标签碰撞检测
        if isinstance(target, str):
            tag = target

            # 获取地图数据
            if st._CURRENT_MAP:
                tile_size = st._CURRENT_MAP.get("tile_size", 16)

                # 计算精灵包围盒覆盖的图块范围（按判定外扩量放大，
                # 避免贴着图块边缘停住时因皮肤间隙漏判该图块的标签）
                min_tile_x = math.floor((r1[0] - SENSOR_EPS) // tile_size)
                max_tile_x = math.floor((r1[2] + SENSOR_EPS) // tile_size)
                min_tile_y = math.floor((r1[1] - SENSOR_EPS) // tile_size)
                max_tile_y = math.floor((r1[3] + SENSOR_EPS) // tile_size)

                static_world = st._CURRENT_MAP.get("static_world")
                if static_world is not None:
                    # 图块标签：加载地图时烘焙成 tag → 格子表，
                    # 查询量只与「带这个标签的图块数」有关，与整张地图大小无关
                    for tile_x, tile_y in static_world.tile_tag_cells(tag):
                        if (
                            min_tile_x <= tile_x <= max_tile_x
                            and min_tile_y <= tile_y <= max_tile_y
                        ):
                            return True
                elif st._MAP_MODEL and tag:
                    # 索引构建失败时的兼容路径：仍按图块全表扫描
                    for layer in st._CURRENT_MAP.get("layers", []):
                        tiles = layer.get("tiles", {})

                        for (tile_x, tile_y), tile_id in tiles.items():
                            if tile_id <= 0:
                                continue
                            # 检查图块是否在精灵包围盒内
                            if not (
                                min_tile_x <= tile_x <= max_tile_x
                                and min_tile_y <= tile_y <= max_tile_y
                            ):
                                continue
                            # 使用Tiled标准：通过firstgid范围查找瓦片集
                            resource_index, tile_index = _find_tileset_for_gid(
                                tile_id, st._CURRENT_MAP["tile_sets"]
                            )
                            if st._MAP_MODEL.get_tile_tag(resource_index, tile_index) == tag:
                                return True

                # 形状层：按真实多边形判定，不再用格子范围（tag 可挂在任意能力类型上）
                # P3：优先走烘焙好的 tag 查找表，避免每次 is_touch 全表扫描
                if tag:
                    if static_world is not None:
                        sprite_shape = self._get_collision_shape()
                        for entry in static_world.tag_entries(tag):
                            # 统一用外扩 SENSOR_EPS 的判定形状：贴着墙面/地面也算碰到
                            if intersects(sprite_shape, entry.probe_shape):
                                return True
                    else:
                        # 索引构建失败时的兼容路径：保持原全表扫描
                        for layer in st._CURRENT_MAP.get("layers", []):
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
        if group_name not in st._GROUPS:
            return None

        for other in st._GROUPS[group_name]:
            # 排除自己
            if other is self:
                continue
            # 这里的 is_touching 是我们之前写的 Pillow AABB 算法
            if self.is_touch(other):
                return other
        return None


    def sweep_test(self, direction="down", distance=None):
        """用身体朝一个方向做一次扫掠测试：前方是否有实心地形阻挡。

        只测试、不移动（对应 Godot 的 test_move / Bullet 的 convexSweepTest）。
        direction: "left"/"right"/"up"/"down"（或 左/右/上/下），也接受用户角度数字
        distance: 探测距离，默认 2 像素；想查更远可以传更大值

        只查静态实心地形（形状层 solid/both、图像碰撞、实心图块），
        感应区域不算阻挡；跳板只有向下且从上方靠近时才算阻挡。

        用法：
            if not hero.sweep_test("right"):
                hero.add_x(4)
        """
        if self._is_deleted or self._collision_disabled or not st._CURRENT_MAP:
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

        static_world = st._CURRENT_MAP.get("static_world")
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
        if st._CURRENT_MAP.get("boundaryCollision", st._CURRENT_MAP.get("gravity", False)):
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


    def raycast(self, direction, distance=1000):
        """从角色所在点（x/y，和 goto/look_at 用的是同一个点）朝一个方向打射线。

        参数与全局 raycast 完全一致，命中返回 RaycastHit，没打中返回 None：
            hero.raycast("right", 200)      # 从角色位置向右探 200 像素
            hero.raycast(hero.angle, 300)   # 沿角色当前朝向
        起点就是角色位置（不是碰撞盒边缘）；角色已删除时返回 None。
        需要从任意点（鼠标、标记）发射时用全局 raycast(x, y, 方向, 距离)。
        """
        if self._is_deleted:
            return None
        return _raycast(self.x, self.y, direction, distance)


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
