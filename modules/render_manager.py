import json,os
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsEllipseItem,QGraphicsSimpleTextItem
from PySide6.QtGui import QPainter, QPixmap, QColor, QFont, QBrush,QTransform,QPen,QFontDatabase
from PySide6.QtCore import Qt


class RenderManager:
    def __init__(self, view_instance):
        self.view = view_instance 
        self.logic_w = 640
        self.logic_h = 480
        self.scene = QGraphicsScene(0, 0, self.logic_w, self.logic_h)
        self.view.setScene(self.scene)
        self.layer_counter = 0  # 🚀 用于自动生成图层的计数器

        # 🚀 1. 加载 HarmonyOS 字体文件
        font_path = os.path.join("assets", "font", "HarmonyOS_Sans_SC_Regular.ttf")
        self.font_id = QFontDatabase.addApplicationFont(font_path)
        
        if self.font_id != -1:
            # 成功加载，获取字体的 Family Name
            self.bubble_font_family = QFontDatabase.applicationFontFamilies(self.font_id)[0]
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
        font = QFont("Arial", 24) # 创建字体对象，16 是字体大小，你可以根据需要调大（如 20 或 24）
        font.setBold(True)        # 让字体加粗，看得更清楚
        self.fps_label.setFont(font)

        self.fps_label.setDefaultTextColor(Qt.green)
        self.fps_label.setZValue(9999) # 确保在最顶层
        self.fps_label.setVisible(False) # 🚀 暂时改为 True
  
        # 固定在左上角
        self.fps_label.setPos(10, 10)

    def apply_fit(self):
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def handle_instruction(self, instruction_json):
        try:
            msg = json.loads(instruction_json)
            cmd_type = msg.get("type")
            data = msg.get("data", {}) # 🚀 统一获取 data 字段

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
                
        except Exception as e:
            pass
        
    def create_sprite(self, sprite_id, data):
        """
        最终完美版：处理背景缩放、自动图层递增、手动层级覆盖
        """
        image_path = data.get("image", "")
        stype = data.get("type", "image")
        
        # 1. 创建基础实例
        item = None
        if stype == "rect":
            item = QGraphicsRectItem(0, 0, data.get("width", 50), data.get("height", 50))
            item.setBrush(QBrush(QColor(data.get("color", "#FF0000"))))
            item.setPen(Qt.NoPen)
        elif stype == "circle":
            r = data.get("radius", 30)
            item = QGraphicsEllipseItem(0, 0, r*2, r*2)
            item.setBrush(QBrush(QColor(data.get("color", "#0000FF"))))
            item.setPen(Qt.NoPen)
        else:
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                item = QGraphicsPixmapItem(pixmap)
                # 设置旋转中心为图片中心
                item.setTransformOriginPoint(pixmap.width()/2, pixmap.height()/2)

        if not item:
            return

        # 2. 基础登记
        self.sprites[sprite_id] = item
        self.scene.addItem(item)

        # 3. 核心层级与类型特殊处理
        if stype == "background":
            # --- 背景特殊逻辑 ---
            item.setZValue(-1000)      # 强制最底层
            item.setEnabled(False)     # 禁用交互，提升性能
            
            # 执行背景自动填充 (Center Crop 逻辑)
            if isinstance(item, QGraphicsPixmapItem):
                rect = item.pixmap().rect()
                if not rect.isEmpty():
                    sw = 640 / rect.width()
                    sh = 480 / rect.height()
                    item.setScale(max(sw, sh)) 
        
        else:
            # --- 普通角色层级逻辑 ---
            if "layer" in data:
                # 如果学生代码里写了 b.layer = 10，优先使用手动值
                item.setZValue(data["layer"])
            else:
                # 默认按创建顺序递增，确保后创建的在上面
                self.layer_counter += 1
                item.setZValue(self.layer_counter)

        # 4. 最后应用坐标、缩放、旋转等基础属性
        self.update_sprite(sprite_id, data)

    def update_sprite(self, sprite_id, data):
        item = self.sprites.get(sprite_id)
        if not item:
            return

        # --- 1. 原有的变换逻辑 (保持不变) ---
        rect = item.boundingRect()
        w, h = rect.width(), rect.height()
        x = data.get("x", item.x() + w/2)
        y = data.get("y", item.y() + h/2)
        angle = data.get("angle", item.rotation())
        sx = data.get("scale_x", getattr(item, '_last_sx', 1.0))
        sy = data.get("scale_y", getattr(item, '_last_sy', 1.0))
        item._last_sx = sx
        item._last_sy = sy

        transform = QTransform()
        transform.translate(w / 2, h / 2)
        transform.scale(sx, sy) 
        transform.rotate(angle)
        transform.translate(-w / 2, -h / 2)

        item.setTransform(transform)
        item.setRotation(0) 
        item.setPos(x - w / 2, y - h / 2) # 修正了你代码中 y/2 的潜在小错误

        if "visible" in data:
            item.setVisible(data["visible"])
        if "layer" in data:
            item.setZValue(data["layer"])
        if "opacity" in data:
            item.setOpacity(data["opacity"])

        # --- 2. 🚀 关键：在这里同步气泡位置 ---
        if hasattr(item, "_bubble"):
            bubble = item._bubble
            if bubble.scene() and bubble.isVisible():
                # 只有当气泡在场景中且可见时才更新
                self._adjust_bubble_size(bubble, bubble._text_obj, item)

    def remove_sprite(self, sprite_id):
        if sprite_id in self.sprites:
            self.scene.removeItem(self.sprites[sprite_id])
            del self.sprites[sprite_id]

    def reset_session(self):
        """重置会话，但不销毁系统级 UI"""
        # 1. 只移除所有的 Sprite 角色
        for sprite_item in self.sprites.values():
            if sprite_item.scene(): # 确保还在场景中
                self.scene.removeItem(sprite_item)
        
        # 2. 清空字典
        self.sprites.clear()
        self.layer_counter = 0

        # 3. 隐藏 FPS 标签（可选，让新运行的代码自己决定是否显示）
        if self.fps_label:
            self.fps_label.setVisible(False)
            self.fps_label.setPlainText("FPS: 0")
    
        
    # --- 待实现的详细功能 ---
    def set_fps_visibility(self, data):
        """处理 show_fps(True/False)"""
        if data.get("action") == "show_fps":
            visible = data.get("value", False)
            self.fps_label.setVisible(visible)

    def update_fps_display(self, data):
        """更新 FPS 文字内容和颜色"""
        # 🚀 确保从 data 字典中提取 fps 键
        fps_val = data.get("fps", 0) 
        self.fps_label.setPlainText(f"FPS: {fps_val}")
        
        # 变色逻辑保持不变
        if fps_val > 55:
            self.fps_label.setDefaultTextColor(Qt.green)
        elif fps_val > 30:
            self.fps_label.setDefaultTextColor(Qt.yellow)
        else:
            self.fps_label.setDefaultTextColor(Qt.red)

    def handle_say(self, sprite_id, text):
        if sprite_id not in self.sprites:
            return
        
        parent_item = self.sprites[sprite_id]
        existing_bubble = getattr(parent_item, "_bubble", None)
        
        # 如果 text 为空或全是空格，隐藏气泡
        if not text or str(text).strip() == "":
            if existing_bubble: existing_bubble.hide()
            return

        if existing_bubble:
            # 🚀 确保气泡如果被 removeItem 了，重新加回来
            if not existing_bubble.scene():
                self.scene.addItem(existing_bubble)
            
            text_item = existing_bubble._text_obj
            text_item.setText(str(text))
            existing_bubble.show()
            self._adjust_bubble_size(existing_bubble, text_item, parent_item)
        else:
            # 创建逻辑保持不变，但增加黑色画笔确保可见
            bubble = QGraphicsRectItem()
            bubble.setBrush(QBrush(Qt.white))
            bubble.setPen(QPen(Qt.black, 1))
            bubble.setZValue(9999)
            
            text_item = QGraphicsSimpleTextItem(str(text), bubble)
            text_item.setBrush(QBrush(Qt.black))
            bubble_font = QFont(self.bubble_font_family, 16)
            text_item.setFont(bubble_font)
            
            self.scene.addItem(bubble)
            bubble._text_obj = text_item
            parent_item._bubble = bubble
            
            self._adjust_bubble_size(bubble, text_item, parent_item)
    
    def _adjust_bubble_size(self, bubble, text_item, parent_item):
        # 1. 自动调整文字和底框大小
        t_rect = text_item.boundingRect()
        padding = 8
        bw = max(t_rect.width() + padding * 2, 50)
        bh = t_rect.height() + padding * 2
        bubble.setRect(0, 0, bw, bh)
        text_item.setPos(padding, padding)

        # 2. 🚀 计算场景坐标 (对标 Scratch 右上角)
        # 必须使用 sceneBoundingRect，因为它包含了缩放和旋转后的真实视觉边界
        p_rect = parent_item.sceneBoundingRect()
        
        # 3. 定位算法：
        # x: 角色的视觉右边缘 - 40像素（稍微内缩）
        # y: 角色的视觉上边缘 - 气泡总高度 - 15像素（间隙）
        target_x = p_rect.right() - 40
        target_y = p_rect.top() - bh +15
        
        # 4. 边界保护：防止气泡飞出舞台顶部（可选）
        if target_y < 0: target_y = 5 
        
        bubble.setPos(target_x, target_y)

    def handle_audio(self, data):
        """后续实现：播放声音"""
        pass

    def handle_camera(self, data):
        """后续实现：镜头缩放、平移"""
        pass