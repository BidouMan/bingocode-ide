import json
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtGui import QPainter, QPixmap, QColor
from PySide6.QtCore import Qt

class StageManager(QGraphicsView):
    def __init__(self, parent_frame):
        super().__init__(parent_frame)
        
        # 1. 核心舞台：只定义逻辑大小
        self.logic_w = 320
        self.logic_h = 240
        self.scene = QGraphicsScene(0, 0, self.logic_w, self.logic_h)
        self.setScene(self.scene)

        # 2. 基础渲染设置 (为了不卡顿)
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setFrameShape(QGraphicsView.NoFrame)
        self.setBackgroundBrush(QColor("#1E1E1E")) # 硬编码一个深色背景即可
        
        # 3. 角色容器
        self.sprites = {}

    def handle_instruction(self, instruction_json):
        """处理 JSON 指令的分发器"""
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
            pass # 初期调试可以打印 e，稳定后忽略

    def create_sprite(self, sprite_id, data):
        pixmap = QPixmap(data.get("image", ""))
        if not pixmap.isNull():
            item = QGraphicsPixmapItem(pixmap)
            # 设置中心点，方便旋转和坐标对齐
            item.setTransformOriginPoint(pixmap.width() / 2, pixmap.height() / 2)
            self.scene.addItem(item)
            self.sprites[sprite_id] = item
            self.update_sprite(sprite_id, data)

    def update_sprite(self, sprite_id, data):
        item = self.sprites.get(sprite_id)
        if item:
            if "x" in data and "y" in data:
                # 这里的坐标映射根据你的需求调整，目前是简单的 (x, y)
                item.setPos(data["x"], data["y"])
            if "angle" in data:
                item.setRotation(data["angle"])

    def reset_session(self):
        """清空所有角色"""
        self.scene.clear()
        self.sprites.clear()