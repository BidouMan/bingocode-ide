import os
import json
from PySide6.QtCore import QObject, Signal


class MapDataModel(QObject):
    """地图数据模型，管理地图的瓦片数据和文件操作"""
    
    data_changed = Signal()  # 数据变化信号
    
    def __init__(self, project_path=""):
        super().__init__()
        self.project_path = project_path
        self.map_data = {}
        self._initialize_default_data()
    
    def _initialize_default_data(self):
        """初始化默认地图数据"""
        self.map_data = {
            "width": 32,          # 地图宽度（瓦片数量）
            "height": 32,         # 地图高度（瓦片数量）
            "tile_size": 32,      # 瓦片大小（像素）
            "layers": [           # 地图图层
                {
                    "name": "ground",
                    "visible": True,
                    "tiles": []
                }
            ],
            "tile_sets": []       # 瓦片集配置
        }
        # 初始化空白瓦片网格
        self._initialize_tiles()
    
    def _initialize_tiles(self):
        """初始化空白瓦片网格"""
        width = self.map_data["width"]
        height = self.map_data["height"]
        
        for layer in self.map_data["layers"]:
            layer["tiles"] = [[0 for _ in range(width)] for _ in range(height)]
    
    def get_tile(self, layer_index, x, y):
        """获取指定位置的瓦片ID"""
        if 0 <= layer_index < len(self.map_data["layers"]):
            layer = self.map_data["layers"][layer_index]
            if 0 <= y < len(layer["tiles"]) and 0 <= x < len(layer["tiles"][0]):
                return layer["tiles"][y][x]
        return 0
    
    def set_tile(self, layer_index, x, y, tile_id):
        """设置指定位置的瓦片ID"""
        if 0 <= layer_index < len(self.map_data["layers"]):
            layer = self.map_data["layers"][layer_index]
            if 0 <= y < len(layer["tiles"]) and 0 <= x < len(layer["tiles"][0]):
                layer["tiles"][y][x] = tile_id
                self.data_changed.emit()
                return True
        return False
    
    def get_map_size(self):
        """获取地图尺寸"""
        return self.map_data["width"], self.map_data["height"]
    
    def get_tile_size(self):
        """获取瓦片大小"""
        return self.map_data["tile_size"]
    
    def get_layer_count(self):
        """获取图层数量"""
        return len(self.map_data["layers"])
    
    def get_layer(self, index):
        """获取指定图层"""
        if 0 <= index < len(self.map_data["layers"]):
            return self.map_data["layers"][index]
        return None
    
    def add_layer(self, name="new_layer"):
        """添加新图层"""
        new_layer = {
            "name": name,
            "visible": True,
            "tiles": []
        }
        self._initialize_layer_tiles(new_layer)
        self.map_data["layers"].append(new_layer)
        self.data_changed.emit()
        return len(self.map_data["layers"]) - 1
    
    def _initialize_layer_tiles(self, layer):
        """初始化图层的瓦片数据"""
        width = self.map_data["width"]
        height = self.map_data["height"]
        layer["tiles"] = [[0 for _ in range(width)] for _ in range(height)]
    
    def remove_layer(self, index):
        """删除图层"""
        if 0 <= index < len(self.map_data["layers"]):
            del self.map_data["layers"][index]
            self.data_changed.emit()
            return True
        return False
    
    def set_map_size(self, width, height):
        """设置地图尺寸"""
        self.map_data["width"] = width
        self.map_data["height"] = height
        # 重新初始化所有图层的瓦片数据
        for layer in self.map_data["layers"]:
            self._initialize_layer_tiles(layer)
        self.data_changed.emit()
    
    def save(self, file_path=None):
        """保存地图数据到文件"""
        if file_path is None:
            file_path = self._get_default_save_path()
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.map_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存地图失败: {e}")
            return False
    
    def load(self, file_path):
        """从文件加载地图数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.map_data = json.load(f)
            self.data_changed.emit()
            return True
        except Exception as e:
            print(f"加载地图失败: {e}")
            return False
    
    def _get_default_save_path(self):
        """获取默认保存路径"""
        if self.project_path:
            maps_dir = os.path.join(self.project_path, "assets", "maps")
            os.makedirs(maps_dir, exist_ok=True)
            return os.path.join(maps_dir, "map.json")
        return "map.json"
    
    def add_tile_set(self, name, image_path, tile_width, tile_height):
        """添加瓦片集"""
        tile_set = {
            "name": name,
            "image_path": image_path,
            "tile_width": tile_width,
            "tile_height": tile_height,
            "tile_count": 0  # 将在加载图片后计算
        }
        self.map_data["tile_sets"].append(tile_set)
        self.data_changed.emit()
        return len(self.map_data["tile_sets"]) - 1
    
    def get_tile_sets(self):
        """获取所有瓦片集"""
        return self.map_data["tile_sets"]
    
    def get_tile_set(self, index):
        """获取指定瓦片集"""
        if 0 <= index < len(self.map_data["tile_sets"]):
            return self.map_data["tile_sets"][index]
        return None