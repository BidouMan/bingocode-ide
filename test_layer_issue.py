#!/usr/bin/env python3
"""
测试图层数据相互污染的问题
"""
import os
import sys
import json

# 添加项目根目录到Python路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from modules.map_editor.layer_manager import LayerManager, DrawingLayer, ImageLayer
from models.map_model import MapDataModel

class MockMapModel:
    def __init__(self):
        self.map_data = {
            "layers": [
                {
                    "id": 0,
                    "name": "Layer 1",
                    "type": "drawing",
                    "visible": True,
                    "tiles": {}
                },
                {
                    "id": 1,
                    "name": "Layer 2",
                    "type": "drawing",
                    "visible": True,
                    "tiles": {}
                }
            ],
            "tile_sets": [
                {
                    "name": "grass_16",
                    "path": "地图4/tilesets/grass_16.png",
                    "resource_type": "tileset",
                    "tile_width": 16,
                    "tile_height": 16
                },
                {
                    "name": "brick_32",
                    "path": "地图4/tilesets/brick_32.png",
                    "resource_type": "tileset",
                    "tile_width": 32,
                    "tile_height": 32
                }
            ],
            "layer_resources_map": {
                "0": [0, 1],  # Layer 1 包含两个资源
                "1": [1, 2]   # Layer 2 只包含第二个资源
            }
        }
    
    def get_tile_size(self):
        return 16
    
    def get_tile_sets(self):
        return self.map_data.get("tile_sets", [])

# 测试图层资源分配
def test_layer_resources():
    print("=== 测试图层资源分配 ===")
    
    # 创建地图模型
    map_model = MockMapModel()
    
    # 创建图层管理器
    layer_manager = LayerManager(map_model)
    layer_manager.initialize_from_map_model()
    
    # 模拟图层资源分配
    layer_resources = {}
    tile_sets = map_model.map_data.get("tile_sets", [])
    layer_resources_map = map_model.map_data.get("layer_resources_map", {})
    
    print(f"加载的瓦片集数量: {len(tile_sets)}")
    for i, resource in enumerate(tile_sets):
        print(f"资源 {i}: {resource['name']}, 路径: {resource['path']}")
    
    print(f"\n图层资源映射: {layer_resources_map}")
    for layer in layer_manager.layers:
        if layer.layer_id not in layer_resources:
            layer_resources[layer.layer_id] = []
        if str(layer.layer_id) in layer_resources_map:
            start_index, end_index = layer_resources_map[str(layer.layer_id)]
            layer_resources[layer.layer_id] = tile_sets[start_index:end_index]
            print(f"为图层 {layer.name} (ID: {layer.layer_id}) 分配资源，索引范围: {start_index}-{end_index}")
            for i, res in enumerate(layer_resources[layer.layer_id]):
                print(f"  资源 {i}: {res['name']}, 路径: {res['path']}")
        else:
            layer_resources[layer.layer_id] = tile_sets
            print(f"为图层 {layer.name} (ID: {layer.layer_id}) 分配所有资源")
            for i, res in enumerate(layer_resources[layer.layer_id]):
                print(f"  资源 {i}: {res['name']}, 路径: {res['path']}")
    
    # 测试图块ID生成
    print("\n=== 测试图块ID生成 ===")
    for layer_id, resources in layer_resources.items():
        print(f"图层 {layer_id} 的资源:")
        for i, resource in enumerate(resources):
            tile_id = (i + 1) * 1000 + 1  # 简单的图块ID生成
            print(f"  资源 {i}: {resource['name']}, 生成的图块ID: {tile_id}")
    
    # 测试全局资源索引
    print("\n=== 测试全局资源索引 ===")
    all_resources = []
    for layer_res in layer_resources.values():
        all_resources.extend(layer_res)
    
    print(f"全局资源列表 (共 {len(all_resources)} 个资源):")
    for i, resource in enumerate(all_resources):
        print(f"  资源 {i}: {resource['name']}, 路径: {resource['path']}")
    
    # 测试根据路径查找全局资源索引
    print("\n=== 测试根据路径查找全局资源索引 ===")
    test_paths = [
        "地图4/tilesets/grass_16.png",
        "地图4/tilesets/brick_32.png"
    ]
    
    for path in test_paths:
        global_index = -1
        for i, res in enumerate(all_resources):
            if res.get("path") == path:
                global_index = i
                break
        print(f"路径 '{path}' 的全局索引: {global_index}")

if __name__ == "__main__":
    test_layer_resources()
