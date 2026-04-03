#!/usr/bin/env python3
"""地图数据模型测试脚本"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.map_model import MapDataModel


def test_map_model():
    """测试地图数据模型的基本功能"""
    print("开始测试地图数据模型...")
    
    # 测试1: 创建地图模型实例
    print("\n1. 测试创建地图模型实例")
    map_model = MapDataModel()
    print("✅ 地图模型实例创建成功")
    
    # 测试2: 测试基本属性访问
    print("\n2. 测试基本属性访问")
    width, height = map_model.get_map_size()
    tile_size = map_model.get_tile_size()
    layer_count = map_model.get_layer_count()
    
    print(f"   地图尺寸: {width}x{height}")
    print(f"   瓦片大小: {tile_size}px")
    print(f"   图层数量: {layer_count}")
    print("✅ 基本属性访问成功")
    
    # 测试3: 测试瓦片操作
    print("\n3. 测试瓦片操作")
    # 设置瓦片
    result = map_model.set_tile(0, 5, 5, 1)
    if result:
        print("   ✅ 设置瓦片成功")
    
    # 获取瓦片
    tile_id = map_model.get_tile(0, 5, 5)
    print(f"   获取瓦片ID: {tile_id}")
    if tile_id == 1:
        print("✅ 瓦片操作成功")
    
    # 测试4: 测试图层操作
    print("\n4. 测试图层操作")
    new_layer_index = map_model.add_layer("test_layer")
    print(f"   新图层索引: {new_layer_index}")
    
    layer = map_model.get_layer(new_layer_index)
    if layer and layer["name"] == "test_layer":
        print("✅ 图层操作成功")
    
    # 测试5: 测试地图尺寸修改
    print("\n5. 测试地图尺寸修改")
    map_model.set_map_size(16, 16)
    new_width, new_height = map_model.get_map_size()
    print(f"   新地图尺寸: {new_width}x{new_height}")
    if new_width == 16 and new_height == 16:
        print("✅ 地图尺寸修改成功")
    
    # 测试6: 测试保存和加载功能
    print("\n6. 测试保存和加载功能")
    test_file = "test_map.json"
    
    # 保存地图
    save_result = map_model.save(test_file)
    if save_result and os.path.exists(test_file):
        print("   ✅ 地图保存成功")
        
        # 加载地图
        new_map_model = MapDataModel()
        load_result = new_map_model.load(test_file)
        if load_result:
            loaded_width, loaded_height = new_map_model.get_map_size()
            print(f"   加载的地图尺寸: {loaded_width}x{loaded_height}")
            print("✅ 地图加载成功")
            
            # 清理测试文件
            os.remove(test_file)
            print("   ✅ 测试文件已清理")
        else:
            print("❌ 地图加载失败")
    else:
        print("❌ 地图保存失败")
    
    # 测试7: 测试瓦片集操作
    print("\n7. 测试瓦片集操作")
    tile_set_index = map_model.add_tile_set("test_tileset", "assets/tilesets/test.png", 32, 32)
    print(f"   瓦片集索引: {tile_set_index}")
    
    tile_sets = map_model.get_tile_sets()
    if tile_sets and tile_sets[tile_set_index]["name"] == "test_tileset":
        print("✅ 瓦片集操作成功")
    
    print("\n🎉 所有测试完成！")


if __name__ == "__main__":
    test_map_model()