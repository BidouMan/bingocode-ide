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
            "width": 40,          # 地图宽度（瓦片数量）- 640/16=40
            "height": 30,         # 地图高度（瓦片数量）- 480/16=30
            "tile_size": 16,      # 瓦片大小（像素）
            "layers": [           # 地图图层
                {
                    "name": "ground",
                    "visible": True,
                    "tiles": {},  # 使用字典存储：(x, y): tile_id
                    "objects": []  # 用于存放不规则的大图或背景
                }
            ],
            "tile_sets": []       # 瓦片集配置
        }
    
    def get_tile(self, layer_index, x, y):
        """获取指定位置的瓦片ID"""
        if 0 <= layer_index < len(self.map_data["layers"]):
            layer = self.map_data["layers"][layer_index]
            return layer["tiles"].get((int(x), int(y)), 0)
        return 0
    
    def set_tile(self, layer_index, x, y, tile_id):
        """设置指定位置的瓦片ID，直接操作字典"""
        if 0 <= layer_index < len(self.map_data["layers"]):
            layer = self.map_data["layers"][layer_index]
            key = (int(x), int(y))
            
            if tile_id == 0:
                # 如果tile_id为0，删除该坐标点以节省内存
                if key in layer["tiles"]:
                    del layer["tiles"][key]
            else:
                # 否则设置瓦片ID
                layer["tiles"][key] = int(tile_id)
            
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
            "tiles": {},
            "objects": []
        }
        self.map_data["layers"].append(new_layer)
        self.data_changed.emit()
        return len(self.map_data["layers"]) - 1
    
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
        self.data_changed.emit()
    
    def save(self, file_path=None):
        """保存地图数据到文件"""
        if file_path is None:
            file_path = self._get_default_save_path()
        
        try:
            # 创建可序列化的副本
            save_data = {
                "width": self.map_data["width"],
                "height": self.map_data["height"],
                "tile_size": self.map_data["tile_size"],
                "layers": [],
                "tile_sets": self.map_data["tile_sets"]
            }
            
            # 将字典的(x, y)转换为JSON支持的列表[[x, y, id], ...]
            for layer in self.map_data["layers"]:
                tiles_list = []
                for (x, y), tile_id in layer["tiles"].items():
                    tiles_list.append([x, y, tile_id])
                
                layer_data = {
                    "name": layer["name"],
                    "visible": layer["visible"],
                    "tiles": tiles_list,
                    "objects": layer["objects"]
                }
                save_data["layers"].append(layer_data)
            
            # 记录保存的所有瓦片坐标
            try:
                import os
                import datetime
                
                record_dir = "/Volumes/WorkStation/MyWork/CodeStation/MyIDE/MyWorkspace/备份"
                os.makedirs(record_dir, exist_ok=True)
                record_file = os.path.join(record_dir, "coordinate_log.md")
                
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                with open(record_file, 'a', encoding='utf-8') as f_record:
                    f_record.write(f"## {timestamp} - Save Map\n\n")
                    f_record.write(f"**File Path:** {file_path}\n\n")
                    f_record.write("**Tiles Saved:**\n\n")
                    
                    for layer_idx, layer_data in enumerate(save_data["layers"]):
                        f_record.write(f"### Layer {layer_idx}: {layer_data['name']}\n\n")
                        for tile in layer_data["tiles"]:
                            f_record.write(f"- [x={tile[0]}, y={tile[1]}] -> ID: {tile[2]}\n")
                        f_record.write("\n")
                        
            except Exception as e:
                print(f"记录保存坐标错误: {e}")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存地图失败: {e}")
            return False
    
    def load(self, file_path):
        """从文件加载地图数据"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
            
            # 重建地图数据结构
            self.map_data = {
                "width": loaded_data["width"],
                "height": loaded_data["height"],
                "tile_size": loaded_data["tile_size"],
                "layers": [],
                "tile_sets": []
            }
            
            # 处理tile_sets，确保每个tile_set都有tiles数组
            for tile_set_data in loaded_data.get("tile_sets", []):
                tile_set = {
                    "name": tile_set_data["name"],
                    "image_path": tile_set_data["image_path"],
                    "tile_width": tile_set_data["tile_width"],
                    "tile_height": tile_set_data["tile_height"],
                    "tile_count": tile_set_data.get("tile_count", 0),
                    "tiles": []
                }
                
                # 处理旧版本的collision属性（兼容旧地图）
                if "collision" in tile_set_data:
                    # 如果有全局collision属性，为每个图块设置相同的碰撞状态
                    collision_value = tile_set_data["collision"]
                    tile_count = tile_set_data.get("tile_count", 0)
                    tile_set["tiles"] = [{"collision": collision_value} for _ in range(tile_count)]
                elif "tiles" in tile_set_data:
                    # 如果已有tiles数组，直接使用
                    tile_set["tiles"] = tile_set_data["tiles"]
                
                self.map_data["tile_sets"].append(tile_set)
            
            # 遍历JSON中的layers，将列表读回，重新构建为以(x, y)为键的字典
            for layer_data in loaded_data["layers"]:
                # 创建图层结构
                layer = {
                    "name": layer_data["name"],
                    "visible": layer_data["visible"],
                    "tiles": {},
                    "objects": layer_data.get("objects", [])
                }
                
                # 将[[x, y, id], ...]转换为{(x, y): id}
                tiles_data = layer_data["tiles"]
                for tile_data in tiles_data:
                    if len(tile_data) == 3:
                        tx, ty, tid = tile_data
                        if tid != 0:
                            layer["tiles"][(int(tx), int(ty))] = int(tid)
                
                self.map_data["layers"].append(layer)
            
            # 记录加载的所有瓦片坐标
            try:
                import os
                import datetime
                
                record_dir = "/Volumes/WorkStation/MyWork/CodeStation/MyIDE/MyWorkspace/备份"
                os.makedirs(record_dir, exist_ok=True)
                record_file = os.path.join(record_dir, "coordinate_log.md")
                
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                with open(record_file, 'a', encoding='utf-8') as f_record:
                    f_record.write(f"## {timestamp} - Load Map\n\n")
                    f_record.write(f"**File Path:** {file_path}\n\n")
                    f_record.write("**Tiles Loaded:**\n\n")
                    
                    for layer_idx, layer_data in enumerate(loaded_data["layers"]):
                        f_record.write(f"### Layer {layer_idx}: {layer_data['name']}\n\n")
                        for tile in layer_data["tiles"]:
                            f_record.write(f"- [x={tile[0]}, y={tile[1]}] -> ID: {tile[2]}\n")
                        f_record.write("\n")
                        
            except Exception as e:
                print(f"记录加载坐标错误: {e}")
            
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
            "tile_count": 0,  # 将在加载图片后计算
            "tiles": []  # 每个图块单独的碰撞设置
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
    
    def set_tile_collision(self, tile_set_index, tile_index, collision):
        """设置单个图块的碰撞状态"""
        if 0 <= tile_set_index < len(self.map_data["tile_sets"]):
            tile_set = self.map_data["tile_sets"][tile_set_index]
            # 确保tiles数组足够大
            while len(tile_set["tiles"]) <= tile_index:
                tile_set["tiles"].append({"collision": True})  # 默认开启碰撞
            tile_set["tiles"][tile_index]["collision"] = collision
            self.data_changed.emit()
            return True
        return False
    
    def get_tile_collision(self, tile_set_index, tile_index):
        """获取单个图块的碰撞状态"""
        if 0 <= tile_set_index < len(self.map_data["tile_sets"]):
            tile_set = self.map_data["tile_sets"][tile_set_index]
            if 0 <= tile_index < len(tile_set["tiles"]):
                return tile_set["tiles"][tile_index].get("collision", True)
        return True
    
    def set_tile_set_collision(self, index, collision):
        """设置整个瓦片集的碰撞状态（兼容旧方法）"""
        if 0 <= index < len(self.map_data["tile_sets"]):
            tile_set = self.map_data["tile_sets"][index]
            # 为所有图块设置相同的碰撞状态
            for i in range(len(tile_set["tiles"])):
                tile_set["tiles"][i]["collision"] = collision
            self.data_changed.emit()
            return True
        return False
    
    def get_tile_set_collision(self, index):
        """获取瓦片集的碰撞状态（兼容旧方法，返回第一个图块的状态）"""
        if 0 <= index < len(self.map_data["tile_sets"]):
            tile_set = self.map_data["tile_sets"][index]
            if tile_set["tiles"]:
                return tile_set["tiles"][0].get("collision", True)
        return True
