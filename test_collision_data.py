#!/usr/bin/env python3
"""碰撞数据结构测试"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.collision_data import (
    CollisionData, RectangleShape, CircleShape, PolygonShape
)


def test_rectangle_shape():
    """测试矩形碰撞形状"""
    print("=== 测试矩形碰撞形状 ===")
    shape = RectangleShape(10, 20, 32, 32)
    aabb = shape.get_aabb()
    print(f"矩形形状: x={shape.x}, y={shape.y}, width={shape.width}, height={shape.height}")
    print(f"AABB边界框: {aabb}")
    assert aabb == [10, 20, 42, 52], f"AABB计算错误: {aabb}"
    print("✓ 矩形形状测试通过")


def test_circle_shape():
    """测试圆形碰撞形状"""
    print("\n=== 测试圆形碰撞形状 ===")
    shape = CircleShape(50, 50, 16)
    aabb = shape.get_aabb()
    print(f"圆形形状: x={shape.x}, y={shape.y}, radius={shape.radius}")
    print(f"AABB边界框: {aabb}")
    assert aabb == [34, 34, 66, 66], f"AABB计算错误: {aabb}"
    print("✓ 圆形形状测试通过")


def test_polygon_shape():
    """测试多边形碰撞形状"""
    print("\n=== 测试多边形碰撞形状 ===")
    # 测试正常多边形
    points = [(0, 0), (32, 0), (32, 32), (0, 32)]
    shape = PolygonShape(points)
    aabb = shape.get_aabb()
    print(f"多边形形状: points={points}")
    print(f"AABB边界框: {aabb}")
    assert aabb == [0, 0, 32, 32], f"AABB计算错误: {aabb}"
    print("✓ 多边形形状测试通过")
    
    # 测试顶点数限制
    try:
        too_many_points = [(0, 0), (10, 0), (20, 0), (30, 0), (40, 0), 
                          (40, 10), (30, 10), (20, 10), (10, 10), (0, 10)]
        shape = PolygonShape(too_many_points)
        assert False, "应该抛出顶点数超限异常"
    except ValueError as e:
        print(f"✓ 多边形顶点数限制测试通过: {e}")


def test_collision_data():
    """测试碰撞数据"""
    print("\n=== 测试碰撞数据 ===")
    
    # 创建碰撞数据
    collision_data = CollisionData("0_5")
    rectangle = RectangleShape(0, 0, 32, 32)
    collision_data.set_shape(rectangle)
    
    # 测试标签功能
    collision_data.add_tag("ground")
    collision_data.add_tag("solid")
    collision_data.add_tag("ground")  # 重复添加
    print(f"标签列表: {collision_data.properties.tags}")
    assert collision_data.properties.tags == ["ground", "solid"], "标签添加错误"
    
    collision_data.remove_tag("solid")
    print(f"移除后标签列表: {collision_data.properties.tags}")
    assert collision_data.properties.tags == ["ground"], "标签移除错误"
    
    # 测试单向碰撞
    collision_data.properties.one_way = True
    collision_data.properties.one_way_direction = "top"
    print(f"单向碰撞: {collision_data.properties.one_way}, 方向: {collision_data.properties.one_way_direction}")
    
    # 测试AABB预计算
    print(f"AABB边界框: {collision_data.aabb}")
    assert collision_data.aabb == [0, 0, 32, 32], "AABB预计算错误"
    
    print("✓ 碰撞数据测试通过")


def test_serialization():
    """测试序列化和反序列化"""
    print("\n=== 测试序列化和反序列化 ===")
    
    # 创建碰撞数据
    collision_data = CollisionData("1_2")
    circle = CircleShape(16, 16, 16)
    collision_data.set_shape(circle)
    collision_data.add_tag("water")
    
    # 序列化
    data_dict = collision_data.to_dict()
    print(f"序列化数据: {data_dict}")
    
    # 反序列化
    restored_data = CollisionData.from_dict(data_dict)
    print(f"反序列化后: tile_id={restored_data.tile_id}, shape_type={restored_data.shape.type}")
    
    # 验证数据完整性
    assert restored_data.tile_id == "1_2", "tile_id不匹配"
    assert restored_data.shape.type == "circle", "形状类型不匹配"
    assert restored_data.properties.tags == ["water"], "标签不匹配"
    
    print("✓ 序列化测试通过")


def main():
    """运行所有测试"""
    print("开始碰撞数据结构测试...")
    
    try:
        test_rectangle_shape()
        test_circle_shape()
        test_polygon_shape()
        test_collision_data()
        test_serialization()
        
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
