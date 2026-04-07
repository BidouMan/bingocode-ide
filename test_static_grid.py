#!/usr/bin/env python3
"""静态网格碰撞系统测试"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.static_grid import StaticCollisionGrid
from modules.collision_data import CollisionData, RectangleShape


def test_basic_functionality():
    """测试基本功能"""
    print("=== 测试基本功能 ===")
    
    # 创建10x10的网格
    grid = StaticCollisionGrid(10, 10, 32)
    
    # 创建碰撞数据
    collision1 = CollisionData("0_0")
    collision1.set_shape(RectangleShape(0, 0, 32, 32))
    collision1.add_tag("ground")
    
    # 添加碰撞
    grid.add_collision(0, 0, collision1)
    
    # 测试获取碰撞
    result = grid.get_collision(16, 16)
    print(f"获取碰撞: {result.tile_id if result else 'None'}")
    assert result == collision1, "获取碰撞失败"
    
    # 测试区域查询
    area_collisions = grid.get_collisions_in_area([0, 0, 64, 64])
    print(f"区域碰撞数量: {len(area_collisions)}")
    assert len(area_collisions) == 1, "区域查询失败"
    
    # 测试标签查询
    tag_collisions = grid.get_collisions_by_tag("ground")
    print(f"标签碰撞数量: {len(tag_collisions)}")
    assert len(tag_collisions) == 1, "标签查询失败"
    
    # 测试标签区域查询
    tag_area_collisions = grid.get_collisions_by_tag_in_area("ground", [0, 0, 64, 64])
    print(f"标签区域碰撞数量: {len(tag_area_collisions)}")
    assert len(tag_area_collisions) == 1, "标签区域查询失败"
    
    print("✓ 基本功能测试通过")


def test_boundary_cases():
    """测试边界情况"""
    print("\n=== 测试边界情况 ===")
    
    # 创建5x5的网格
    grid = StaticCollisionGrid(5, 5, 32)
    
    # 测试边界外查询
    result = grid.get_collision(-10, -10)
    print(f"边界外查询: {result}")
    assert result is None, "边界外查询应该返回None"
    
    result = grid.get_collision(200, 200)
    print(f"边界外查询: {result}")
    assert result is None, "边界外查询应该返回None"
    
    # 测试空标签查询
    collisions = grid.get_collisions_by_tag("nonexistent")
    print(f"空标签查询数量: {len(collisions)}")
    assert len(collisions) == 0, "空标签查询应该返回空列表"
    
    # 测试移除功能
    collision = CollisionData("1_1")
    collision.set_shape(RectangleShape(32, 32, 32, 32))
    grid.add_collision(32, 32, collision)
    
    removed = grid.remove_collision(32, 32)
    print(f"移除碰撞: {removed.tile_id if removed else 'None'}")
    assert removed == collision, "移除碰撞失败"
    
    # 验证已移除
    result = grid.get_collision(48, 48)
    print(f"验证移除: {result}")
    assert result is None, "移除后应该返回None"
    
    print("✓ 边界情况测试通过")


def test_performance():
    """测试性能（验证O(1)查询）"""
    print("\n=== 测试性能 ===")
    
    # 创建1000x1000的大网格
    grid = StaticCollisionGrid(1000, 1000, 32)
    
    # 添加一些碰撞数据
    for i in range(0, 100000, 100):
        x = (i % 1000) * 32
        y = (i // 1000) * 32
        collision = CollisionData(f"tile_{i}")
        collision.set_shape(RectangleShape(x, y, 32, 32))
        grid.add_collision(x, y, collision)
    
    print(f"网格尺寸: {grid.get_grid_size()}")
    print(f"碰撞数量: {grid.to_dict()['collision_count']}")
    
    # 测试查询性能
    start_time = time.time()
    
    # 执行多次查询
    for i in range(10000):
        x = (i % 1000) * 32 + 16
        y = (i // 1000) * 32 + 16
        grid.get_collision(x, y)
    
    end_time = time.time()
    elapsed = end_time - start_time
    queries_per_second = 10000 / elapsed
    
    print(f"查询性能: {queries_per_second:.2f}次/秒")
    assert queries_per_second > 100000, f"性能不足: {queries_per_second}次/秒"
    
    print("✓ 性能测试通过")


def test_tag_index():
    """测试标签索引功能"""
    print("\n=== 测试标签索引 ===")
    
    grid = StaticCollisionGrid(10, 10, 32)
    
    # 创建不同标签的碰撞
    ground1 = CollisionData("ground_1")
    ground1.set_shape(RectangleShape(0, 0, 32, 32))
    ground1.add_tag("ground")
    
    ground2 = CollisionData("ground_2")
    ground2.set_shape(RectangleShape(32, 0, 32, 32))
    ground2.add_tag("ground")
    
    wall = CollisionData("wall_1")
    wall.set_shape(RectangleShape(0, 32, 32, 32))
    wall.add_tag("wall")
    
    water = CollisionData("water_1")
    water.set_shape(RectangleShape(32, 32, 32, 32))
    water.add_tag("water")
    
    # 添加碰撞
    grid.add_collision(0, 0, ground1)
    grid.add_collision(32, 0, ground2)
    grid.add_collision(0, 32, wall)
    grid.add_collision(32, 32, water)
    
    # 测试标签查询
    ground_collisions = grid.get_collisions_by_tag("ground")
    print(f"ground标签碰撞数量: {len(ground_collisions)}")
    assert len(ground_collisions) == 2, "ground标签查询失败"
    
    wall_collisions = grid.get_collisions_by_tag("wall")
    print(f"wall标签碰撞数量: {len(wall_collisions)}")
    assert len(wall_collisions) == 1, "wall标签查询失败"
    
    # 测试标签区域查询
    area_ground = grid.get_collisions_by_tag_in_area("ground", [0, 0, 64, 32])
    print(f"区域内ground标签碰撞数量: {len(area_ground)}")
    assert len(area_ground) == 2, "区域ground标签查询失败"
    
    # 测试移除后标签索引更新
    grid.remove_collision(32, 0)
    ground_collisions = grid.get_collisions_by_tag("ground")
    print(f"移除后ground标签碰撞数量: {len(ground_collisions)}")
    assert len(ground_collisions) == 1, "移除后标签索引更新失败"
    
    print("✓ 标签索引测试通过")


def test_clear_function():
    """测试清空功能"""
    print("\n=== 测试清空功能 ===")
    
    grid = StaticCollisionGrid(5, 5, 32)
    
    # 添加碰撞
    collision = CollisionData("test")
    collision.set_shape(RectangleShape(0, 0, 32, 32))
    collision.add_tag("test")
    grid.add_collision(0, 0, collision)
    
    # 验证有数据
    assert grid.get_collision(16, 16) is not None, "应该有碰撞数据"
    assert len(grid.get_collisions_by_tag("test")) == 1, "标签索引应该有数据"
    
    # 清空网格
    grid.clear()
    
    # 验证已清空
    assert grid.get_collision(16, 16) is None, "清空后应该没有碰撞数据"
    assert len(grid.get_collisions_by_tag("test")) == 0, "清空后标签索引应该为空"
    
    print("✓ 清空功能测试通过")


def main():
    """运行所有测试"""
    print("开始静态网格碰撞系统测试...")
    
    try:
        test_basic_functionality()
        test_boundary_cases()
        test_performance()
        test_tag_index()
        test_clear_function()
        
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
