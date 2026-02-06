import json
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsEllipseItem
from PySide6.QtGui import QPainter, QPixmap, QColor, QPen, QBrush
from PySide6.QtCore import Qt

# modules/stage_manager.py

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
            data = msg.get("data", {})

            if cmd_type == "CREATE":
                self.create_sprite(sprite_id, data)
            elif cmd_type == "UPDATE":
                self.update_sprite(sprite_id, data)
            elif cmd_type == "REMOVE": # 🚀 新增：删除角色
                self.remove_sprite(sprite_id)
            elif cmd_type == "RESET":
                self.reset_session()
        except Exception as e:
            print(f"Render Error: {e}")

    def create_sprite(self, sprite_id, data):
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
            pixmap = QPixmap(data.get("image", ""))
            if not pixmap.isNull():
                item = QGraphicsPixmapItem(pixmap)
                # 设置旋转中心
                item.setTransformOriginPoint(pixmap.width()/2, pixmap.height()/2)

        if item:
            # 🚀 允许通过 JSON 传递 z_index 控制层级
            item.setZValue(data.get("z", 0))
            self.scene.addItem(item)
            self.sprites[sprite_id] = item
            self.update_sprite(sprite_id, data)

    def update_sprite(self, sprite_id, data):
        item = self.sprites.get(sprite_id)
        if item:
            rect = item.boundingRect()
            if "x" in data and "y" in data:
                # 保持中心对齐逻辑
                item.setPos(data["x"] - rect.width()/2, data["y"] - rect.height()/2)
            if "angle" in data:
                item.setRotation(data["angle"])
            if "z" in data:
                item.setZValue(data["z"])
            if "opacity" in data: # 🚀 新增：透明度支持 (0.0 - 1.0)
                item.setOpacity(data["opacity"])

    def remove_sprite(self, sprite_id):
        if sprite_id in self.sprites:
            self.scene.removeItem(self.sprites[sprite_id])
            del self.sprites[sprite_id]

    def reset_session(self):
        self.scene.clear()
        self.sprites.clear()