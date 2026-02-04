import json
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsEllipseItem
from PySide6.QtGui import QPainter, QPixmap, QColor, QPen, QBrush
from PySide6.QtCore import Qt

class StageManager:
    def __init__(self, view_instance):
        # 🚀 直接接管 Designer 里的 game_view，解决层级覆盖问题
        self.view = view_instance 
        
        # 1. 核心舞台：统一使用 640x480 逻辑分辨率
        self.logic_w = 640
        self.logic_h = 480
        self.scene = QGraphicsScene(0, 0, self.logic_w, self.logic_h)
        self.view.setScene(self.scene)

        # 2. 渲染优化
        self.view.setRenderHint(QPainter.Antialiasing) # 抗锯齿
        self.view.setRenderHint(QPainter.SmoothPixmapTransform) # 平滑缩放
        self.view.setFrameShape(QGraphicsView.NoFrame)
        self.view.setBackgroundBrush(QColor("#1E1E1E"))
        
        # 3. 彻底禁用滚动条，防止缩放时出现黑边
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 4. 角色容器
        self.sprites = {}

        # 🚀 初始执行一次缩放对齐
        self.apply_fit()

    def apply_fit(self):
        """让场景等比缩放以填满当前的 view 窗口"""
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def handle_instruction(self, instruction_json):
        try:
            msg = json.loads(instruction_json)
            cmd_type = msg.get("type")
            sprite_id = str(msg.get("id"))
            data = msg.get("data", {})

            if cmd_type == "CREATE":
                self.create_sprite(sprite_id, data)
            elif cmd_type == "UPDATE":
                self.update_sprite(sprite_id, data)
            elif cmd_type == "RESET":
                self.reset_session()
        except Exception as e:
            print(f"Render Error: {e}")

    def create_sprite(self, sprite_id, data):
        stype = data.get("type", "image")
        item = None
        
        # 🚀 增加：对几何图形的渲染支持
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
            pixmap = QPixmap(data.get("image", ""))
            if not pixmap.isNull():
                item = QGraphicsPixmapItem(pixmap)
                item.setTransformOriginPoint(pixmap.width() / 2, pixmap.height() / 2)

        if item:
            self.scene.addItem(item)
            self.sprites[sprite_id] = item
            self.update_sprite(sprite_id, data)

    def update_sprite(self, sprite_id, data):
        item = self.sprites.get(sprite_id)
        if item:
            # 自动中心对齐逻辑
            rect = item.boundingRect()
            if "x" in data and "y" in data:
                item.setPos(data["x"] - rect.width()/2, data["y"] - rect.height()/2)
            if "angle" in data:
                item.setRotation(data["angle"])
            
            # 🚀 每次更新后确保缩放依然正确（应对窗口拉伸）
            self.apply_fit()

    def reset_session(self):
        self.scene.clear()
        self.sprites.clear()