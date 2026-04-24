import json, os
from PySide6.QtWidgets import (
    QGraphicsView,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsEllipseItem,
    QGraphicsSimpleTextItem,
    QGraphicsPathItem,
)
from PySide6.QtGui import (
    QPainter,
    QPixmap,
    QColor,
    QFont,
    QBrush,
    QTransform,
    QPen,
    QFontDatabase,
    QPainterPath,
)
from PySide6.QtCore import Qt, QObject, QEvent, QRect as QtCore_QRect


class RenderManager(QObject):
    def __init__(self, view_instance, app_controller=None):
        super().__init__()
        self.view = view_instance
        self.app_controller = app_controller
        self.logic_w = 640
        self.logic_h = 480
        self.scene = QGraphicsScene(0, 0, self.logic_w, self.logic_h)
        self.view.setScene(self.scene)
        self.layer_counter = 0  # 🚀 用于自动生成图层的计数器

        # 🚀 1. 加载 HarmonyOS 字体文件
        current_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(current_dir)

        font_path = os.path.join(
            root_dir, "assets", "font", "HarmonyOS_Sans_SC_Regular.ttf"
        )

        # 调试用（确认后可删除）：打印一下实际探测的路径
        # print(f"DEBUG: 尝试加载字体路径: {font_path}")

        self.font_id = QFontDatabase.addApplicationFont(font_path)

        if self.font_id != -1:
            # 成功加载，获取字体的 Family Name
            self.bubble_font_family = QFontDatabase.applicationFontFamilies(
                self.font_id
            )[0]
        else:
            # 万一加载失败（路径错等），降级使用系统黑体
            print(f"Warning: Font file not found at {font_path}")
            self.bubble_font_family = "Microsoft YaHei"

        # 基础配置
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setBackgroundBrush(QColor("#1E1E1E"))
        self.view.setFrameShape(QGraphicsView.NoFrame)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 性能优化：减轻集成显卡压力
        self.view.setViewportUpdateMode(QGraphicsView.MinimalViewportUpdate)
        self.view.setOptimizationFlag(QGraphicsView.IndirectPainting)

        self.sprites = {}
        self.static_layers = {}  # 静态图层烘焙，{layer_idx: QGraphicsPixmapItem}
        self.apply_fit()

        # 显示FPS帧数
        self.fps_label = self.scene.addText("FPS: 0")
        # 🚀 设置字体大小
        font = QFont(
            "Arial", 24
        )  # 创建字体对象，16 是字体大小，你可以根据需要调大（如 20 或 24）
        font.setBold(True)  # 让字体加粗，看得更清楚
        self.fps_label.setFont(font)

        self.fps_label.setDefaultTextColor(Qt.green)
        self.fps_label.setZValue(9999)  # 确保在最顶层
        self.fps_label.setVisible(False)  # 🚀 暂时改为 True
        # 固定在左上角
        self.fps_label.setPos(10, 10)

        # 🚀 新增：启用鼠标追踪
        if hasattr(self, "view") and self.view:
            self.view.setMouseTracking(True)
            # 🚀 新增：安装事件过滤器
            if self.view.viewport():
                self.view.viewport().installEventFilter(self)

    def apply_fit(self):
        # 缩放场景以适应视图的大小，保持宽高比
        # 这样在编辑器模式下，当窗口尺寸较小时，游戏内容会被缩放到窗口大小
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def handle_instruction(self, instruction_json):
        try:
            msg = json.loads(instruction_json)
            cmd_type = msg.get("type")
            data = msg.get("data", {})  # 🚀 统一获取 data 字段

            # 1. 优先处理系统指令
            if cmd_type == "UI_COMMAND":
                self.set_fps_visibility(data)
                return

            if cmd_type == "FPS_UPDATE":
                # 🚀 确保这里被调用
                self.update_fps_display(data)
                return

            # 2. 处理角色指令（必须包含 id）
            if "id" in msg:
                sprite_id = str(msg.get("id"))
                if cmd_type == "CREATE":
                    self.create_sprite(sprite_id, data)
                elif cmd_type == "UPDATE":
                    self.update_sprite(sprite_id, data)
                elif cmd_type == "SAY":
                    text_content = data.get("text", "")
                    self.handle_say(sprite_id, text_content)
                elif cmd_type == "DELETE" or cmd_type == "REMOVE":
                    self.remove_sprite(sprite_id)
                elif cmd_type == "RESET":
                    self.reset_session()
                elif cmd_type == "PLAY_ANIMATION":
                    self.play_animation(sprite_id, data)

            # 3. 处理批量渲染指令
            elif cmd_type == "CREATE_BATCH":
                self.create_batch_tiles(data)

            # 4. 处理摄像机更新指令
            elif cmd_type == "CAMERA_UPDATE":
                self.handle_camera_update(data)

            # 5. 处理场景更新指令
            elif cmd_type == "SCENE_UPDATE":
                self.handle_scene_update(data)

        except Exception as e:
            print(f"❌ [RenderManager] 处理指令失败: {e}")

    def create_sprite(self, sprite_id, data):
        """创建精灵"""
        image_path = data.get("image", "")
        stype = data.get("type", "image")
        print(f"✅ [RenderManager] 收到创建精灵指令: {sprite_id}")
        print(f"   - 图片路径: {image_path}")
        print(f"   - 类型: {stype}")

        item = None
        if stype == "rect":
            item = QGraphicsRectItem(
                0, 0, data.get("width", 50), data.get("height", 50)
            )
            item.setBrush(QBrush(QColor(data.get("color", "#FF0000"))))
            item.setPen(Qt.NoPen)
            print(f"✅ [RenderManager] 创建矩形精灵")
        elif stype == "circle":
            r = data.get("radius", 30)
            item = QGraphicsEllipseItem(0, 0, r * 2, r * 2)
            item.setBrush(QBrush(QColor(data.get("color", "#0000FF"))))
            item.setPen(Qt.NoPen)
            print(f"✅ [RenderManager] 创建圆形精灵")
        else:
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                item = QGraphicsPixmapItem(pixmap)
                item.setTransformOriginPoint(pixmap.width() / 2, pixmap.height() / 2)
                print(f"✅ [RenderManager] 创建图片精灵，尺寸: {pixmap.size()}")

                # 存储精灵数据，用于动画播放
                if "sprite_dir" in data and "config" in data:
                    config = data["config"]
                    # 检查 frames 或 costumes 字段
                    if "frames" in config:
                        costumes = config["frames"]
                    else:
                        costumes = config.get("costumes", [])

                    item.sprite_data = {
                        "sprite_dir": data["sprite_dir"],
                        "config": config,
                        "costumes": costumes,
                    }
                    print(
                        f"✅ [RenderManager] 存储精灵数据，服装数量: {len(item.sprite_data['costumes'])}"
                    )
            else:
                print(f"❌ [RenderManager] 图片加载失败: {image_path}")

        if not item:
            print(f"❌ [RenderManager] 创建精灵失败")
            return

        self.sprites[sprite_id] = item
        self.scene.addItem(item)
        print(
            f"✅ [RenderManager] 精灵添加到场景，场景物品数量: {self.scene.items().__len__()}"
        )

        if stype == "background":
            item.setZValue(-1000)
            item.setEnabled(False)
            if isinstance(item, QGraphicsPixmapItem):
                r = item.pixmap().rect()
                if not r.isEmpty():
                    item.setScale(max(640 / r.width(), 480 / r.height()))
                    print(f"✅ [RenderManager] 设置背景缩放: {item.scale()}")
        else:
            self.layer_counter += 1
            z_value = data.get("layer", self.layer_counter)
            item.setZValue(z_value)
            print(f"✅ [RenderManager] 设置精灵 Z 值: {z_value}")

        self.update_sprite(sprite_id, data)
        print(f"✅ [RenderManager] 更新精灵完成")

    def update_sprite(self, sprite_id, data):
        """
        优化后的更新逻辑：统一变换矩阵，确保旋转、缩放、镜像和气泡同步正常工作
        """
        item = self.sprites.get(sprite_id)
        if not item:
            return

        # 处理图像更新
        if "image" in data:
            image_path = data["image"]
            pixmap = QPixmap(image_path)
            if not pixmap.isNull() and isinstance(item, QGraphicsPixmapItem):
                item.setPixmap(pixmap)
                item.setTransformOriginPoint(pixmap.width() / 2, pixmap.height() / 2)

        # 1. 基础属性获取 (优先从 data 取，取不到则保持当前状态)
        rect = item.boundingRect()
        original_w, original_h = rect.width(), rect.height()

        # 核心坐标：data 传的是中心点坐标
        x = data.get("x", item.x() + original_w / 2)
        y = data.get("y", item.y() + original_h / 2)

        # 旋转与缩放
        angle = data.get("angle", getattr(item, "_last_angle", 0.0))
        scale = data.get("scale", getattr(item, "_last_scale", 1.0))
        sx = data.get("scale_x", getattr(item, "_last_sx", 1.0))
        sy = data.get("scale_y", getattr(item, "_last_sy", 1.0))

        # 缓存当前状态以便下次增量更新
        item._last_angle = angle
        item._last_scale = scale
        item._last_sx = sx
        item._last_sy = sy

        # 2. 🚀 统一变换矩阵 (处理 旋转 + 缩放 + 镜像)
        # 我们绕着 boundingRect 的中心进行变换
        transform = QTransform()
        transform.translate(original_w / 2, original_h / 2)  # 移到中心
        transform.scale(sx, sy)  # 只使用scale_x和scale_y，不与scale相乘
        transform.rotate(angle)  # 应用旋转
        transform.translate(-original_w / 2, -original_h / 2)  # 移回原点

        item.setTransform(transform)

        # 注意：使用了 Transform 后，不要再直接用 setRotation，否则会叠加
        item.setRotation(0)

        # 计算缩放后的尺寸
        scaled_w = original_w * sx
        scaled_h = original_h * sy

        # 设置位置：将逻辑中心点对齐到物理左上角
        item.setPos(x - scaled_w / 2, y - scaled_h / 2)
        print(
            f"DEBUG: 渲染图像位置 - 原始位置: ({x}, {y}), 缩放后尺寸: ({scaled_w}, {scaled_h}), 最终位置: ({x - scaled_w / 2}, {y - scaled_h / 2})"
        )
        print(f"DEBUG: 渲染图像缩放值 - scale: {scale}, scale_x: {sx}, scale_y: {sy}")
        item._vox = data.get("vox", getattr(item, "_vox", 0))
        item._voy = data.get("voy", getattr(item, "_voy", 0))
        item._raw_cw = data.get("raw_cw", getattr(item, "_raw_cw", 0))
        item._raw_ch = data.get("raw_ch", getattr(item, "_raw_ch", 0))

        # 3. 辅助属性更新
        if "visible" in data:
            item.setVisible(data["visible"])
        if "layer" in data:
            item.setZValue(data["layer"])
        if "opacity" in data:
            item.setOpacity(data["opacity"])

        # 4. 🚀 绘制碰撞盒（可视化调试）
        hitbox = data.get("hitbox")
        if hitbox:
            # 创建或更新碰撞盒矩形
            if not hasattr(item, "_hitbox_rect"):
                # 创建碰撞盒作为场景的直接子项
                item._hitbox_rect = QGraphicsRectItem()
                item._hitbox_rect.setPen(QPen(QColor(255, 0, 0, 128), 1))
                item._hitbox_rect.setBrush(Qt.NoBrush)
                item._hitbox_rect.setZValue(10000)  # 确保在最顶层
                self.scene.addItem(item._hitbox_rect)

            # 更新碰撞盒位置和大小
            # 直接使用碰撞盒的绝对位置
            left, top, right, bottom = hitbox
            item._hitbox_rect.setRect(left, top, right - left, bottom - top)
            item._hitbox_rect.setVisible(True)
        elif hasattr(item, "_hitbox_rect"):
            item._hitbox_rect.setVisible(False)

        # 5. 🚀 气泡同步更新
        if hasattr(item, "_bubble"):
            bubble = item._bubble
            if bubble.scene() and bubble.isVisible():
                # 调用你现有的气泡调整逻辑
                self._adjust_bubble_size(bubble, bubble._text_obj, item)

    def remove_sprite(self, sprite_id):
        if sprite_id in self.sprites:
            item = self.sprites[sprite_id]
            # 移除碰撞盒（如果存在）
            if hasattr(item, "_hitbox_rect"):
                self.scene.removeItem(item._hitbox_rect)
                del item._hitbox_rect
            # 移除精灵
            self.scene.removeItem(item)
            del self.sprites[sprite_id]

    def reset_session(self):
        """物理重置：清空场景并重建基础 UI"""
        # 停止所有动画定时器
        for sprite_id, item in list(self.sprites.items()):
            if hasattr(item, "animation_timer"):
                try:
                    item.animation_timer.stop()
                    del item.animation_timer
                except:
                    pass

        self.scene.clear()  # 物理清理所有 Item
        self.sprites.clear()  # 清空引用字典
        self.static_layers.clear()  # 清空静态图层
        self.layer_counter = 0  # 重置图层

        # 🚀 重新安装事件过滤器
        if hasattr(self, "view") and self.view and self.view.viewport():
            self.view.viewport().removeEventFilter(self)
            self.view.viewport().installEventFilter(self)
            print("✅ [RenderManager] 事件过滤器已重新安装")

        # 🚀 既然 scene 已经干干净净了，直接重新创建 FPS 标签即可
        self._setup_fps_label()

    def update_fps_display(self, data):
        """更新 FPS 数值"""
        if self.fps_label:
            fps_val = data.get("fps", 0)
            self.fps_label.setPlainText(f"FPS: {fps_val}")

        # 变色逻辑保持不变
        if fps_val > 55:
            self.fps_label.setDefaultTextColor(Qt.green)
        elif fps_val > 30:
            self.fps_label.setDefaultTextColor(Qt.yellow)
        else:
            self.fps_label.setDefaultTextColor(Qt.red)

    def set_fps_visibility(self, data):
        """控制 FPS 显示/隐藏"""
        if self.fps_label:
            visible = data.get("visible", False)
            self.fps_label.setVisible(visible)

    def handle_say(self, sprite_id, text):
        if sprite_id not in self.sprites:
            return
        parent_item = self.sprites[sprite_id]

        # 1. 检查或创建气泡
        existing_bubble = getattr(parent_item, "_bubble", None)

        if not text or str(text).strip() == "":
            if existing_bubble:
                existing_bubble.hide()
            return

        if not existing_bubble:
            # 🚀 创建 PathItem
            bubble = QGraphicsPathItem()
            bubble.setBrush(QBrush(Qt.white))
            bubble.setPen(QPen(Qt.black, 1.5))
            bubble.setZValue(9999)

            text_item = QGraphicsSimpleTextItem(str(text), bubble)
            text_item.setBrush(QBrush(Qt.black))
            text_item.setFont(QFont(self.bubble_font_family, 16))

            self.scene.addItem(bubble)
            bubble._text_obj = text_item
            parent_item._bubble = bubble
            existing_bubble = bubble
        else:
            existing_bubble._text_obj.setText(str(text))
            existing_bubble.show()

        # 2. 强制刷新尺寸和路径
        self._adjust_bubble_size(
            existing_bubble, existing_bubble._text_obj, parent_item
        )

    def eventFilter(self, obj, event):
        """事件过滤器，捕获鼠标事件"""
        try:
            if hasattr(self, "view") and self.view and obj == self.view.viewport():
                # 鼠标按下
                if event.type() == event.Type.MouseButtonPress:
                    self.handle_mouse_press(event)
                    return True

                # 鼠标释放
                elif event.type() == event.Type.MouseButtonRelease:
                    self.handle_mouse_release(event)
                    return True

                elif event.type() == QEvent.MouseMove:
                    scene_pos = self.view.mapToScene(event.pos())
                    # 格式：M_MOVE:x,y
                    self.send_to_child(
                        f"M_MOVE:{round(scene_pos.x(), 1)},{round(scene_pos.y(), 1)}"
                    )
        except RuntimeError:
            # 对象已销毁，忽略事件
            pass

        return super().eventFilter(obj, event)

    def handle_mouse_press(self, event):
        """处理鼠标按下"""
        self.view.setFocus()
        # 🚀 发送鼠标按下消息给子进程
        self.send_to_child("M_DOWN:")

    def handle_mouse_release(self, event):
        """处理鼠标释放"""
        # 🚀 发送鼠标释放消息给子进程
        self.send_to_child("M_UP:")

    def send_to_child(self, message):
        """发送消息到子进程"""
        # 🚀 使用 AppController 的 _send_to_engine 方法
        if self.app_controller:
            self.app_controller._send_to_engine(message)

    def handle_audio(self, data):
        """后续实现：播放声音"""
        pass

    def handle_camera(self, data):
        """后续实现：镜头缩放、平移"""
        pass

    def handle_scene_update(self, data):
        """处理场景更新指令，更新SceneRect"""
        # 保持逻辑尺寸为640*480，无论地图大小如何
        width = 640
        height = 480

        # 更新场景大小
        self.scene.setSceneRect(0, 0, width, height)
        print(f"✅ [RenderManager] 场景更新 - 尺寸: {width}x{height}")
        print(f"   - 场景边界: {self.scene.sceneRect()}")

        # 应用适配，确保视图大小与场景大小匹配
        self.apply_fit()

        # 确保视图可以滚动到新的边界
        self.view.ensureVisible(self.scene.sceneRect())

    def handle_camera_update(self, data):
        """处理摄像机更新指令"""
        x = data.get("x", 320)
        y = data.get("y", 240)
        map_width = data.get("map_width", 0)
        map_height = data.get("map_height", 0)
        tile_size = data.get("tile_size", 16)

        # 调用高性能摄像机更新方法
        self.update_camera(x, y, map_width, map_height, tile_size)

    def update_camera(self, target_x, target_y, map_w_tiles, map_h_tiles, tile_size=16):
        """
        高性能摄像机更新
        :param target_x, target_y: 玩家当前的像素坐标
        :param map_w_tiles, map_h_tiles: 地图总行列数（用于动态计算边界）
        :param tile_size: 图块尺寸，默认值为16
        """
        map_px_w = map_w_tiles * tile_size
        map_px_h = map_h_tiles * tile_size

        view_w, view_h = 640, 480

        # 1. 计算摄像机中心点允许滑动的极限区间
        # 当地图小于等于窗口时，摄像机可以自由跟随玩家
        if map_px_w <= view_w:
            limit_min_x = 0
            limit_max_x = map_px_w
        else:
            limit_min_x = view_w / 2
            limit_max_x = map_px_w - view_w / 2

        if map_px_h <= view_h:
            limit_min_y = 0
            limit_max_y = map_px_h
        else:
            limit_min_y = view_h / 2
            limit_max_y = map_px_h - view_h / 2

        # 2. 限制计算 (Clamping)
        cam_x = max(limit_min_x, min(target_x, limit_max_x))
        cam_y = max(limit_min_y, min(target_y, limit_max_y))

        # 3. 执行底层视口居中（由 Qt C++ 内核处理，对老电脑极其友好）
        self.view.centerOn(cam_x, cam_y)

    def play_animation(self, sprite_id, data):
        """播放动画"""
        item = self.sprites.get(sprite_id)
        if not item:
            return

        sprite_data = item.sprite_data
        if not sprite_data or "costumes" not in sprite_data:
            return

        costumes = sprite_data["costumes"]
        fps = data.get("fps", 10)

        # 停止之前的动画
        if hasattr(item, "animation_timer"):
            item.animation_timer.stop()
            del item.animation_timer

        # 初始化当前帧索引
        item.current_frame_index = 0

        def update_frame():
            if item.current_frame_index >= len(costumes):
                item.current_frame_index = 0

            frame_file = costumes[item.current_frame_index]

            # 构建完整的图片路径
            sprite_dir = sprite_data.get("sprite_dir", "")
            if sprite_dir:
                image_path = os.path.join(sprite_dir, frame_file)

                # 更新精灵图片
                pixmap = QPixmap(image_path)
                if not pixmap.isNull():
                    if isinstance(item, QGraphicsPixmapItem):
                        item.setPixmap(pixmap)
                        item.setTransformOriginPoint(
                            pixmap.width() / 2, pixmap.height() / 2
                        )

            # 下一帧
            item.current_frame_index += 1

        # 创建并启动定时器
        item.animation_timer = QTimer()
        item.animation_timer.timeout.connect(update_frame)
        item.animation_timer.setInterval(int(1000 / fps))
        item.animation_timer.start()

    def create_batch_tiles(self, data):
        """批量创建瓦片精灵和图像精灵 - 静态图层烘焙模式"""
        tiles = data.get("tiles", [])
        tile_size = data.get("tile_size", 16)

        if not tiles:
            return

        # 处理图像精灵
        image_tiles = [tile for tile in tiles if tile.get("type") == "image"]
        if image_tiles:
            for image_data in image_tiles:
                sprite_id = image_data.get("id")
                if not sprite_id:
                    continue

                # 检查精灵是否已存在
                if sprite_id in self.sprites:
                    # 更新现有精灵
                    self.update_sprite(sprite_id, image_data)
                else:
                    # 创建新精灵
                    # 转换数据格式以匹配create_sprite的预期格式
                    create_data = {
                        "image": image_data.get("image_path", ""),
                        "x": image_data.get("x", 0),
                        "y": image_data.get("y", 0),
                        "angle": image_data.get("angle", 0),
                        "scale": image_data.get("scale", 1.0),
                        "scale_x": image_data.get("scale_x", 1.0),
                        "scale_y": image_data.get("scale_y", 1.0),
                        "opacity": image_data.get("opacity", 1.0),
                        "type": "image",
                        "layer": image_data.get("layer", 0),
                    }
                    self.create_sprite(sprite_id, create_data)

            print(f"✅ [RenderManager] 处理了 {len(image_tiles)} 个图像精灵")

        # 处理瓦片精灵
        tile_tiles = [tile for tile in tiles if tile.get("type") == "tile"]
        if tile_tiles:
            # 获取所有瓦片集信息
            tile_sets = data.get("tile_sets", [])
            if not tile_sets:
                return

            # 创建瓦片集字典，用于快速查找
            tile_set_dict = {}
            for i, tile_set in enumerate(tile_sets):
                tile_set_dict[i] = {
                    "image_path": tile_set.get("image_path", ""),
                    "tile_width": tile_set.get("tile_width", 16),
                    "tile_height": tile_set.get("tile_height", 16),
                    "pixmap": None,
                    "cols": 0,
                    "rows": 0,
                }

            # 加载所有瓦片集图片
            for tile_set_index, tile_set_info in tile_set_dict.items():
                image_path = tile_set_info["image_path"]
                if image_path:
                    # 初始化project_path变量
                    project_path = ""
                    # 如果是相对路径，转换为绝对路径
                    if not os.path.isabs(image_path):
                        # 获取项目路径
                        if self.app_controller and hasattr(
                            self.app_controller, "project_manager"
                        ):
                            project_path = (
                                self.app_controller.project_manager.project_root
                            )

                    if project_path:
                        image_path = os.path.join(project_path, image_path)

                    # 检查路径是否为目录，如果是，则尝试使用瓦片集名称作为文件名
                    if os.path.isdir(image_path):
                        # 获取瓦片集名称
                        tile_set_name = tile_sets[tile_set_index].get("name", "")
                        if tile_set_name:
                            # 构建完整的文件路径，确保包含tilesets目录
                            # 首先尝试在目录中查找tilesets子目录
                            tilesets_dir = os.path.join(image_path, "tilesets")
                            if os.path.isdir(tilesets_dir):
                                # 如果存在tilesets目录，则使用它
                                image_path = os.path.join(tilesets_dir, tile_set_name)
                                print(
                                    f"⚠️ [RenderManager] 瓦片集路径是目录，尝试使用tilesets子目录: {image_path}"
                                )
                            else:
                                # 否则直接使用目录路径
                                image_path = os.path.join(image_path, tile_set_name)
                                print(
                                    f"⚠️ [RenderManager] 瓦片集路径是目录，尝试使用文件名: {image_path}"
                                )

                    pixmap = QPixmap(image_path)
                    if not pixmap.isNull():
                        tile_set_info["pixmap"] = pixmap
                        tile_set_info["cols"] = (
                            pixmap.width() // tile_set_info["tile_width"]
                        )
                        tile_set_info["rows"] = (
                            pixmap.height() // tile_set_info["tile_height"]
                        )
                        print(
                            f"✅ [RenderManager] 加载瓦片集 {tile_set_index}: {image_path}"
                        )
                        print(f"   - 尺寸: {pixmap.size()}")
                        print(
                            f"   - 瓦片大小: {tile_set_info['tile_width']}x{tile_set_info['tile_height']}"
                        )
                        print(
                            f"   - 行列数: {tile_set_info['cols']}x{tile_set_info['rows']}"
                        )
                    else:
                        print(f"❌ [RenderManager] 瓦片集加载失败: {image_path}")

            # 按图层分组瓦片
            tiles_by_layer = {}

            # 找到所有瓦片的最小和最大坐标
            min_x = float("inf")
            max_x = -float("inf")
            min_y = float("inf")
            max_y = -float("inf")

            for tile_data in tile_tiles:
                layer = tile_data.get("layer", 0)
                if layer not in tiles_by_layer:
                    tiles_by_layer[layer] = []
                tiles_by_layer[layer].append(tile_data)

                # 更新地图尺寸
                x = tile_data.get("x", 0)
                y = tile_data.get("y", 0)
                min_x = min(min_x, x - tile_size)
                max_x = max(max_x, x + tile_size)
                min_y = min(min_y, y - tile_size)
                max_y = max(max_y, y + tile_size)

            # 确保图层大小至少为场景大小
            scene_rect = self.scene.sceneRect()
            min_x = min(min_x, scene_rect.left())
            max_x = max(max_x, scene_rect.right())
            min_y = min(min_y, scene_rect.top())
            max_y = max(max_y, scene_rect.bottom())

            # 为每个图层创建静态烘焙图
            for layer, layer_tiles in tiles_by_layer.items():
                # 创建图层的像素图，使用整个地图的大小
                layer_width = max_x - min_x
                layer_height = max_y - min_y
                layer_pixmap = QPixmap(layer_width, layer_height)
                layer_pixmap.fill(Qt.transparent)

                # 创建画家
                painter = QPainter(layer_pixmap)

                # 绘制所有瓦片到图层像素图
                for tile_data in layer_tiles:
                    tile_id = tile_data.get("tile_id", 0)
                    if tile_id <= 0:
                        continue

                    # 获取瓦片集索引（默认为0）
                    tile_set_index = tile_data.get("tile_set_index", 0)

                    # 检查瓦片集是否存在
                    if tile_set_index not in tile_set_dict:
                        continue

                    tile_set_info = tile_set_dict[tile_set_index]
                    pixmap = tile_set_info.get("pixmap")

                    if not pixmap:
                        continue

                    # 计算瓦片在瓦片集中的位置
                    tile_index = tile_id - 1
                    tile_col = tile_index % tile_set_info["cols"]
                    tile_row = tile_index // tile_set_info["cols"]

                    # 检查瓦片索引是否有效
                    if tile_row >= tile_set_info["rows"]:
                        continue

                    # 从瓦片集中裁剪出单个瓦片
                    tile_rect = QtCore_QRect(
                        tile_col * tile_set_info["tile_width"],
                        tile_row * tile_set_info["tile_height"],
                        tile_set_info["tile_width"],
                        tile_set_info["tile_height"],
                    )
                    tile_pixmap = pixmap.copy(tile_rect)

                    if tile_pixmap.isNull():
                        continue

                    # 计算绘制位置（使用相对坐标）
                    x = tile_data.get("x", 0)
                    y = tile_data.get("y", 0)
                    draw_x = x - min_x - tile_size // 2
                    draw_y = y - min_y - tile_size // 2

                    # 绘制瓦片到图层像素图
                    painter.drawPixmap(draw_x, draw_y, tile_pixmap)

                painter.end()

                # 移除旧的图层（如果存在）
                if layer in self.static_layers:
                    old_item = self.static_layers[layer]
                    self.scene.removeItem(old_item)
                    del old_item

                # 创建图层精灵
                layer_item = QGraphicsPixmapItem(layer_pixmap)
                layer_item.setZValue(layer)

                # 设置图层位置（使用最小坐标作为偏移）
                layer_item.setPos(min_x, min_y)

                # 存储图层
                self.static_layers[layer] = layer_item
                self.scene.addItem(layer_item)

                print(
                    f"✅ [RenderManager] 创建静态图层 {layer}，包含 {len(layer_tiles)} 个瓦片"
                )

            print(f"✅ [RenderManager] 静态图层烘焙完成，总瓦片数: {len(tile_tiles)}")

    # ---------- 内部函数 ----------
    def _setup_fps_label(self):
        """统一管理 FPS 标签的创建和样式配置"""
        # 如果已存在（比如重新配置），先不理会，由 reset_session 统一 clear
        self.fps_label = self.scene.addText("FPS: 0")
        font = QFont("Arial", 24)
        font.setBold(True)
        self.fps_label.setFont(font)
        self.fps_label.setDefaultTextColor(Qt.green)
        self.fps_label.setZValue(9999)
        self.fps_label.setPos(10, 10)
        self.fps_label.setVisible(False)  # 默认隐藏

    def _adjust_bubble_size(self, bubble, text_item, parent_item):
        """
        最终校准版：解决穿帮、解决距离过远、复现 Scratch 逻辑
        """
        # --- 1. 获取物理属性 (从缓存读取) ---
        vox = getattr(parent_item, "_vox", 0)
        voy = getattr(parent_item, "_voy", 0)
        raw_cw = getattr(parent_item, "_raw_cw", 0)
        raw_ch = getattr(parent_item, "_raw_ch", 0)
        sx = getattr(parent_item, "_last_sx", 1.0)
        sy = getattr(parent_item, "_last_sy", 1.0)

        # 🚀 计算角色在 Scene 里的物理中心 (考虑到 QGraphicsPixmapItem 默认是以左上角 setPos)
        # 修正：parent_item.x() 是左上角，加上半宽才是中心
        pw, ph = parent_item.pixmap().width(), parent_item.pixmap().height()
        base_cx = parent_item.x() + pw / 2
        base_cy = parent_item.y() + ph / 2

        # 🚀 计算内容（画中人）的真实视觉中心 (补偿偏移量)
        # scx, scy 是“画中人”在屏幕上的像素坐标
        scx = base_cx + (vox * abs(sx))
        scy = base_cy + (voy * abs(sy))

        # 当前缩放下的视觉半高 (用于找头顶)
        v_hh = (raw_ch * abs(sy)) / 2.0
        v_hw = (raw_cw * abs(sx)) / 2.0

        # --- 2. 气泡尺寸与路径绘制 (修复穿帮) ---
        padding, radius, arrow_h, arrow_w = 12, 12, 12, 15
        t_rect = text_item.boundingRect()
        bw = max(t_rect.width() + padding * 2, 60)
        bh = t_rect.height() + padding * 2

        # 判定是否翻转 (Scratch 逻辑：大角色且镜像时翻转气泡)
        is_flipped = (sx < 0) and (raw_cw * abs(sx) > 100)
        arrow_x = bw - 30 if is_flipped else 15  # 箭头在底部的起点

        path = QPainterPath()
        path.moveTo(radius, 0)
        path.lineTo(bw - radius, 0)
        path.arcTo(bw - radius * 2, 0, radius * 2, radius * 2, 90, -90)
        path.lineTo(bw, bh - radius)
        path.arcTo(bw - radius * 2, bh - radius * 2, radius * 2, radius * 2, 0, -90)

        # 底部：一笔画出小尾巴，防止穿帮
        if is_flipped:
            path.lineTo(arrow_x + arrow_w, bh)
            path.lineTo(arrow_x + arrow_w + 5, bh + arrow_h)  # 略微向外倾斜
            path.lineTo(arrow_x, bh)
        else:
            path.lineTo(arrow_x + arrow_w, bh)
            path.lineTo(arrow_x - 5, bh + arrow_h)  # 向左指
            path.lineTo(arrow_x, bh)

        path.lineTo(radius, bh)
        path.arcTo(0, bh - radius * 2, radius * 2, radius * 2, 270, -90)
        path.lineTo(0, radius)
        path.arcTo(0, 0, radius * 2, radius * 2, 180, -90)
        path.closeSubpath()

        bubble.setPath(path)
        text_item.setPos(padding, padding)

        # --- 3. 最终定位 (紧贴头顶) ---
        # 锚点定在角色视觉边缘
        if is_flipped:
            target_x = scx - v_hw - (bw - 30) + 10
        else:
            target_x = scx + v_hw - 10

        # y 坐标：视觉头顶 - 气泡高 - 箭头高 + 5像素缓冲 (防止完全贴死)
        target_y = (scy - v_hh) - bh - arrow_h + 5

        # --- 4. 边界保护 ---
        if target_x < 10:
            target_x = 10
        if target_x + bw > 630:
            target_x = 630 - bw
        if target_y < 10:
            target_y = 10

        bubble.setPos(target_x, target_y)

    def destroy(self):
        """销毁RenderManager，移除事件过滤器，防止程序关闭时崩溃"""
        try:
            if hasattr(self, "view") and self.view and self.view.viewport():
                self.view.viewport().removeEventFilter(self)
                print("✅ [RenderManager] 事件过滤器已移除")
        except Exception as e:
            print(f"❌ [RenderManager] 移除事件过滤器失败: {e}")
