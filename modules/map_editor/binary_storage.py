"""二进制存储系统"""
import struct
import numpy as np
import zlib
import json
from typing import Dict, Any, List, Tuple
from models.collision_data import CollisionData


class BinaryStorage:
    """二进制存储系统"""
    
    # 文件格式常量
    MAGIC_NUMBER = 0x4D415050  # "MAP_"
    VERSION = 1
    
    @staticmethod
    def save_map_binary(map_data: Dict[str, Any], file_path: str):
        """
        保存地图数据为二进制格式
        
        Args:
            map_data: 地图数据字典
            file_path: 文件路径
        """
        with open(file_path, 'wb') as f:
            # 写入文件头
            f.write(struct.pack('<I', BinaryStorage.MAGIC_NUMBER))
            f.write(struct.pack('<I', BinaryStorage.VERSION))
            
            # 写入地图尺寸
            width = map_data.get('width', 0)
            height = map_data.get('height', 0)
            f.write(struct.pack('<II', width, height))
            
            # 写入图块数据
            if 'tiles' in map_data:
                # 创建numpy数组存储图块数据
                tile_array = np.zeros((height, width), dtype=np.uint16)
                
                # 填充图块数据
                for (x, y), tile_id in map_data['tiles'].items():
                    if 0 <= x < width and 0 <= y < height:
                        tile_array[y][x] = tile_id
                
                # 一次性写入所有数据
                tile_array.tofile(f)
    
    @staticmethod
    def load_map_binary(file_path: str) -> Dict[str, Any]:
        """
        从二进制文件加载地图数据
        
        Args:
            file_path: 文件路径
            
        Returns:
            地图数据字典
        """
        with open(file_path, 'rb') as f:
            # 读取文件头
            magic = struct.unpack('<I', f.read(4))[0]
            if magic != BinaryStorage.MAGIC_NUMBER:
                raise ValueError("无效的文件格式")
            
            version = struct.unpack('<I', f.read(4))[0]
            if version != BinaryStorage.VERSION:
                raise ValueError(f"不支持的文件版本: {version}")
            
            # 读取地图尺寸
            width, height = struct.unpack('<II', f.read(8))
            
            # 使用numpy一次性加载所有图块数据
            tile_data = np.fromfile(f, dtype=np.uint16, count=width * height)
            tile_grid = tile_data.reshape((height, width))
            
            # 构建稀疏图块数据
            tiles = {}
            for y in range(height):
                for x in range(width):
                    tile_id = tile_grid[y][x]
                    if tile_id > 0:
                        tiles[(x, y)] = tile_id
            
            return {
                'width': width,
                'height': height,
                'tiles': tiles
            }
    
    @staticmethod
    def save_collision_data(collision_data_list: List[CollisionData], file_path: str):
        """
        保存碰撞数据为二进制格式
        
        Args:
            collision_data_list: 碰撞数据列表
            file_path: 文件路径
        """
        # 转换为字典格式
        data_list = [collision.to_dict() for collision in collision_data_list]
        
        # 使用zlib压缩数据
        json_data = json.dumps(data_list, separators=(',', ':')).encode('utf-8')
        compressed_data = zlib.compress(json_data, level=9)
        
        with open(file_path, 'wb') as f:
            # 写入文件头
            f.write(struct.pack('<I', BinaryStorage.MAGIC_NUMBER))
            f.write(struct.pack('<I', BinaryStorage.VERSION))
            
            # 写入压缩数据大小
            f.write(struct.pack('<I', len(compressed_data)))
            
            # 写入压缩数据
            f.write(compressed_data)
    
    @staticmethod
    def load_collision_data(file_path: str) -> List[CollisionData]:
        """
        从二进制文件加载碰撞数据
        
        Args:
            file_path: 文件路径
            
        Returns:
            碰撞数据列表
        """
        with open(file_path, 'rb') as f:
            # 读取文件头
            magic = struct.unpack('<I', f.read(4))[0]
            if magic != BinaryStorage.MAGIC_NUMBER:
                raise ValueError("无效的文件格式")
            
            version = struct.unpack('<I', f.read(4))[0]
            if version != BinaryStorage.VERSION:
                raise ValueError(f"不支持的文件版本: {version}")
            
            # 读取压缩数据大小
            data_size = struct.unpack('<I', f.read(4))[0]
            
            # 读取压缩数据
            compressed_data = f.read(data_size)
            
            # 解压缩数据
            json_data = zlib.decompress(compressed_data)
            data_list = json.loads(json_data.decode('utf-8'))
            
            # 转换为CollisionData对象
            collision_data_list = []
            for data in data_list:
                collision_data = CollisionData.from_dict(data)
                collision_data_list.append(collision_data)
            
            return collision_data_list
    
    @staticmethod
    def save_metadata(metadata: Dict[str, Any], file_path: str):
        """
        保存元数据为二进制格式
        
        Args:
            metadata: 元数据字典
            file_path: 文件路径
        """
        # 使用zlib压缩数据
        json_data = json.dumps(metadata, separators=(',', ':')).encode('utf-8')
        compressed_data = zlib.compress(json_data, level=9)
        
        with open(file_path, 'wb') as f:
            # 写入文件头
            f.write(struct.pack('<I', BinaryStorage.MAGIC_NUMBER))
            f.write(struct.pack('<I', BinaryStorage.VERSION))
            
            # 写入压缩数据大小
            f.write(struct.pack('<I', len(compressed_data)))
            
            # 写入压缩数据
            f.write(compressed_data)
    
    @staticmethod
    def load_metadata(file_path: str) -> Dict[str, Any]:
        """
        从二进制文件加载元数据
        
        Args:
            file_path: 文件路径
            
        Returns:
            元数据字典
        """
        with open(file_path, 'rb') as f:
            # 读取文件头
            magic = struct.unpack('<I', f.read(4))[0]
            if magic != BinaryStorage.MAGIC_NUMBER:
                raise ValueError("无效的文件格式")
            
            version = struct.unpack('<I', f.read(4))[0]
            if version != BinaryStorage.VERSION:
                raise ValueError(f"不支持的文件版本: {version}")
            
            # 读取压缩数据大小
            data_size = struct.unpack('<I', f.read(4))[0]
            
            # 读取压缩数据
            compressed_data = f.read(data_size)
            
            # 解压缩数据
            json_data = zlib.decompress(compressed_data)
            metadata = json.loads(json_data.decode('utf-8'))
            
            return metadata
    
    @staticmethod
    def save_resources(resources: Dict[str, Any], file_path: str):
        """
        保存资源数据为二进制格式
        
        Args:
            resources: 资源数据字典
            file_path: 文件路径
        """
        BinaryStorage.save_metadata(resources, file_path)
    
    @staticmethod
    def load_resources(file_path: str) -> Dict[str, Any]:
        """
        从二进制文件加载资源数据
        
        Args:
            file_path: 文件路径
            
        Returns:
            资源数据字典
        """
        return BinaryStorage.load_metadata(file_path)


class MapFileManager:
    """地图文件管理器"""
    
    def __init__(self, base_path: str):
        """
        初始化地图文件管理器
        
        Args:
            base_path: 地图文件基础路径
        """
        self.base_path = base_path
    
    def save_map(self, map_data: Dict[str, Any], collision_data: List[CollisionData], 
                 metadata: Dict[str, Any], resources: Dict[str, Any]):
        """
        保存完整的地图数据
        
        Args:
            map_data: 地图数据
            collision_data: 碰撞数据列表
            metadata: 元数据
            resources: 资源数据
        """
        # 保存图块数据
        BinaryStorage.save_map_binary(map_data, f"{self.base_path}.tiles")
        
        # 保存碰撞数据
        BinaryStorage.save_collision_data(collision_data, f"{self.base_path}.collision")
        
        # 保存元数据
        BinaryStorage.save_metadata(metadata, f"{self.base_path}.info")
        
        # 保存资源数据
        BinaryStorage.save_resources(resources, f"{self.base_path}.resources")
    
    def load_map(self) -> Tuple[Dict[str, Any], List[CollisionData], Dict[str, Any], Dict[str, Any]]:
        """
        加载完整的地图数据
        
        Returns:
            (地图数据, 碰撞数据列表, 元数据, 资源数据)
        """
        # 加载图块数据
        map_data = BinaryStorage.load_map_binary(f"{self.base_path}.tiles")
        
        # 加载碰撞数据
        collision_data = BinaryStorage.load_collision_data(f"{self.base_path}.collision")
        
        # 加载元数据
        metadata = BinaryStorage.load_metadata(f"{self.base_path}.info")
        
        # 加载资源数据
        resources = BinaryStorage.load_resources(f"{self.base_path}.resources")
        
        return map_data, collision_data, metadata, resources
