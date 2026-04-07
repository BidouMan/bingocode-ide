#!/usr/bin/env python3
"""测试Sprite与标签碰撞系统的集成"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from modules.bingo_engine import Sprite, init_collision_system
from modules.collision_data import CollisionData, RectangleShape, CollisionProperties


def test_sprite_tag_collision():
    """测试Sprite与标签碰撞系统的集成"""
    print("开始测试Sprite与标签碰撞系统的集成...")
    
    # 初始化碰撞系统
    init_collision_system(20, 15, 32)
    print("✅ 碰撞系统初始化成功")
    
    # 创建一个测试精灵（使用不存在的图片，但应该能正常创建）
    sprite = Sprite("test_sprite")
    print(f"✅ 创建精灵成功，ID: {sprite.id}")
    
    # 创建碰撞数据
    collision_data = CollisionData("test_tile")
    collision_shape = RectangleShape(0, 0, 32, 32)
    collision_data.set_shape(collision_shape)
    collision_data.add_tag('ground')
    collision_data.add_tag('solid')
    
    # 获取全局碰撞系统
    from modules.bingo_engine import _COLLISION_SYSTEM
    
    # 添加碰撞数据到碰撞系统
    _COLLISION_SYSTEM.add_collision(16, 16, collision_data)
    print("✅ 添加碰撞数据成功")
    
    # 测试1：精灵不在碰撞区域
    sprite.set_xy(100, 100)
    result = sprite.is_touch('ground')
    print(f"测试1 - 精灵不在碰撞区域: {result}")
    assert result == False, "测试1失败：精灵不在碰撞区域应该返回False"
    
    # 测试2：精灵在碰撞区域
    sprite.set_xy(16, 16)
    result = sprite.is_touch('ground')
    print(f"测试2 - 精灵在碰撞区域: {result}")
    assert result == True, "测试2失败：精灵在碰撞区域应该返回True"
    
    # 测试3：测试不存在的标签
    result = sprite.is_touch('nonexistent')
    print(f"测试3 - 测试不存在的标签: {result}")
    assert result == False, "测试3失败：不存在的标签应该返回False"
    
    # 测试4：测试另一个标签
    result = sprite.is_touch('solid')
    print(f"测试4 - 测试另一个标签: {result}")
    assert result == True, "测试4失败：应该检测到solid标签"
    
    # 测试5：测试与其他Sprite的碰撞（保持原有功能）
    sprite2 = Sprite("test_sprite2")
    sprite2.set_xy(16, 16)
    result = sprite.is_touch(sprite2)
    print(f"测试5 - Sprite间碰撞检测: {result}")
    assert result == True, "测试5失败：Sprite间碰撞检测应该正常工作"
    
    print("🎉 所有测试通过！Sprite与标签碰撞系统集成成功！")


if __name__ == "__main__":
    test_sprite_tag_collision()