import json,os
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsEllipseItem
from PySide6.QtGui import QPainter, QPixmap, QColor, QPen, QBrush,QTransform
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

    def apply_fit(self):
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def handle_instruction(self, instruction_json):
        try:
            msg = json.loads(instruction_json)
            cmd_type = msg.get("type")
            sprite_id = str(msg.get("id"))
            data = msg.get("data", msg) 

            # 🚀 只保留核心的分发逻辑
            if cmd_type == "CREATE":
                self.create_sprite(sprite_id, data)
            elif cmd_type == "UPDATE":
                self.update_sprite(sprite_id, data)
            elif cmd_type == "REMOVE":
                self.remove_sprite(sprite_id)
            elif cmd_type == "RESET":
                self.reset_session()
        except:
            pass # 渲染层保持安静，解析不了的指令直接丢弃

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

    def update_sprite(self, sprite_id, data):
        item = self.sprites.get(sprite_id)
        if item:
            rect = item.boundingRect()
            w, h = rect.width(), rect.height()

            # 1. 🚀 获取当前或指令中的状态
            # 如果 data 里没有，就从 item 身上取当前值，保证状态连贯
            x = data.get("x", item.x() + w/2)
            y = data.get("y", item.y() + h/2)
            angle = data.get("angle", item.rotation())
            # 这里的 scale_x 我们需要从 data 获取，因为 item 身上不好直接拿矩阵缩放值
            sx = data.get("scale_x", getattr(item, '_last_sx', 1.0))
            item._last_sx = sx # 记录一下，方便下次读取

            # 2. 🚀 手动构建变换矩阵 (核心逻辑)
            transform = QTransform()
            # A. 先平移到图片的中心点
            transform.translate(w / 2, h / 2)
            # B. 在中心点执行缩放（左右翻转）
            transform.scale(sx, 1.0)
            # C. 在中心点执行旋转
            transform.rotate(angle)
            # D. 平移回左上角，完成“中心变换”
            transform.translate(-w / 2, -h / 2)

            # 3. 🚀 应用矩阵并设置物理位置
            item.setTransform(transform)
            # 既然旋转已经在矩阵里做了，我们就把 item 自身的 rotation 设为 0，防止叠加
            item.setRotation(0) 
            
            # 最终对齐位置：将物体的左上角放在 (x - w/2, y - h/2)
            item.setPos(x - w / 2, y / 2 if h==0 else y - h / 2)

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
        self.scene.clear()
        self.sprites.clear()
    

    # --- 待实现的详细功能 ---
    def create_text(self, sprite_id, data):
        """后续实现：在屏幕上显示文字"""
        pass

    def handle_audio(self, data):
        """后续实现：播放声音"""
        pass

    def handle_camera(self, data):
        """后续实现：镜头缩放、平移"""
        pass