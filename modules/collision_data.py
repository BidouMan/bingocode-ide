"""碰撞数据结构定义"""
from typing import List, Dict, Any, Optional


class CollisionShape:
    """碰撞形状基类"""
    def __init__(self, shape_type: str):
        self.type = shape_type
    
    def get_aabb(self) -> List[float]:
        """获取边界框 [left, top, right, bottom]"""
        raise NotImplementedError


class RectangleShape(CollisionShape):
    """矩形碰撞形状"""
    def __init__(self, x: float, y: float, width: float, height: float):
        super().__init__("rectangle")
        self.x = x
        self.y = y
        self.width = width
        self.height = height
    
    def get_aabb(self) -> List[float]:
        """获取边界框"""
        return [self.x, self.y, self.x + self.width, self.y + self.height]


class CircleShape(CollisionShape):
    """圆形碰撞形状"""
    def __init__(self, x: float, y: float, radius: float):
        super().__init__("circle")
        self.x = x
        self.y = y
        self.radius = radius
    
    def get_aabb(self) -> List[float]:
        """获取边界框"""
        return [
            self.x - self.radius,
            self.y - self.radius,
            self.x + self.radius,
            self.y + self.radius
        ]


class PolygonShape(CollisionShape):
    """多边形碰撞形状"""
    def __init__(self, points: List[tuple]):
        super().__init__("polygon")
        # 限制多边形顶点数不超过8个（性能优化）
        if len(points) > 8:
            raise ValueError("多边形顶点数不能超过8个")
        self.points = points
    
    def get_aabb(self) -> List[float]:
        """获取边界框"""
        if not self.points:
            return [0, 0, 0, 0]
        
        min_x = min(p[0] for p in self.points)
        max_x = max(p[0] for p in self.points)
        min_y = min(p[1] for p in self.points)
        max_y = max(p[1] for p in self.points)
        
        return [min_x, min_y, max_x, max_y]


class CollisionProperties:
    """碰撞属性"""
    def __init__(self):
        self.tags: List[str] = []
        self.one_way: bool = False
        self.one_way_direction: str = "top"  # top, bottom, left, right
        self.collision_type: str = "solid"  # solid, trigger, damage


class CollisionData:
    """碰撞数据"""
    def __init__(self, tile_id: str):
        self.tile_id = tile_id
        self.enabled: bool = True
        self.shape: Optional[CollisionShape] = None
        self.properties: CollisionProperties = CollisionProperties()
        self.aabb: List[float] = [0, 0, 0, 0]  # 预计算的AABB边界框
    
    def set_shape(self, shape: CollisionShape):
        """设置碰撞形状并更新AABB"""
        self.shape = shape
        self.aabb = shape.get_aabb()
    
    def add_tag(self, tag: str):
        """添加碰撞标签"""
        if tag not in self.properties.tags:
            self.properties.tags.append(tag)
    
    def remove_tag(self, tag: str):
        """移除碰撞标签"""
        if tag in self.properties.tags:
            self.properties.tags.remove(tag)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        shape_data = {}
        if self.shape:
            if self.shape.type == "rectangle":
                shape_data = {
                    "x": self.shape.x,
                    "y": self.shape.y,
                    "width": self.shape.width,
                    "height": self.shape.height
                }
            elif self.shape.type == "circle":
                shape_data = {
                    "x": self.shape.x,
                    "y": self.shape.y,
                    "radius": self.shape.radius
                }
            elif self.shape.type == "polygon":
                shape_data = {
                    "points": self.shape.points
                }
        
        return {
            "tile_id": self.tile_id,
            "collision": {
                "enabled": self.enabled,
                "type": self.shape.type if self.shape else "rectangle",
                "shape": shape_data,
                "properties": {
                    "tags": self.properties.tags,
                    "one_way": self.properties.one_way,
                    "one_way_direction": self.properties.one_way_direction,
                    "collision_type": self.properties.collision_type
                }
            },
            "aabb": self.aabb
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CollisionData":
        """从字典创建碰撞数据"""
        collision_data = cls(data["tile_id"])
        collision_data.enabled = data["collision"]["enabled"]
        
        # 创建碰撞形状
        shape_type = data["collision"]["type"]
        shape_data = data["collision"]["shape"]
        
        if shape_type == "rectangle":
            shape = RectangleShape(
                shape_data["x"],
                shape_data["y"],
                shape_data["width"],
                shape_data["height"]
            )
        elif shape_type == "circle":
            shape = CircleShape(
                shape_data["x"],
                shape_data["y"],
                shape_data["radius"]
            )
        elif shape_type == "polygon":
            shape = PolygonShape(shape_data["points"])
        else:
            # 默认创建矩形
            shape = RectangleShape(0, 0, 32, 32)
        
        collision_data.set_shape(shape)
        
        # 设置属性
        properties = data["collision"]["properties"]
        collision_data.properties.tags = properties.get("tags", [])
        collision_data.properties.one_way = properties.get("one_way", False)
        collision_data.properties.one_way_direction = properties.get("one_way_direction", "top")
        collision_data.properties.collision_type = properties.get("collision_type", "solid")
        
        # 设置AABB
        collision_data.aabb = data.get("aabb", shape.get_aabb())
        
        return collision_data


# 碰撞类型常量
COLLISION_TYPES = {
    "rectangle": 0,
    "circle": 1,
    "polygon": 2
}
