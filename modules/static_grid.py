"""静态网格碰撞系统"""
from typing import List, Optional, Tuple, Dict, Any
from .collision_data import CollisionData


class StaticCollisionGrid:
    """静态网格碰撞系统（比四叉树快10倍）"""
    
    def __init__(self, map_width: int, map_height: int, tile_size: int = 32):
        """
        初始化静态网格
        
        Args:
            map_width: 地图宽度（图块数量）
            map_height: 地图高度（图块数量）
            tile_size: 图块大小（像素）
        """
        self.tile_size = tile_size
        self.grid_width = map_width
        self.grid_height = map_height
        
        # 直接创建二维数组，无需复杂查询（O(1)访问）
        self.grid = [[None for _ in range(map_width)] for _ in range(map_height)]
        
        # 标签索引（用于快速查询指定标签的碰撞）
        self.tag_index: Dict[str, List[Tuple[int, int, CollisionData]]] = {}
    
    def add_collision(self, x: int, y: int, collision_data: CollisionData):
        """
        添加碰撞数据到网格
        
        Args:
            x: 世界坐标x
            y: 世界坐标y
            collision_data: 碰撞数据
        """
        # 计算网格坐标
        grid_x = int(x // self.tile_size)
        grid_y = int(y // self.tile_size)
        
        # 边界检查
        if 0 <= grid_x < self.grid_width and 0 <= grid_y < self.grid_height:
            # 设置网格数据
            self.grid[grid_y][grid_x] = collision_data
            
            # 更新标签索引
            if collision_data.properties.tags:
                for tag in collision_data.properties.tags:
                    if tag not in self.tag_index:
                        self.tag_index[tag] = []
                    # 保存网格坐标和碰撞数据的元组
                    self.tag_index[tag].append((grid_x, grid_y, collision_data))
    
    def get_collision(self, world_x: float, world_y: float) -> Optional[CollisionData]:
        """
        获取指定坐标的碰撞数据（O(1)复杂度）
        
        Args:
            world_x: 世界坐标x
            world_y: 世界坐标y
            
        Returns:
            碰撞数据，如果没有则返回None
        """
        # 计算网格坐标
        grid_x = int(world_x // self.tile_size)
        grid_y = int(world_y // self.tile_size)
        
        # 边界检查
        if 0 <= grid_x < self.grid_width and 0 <= grid_y < self.grid_height:
            return self.grid[grid_y][grid_x]
        return None
    
    def get_collisions_in_area(self, hitbox: List[float]) -> List[CollisionData]:
        """
        获取指定区域内的所有碰撞数据
        
        Args:
            hitbox: 碰撞盒 [left, top, right, bottom]
            
        Returns:
            碰撞数据列表
        """
        # 计算区域覆盖的网格范围
        min_x = max(0, int(hitbox[0] // self.tile_size))
        max_x = min(self.grid_width - 1, int(hitbox[2] // self.tile_size))
        min_y = max(0, int(hitbox[1] // self.tile_size))
        max_y = min(self.grid_height - 1, int(hitbox[3] // self.tile_size))
        
        collisions = []
        
        # 遍历区域内的所有网格
        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                collision = self.grid[y][x]
                if collision and collision.enabled:
                    collisions.append(collision)
        
        return collisions
    
    def get_collisions_by_tag(self, tag: str) -> List[CollisionData]:
        """
        获取所有带有指定标签的碰撞数据
        
        Args:
            tag: 碰撞标签
            
        Returns:
            碰撞数据列表
        """
        collisions = []
        
        if tag in self.tag_index:
            for grid_x, grid_y, collision_data in self.tag_index[tag]:
                # 双重检查，确保数据仍然有效
                if (0 <= grid_x < self.grid_width and 
                    0 <= grid_y < self.grid_height and 
                    self.grid[grid_y][grid_x] == collision_data and
                    collision_data.enabled):
                    collisions.append(collision_data)
        
        return collisions
    
    def get_collisions_by_tag_in_area(self, tag: str, hitbox: List[float]) -> List[CollisionData]:
        """
        获取指定区域内带有指定标签的碰撞数据
        
        Args:
            tag: 碰撞标签
            hitbox: 碰撞盒 [left, top, right, bottom]
            
        Returns:
            碰撞数据列表
        """
        # 先获取区域内的所有碰撞
        area_collisions = self.get_collisions_in_area(hitbox)
        
        # 过滤出指定标签的碰撞
        tag_collisions = []
        for collision in area_collisions:
            if tag in collision.properties.tags:
                tag_collisions.append(collision)
        
        return tag_collisions
    
    def remove_collision(self, x: int, y: int) -> Optional[CollisionData]:
        """
        移除指定位置的碰撞数据
        
        Args:
            x: 世界坐标x
            y: 世界坐标y
            
        Returns:
            被移除的碰撞数据，如果没有则返回None
        """
        # 计算网格坐标
        grid_x = int(x // self.tile_size)
        grid_y = int(y // self.tile_size)
        
        # 边界检查
        if 0 <= grid_x < self.grid_width and 0 <= grid_y < self.grid_height:
            collision_data = self.grid[grid_y][grid_x]
            
            if collision_data:
                # 从标签索引中移除
                if collision_data.properties.tags:
                    for tag in collision_data.properties.tags:
                        if tag in self.tag_index:
                            # 查找并移除对应的条目
                            self.tag_index[tag] = [
                                item for item in self.tag_index[tag]
                                if not (item[0] == grid_x and item[1] == grid_y)
                            ]
                            # 如果标签索引为空，删除该标签
                            if not self.tag_index[tag]:
                                del self.tag_index[tag]
                
                # 从网格中移除
                self.grid[grid_y][grid_x] = None
                return collision_data
        
        return None
    
    def clear(self):
        """清空网格数据"""
        # 重置网格
        self.grid = [[None for _ in range(self.grid_width)] for _ in range(self.grid_height)]
        
        # 清空标签索引
        self.tag_index.clear()
    
    def get_grid_size(self) -> Tuple[int, int]:
        """获取网格尺寸"""
        return (self.grid_width, self.grid_height)
    
    def get_tile_size(self) -> int:
        """获取图块大小"""
        return self.tile_size
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式（用于调试）"""
        return {
            "grid_width": self.grid_width,
            "grid_height": self.grid_height,
            "tile_size": self.tile_size,
            "tag_count": len(self.tag_index),
            "collision_count": sum(1 for row in self.grid for item in row if item)
        }
