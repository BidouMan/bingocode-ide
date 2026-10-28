"""Sprite 素材与碰撞盒装载（Mixin）：bsf/bgs/单图解析、hitbox 构建、标记点世界坐标、变换同步。

什么时候来这里改：角色图片换不了、缩略图/帧矩形错位、碰撞盒偏移、挂点(marker)坐标不对、缩放/旋转后碰撞错。
纯几何算法在 collision_geometry.py。"""
import json
import math
import os
from models.shape_kernel import aabb_shape, capsule_shape, polygon_shape
from collision_geometry import _image_bbox_info
import engine_state as st


class SpriteAssetsMixin:
    """Sprite 素材装载与碰撞盒/挂点几何（由 sprite.Sprite 继承）。"""

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
        if hasattr(self, "_cached_rect_frame") and self._cached_rect_frame == st._PERF_STATS["frame_count"]:
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
        self._cached_rect_frame = st._PERF_STATS["frame_count"]
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
            st._PERF_STATS["frame_count"],
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
        st._FRAME_UPDATES.append(update_data)
