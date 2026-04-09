"""碰撞检测算法实现"""
from typing import List, Tuple, Optional
from models.collision_data import CollisionData, RectangleShape, CircleShape, PolygonShape


class CollisionDetector:
    """碰撞检测器"""
    
    @staticmethod
    def aabb_overlap(rect1: List[float], rect2: List[float]) -> bool:
        """
        快速AABB碰撞检测
        
        Args:
            rect1: 第一个矩形 [left, top, right, bottom]
            rect2: 第二个矩形 [left, top, right, bottom]
            
        Returns:
            是否碰撞
        """
        # 使用严格的小于等于比较，边缘接触不算碰撞
        return not (rect1[2] <= rect2[0] or rect1[0] >= rect2[2] or 
                    rect1[3] <= rect2[1] or rect1[1] >= rect2[3])
    
    @staticmethod
    def check_rectangle_collision(hitbox: List[float], shape: RectangleShape) -> bool:
        """
        检查矩形碰撞
        
        Args:
            hitbox: 碰撞盒 [left, top, right, bottom]
            shape: 矩形形状
            
        Returns:
            是否碰撞
        """
        # 构建矩形的AABB
        rect_aabb = [
            shape.x,
            shape.y,
            shape.x + shape.width,
            shape.y + shape.height
        ]
        
        # 使用AABB检测
        return CollisionDetector.aabb_overlap(hitbox, rect_aabb)
    
    @staticmethod
    def check_circle_collision(hitbox: List[float], shape: CircleShape) -> bool:
        """
        检查圆形碰撞
        
        Args:
            hitbox: 碰撞盒 [left, top, right, bottom]
            shape: 圆形形状
            
        Returns:
            是否碰撞
        """
        # 计算碰撞盒的中心
        hitbox_center_x = (hitbox[0] + hitbox[2]) / 2
        hitbox_center_y = (hitbox[1] + hitbox[3]) / 2
        
        # 计算圆形到碰撞盒中心的距离
        dx = abs(hitbox_center_x - shape.x)
        dy = abs(hitbox_center_y - shape.y)
        
        # 如果距离大于圆形半径加上碰撞盒半宽/半高，则不碰撞
        hitbox_half_width = (hitbox[2] - hitbox[0]) / 2
        hitbox_half_height = (hitbox[3] - hitbox[1]) / 2
        
        if dx > hitbox_half_width + shape.radius:
            return False
        if dy > hitbox_half_height + shape.radius:
            return False
        
        # 如果距离小于碰撞盒半宽/半高，则一定碰撞
        if dx <= hitbox_half_width:
            return True
        if dy <= hitbox_half_height:
            return True
        
        # 检查角落碰撞
        corner_dx = dx - hitbox_half_width
        corner_dy = dy - hitbox_half_height
        corner_distance_squared = corner_dx * corner_dx + corner_dy * corner_dy
        
        return corner_distance_squared <= shape.radius * shape.radius
    
    @staticmethod
    def _project_points(points: List[Tuple[float, float]], axis: Tuple[float, float]) -> Tuple[float, float]:
        """
        将点投影到轴上
        
        Args:
            points: 点列表
            axis: 投影轴
            
        Returns:
            (min, max) 投影范围
        """
        min_val = float('inf')
        max_val = float('-inf')
        
        for x, y in points:
            projection = x * axis[0] + y * axis[1]
            min_val = min(min_val, projection)
            max_val = max(max_val, projection)
        
        return min_val, max_val
    
    @staticmethod
    def _overlap_on_axis(min1: float, max1: float, min2: float, max2: float) -> bool:
        """
        检查两个投影区间是否重叠
        
        Args:
            min1, max1: 第一个区间
            min2, max2: 第二个区间
            
        Returns:
            是否重叠
        """
        return not (max1 < min2 or max2 < min1)
    
    @staticmethod
    def check_polygon_collision(hitbox: List[float], shape: PolygonShape) -> bool:
        """
        检查多边形碰撞（使用分离轴定理）
        
        Args:
            hitbox: 碰撞盒 [left, top, right, bottom]
            shape: 多边形形状
            
        Returns:
            是否碰撞
        """
        # 将碰撞盒转换为多边形
        hitbox_points = [
            (hitbox[0], hitbox[1]),
            (hitbox[2], hitbox[1]),
            (hitbox[2], hitbox[3]),
            (hitbox[0], hitbox[3])
        ]
        
        polygon_points = shape.points
        
        # 生成所有可能的分离轴
        axes = []
        
        # 多边形的边
        for i in range(len(polygon_points)):
            p1 = polygon_points[i]
            p2 = polygon_points[(i + 1) % len(polygon_points)]
            edge = (p2[0] - p1[0], p2[1] - p1[1])
            # 垂直于边的轴
            axis = (-edge[1], edge[0])
            # 归一化
            length = (axis[0] ** 2 + axis[1] ** 2) ** 0.5
            if length > 0:
                axis = (axis[0] / length, axis[1] / length)
                axes.append(axis)
        
        # 碰撞盒的边
        for i in range(len(hitbox_points)):
            p1 = hitbox_points[i]
            p2 = hitbox_points[(i + 1) % len(hitbox_points)]
            edge = (p2[0] - p1[0], p2[1] - p1[1])
            # 垂直于边的轴
            axis = (-edge[1], edge[0])
            # 归一化
            length = (axis[0] ** 2 + axis[1] ** 2) ** 0.5
            if length > 0:
                axis = (axis[0] / length, axis[1] / length)
                axes.append(axis)
        
        # 检查所有轴
        for axis in axes:
            # 投影多边形
            poly_min, poly_max = CollisionDetector._project_points(polygon_points, axis)
            # 投影碰撞盒
            box_min, box_max = CollisionDetector._project_points(hitbox_points, axis)
            # 检查重叠
            if not CollisionDetector._overlap_on_axis(poly_min, poly_max, box_min, box_max):
                return False
        
        return True
    
    @staticmethod
    def check_collision(hitbox: List[float], collision_data: CollisionData) -> bool:
        """
        分级碰撞检测
        
        Args:
            hitbox: 碰撞盒 [left, top, right, bottom]
            collision_data: 碰撞数据
            
        Returns:
            是否碰撞
        """
        # 快速AABB检测（90%的碰撞在这一步就会被过滤）
        if not CollisionDetector.aabb_overlap(hitbox, collision_data.aabb):
            return False
        
        # 精确检测
        if collision_data.shape.type == "rectangle":
            return CollisionDetector.check_rectangle_collision(hitbox, collision_data.shape)
        elif collision_data.shape.type == "circle":
            return CollisionDetector.check_circle_collision(hitbox, collision_data.shape)
        elif collision_data.shape.type == "polygon":
            # 限制多边形顶点数（性能优化）
            if len(collision_data.shape.points) > 8:
                # 顶点太多，降级为AABB检测
                return True
            return CollisionDetector.check_polygon_collision(hitbox, collision_data.shape)
        
        return False
    
    @staticmethod
    def check_one_way_collision(hitbox: List[float], collision_data: CollisionData, 
                              velocity: Tuple[float, float] = (0, 0)) -> bool:
        """
        检查单向碰撞
        
        Args:
            hitbox: 碰撞盒 [left, top, right, bottom]
            collision_data: 碰撞数据
            velocity: 移动速度 (dx, dy)
            
        Returns:
            是否碰撞
        """
        # 不是单向碰撞，直接返回普通碰撞结果
        if not collision_data.properties.one_way:
            return CollisionDetector.check_collision(hitbox, collision_data)
        
        # 检查是否碰撞
        if not CollisionDetector.check_collision(hitbox, collision_data):
            return False
        
        # 根据方向判断是否应该碰撞
        direction = collision_data.properties.one_way_direction
        
        if direction == "top":
            # 只有从下方（向上移动）碰撞才有效
            return velocity[1] < 0
        elif direction == "bottom":
            # 只有从上方（向下移动）碰撞才有效
            return velocity[1] > 0
        elif direction == "left":
            # 只有从右侧（向左移动）碰撞才有效
            return velocity[0] < 0
        elif direction == "right":
            # 只有从左侧（向右移动）碰撞才有效
            return velocity[0] > 0
        
        return True
