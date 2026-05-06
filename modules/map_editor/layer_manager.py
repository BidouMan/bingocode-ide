import os
from PySide6.QtCore import QObject, Signal, QPointF, Qt
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene
from PySide6.QtGui import QPixmap, QTransform


class Layer(QObject):
    """图层基类，定义图层的基本属性和方法"""
    
    # 信号定义
    layer_changed = Signal()  # 图层变化信号
    visibility_changed = Signal(bool)  # 可见性变化信号
    locked_changed = Signal(bool)  # 锁定状态变化信号
    
    def __init__(self, layer_id, name, layer_type, parent=None):
        super().__init__(parent)
        self.layer_id = layer_id  # 唯一标识符
        self.name = name  # 图层名称
        self.layer_type = layer_type  # 图层类型："drawing" 或 "image"
        self.visible = True  # 是否可见
        self.locked = False  # 是否锁定
        self.items = []  # 图层中的元素
        self.properties = {}  # 图层属性
        self.resources = []  # 图层独立的资源列表
        self.selected_resource_index = -1  # 当前选中的资源索引
        self.selected_tile_index = -1  # 当前选中的图块索引
    
    def set_name(self, name):
        """设置图层名称"""
        self.name = name
        self.layer_changed.emit()
    
    def set_visible(self, visible):
        """设置图层可见性"""
        self.visible = visible
        self.visibility_changed.emit(visible)
        self.layer_changed.emit()
    
    def set_locked(self, locked):
        """设置图层锁定状态"""
        self.locked = locked
        self.locked_changed.emit(locked)
        self.layer_changed.emit()
    
    def add_item(self, item):
        """添加元素到图层"""
        self.items.append(item)
        self.layer_changed.emit()
    
    def remove_item(self, item):
        """从图层中移除元素"""
        if item in self.items:
            self.items.remove(item)
            self.layer_changed.emit()
    
    def clear_items(self):
        """清空图层中的所有元素"""
        self.items.clear()
        self.layer_changed.emit()
    
    def to_dict(self):
        """将图层转换为字典，用于保存"""
        return {
            "id": self.layer_id,
            "name": self.name,
            "type": self.layer_type,
            "visible": self.visible,
            "locked": self.locked,
            "properties": self.properties
        }
    
    @classmethod
    def from_dict(cls, data, parent=None):
        """从字典创建图层"""
        layer_id = data.get("id", 0)  # 提供默认值
        layer_name = data.get("name", "Layer")  # 提供默认值
        # 对于DrawingLayer和ImageLayer，它们的构造函数不接受layer_type参数
        if cls.__name__ in ["DrawingLayer", "ImageLayer"]:
            # 只传递必要的参数，parent是可选的
            if parent:
                layer = cls(layer_id, layer_name, parent)
            else:
                layer = cls(layer_id, layer_name)
        else:
            layer_type = data.get("type", "drawing")  # 提供默认值
            if parent:
                layer = cls(layer_id, layer_name, layer_type, parent)
            else:
                layer = cls(layer_id, layer_name, layer_type)
        layer.visible = data.get("visible", True)
        layer.locked = data.get("locked", False)
        layer.properties = data.get("properties", {})
        return layer


class DrawingLayer(Layer):
    """绘制图层，用于瓦片地图绘制"""
    
    def __init__(self, layer_id, name, parent=None):
        super().__init__(layer_id, name, "drawing", parent)
        self.tiles = {}  # 瓦片数据：{(x, y): tile_id}
    
    def set_tile(self, x, y, tile_id):
        """设置瓦片"""
        key = (int(x), int(y))
        if tile_id == 0:
            if key in self.tiles:
                del self.tiles[key]
        else:
            self.tiles[key] = int(tile_id)
        self.layer_changed.emit()
    
    def get_tile(self, x, y):
        """获取瓦片"""
        key = (int(x), int(y))
        return self.tiles.get(key, 0)
    
    def clear_tiles(self):
        """清空瓦片"""
        self.tiles.clear()
        self.layer_changed.emit()
    
    def to_dict(self):
        """将图层转换为字典，用于保存"""
        data = super().to_dict()
        data["tiles"] = self.tiles
        return data
    
    @classmethod
    def from_dict(cls, data, parent=None):
        """从字典创建图层"""
        layer = super().from_dict(data, parent)
        layer.tiles = data.get("tiles", {})
        return layer


class ImageLayer(Layer):
    """图像图层，用于管理独立图像"""
    
    def __init__(self, layer_id, name, parent=None):
        super().__init__(layer_id, name, "image", parent)
        self.images = []  # 图像数据：[ImageData]
    
    def add_image(self, image_data):
        """添加图像"""
        self.images.append(image_data)
        self.layer_changed.emit()
    
    def remove_image(self, image_data):
        """移除图像"""
        if image_data in self.images:
            self.images.remove(image_data)
            self.layer_changed.emit()
    
    def clear_images(self):
        """清空图像"""
        self.images.clear()
        self.layer_changed.emit()
    
    def to_dict(self):
        """将图层转换为字典，用于保存"""
        data = super().to_dict()
        data["images"] = [img.to_dict() for img in self.images]
        return data
    
    @classmethod
    def from_dict(cls, data, parent=None):
        """从字典创建图层"""
        layer = super().from_dict(data, parent)
        # 从数据中加载图像数据
        layer.images = []
        if "images" in data:
            for image_data in data["images"]:
                image = ImageData.from_dict(image_data)
                layer.images.append(image)
        return layer


class ImageData:
    """图像数据类，存储图像的路径和变换信息"""
    
    def __init__(self, image_path, position=None, rotation=0, scale=1.0, opacity=1.0):
        self.image_path = image_path  # 图像路径
        self.position = position or QPointF(0, 0)  # 位置
        self.rotation = rotation  # 旋转角度（度）
        self.scale = scale  # 缩放比例（向后兼容）
        self.scale_x = scale  # 宽度缩放比例
        self.scale_y = scale  # 高度缩放比例
        self.opacity = opacity  # 透明度
        self.pixmap = None  # 缓存的图像
        self.collision_type = "图像"  # 碰撞类型：图像/墙体/跳板/背景/自定义
        self.collision_enabled = False  # 碰撞是否启用（图像图层默认关闭）
        self.collision_shape = None  # 碰撞形状
        self._load_pixmap()
    
    def _load_pixmap(self):
        """加载图像"""
        if os.path.exists(self.image_path):
            self.pixmap = QPixmap(self.image_path)
    
    def get_transform(self):
        """获取变换矩阵"""
        transform = QTransform()
        # 变换顺序：缩放 -> 旋转
        # 注意：位置通过 setPos 直接设置，不包含在变换中
        transform.scale(self.scale_x, self.scale_y)
        transform.rotate(self.rotation)
        return transform
    
    def to_dict(self):
        """将图像数据转换为字典"""
        w = self.pixmap.width() if self.pixmap else 1
        h = self.pixmap.height() if self.pixmap else 1
        return {
            "image_path": self.image_path,
            "position": [self.position.x(), self.position.y()],
            "rotation": self.rotation,
            "scale": self.scale,
            "scale_x": self.scale_x,
            "scale_y": self.scale_y,
            "opacity": self.opacity,
            "width": w,
            "height": h,
            "collision_type": self.collision_type,
            "collision_enabled": self.collision_enabled,
            "collision_shape": self.collision_shape
        }
    
    @classmethod
    def from_dict(cls, data):
        """从字典创建图像数据"""
        position = QPointF(data["position"][0], data["position"][1])
        scale = data.get("scale", 1.0)
        image_data = cls(
            data["image_path"],
            position,
            data.get("rotation", 0),
            scale,
            data.get("opacity", 1.0)
        )
        # 加载scale_x和scale_y属性，如果没有则使用scale值
        image_data.scale_x = data.get("scale_x", scale)
        image_data.scale_y = data.get("scale_y", scale)
        image_data.collision_type = data.get("collision_type", "图像")
        image_data.collision_enabled = data.get("collision_enabled", False)
        image_data.collision_shape = data.get("collision_shape", None)
        return image_data


class LayerManager(QObject):
    """图层管理器，负责图层的创建、删除、排序等操作"""
    
    # 信号定义
    layers_changed = Signal()  # 图层列表变化信号
    current_layer_changed = Signal(int)  # 当前图层变化信号
    
    def __init__(self, map_model, parent=None):
        super().__init__(parent)
        self.map_model = map_model  # 地图数据模型
        self.layers = []  # 图层列表
        self.current_layer_index = 0  # 当前图层索引
        self.layer_id_counter = 0  # 图层ID计数器
    
    def initialize_from_map_model(self):
        """从地图数据模型初始化图层"""
        self.layers.clear()

        self.layer_id_counter = 0

        map_layers = self.map_model.map_data.get("layers", [])
        for i, layer_data in enumerate(map_layers):
            layer_id = layer_data.get("id", self._get_next_layer_id())
            layer_name = layer_data.get("name", f"Layer {i}")
            if layer_id >= self.layer_id_counter:
                self.layer_id_counter = layer_id + 1

            layer_type = layer_data.get("type", "drawing")

            if layer_type == "drawing":
                layer = DrawingLayer.from_dict(layer_data)
                layer.layer_id = layer_id
            else:
                layer = ImageLayer.from_dict(layer_data)
                layer.layer_id = layer_id
            self.layers.append(layer)

        if not self.layers:
            self.create_layer("image", "图层")

        self.layers_changed.emit()
    
    def create_layer(self, layer_type, name=None):
        """创建新图层"""
        layer_id = self._get_next_layer_id()
        if not name:
            name = "图层"
        
        if layer_type == "drawing":
            layer = DrawingLayer(layer_id, name)
        else:
            layer = ImageLayer(layer_id, name)
        
        self.layers.append(layer)
        self.current_layer_index = len(self.layers) - 1
        self.layers_changed.emit()
        self.current_layer_changed.emit(self.current_layer_index)
        return layer
    
    def delete_layer(self, index):
        """删除图层"""
        if 0 <= index < len(self.layers):
            del self.layers[index]
            # 如果删除的是当前图层，切换到上一个图层
            if self.current_layer_index >= index:
                self.current_layer_index = max(0, self.current_layer_index - 1)
            self.layers_changed.emit()
            self.current_layer_changed.emit(self.current_layer_index)
            return True
        return False
    
    def move_layer_up(self, index):
        """将图层上移"""
        if 0 < index < len(self.layers):
            self.layers[index], self.layers[index - 1] = self.layers[index - 1], self.layers[index]
            # 如果移动的是当前图层，更新索引
            if self.current_layer_index == index:
                self.current_layer_index -= 1
            elif self.current_layer_index == index - 1:
                self.current_layer_index += 1
            self.layers_changed.emit()
            return True
        return False
    
    def move_layer_down(self, index):
        """将图层下移"""
        if 0 <= index < len(self.layers) - 1:
            self.layers[index], self.layers[index + 1] = self.layers[index + 1], self.layers[index]
            # 如果移动的是当前图层，更新索引
            if self.current_layer_index == index:
                self.current_layer_index += 1
            elif self.current_layer_index == index + 1:
                self.current_layer_index -= 1
            self.layers_changed.emit()
            return True
        return False
    
    def set_current_layer(self, index):
        """设置当前图层"""
        if 0 <= index < len(self.layers):
            self.current_layer_index = index
            self.current_layer_changed.emit(index)
            # 切换图层时发出资源变化信号
            self.layers_changed.emit()
            return True
        return False
    
    def get_current_layer(self):
        """获取当前图层"""
        if 0 <= self.current_layer_index < len(self.layers):
            return self.layers[self.current_layer_index]
        return None
    
    def get_layer(self, index):
        """获取指定图层"""
        if 0 <= index < len(self.layers):
            return self.layers[index]
        return None
    
    def get_layer_count(self):
        """获取图层数量"""
        return len(self.layers)
    
    def update_map_model(self):
        """更新地图数据模型"""
        layers_data = []
        for i, layer in enumerate(self.layers):
            layer_data = layer.to_dict()
            if layer.layer_type == "drawing":
                layer_data["tiles"] = layer.tiles
                layer_data["objects"] = []
            else:
                layer_data["tiles"] = {}
                layer_data["objects"] = []
                # 保存图像数据到images字段
                layer_data["images"] = [img.to_dict() for img in layer.images]
                # 同时保存到objects字段以保持兼容性
                for image_data in layer.images:
                    obj = {
                        "type": "image",
                        "image_path": image_data.image_path,
                        "x": image_data.position.x(),
                        "y": image_data.position.y(),
                        "rotation": image_data.rotation,
                        "scale": image_data.scale,
                        "opacity": image_data.opacity
                    }
                    layer_data["objects"].append(obj)
            layers_data.append(layer_data)

        self.map_model.map_data["layers"] = layers_data
        self.map_model.data_changed.emit()
    
    def _get_next_layer_id(self):
        """获取下一个图层ID"""
        layer_id = self.layer_id_counter
        self.layer_id_counter += 1
        return layer_id
