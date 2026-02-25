import json,os
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsEllipseItem
from PySide6.QtGui import QPainter, QPixmap, QColor, QFont, QBrush,QTransform
from PySide6.QtCore import Qt


class RenderManager:
    def __init__(self, view_instance):
        self.view = view_instance 
        self.logic_w = 640
        self.logic_h = 480
        self.scene = QGraphicsScene(0, 0, self.logic_w, self.logic_h)
        self.view.setScene(self.scene)

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
                elif cmd_type == "DELETE" or cmd_type == "REMOVE":
                    self.remove_sprite(sprite_id)
                elif cmd_type == "RESET":
                    self.reset_session()
                
        except Exception as e:
            pass
        
    def create_sprite(self, sprite_id, data):
        # 🚀 移除 DEBUG 打印，直接加载
        image_path = data.get("image", "")
        stype = data.get("type", "image")
        
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
                item.setTransformOriginPoint(pixmap.width()/2, pixmap.height()/2)

        if item:
            item.setZValue(data.get("z", 0))
            self.scene.addItem(item)
            self.sprites[sprite_id] = item
            self.update_sprite(sprite_id, data)
        
        # 🚀 处理层级
        z_value = data.get("z_value", 0) # 默认层级是 0
        item.setZValue(z_value)
        
        # 🚀 如果是背景图，可以禁用它的碰撞或交互（可选）
        if data.get("type") == "background":
            item.setEnabled(False) # 背景不响应鼠标等交互
            # render_manager.py 内部
            rect = item.pixmap().rect()
            scale_x = 640 / rect.width()
            scale_y = 480 / rect.height()
            item.setScale(max(scale_x, scale_y)) # 类似 center crop 的效果

    def update_sprite(self, sprite_id, data):
        item = self.sprites.get(sprite_id)
        if item:
            rect = item.boundingRect()
            w, h = rect.width(), rect.height()

            x = data.get("x", item.x() + w/2)
            y = data.get("y", item.y() + h/2)
            angle = data.get("angle", item.rotation())
            
            # 🚀 获取两个方向的缩放值，如果没有则默认为 1.0
            sx = data.get("scale_x", getattr(item, '_last_sx', 1.0))
            sy = data.get("scale_y", getattr(item, '_last_sy', 1.0))
            item._last_sx = sx
            item._last_sy = sy

            transform = QTransform()
            transform.translate(w / 2, h / 2)
            # 🚀 关键：同时应用 sx 和 sy 实现等比缩放
            transform.scale(sx, sy) 
            transform.rotate(angle)
            transform.translate(-w / 2, -h / 2)

            item.setTransform(transform)
            item.setRotation(0) 
            
            # 保持中心点对齐
            item.setPos(x - w / 2, y / 2 if h==0 else y - h / 2)

            if "visible" in data:
                item.setVisible(data["visible"])
            # 5. 其他属性
            if "z" in data:
                item.setZValue(data["z"])
            if "opacity" in data:
                item.setOpacity(data["opacity"])

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

    def create_text(self, sprite_id, data):
        """后续实现：在屏幕上显示文字"""
        pass

    def handle_audio(self, data):
        """后续实现：播放声音"""
        pass

    def handle_camera(self, data):
        """后续实现：镜头缩放、平移"""
        pass