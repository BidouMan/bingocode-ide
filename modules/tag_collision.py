"""标签碰撞系统"""
from typing import Dict, List, Tuple, Optional, Any
from .collision_data import CollisionData
from .static_grid import StaticCollisionGrid
from .collision_detector import CollisionDetector


class CollisionCache:
    """碰撞检测结果缓存"""
    
    def __init__(self, max_cache_size: int = 1000, max_age: int = 3):
        """
        初始化缓存
        
        Args:
            max_cache_size: 最大缓存大小
            max_age: 缓存最大保留帧数
        """
        self.cache = {}
        self.max_cache_size = max_cache_size
        self.max_age = max_age
        self.frame_count = 0
    
    def update_frame(self):
        """更新帧数"""
        self.frame_count += 1
    
    def get_result(self, sprite_id: int, tag: str, hitbox_hash: int) -> Optional[bool]:
        """
        获取缓存结果
        
        Args:
            sprite_id: 精灵ID
            tag: 碰撞标签
            hitbox_hash: 碰撞盒哈希值
            
        Returns:
            缓存的碰撞结果，如果没有则返回None
        """
        key = (sprite_id, tag, hitbox_hash)
        if key in self.cache:
            result, timestamp = self.cache[key]
            if self.frame_count - timestamp < self.max_age:
                return result
        return None
    
    def set_result(self, sprite_id: int, tag: str, hitbox_hash: int, result: bool):
        """
        设置缓存结果
        
        Args:
            sprite_id: 精灵ID
            tag: 碰撞标签
            hitbox_hash: 碰撞盒哈希值
            result: 碰撞结果
        """
        key = (sprite_id, tag, hitbox_hash)
        
        # 如果缓存已满，删除最旧的条目
        if len(self.cache) >= self.max_cache_size:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        
        self.cache[key] = (result, self.frame_count)
    
    def clear(self):
        """清空缓存"""
        self.cache.clear()


class TagCollisionSystem:
    """基于标签的碰撞检测系统"""
    
    def __init__(self, map_width: int, map_height: int, tile_size: int = 32):
        """
        初始化标签碰撞系统
        
        Args:
            map_width: 地图宽度（图块数量）
            map_height: 地图高度（图块数量）
            tile_size: 图块大小（像素）
        """
        self.collision_grid = StaticCollisionGrid(map_width, map_height, tile_size)
        self.collision_cache = CollisionCache()
        self.tag_index: Dict[str, List[CollisionData]] = {}
    
    def add_collision(self, x: int, y: int, collision_data: CollisionData):
        """
        添加碰撞数据
        
        Args:
            x: 世界坐标x
            y: 世界坐标y
            collision_data: 碰撞数据
        """
        # 添加到静态网格
        self.collision_grid.add_collision(x, y, collision_data)
        
        # 更新标签索引
        if collision_data.properties.tags:
            for tag in collision_data.properties.tags:
                if tag not in self.tag_index:
                    self.tag_index[tag] = []
                self.tag_index[tag].append(collision_data)
    
    def remove_collision(self, x: int, y: int) -> Optional[CollisionData]:
        """
        移除碰撞数据
        
        Args:
            x: 世界坐标x
            y: 世界坐标y
            
        Returns:
            被移除的碰撞数据，如果没有则返回None
        """
        collision_data = self.collision_grid.remove_collision(x, y)
        
        if collision_data:
            # 从标签索引中移除
            if collision_data.properties.tags:
                for tag in collision_data.properties.tags:
                    if tag in self.tag_index:
                        self.tag_index[tag] = [
                            cd for cd in self.tag_index[tag]
                            if cd != collision_data
                        ]
                        # 如果标签索引为空，删除该标签
                        if not self.tag_index[tag]:
                            del self.tag_index[tag]
        
        return collision_data
    
    def check_tag_collision(self, sprite_id: int, hitbox: List[float], tag: str, 
                          velocity: Tuple[float, float] = (0, 0)) -> bool:
        """
        检查精灵是否碰到指定标签的碰撞
        
        Args:
            sprite_id: 精灵ID
            hitbox: 碰撞盒 [left, top, right, bottom]
            tag: 碰撞标签
            velocity: 移动速度 (dx, dy)
            
        Returns:
            是否碰撞
        """
        # 如果标签不存在，直接返回False
        if tag not in self.tag_index:
            return False
        
        # 计算碰撞盒哈希用于缓存
        hitbox_hash = hash(tuple(hitbox))
        
        # 尝试从缓存获取结果
        cached_result = self.collision_cache.get_result(sprite_id, tag, hitbox_hash)
        if cached_result is not None:
            return cached_result
        
        # 获取区域内的所有碰撞
        area_collisions = self.collision_grid.get_collisions_in_area(hitbox)
        
        # 过滤出指定标签的碰撞
        tag_collisions = []
        for collision in area_collisions:
            if tag in collision.properties.tags:
                tag_collisions.append(collision)
        
        # 检查碰撞
        result = False
        for collision in tag_collisions:
            if collision.enabled:
                # 检查单向碰撞
                if collision.properties.one_way:
                    if CollisionDetector.check_one_way_collision(hitbox, collision, velocity):
                        result = True
                        break
                else:
                    # 普通碰撞检测
                    if CollisionDetector.check_collision(hitbox, collision):
                        result = True
                        break
        
        # 缓存结果
        self.collision_cache.set_result(sprite_id, tag, hitbox_hash, result)
        
        return result
    
    def check_multiple_tags(self, sprite_id: int, hitbox: List[float], 
                          tags: List[str], velocity: Tuple[float, float] = (0, 0)) -> Dict[str, bool]:
        """
        检查精灵是否碰到多个标签的碰撞
        
        Args:
            sprite_id: 精灵ID
            hitbox: 碰撞盒 [left, top, right, bottom]
            tags: 碰撞标签列表
            velocity: 移动速度 (dx, dy)
            
        Returns:
            标签碰撞结果字典
        """
        results = {}
        for tag in tags:
            results[tag] = self.check_tag_collision(sprite_id, hitbox, tag, velocity)
        return results
    
    def get_collisions_by_tag(self, tag: str) -> List[CollisionData]:
        """
        获取所有带有指定标签的碰撞数据
        
        Args:
            tag: 碰撞标签
            
        Returns:
            碰撞数据列表
        """
        return self.tag_index.get(tag, [])
    
    def update_frame(self):
        """更新帧数（用于缓存管理）"""
        self.collision_cache.update_frame()
    
    def clear(self):
        """清空所有数据"""
        self.collision_grid.clear()
        self.tag_index.clear()
        self.collision_cache.clear()
    
    def get_grid(self) -> StaticCollisionGrid:
        """获取静态网格"""
        return self.collision_grid
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        return {
            "cache_size": len(self.collision_cache.cache),
            "max_cache_size": self.collision_cache.max_cache_size,
            "frame_count": self.collision_cache.frame_count
        }
