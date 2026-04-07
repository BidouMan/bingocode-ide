import os
import json
import math
import numpy as np
from PySide6.QtCore import QObject, Signal


class ChunkedMapData:
    """区块化地图数据模型，使用空间哈希+NumPy矩阵的混血架构"""
    
    def __init__(self, chunk_size=16):
        self.chunk_size = chunk_size
        self.chunks = {}  # 结构: {(chunk_x, chunk_y): np.ndarray}
        self.empty_tile_id = 0

    def _get_or_create_chunk(self, chunk_x, chunk_y):
        """获取或创建指定区块"""
        chunk_key = (chunk_x, chunk_y)
        if chunk_key not in self.chunks:
            self.chunks[chunk_key] = np.full(
                (self.chunk_size, self.chunk_size),
                self.empty_tile_id,
                dtype=np.int32,
            )
        return self.chunks[chunk_key]

    def set_tile(self, world_x, world_y, tile_id):
        """设置世界坐标下的瓦片ID"""
        # 使用math.floor确保负数坐标也能正确归入对应的Chunk
        cx = math.floor(world_x / self.chunk_size)
        cy = math.floor(world_y / self.chunk_size)
        
        # 计算在Chunk内部的相对位置
        lx = world_x - (cx * self.chunk_size)
        ly = world_y - (cy * self.chunk_size)
        
        self._get_or_create_chunk(cx, cy)[ly, lx] = tile_id

    def get_tile(self, world_x, world_y):
        """获取世界坐标下的瓦片ID"""
        # 使用math.floor确保负数坐标也能正确归入对应的Chunk
        cx = math.floor(world_x / self.chunk_size)
        cy = math.floor(world_y / self.chunk_size)
        
        chunk_key = (cx, cy)
        if chunk_key not in self.chunks:
            return self.empty_tile_id
        
        # 计算在Chunk内部的相对位置
        lx = world_x - (cx * self.chunk_size)
        ly = world_y - (cy * self.chunk_size)
        
        return self.chunks[chunk_key][ly, lx]

    def get_visible_chunks(self, left, top, right, bottom):
        """返回当前屏幕视口内涵盖的所有区块"""
        start_cx = math.floor(left / self.chunk_size)
        end_cx = math.floor(right / self.chunk_size)
        start_cy = math.floor(top / self.chunk_size)
        end_cy = math.floor(bottom / self.chunk_size)

        visible = []
        for cy in range(start_cy, end_cy + 1):
            for cx in range(start_cx, end_cx + 1):
                if (cx, cy) in self.chunks:
                    visible.append((cx, cy, self.chunks[(cx, cy)]))
        return visible


class MapDataModel(QObject):
    """地图数据模型，管理地图的瓦片数据和文件操作"""
    
    data_changed = Signal()  # 数据变化信号
    
    def __init__(self, project_path=""):
        super().__init__()
        self.project_path = project_path
        self.map_data = {}
        self.layer_chunks = {}  # key: int 图层序号 → value: ChunkedMapData
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
                    "tiles": []  # 仅用于兼容导出，运行时使用 layer_chunks
                }
            ],
            "tile_sets": []       # 瓦片集配置
        }
        
        # 为默认图层创建 ChunkedMapData
        self.layer_chunks[0] = ChunkedMapData(chunk_size=16)
    
    def get_tile(self, layer_index, x, y):
        """获取指定位置的瓦片ID"""
        if 0 <= layer_index < len(self.map_data["layers"]):
            # 从 layer_chunks 获取数据，禁止遍历列表
            if layer_index in self.layer_chunks:
                return self.layer_chunks[layer_index].get_tile(x, y)
            return 0
        return 0
    
    def set_tile(self, layer_index, x, y, tile_id):
        """设置指定位置的瓦片ID，写入 layer_chunks"""
        if 0 <= layer_index < len(self.map_data["layers"]):
            # 写入 layer_chunks，禁止直接操作 layer["tiles"]
            if layer_index in self.layer_chunks:
                self.layer_chunks[layer_index].set_tile(x, y, tile_id)
                self.data_changed.emit()
                return True
            return False
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
            "tiles": []  # 仅用于兼容导出，运行时使用 layer_chunks
        }
        self.map_data["layers"].append(new_layer)
        new_index = len(self.map_data["layers"]) - 1
        self.layer_chunks[new_index] = ChunkedMapData(chunk_size=16)
        self.data_changed.emit()
        return new_index
    
    def remove_layer(self, index):
        """删除图层"""
        if 0 <= index < len(self.map_data["layers"]):
            del self.map_data["layers"][index]
            if index in self.layer_chunks:
                del self.layer_chunks[index]
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
            
            # 遍历 layer_chunks 中所有区块，收集所有非 0 瓦片
            for layer_index, layer in enumerate(self.map_data["layers"]):
                tiles_list = []
                
                # 从 ChunkedMapData 导出数据
                if layer_index in self.layer_chunks:
                    chunked_data = self.layer_chunks[layer_index]
                    
                    # 遍历所有区块
                    for (chunk_x, chunk_y), chunk in chunked_data.chunks.items():
                        # 遍历区块内的所有瓦片
                        for local_y in range(chunk.shape[0]):
                            for local_x in range(chunk.shape[1]):
                                tile_id = chunk[local_y, local_x]
                                if tile_id != 0:
                                    # 计算世界坐标
                                    world_x = chunk_x * chunked_data.chunk_size + local_x
                                    world_y = chunk_y * chunked_data.chunk_size + local_y
                                    # 将NumPy类型转换为Python原生类型，确保JSON可序列化
                                    tiles_list.append([int(world_x), int(world_y), int(tile_id)])
                
                layer_data = {
                    "name": layer["name"],
                    "visible": layer["visible"],
                    "tiles": tiles_list
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
                "tile_sets": loaded_data["tile_sets"]
            }
            
            # 清空所有 layer_chunks
            self.layer_chunks.clear()
            
            # 遍历 JSON 中的 layers
            for layer_data in loaded_data["layers"]:
                # 创建图层结构（仅用于兼容导出）
                layer = {
                    "name": layer_data["name"],
                    "visible": layer_data["visible"],
                    "tiles": []  # 仅用于兼容导出，运行时使用 layer_chunks
                }
                self.map_data["layers"].append(layer)
                
                # 获取图层索引
                layer_index = len(self.map_data["layers"]) - 1
                
                # 为图层创建 ChunkedMapData
                self.layer_chunks[layer_index] = ChunkedMapData(chunk_size=16)
                
                # 遍历 JSON 中的 tiles: [[x,y,tile_id], ...]
                tiles_data = layer_data["tiles"]
                
                # 检测格式：如果是二维数组（旧格式），转换为稀疏格式
                if tiles_data and isinstance(tiles_data[0], list) and isinstance(tiles_data[0][0], (int, float)):
                    # 旧格式：二维数组 [[tile_id, tile_id, ...], [tile_id, ...], ...]
                    for y, row in enumerate(tiles_data):
                        for x, tile_id in enumerate(row):
                            if tile_id != 0:
                                # 对每个点执行：chunk.set_tile(x, y, tile_id)
                                self.layer_chunks[layer_index].set_tile(x, y, tile_id)
                else:
                    # 新格式：稀疏格式 [[x, y, tile_id], [x, y, tile_id], ...]
                    # 首先确保当前图层的 chunked 实例已存在
                    if layer_index not in self.layer_chunks:
                        self.layer_chunks[layer_index] = ChunkedMapData(chunk_size=16)
                        
                    chunk_data = self.layer_chunks[layer_index]
                    
                    for tile_data in tiles_data:
                        if len(tile_data) == 3:
                            tx, ty, tid = tile_data
                            if tid != 0:
                                # 显式转换确保类型正确
                                chunk_data.set_tile(int(tx), int(ty), int(tid))
            
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