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

        self.sprites = {}
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
        self.view.setMouseTracking(True)
        # 🚀 新增：安装事件过滤器
        self.view.viewport().installEventFilter(self)

    def apply_fit(self):
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

        except Exception as e:
            # 🚀 必须打印错误，否则如果里面崩溃了你完全不知道
            print(f"❌ [IDE 指令解析失败]: {e}")
            import traceback

            traceback.print_exc()

    def create_sprite(self, sprite_id, data):
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
            if not pixmap.isNull():
                if isinstance(item, QGraphicsPixmapItem):
                    item.setPixmap(pixmap)
                    item.setTransformOriginPoint(
                        pixmap.width() / 2, pixmap.height() / 2
                    )

        # 1. 基础属性获取 (优先从 data 取，取不到则保持当前状态)
        rect = item.boundingRect()
        w, h = rect.width(), rect.height()

        # 核心坐标：data 传的是中心点坐标
        x = data.get("x", item.x() + w / 2)
        y = data.get("y", item.y() + h / 2)

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
        transform.translate(w / 2, h / 2)  # 移到中心
        transform.scale(sx * scale, sy * scale)  # 应用镜像缩放和整体缩放
        transform.rotate(angle)  # 应用旋转
        transform.translate(-w / 2, -h / 2)  # 移回原点

        item.setTransform(transform)

        # 注意：使用了 Transform 后，不要再直接用 setRotation，否则会叠加
        item.setRotation(0)

        # 设置位置：将逻辑中心点对齐到物理左上角
        item.setPos(x - w / 2, y - h / 2)
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

        # 4. 🚀 气泡同步更新
        if hasattr(item, "_bubble"):
            bubble = item._bubble
            if bubble.scene() and bubble.isVisible():
                # 调用你现有的气泡调整逻辑
                self._adjust_bubble_size(bubble, bubble._text_obj, item)

    def remove_sprite(self, sprite_id):
        if sprite_id in self.sprites:
            self.scene.removeItem(self.sprites[sprite_id])
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
        self.layer_counter = 0  # 重置图层

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

    def play_animation(self, sprite_id, data):
        """播放动画"""
        item = self.sprites.get(sprite_id)
        if not item:
            return

        # 获取动画配置
        animation_name = data.get("animation")
        start = data.get("start", 1)
        end = data.get("end", 1)
        fps = data.get("fps", 10)

        # 获取精灵的配置信息（从 sprite_data 属性中获取）
        if not hasattr(item, "sprite_data"):
            return

        sprite_data = item.sprite_data
        if not sprite_data or "costumes" not in sprite_data:
            return

        costumes = sprite_data["costumes"]

        # 创建动画定时器
        from PySide6.QtCore import QTimer

        # 停止之前的动画
        if hasattr(item, "animation_timer"):
            item.animation_timer.stop()

        # 初始化动画状态
        item.current_frame_index = start - 1  # 转换为 0-based 索引
        item.animation_start = start - 1
        item.animation_end = end - 1
        item.animation_fps = fps

        def update_frame():
            if not item or item.current_frame_index > item.animation_end:
                item.current_frame_index = item.animation_start

            # 获取当前帧的图片路径
            if item.current_frame_index < len(costumes):
                costume = costumes[item.current_frame_index]
                if isinstance(costume, dict):
                    frame_file = costume.get("file")
                else:
                    frame_file = costume

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
        """批量创建瓦片精灵"""
        tiles = data.get("tiles", [])
        tile_size = data.get("tile_size", 32)

        if not tiles:
            return

        # 获取所有瓦片集信息
        tile_sets = data.get("tile_sets", [])
        if not tile_sets:
            return

        # 创建瓦片集字典，用于快速查找
        tile_set_dict = {}
        for i, tile_set in enumerate(tile_sets):
            tile_set_dict[i] = {
                "image_path": tile_set.get("image_path", ""),
                "tile_width": tile_set.get("tile_width", 32),
                "tile_height": tile_set.get("tile_height", 32),
                "pixmap": None,
                "cols": 0,
                "rows": 0,
            }

        # 加载所有瓦片集图片
        for tile_set_index, tile_set_info in tile_set_dict.items():
            image_path = tile_set_info["image_path"]
            if image_path:
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

        created_count = 0
        for tile_data in tiles:
            sprite_id = tile_data.get("id")
            if not sprite_id:
                continue

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

            # 创建瓦片精灵
            item = QGraphicsPixmapItem(tile_pixmap)
            item.setTransformOriginPoint(tile_size // 2, tile_size // 2)

            # 存储精灵
            self.sprites[sprite_id] = item
            self.scene.addItem(item)

            # 设置图层
            layer = tile_data.get("layer", 0)
            item.setZValue(layer)

            # 更新位置
            x = tile_data.get("x", 0)
            y = tile_data.get("y", 0)
            item.setPos(x - tile_size // 2, y - tile_size // 2)

            created_count += 1

        print(f"✅ [RenderManager] 批量创建 {created_count} 个瓦片精灵完成")

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
