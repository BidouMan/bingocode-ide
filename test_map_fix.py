#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试地图编辑器不同尺寸图块保存和加载功能
"""

import os
import sys
import tempfile
import shutil

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from models.map_model import MapDataModel

def test_different_size_tiles():
    """测试不同尺寸图块的保存和加载"""
    print("=== 测试不同尺寸图块的保存和加载 ===")
    
    # 创建临时目录
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建地图模型
        map_model = MapDataModel()
        
        # 添加不同尺寸的瓦片集
        tile_set_16 = map_model.add_tile_set("16x16 tiles", "assets/tiles/16x16.png", 16, 16)
        tile_set_32 = map_model.add_tile_set("32x32 tiles", "assets/tiles/32x32.png", 32, 32)
        tile_set_64 = map_model.add_tile_set("64x64 tiles", "assets/tiles/64x64.png", 64, 64)
        
        # 在不同位置绘制不同尺寸的图块
        # 16x16图块
        map_model.set_tile(0, 0, 0, 1001)  # 资源0，图块0
        map_model.set_tile(0, 1, 0, 1002)  # 资源0，图块1
        map_model.set_tile(0, 0, 1, 1003)  # 资源0，图块2
        
        # 32x32图块
        map_model.set_tile(0, 2, 2, 2001)  # 资源1，图块0
        map_model.set_tile(0, 4, 2, 2002)  # 资源1，图块1
        
        # 64x64图块
        map_model.set_tile(0, 6, 6, 3001)  # 资源2，图块0
        
        # 保存地图
        map_path = os.path.join(temp_dir, "test_map.info")
        print(f"保存地图到: {map_path}")
        save_result = map_model.save(map_path)
        print(f"保存结果: {save_result}")
        
        # 检查保存的文件
        base_name = os.path.splitext(map_path)[0]
        expected_files = [
            f"{base_name}.info",
            f"{base_name}.tiles",
            f"{base_name}.collision",
            f"{base_name}.resources"
        ]
        
        print("\n检查保存的文件:")
        for file_path in expected_files:
            exists = os.path.exists(file_path)
            print(f"  {os.path.basename(file_path)}: {'✅' if exists else '❌'}")
        
        # 创建新的地图模型加载保存的数据
        new_map_model = MapDataModel()
        print(f"\n加载地图: {map_path}")
        load_result = new_map_model.load(map_path)
        print(f"加载结果: {load_result}")
        
        # 验证加载的数据
        print("\n验证加载的数据:")
        
        # 检查瓦片集数量
        tile_sets = new_map_model.get_tile_sets()
        print(f"瓦片集数量: {len(tile_sets)}")
        for i, tile_set in enumerate(tile_sets):
            print(f"  瓦片集 {i}: {tile_set['name']}, 尺寸: {tile_set['tile_width']}x{tile_set['tile_height']}")
        
        # 检查图块数据
        layer = new_map_model.get_layer(0)
        tiles = layer["tiles"]
        print(f"\n图层0图块数量: {len(tiles)}")
        
        # 验证每个图块
        expected_tiles = [
            ((0, 0), 1001),
            ((1, 0), 1002),
            ((0, 1), 1003),
            ((2, 2), 2001),
            ((4, 2), 2002),
            ((6, 6), 3001)
        ]
        
        all_correct = True
        for (x, y), expected_id in expected_tiles:
            actual_id = new_map_model.get_tile(0, x, y)
            status = "✅" if actual_id == expected_id else "❌"
            print(f"  ({x}, {y}): 期望={expected_id}, 实际={actual_id} {status}")
            if actual_id != expected_id:
                all_correct = False
        
        return all_correct

def test_negative_coordinates():
    """测试负坐标的保存和加载"""
    print("\n\n=== 测试负坐标的保存和加载 ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        map_model = MapDataModel()
        
        # 添加瓦片集
        map_model.add_tile_set("tiles", "assets/tiles/tiles.png", 16, 16)
        
        # 在负坐标位置绘制图块
        map_model.set_tile(0, -5, -5, 1001)
        map_model.set_tile(0, -3, -2, 1002)
        map_model.set_tile(0, 0, 0, 1003)
        map_model.set_tile(0, 5, 5, 1004)
        
        # 保存地图
        map_path = os.path.join(temp_dir, "test_negative_coords.info")
        print(f"保存地图到: {map_path}")
        save_result = map_model.save(map_path)
        print(f"保存结果: {save_result}")
        
        # 加载地图
        new_map_model = MapDataModel()
        print(f"\n加载地图: {map_path}")
        load_result = new_map_model.load(map_path)
        print(f"加载结果: {load_result}")
        
        # 验证负坐标图块
        expected_tiles = [
            ((-5, -5), 1001),
            ((-3, -2), 1002),
            ((0, 0), 1003),
            ((5, 5), 1004)
        ]
        
        all_correct = True
        print("\n验证负坐标图块:")
        for (x, y), expected_id in expected_tiles:
            actual_id = new_map_model.get_tile(0, x, y)
            status = "✅" if actual_id == expected_id else "❌"
            print(f"  ({x}, {y}): 期望={expected_id}, 实际={actual_id} {status}")
            if actual_id != expected_id:
                all_correct = False
        
        return all_correct

if __name__ == "__main__":
    print("开始测试地图编辑器修复...")
    
    # 运行测试
    test1_result = test_different_size_tiles()
    test2_result = test_negative_coordinates()
    
    print("\n\n=== 测试结果汇总 ===")
    print(f"不同尺寸图块测试: {'✅ 通过' if test1_result else '❌ 失败'}")
    print(f"负坐标测试: {'✅ 通过' if test2_result else '❌ 失败'}")
    
    if test1_result and test2_result:
        print("\n🎉 所有测试通过！地图编辑器修复成功！")
        sys.exit(0)
    else:
        print("\n❌ 测试失败，请检查修复是否正确。")
        sys.exit(1)