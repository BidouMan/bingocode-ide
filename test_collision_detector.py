#!/usr/bin/env python3
"""碰撞检测算法测试"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.collision_detector import CollisionDetector
from modules.collision_data import CollisionData, RectangleShape, CircleShape, PolygonShape


def test_aabb_overlap():
    """测试AABB快速检测"""
    print("=== 测试AABB快速检测 ===")
    
    # 测试碰撞
    rect1 = [0, 0, 32, 32]
    rect2 = [16, 16, 48, 48]
    result = CollisionDetector.aabb_overlap(rect1, rect2)
    print(f"重叠测试 (碰撞): {result}")
    assert result == True, "应该碰撞"
    
    # 测试不碰撞
    rect1 = [0, 0, 32, 32]
    rect2 = [32, 32, 64, 64]
    result = CollisionDetector.aabb_overlap(rect1, rect2)
    print(f"重叠测试 (不碰撞): {result}")
    assert result == False, "不应该碰撞"
    
    # 测试边缘碰撞
    rect1 = [0, 0, 32, 32]
    rect2 = [32, 0, 64, 32]
    result = CollisionDetector.aabb_overlap(rect1, rect2)
    print(f"重叠测试 (边缘碰撞): {result}")
    assert result == False, "边缘不应该碰撞"
    
    print("✓ AABB快速检测测试通过")


def test_rectangle_collision():
    """测试矩形碰撞检测"""
    print("\n=== 测试矩形碰撞检测 ===")
    
    # 创建矩形形状
    rectangle = RectangleShape(0, 0, 32, 32)
    
    # 测试碰撞
    hitbox1 = [16, 16, 48, 48]
    result = CollisionDetector.check_rectangle_collision(hitbox1, rectangle)
    print(f"矩形碰撞测试 (碰撞): {result}")
    assert result == True, "应该碰撞"
    
    # 测试不碰撞
    hitbox2 = [32, 32, 64, 64]
    result = CollisionDetector.check_rectangle_collision(hitbox2, rectangle)
    print(f"矩形碰撞测试 (不碰撞): {result}")
    assert result == False, "不应该碰撞"
    
    # 测试包含关系
    hitbox3 = [8, 8, 24, 24]
    result = CollisionDetector.check_rectangle_collision(hitbox3, rectangle)
    print(f"矩形碰撞测试 (包含): {result}")
    assert result == True, "应该碰撞"
    
    print("✓ 矩形碰撞检测测试通过")


def test_circle_collision():
    """测试圆形碰撞检测"""
    print("\n=== 测试圆形碰撞检测 ===")
    
    # 创建圆形形状
    circle = CircleShape(16, 16, 16)
    
    # 测试碰撞
    hitbox1 = [0, 0, 32, 32]
    result = CollisionDetector.check_circle_collision(hitbox1, circle)
    print(f"圆形碰撞测试 (碰撞): {result}")
    assert result == True, "应该碰撞"
    
    # 测试不碰撞
    hitbox2 = [32, 32, 64, 64]
    result = CollisionDetector.check_circle_collision(hitbox2, circle)
    print(f"圆形碰撞测试 (不碰撞): {result}")
    assert result == False, "不应该碰撞"
    
    # 测试边缘碰撞
    hitbox3 = [32, 0, 64, 32]
    result = CollisionDetector.check_circle_collision(hitbox3, circle)
    print(f"圆形碰撞测试 (边缘碰撞): {result}")
    assert result == True, "应该碰撞"
    
    print("✓ 圆形碰撞检测测试通过")


def test_polygon_collision():
    """测试多边形碰撞检测"""
    print("\n=== 测试多边形碰撞检测 ===")
    
    # 创建正方形多边形
    square_points = [(0, 0), (32, 0), (32, 32), (0, 32)]
    polygon = PolygonShape(square_points)
    
    # 测试碰撞
    hitbox1 = [16, 16, 48, 48]
    result = CollisionDetector.check_polygon_collision(hitbox1, polygon)
    print(f"多边形碰撞测试 (碰撞): {result}")
    assert result == True, "应该碰撞"
    
    # 测试不碰撞
    hitbox2 = [33, 33, 65, 65]  # 完全不接触的位置
    result = CollisionDetector.check_polygon_collision(hitbox2, polygon)
    print(f"多边形碰撞测试 (不碰撞): {result}")
    assert result == False, "不应该碰撞"
    
    # 创建三角形多边形
    triangle_points = [(0, 0), (32, 0), (16, 32)]
    triangle = PolygonShape(triangle_points)
    
    hitbox3 = [8, 8, 24, 24]
    result = CollisionDetector.check_polygon_collision(hitbox3, triangle)
    print(f"三角形碰撞测试 (碰撞): {result}")
    assert result == True, "应该碰撞"
    
    print("✓ 多边形碰撞检测测试通过")


def test_hierarchical_collision():
    """测试分级碰撞检测"""
    print("\n=== 测试分级碰撞检测 ===")
    
    # 创建碰撞数据
    collision_data = CollisionData("test")
    
    # 测试矩形碰撞
    rectangle = RectangleShape(0, 0, 32, 32)
    collision_data.set_shape(rectangle)
    
    hitbox1 = [16, 16, 48, 48]
    result = CollisionDetector.check_collision(hitbox1, collision_data)
    print(f"分级检测 (矩形碰撞): {result}")
    assert result == True, "应该碰撞"
    
    hitbox2 = [32, 32, 64, 64]
    result = CollisionDetector.check_collision(hitbox2, collision_data)
    print(f"分级检测 (矩形不碰撞): {result}")
    assert result == False, "不应该碰撞"
    
    # 测试圆形碰撞
    circle = CircleShape(16, 16, 16)
    collision_data.set_shape(circle)
    
    hitbox3 = [0, 0, 32, 32]
    result = CollisionDetector.check_collision(hitbox3, collision_data)
    print(f"分级检测 (圆形碰撞): {result}")
    assert result == True, "应该碰撞"
    
    print("✓ 分级碰撞检测测试通过")


def test_one_way_collision():
    """测试单向碰撞"""
    print("\n=== 测试单向碰撞 ===")
    
    # 创建单向碰撞数据
    collision_data = CollisionData("platform")
    collision_data.set_shape(RectangleShape(0, 0, 100, 10))
    collision_data.properties.one_way = True
    collision_data.properties.one_way_direction = "top"
    
    # 测试从下方碰撞（应该碰撞）
    hitbox = [50, 5, 60, 15]  # 与矩形重叠的位置
    velocity = (0, -5)  # 向上移动
    result = CollisionDetector.check_one_way_collision(hitbox, collision_data, velocity)
    print(f"单向碰撞测试 (从下方碰撞): {result}")
    assert result == True, "应该碰撞"
    
    # 测试从上方碰撞（不应该碰撞）
    hitbox = [50, -5, 60, 5]  # 与矩形重叠的位置
    velocity = (0, 5)  # 向下移动
    result = CollisionDetector.check_one_way_collision(hitbox, collision_data, velocity)
    print(f"单向碰撞测试 (从上方碰撞): {result}")
    assert result == False, "不应该碰撞"
    
    # 测试非单向碰撞
    collision_data.properties.one_way = False
    result = CollisionDetector.check_one_way_collision(hitbox, collision_data, velocity)
    print(f"单向碰撞测试 (非单向碰撞): {result}")
    assert result == True, "应该碰撞"
    
    print("✓ 单向碰撞测试通过")


def test_performance():
    """测试性能"""
    print("\n=== 测试性能 ===")
    
    # 创建测试数据
    collision_data = CollisionData("test")
    collision_data.set_shape(RectangleShape(0, 0, 32, 32))
    
    hitbox = [16, 16, 48, 48]
    
    # 测试AABB性能
    start_time = time.time()
    for i in range(100000):
        CollisionDetector.aabb_overlap(hitbox, collision_data.aabb)
    aabb_time = time.time() - start_time
    
    # 测试分级检测性能
    start_time = time.time()
    for i in range(100000):
        CollisionDetector.check_collision(hitbox, collision_data)
    collision_time = time.time() - start_time
    
    print(f"AABB检测性能: {100000 / aabb_time:.2f}次/秒")
    print(f"分级检测性能: {100000 / collision_time:.2f}次/秒")
    
    # 验证性能
    assert aabb_time < 0.1, f"AABB检测太慢: {aabb_time}秒"
    assert collision_time < 0.2, f"分级检测太慢: {collision_time}秒"
    
    print("✓ 性能测试通过")


def test_edge_cases():
    """测试边界情况"""
    print("\n=== 测试边界情况 ===")
    
    # 测试空多边形
    try:
        empty_polygon = PolygonShape([])
        hitbox = [0, 0, 32, 32]
        result = CollisionDetector.check_polygon_collision(hitbox, empty_polygon)
        print(f"空多边形测试: {result}")
    except Exception as e:
        print(f"空多边形测试: 正确抛出异常")
    
    # 测试极大坐标
    collision_data = CollisionData("large")
    collision_data.set_shape(RectangleShape(1000000, 1000000, 32, 32))
    
    hitbox1 = [1000016, 1000016, 1000048, 1000048]
    result = CollisionDetector.check_collision(hitbox1, collision_data)
    print(f"大坐标测试 (碰撞): {result}")
    assert result == True, "应该碰撞"
    
    hitbox2 = [0, 0, 32, 32]
    result = CollisionDetector.check_collision(hitbox2, collision_data)
    print(f"大坐标测试 (不碰撞): {result}")
    assert result == False, "不应该碰撞"
    
    print("✓ 边界情况测试通过")


def main():
    """运行所有测试"""
    print("开始碰撞检测算法测试...")
    
    try:
        test_aabb_overlap()
        test_rectangle_collision()
        test_circle_collision()
        test_polygon_collision()
        test_hierarchical_collision()
        test_one_way_collision()
        test_performance()
        test_edge_cases()
        
        print("\n🎉 所有测试通过！")
        return True
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
