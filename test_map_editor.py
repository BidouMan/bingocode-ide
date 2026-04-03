#!/usr/bin/env python3
"""地图编辑器管理器测试脚本"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from modules.map_editor_manager import MapEditorManager


def test_map_editor_manager():
    """测试地图编辑器管理器的基本功能"""
    print("开始测试地图编辑器管理器...")
    
    # 测试1: 创建地图编辑器管理器实例
    print("\n1. 测试创建地图编辑器管理器实例")
    map_editor = MapEditorManager()
    print("✅ 地图编辑器管理器实例创建成功")
    
    # 测试2: 测试获取地图模型
    print("\n2. 测试获取地图模型")
    map_model = map_editor.get_map_model()
    if map_model:
        print("✅ 获取地图模型成功")
    
    # 测试3: 测试工具设置
    print("\n3. 测试工具设置")
    map_editor.set_tool("brush")
    current_tool = map_editor.get_current_tool()
    print(f"   当前工具: {current_tool}")
    if current_tool == "brush":
        print("✅ 工具设置成功")
    
    # 测试4: 测试瓦片ID设置
    print("\n4. 测试瓦片ID设置")
    map_editor.set_current_tile(5)
    current_tile = map_editor.get_current_tile_id()
    print(f"   当前瓦片ID: {current_tile}")
    if current_tile == 5:
        print("✅ 瓦片ID设置成功")
    
    # 测试5: 测试图层设置
    print("\n5. 测试图层设置")
    map_editor.set_current_layer(0)
    current_layer = map_editor.get_current_layer()
    print(f"   当前图层: {current_layer}")
    if current_layer == 0:
        print("✅ 图层设置成功")
    
    # 测试6: 测试添加图层
    print("\n6. 测试添加图层")
    new_layer_index = map_editor.add_layer("test_layer")
    print(f"   新图层索引: {new_layer_index}")
    if new_layer_index == 1:
        print("✅ 添加图层成功")
    
    # 测试7: 测试删除图层
    print("\n7. 测试删除图层")
    result = map_editor.remove_layer(1)
    print(f"   删除结果: {result}")
    if result:
        print("✅ 删除图层成功")
    
    # 测试8: 测试添加瓦片集
    print("\n8. 测试添加瓦片集")
    tile_set_index = map_editor.add_tile_set("test_tileset", "assets/tilesets/test.png", 32, 32)
    print(f"   瓦片集索引: {tile_set_index}")
    if tile_set_index == 0:
        print("✅ 添加瓦片集成功")
    
    # 测试9: 测试更新地图尺寸
    print("\n9. 测试更新地图尺寸")
    map_editor.update_map_size(20, 20)
    width, height = map_model.get_map_size()
    print(f"   新地图尺寸: {width}x{height}")
    if width == 20 and height == 20:
        print("✅ 更新地图尺寸成功")
    
    print("\n🎉 所有测试完成！")


if __name__ == "__main__":
    test_map_editor_manager()