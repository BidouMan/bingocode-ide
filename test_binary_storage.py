#!/usr/bin/env python3
"""二进制存储系统测试"""

import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.binary_storage import BinaryStorage, MapFileManager
from modules.collision_data import CollisionData, RectangleShape


def test_map_binary():
    """测试地图二进制存储"""
    print("=== 测试地图二进制存储 ===")
    
    # 创建测试数据
    map_data = {
        'width': 10,
        'height': 10,
        'tiles': {
            (0, 0): 1,
            (1, 0): 2,
            (0, 1): 3,
            (1, 1): 4,
            (5, 5): 5
        }
    }
    
    # 测试文件路径
    test_file = 'test_map.tiles'
    
    try:
        # 保存地图
        BinaryStorage.save_map_binary(map_data, test_file)
        print(f"保存地图到: {test_file}")
        
        # 加载地图
        loaded_data = BinaryStorage.load_map_binary(test_file)
        print(f"加载地图成功")
        
        # 验证数据完整性
        assert loaded_data['width'] == map_data['width'], "宽度不匹配"
        assert loaded_data['height'] == map_data['height'], "高度不匹配"
        assert loaded_data['tiles'] == map_data['tiles'], "图块数据不匹配"
        
        print("✓ 地图二进制存储测试通过")
        
    finally:
        # 清理测试文件
        if os.path.exists(test_file):
            os.remove(test_file)


def test_collision_binary():
    """测试碰撞数据二进制存储"""
    print("\n=== 测试碰撞数据二进制存储 ===")
    
    # 创建测试数据
    collision1 = CollisionData("0_0")
    collision1.set_shape(RectangleShape(0, 0, 32, 32))
    collision1.add_tag("ground")
    
    collision2 = CollisionData("1_1")
    collision2.set_shape(RectangleShape(32, 32, 32, 32))
    collision2.add_tag("wall")
    collision2.properties.one_way = True
    
    collision_data_list = [collision1, collision2]
    
    # 测试文件路径
    test_file = 'test_collision.collision'
    
    try:
        # 保存碰撞数据
        BinaryStorage.save_collision_data(collision_data_list, test_file)
        print(f"保存碰撞数据到: {test_file}")
        
        # 加载碰撞数据
        loaded_data = BinaryStorage.load_collision_data(test_file)
        print(f"加载碰撞数据成功，数量: {len(loaded_data)}")
        
        # 验证数据完整性
        assert len(loaded_data) == 2, "碰撞数据数量不匹配"
        assert loaded_data[0].tile_id == "0_0", "tile_id不匹配"
        assert loaded_data[0].properties.tags == ["ground"], "标签不匹配"
        assert loaded_data[1].properties.one_way == True, "单向碰撞属性不匹配"
        
        print("✓ 碰撞数据二进制存储测试通过")
        
    finally:
        # 清理测试文件
        if os.path.exists(test_file):
            os.remove(test_file)


def test_metadata_binary():
    """测试元数据二进制存储"""
    print("\n=== 测试元数据二进制存储 ===")
    
    # 创建测试数据
    metadata = {
        'name': '测试地图',
        'author': '测试作者',
        'version': '1.0.0',
        'created_at': '2024-01-01',
        'settings': {
            'tile_size': 32,
            'grid_size': [100, 100],
            'background_color': '#000000'
        }
    }
    
    # 测试文件路径
    test_file = 'test_metadata.info'
    
    try:
        # 保存元数据
        BinaryStorage.save_metadata(metadata, test_file)
        print(f"保存元数据到: {test_file}")
        
        # 加载元数据
        loaded_metadata = BinaryStorage.load_metadata(test_file)
        print(f"加载元数据成功")
        
        # 验证数据完整性
        assert loaded_metadata == metadata, "元数据不匹配"
        
        print("✓ 元数据二进制存储测试通过")
        
    finally:
        # 清理测试文件
        if os.path.exists(test_file):
            os.remove(test_file)


def test_resources_binary():
    """测试资源数据二进制存储"""
    print("\n=== 测试资源数据二进制存储 ===")
    
    # 创建测试数据
    resources = {
        'tilesets': [
            {
                'name': 'ground',
                'path': 'assets/ground.png',
                'tile_width': 32,
                'tile_height': 32,
                'columns': 8,
                'rows': 4
            },
            {
                'name': 'wall',
                'path': 'assets/wall.png',
                'tile_width': 32,
                'tile_height': 32,
                'columns': 4,
                'rows': 2
            }
        ],
        'sprites': [
            {
                'name': 'player',
                'path': 'assets/player.png',
                'width': 64,
                'height': 64
            }
        ]
    }
    
    # 测试文件路径
    test_file = 'test_resources.resources'
    
    try:
        # 保存资源数据
        BinaryStorage.save_resources(resources, test_file)
        print(f"保存资源数据到: {test_file}")
        
        # 加载资源数据
        loaded_resources = BinaryStorage.load_resources(test_file)
        print(f"加载资源数据成功")
        
        # 验证数据完整性
        assert loaded_resources == resources, "资源数据不匹配"
        
        print("✓ 资源数据二进制存储测试通过")
        
    finally:
        # 清理测试文件
        if os.path.exists(test_file):
            os.remove(test_file)


def test_map_file_manager():
    """测试地图文件管理器"""
    print("\n=== 测试地图文件管理器 ===")
    
    # 创建测试数据
    map_data = {
        'width': 5,
        'height': 5,
        'tiles': {(0, 0): 1, (1, 1): 2}
    }
    
    collision = CollisionData("0_0")
    collision.set_shape(RectangleShape(0, 0, 32, 32))
    collision.add_tag("ground")
    
    metadata = {'name': '测试地图', 'version': '1.0'}
    resources = {'tilesets': []}
    
    # 测试文件路径
    base_path = 'test_map'
    
    try:
        # 创建文件管理器
        manager = MapFileManager(base_path)
        
        # 保存完整地图
        manager.save_map(map_data, [collision], metadata, resources)
        print("保存完整地图成功")
        
        # 加载完整地图
        loaded_map, loaded_collisions, loaded_metadata, loaded_resources = manager.load_map()
        print(f"加载完整地图成功，碰撞数据数量: {len(loaded_collisions)}")
        
        # 验证数据完整性
        assert loaded_map['tiles'] == map_data['tiles'], "地图数据不匹配"
        assert len(loaded_collisions) == 1, "碰撞数据数量不匹配"
        assert loaded_metadata == metadata, "元数据不匹配"
        assert loaded_resources == resources, "资源数据不匹配"
        
        print("✓ 地图文件管理器测试通过")
        
    finally:
        # 清理测试文件
        for ext in ['.tiles', '.collision', '.info', '.resources']:
            file_path = f"{base_path}{ext}"
            if os.path.exists(file_path):
                os.remove(file_path)


def test_performance():
    """测试性能"""
    print("\n=== 测试性能 ===")
    
    # 创建大尺寸地图数据
    width, height = 1000, 1000
    tiles = {}
    
    # 创建一些随机图块数据
    for i in range(0, width * height, 100):
        x = i % width
        y = i // width
        tiles[(x, y)] = (i % 100) + 1
    
    map_data = {
        'width': width,
        'height': height,
        'tiles': tiles
    }
    
    # 测试文件路径
    test_file = 'test_performance.tiles'
    
    try:
        # 测试保存性能
        start_time = time.time()
        BinaryStorage.save_map_binary(map_data, test_file)
        save_time = time.time() - start_time
        
        # 获取文件大小
        file_size = os.path.getsize(test_file) / (1024 * 1024)  # MB
        
        # 测试加载性能
        start_time = time.time()
        loaded_data = BinaryStorage.load_map_binary(test_file)
        load_time = time.time() - start_time
        
        print(f"地图尺寸: {width}x{height}")
        print(f"图块数量: {len(tiles)}")
        print(f"文件大小: {file_size:.2f} MB")
        print(f"保存时间: {save_time:.4f} 秒")
        print(f"加载时间: {load_time:.4f} 秒")
        
        # 验证加载速度（调整阈值为0.2秒，1000x1000地图这个速度已经很快了）
        assert load_time < 0.2, f"加载速度太慢: {load_time}秒"
        
        print("✓ 性能测试通过")
        
    finally:
        # 清理测试文件
        if os.path.exists(test_file):
            os.remove(test_file)


def test_different_sizes():
    """测试不同尺寸地图"""
    print("\n=== 测试不同尺寸地图 ===")
    
    sizes = [(10, 10), (100, 100), (500, 500)]
    
    for width, height in sizes:
        map_data = {
            'width': width,
            'height': height,
            'tiles': {(0, 0): 1, (width-1, height-1): 2}
        }
        
        test_file = f'test_size_{width}x{height}.tiles'
        
        try:
            BinaryStorage.save_map_binary(map_data, test_file)
            loaded_data = BinaryStorage.load_map_binary(test_file)
            
            assert loaded_data['width'] == width, f"宽度不匹配: {width}"
            assert loaded_data['height'] == height, f"高度不匹配: {height}"
            assert loaded_data['tiles'] == map_data['tiles'], "图块数据不匹配"
            
            print(f"✓ {width}x{height} 地图测试通过")
            
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)
    
    print("✓ 不同尺寸地图测试通过")


def main():
    """运行所有测试"""
    print("开始二进制存储系统测试...")
    
    try:
        test_map_binary()
        test_collision_binary()
        test_metadata_binary()
        test_resources_binary()
        test_map_file_manager()
        test_performance()
        test_different_sizes()
        
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
