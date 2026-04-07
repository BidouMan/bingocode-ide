#!/usr/bin/env python3
"""标签碰撞系统测试"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.tag_collision import TagCollisionSystem, CollisionCache
from modules.collision_data import CollisionData, RectangleShape


def test_basic_functionality():
    """测试基本功能"""
    print("=== 测试基本功能 ===")
    
    # 创建标签碰撞系统
    collision_system = TagCollisionSystem(10, 10)
    
    # 创建碰撞数据
    collision1 = CollisionData("0_0")
    collision1.set_shape(RectangleShape(0, 0, 32, 32))
    collision1.add_tag("ground")
    
    collision2 = CollisionData("1_1")
    collision2.set_shape(RectangleShape(32, 32, 32, 32))
    collision2.add_tag("wall")
    
    # 添加碰撞数据
    collision_system.add_collision(0, 0, collision1)
    collision_system.add_collision(32, 32, collision2)
    
    # 测试标签碰撞检测
    hitbox = [16, 16, 48, 48]
    result = collision_system.check_tag_collision(1, hitbox, "ground")
    print(f"标签碰撞测试 (ground): {result}")
    assert result == True, "应该碰撞ground"
    
    result = collision_system.check_tag_collision(1, hitbox, "wall")
    print(f"标签碰撞测试 (wall): {result}")
    assert result == True, "应该碰撞wall"
    
    result = collision_system.check_tag_collision(1, hitbox, "water")
    print(f"标签碰撞测试 (water): {result}")
    assert result == False, "不应该碰撞water"
    
    print("✓ 基本功能测试通过")


def test_cache_mechanism():
    """测试缓存机制"""
    print("\n=== 测试缓存机制 ===")
    
    # 创建标签碰撞系统
    collision_system = TagCollisionSystem(10, 10)
    
    # 创建碰撞数据
    collision = CollisionData("0_0")
    collision.set_shape(RectangleShape(0, 0, 32, 32))
    collision.add_tag("ground")
    collision_system.add_collision(0, 0, collision)
    
    hitbox = [16, 16, 48, 48]
    
    # 第一次检测（应该计算）
    start_time = time.time()
    result1 = collision_system.check_tag_collision(1, hitbox, "ground")
    time1 = time.time() - start_time
    
    # 第二次检测（应该命中缓存）
    start_time = time.time()
    result2 = collision_system.check_tag_collision(1, hitbox, "ground")
    time2 = time.time() - start_time
    
    print(f"第一次检测时间: {time1:.6f}秒")
    print(f"第二次检测时间: {time2:.6f}秒")
    print(f"缓存命中: {result1 == result2}")
    
    # 验证缓存命中（第二次应该更快）
    assert time2 < time1, "缓存应该更快"
    assert result1 == result2 == True, "结果应该一致"
    
    # 测试缓存过期
    for i in range(5):
        collision_system.update_frame()
    
    # 缓存应该过期
    start_time = time.time()
    result3 = collision_system.check_tag_collision(1, hitbox, "ground")
    time3 = time.time() - start_time
    
    print(f"缓存过期后检测时间: {time3:.6f}秒")
    assert time3 > time2, "缓存过期后应该重新计算"
    
    print("✓ 缓存机制测试通过")


def test_multiple_tags():
    """测试多标签检测"""
    print("\n=== 测试多标签检测 ===")
    
    # 创建标签碰撞系统
    collision_system = TagCollisionSystem(20, 20)
    
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
    
    # 添加碰撞数据
    collision_system.add_collision(0, 0, ground1)
    collision_system.add_collision(32, 0, ground2)
    collision_system.add_collision(0, 32, wall)
    collision_system.add_collision(32, 32, water)
    
    # 测试多标签检测
    hitbox = [16, 16, 48, 48]
    results = collision_system.check_multiple_tags(1, hitbox, ["ground", "wall", "water"])
    
    print(f"多标签检测结果: {results}")
    assert results["ground"] == True, "应该碰撞ground"
    assert results["wall"] == True, "应该碰撞wall"
    assert results["water"] == False, "不应该碰撞water"
    
    print("✓ 多标签检测测试通过")


def test_one_way_collision():
    """测试单向碰撞"""
    print("\n=== 测试单向碰撞 ===")
    
    # 创建标签碰撞系统
    collision_system = TagCollisionSystem(10, 10)
    
    # 创建单向碰撞数据
    platform = CollisionData("platform")
    platform.set_shape(RectangleShape(0, 0, 100, 10))
    platform.add_tag("platform")
    platform.properties.one_way = True
    platform.properties.one_way_direction = "top"
    
    collision_system.add_collision(0, 0, platform)
    
    # 测试从下方碰撞
    hitbox = [50, 5, 60, 15]
    result = collision_system.check_tag_collision(1, hitbox, "platform", (0, -5))
    print(f"单向碰撞测试 (从下方): {result}")
    assert result == True, "应该碰撞"
    
    # 测试从上方碰撞
    hitbox = [50, -5, 60, 5]
    result = collision_system.check_tag_collision(1, hitbox, "platform", (0, 5))
    print(f"单向碰撞测试 (从上方): {result}")
    assert result == False, "不应该碰撞"
    
    print("✓ 单向碰撞测试通过")


def test_remove_collision():
    """测试移除碰撞"""
    print("\n=== 测试移除碰撞 ===")
    
    # 创建标签碰撞系统
    collision_system = TagCollisionSystem(10, 10)
    
    # 创建碰撞数据
    collision = CollisionData("test")
    collision.set_shape(RectangleShape(0, 0, 32, 32))
    collision.add_tag("test")
    
    collision_system.add_collision(0, 0, collision)
    
    # 验证添加成功
    hitbox = [16, 16, 48, 48]
    result = collision_system.check_tag_collision(1, hitbox, "test")
    assert result == True, "应该碰撞"
    
    # 移除碰撞
    removed = collision_system.remove_collision(0, 0)
    print(f"移除碰撞: {removed.tile_id if removed else 'None'}")
    assert removed == collision, "应该移除正确的碰撞"
    
    # 验证移除成功
    result = collision_system.check_tag_collision(1, hitbox, "test")
    print(f"移除后碰撞测试: {result}")
    assert result == False, "不应该碰撞"
    
    print("✓ 移除碰撞测试通过")


def test_performance():
    """测试性能"""
    print("\n=== 测试性能 ===")
    
    # 创建大尺寸系统
    collision_system = TagCollisionSystem(100, 100)
    
    # 添加大量碰撞数据
    for i in range(0, 1000):
        x = (i % 100) * 32
        y = (i // 100) * 32
        collision = CollisionData(f"tile_{i}")
        collision.set_shape(RectangleShape(x, y, 32, 32))
        
        # 循环添加不同标签
        if i % 3 == 0:
            collision.add_tag("ground")
        elif i % 3 == 1:
            collision.add_tag("wall")
        else:
            collision.add_tag("water")
        
        collision_system.add_collision(x, y, collision)
    
    print(f"添加碰撞数量: {len(collision_system.get_collisions_by_tag('ground'))} ground, "
          f"{len(collision_system.get_collisions_by_tag('wall'))} wall, "
          f"{len(collision_system.get_collisions_by_tag('water'))} water")
    
    # 测试性能
    hitbox = [150, 150, 182, 182]
    
    # 预热缓存
    for i in range(10):
        collision_system.check_tag_collision(1, hitbox, "ground")
    
    # 测试性能
    start_time = time.time()
    for i in range(10000):
        collision_system.check_tag_collision(1, hitbox, "ground")
    elapsed = time.time() - start_time
    
    print(f"标签碰撞检测性能: {10000 / elapsed:.2f}次/秒")
    assert elapsed < 0.1, f"性能不足: {elapsed}秒"
    
    print("✓ 性能测试通过")


def test_edge_cases():
    """测试边界情况"""
    print("\n=== 测试边界情况 ===")
    
    # 创建标签碰撞系统
    collision_system = TagCollisionSystem(5, 5)
    
    # 测试空标签
    hitbox = [0, 0, 32, 32]
    result = collision_system.check_tag_collision(1, hitbox, "")
    print(f"空标签测试: {result}")
    assert result == False, "空标签应该返回False"
    
    # 测试不存在的标签
    result = collision_system.check_tag_collision(1, hitbox, "nonexistent")
    print(f"不存在标签测试: {result}")
    assert result == False, "不存在的标签应该返回False"
    
    # 测试禁用的碰撞
    collision = CollisionData("disabled")
    collision.set_shape(RectangleShape(0, 0, 32, 32))
    collision.add_tag("test")
    collision.enabled = False
    collision_system.add_collision(0, 0, collision)
    
    result = collision_system.check_tag_collision(1, hitbox, "test")
    print(f"禁用碰撞测试: {result}")
    assert result == False, "禁用的碰撞应该返回False"
    
    print("✓ 边界情况测试通过")


def main():
    """运行所有测试"""
    print("开始标签碰撞系统测试...")
    
    try:
        test_basic_functionality()
        test_cache_mechanism()
        test_multiple_tags()
        test_one_way_collision()
        test_remove_collision()
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
