#!/usr/bin/env python3
"""
测试图层资源保存和加载的正确性
"""

import os
import sys
import tempfile
import shutil
from PySide6.QtWidgets import QApplication

# 添加项目根目录到路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from modules.map_editor.map_editor_manager import MapEditorManager
from models.map_model import MapDataModel

class TestLayerResources:
    def __init__(self):
        self.app = QApplication([])
        self.temp_dir = tempfile.mkdtemp()
        print(f"创建临时测试目录: {self.temp_dir}")
        
        # 创建测试资源目录
        self.assets_dir = os.path.join(self.temp_dir, "assets")
        self.maps_dir = os.path.join(self.assets_dir, "maps")
        os.makedirs(self.maps_dir, exist_ok=True)
        
        # 创建测试地图编辑器
        self.map_editor = MapEditorManager()
        
    def create_test_map(self):
        """创建测试地图"""
        print("\n=== 创建测试地图 ===")
        
        # 创建新地图
        self.map_editor.new_map()
        
        # 创建绘制图层
        print("创建绘制图层...")
        drawing_layer = self.map_editor.create_new_layer("drawing")
        print(f"创建绘制图层: {drawing_layer.name}")
        
        # 创建图像图层
        print("创建图像图层...")
        image_layer = self.map_editor.create_new_layer("image")
        print(f"创建图像图层: {image_layer.name}")
        
        # 模拟上传资源到绘制图层
        print("\n=== 模拟上传资源到绘制图层 ===")
        # 这里我们需要模拟资源上传，实际测试时需要真实的图像文件
        # 暂时使用占位符资源
        drawing_resources = [
            {
                "name": "grass_16.png",
                "path": "/Users/amixc/Desktop/IDEtest/Test/assets/maps/地图7/tilesets/grass_16.png",
                "resource_type": "tileset",
                "tile_width": 16,
                "tile_height": 16
            }
        ]
        
        # 模拟上传资源到图像图层
        print("\n=== 模拟上传资源到图像图层 ===")
        image_resources = [
            {
                "name": "bg.png",
                "path": "/Users/amixc/Desktop/IDEtest/Test/assets/maps/地图7/tilesets/bg.png",
                "resource_type": "image",
                "tile_width": 1,
                "tile_height": 1
            }
        ]
        
        # 为图层分配资源
        print("\n=== 为图层分配资源 ===")
        self.map_editor.layer_resources[drawing_layer.layer_id] = drawing_resources
        self.map_editor.layer_resources[image_layer.layer_id] = image_resources
        
        print(f"绘制图层资源数量: {len(self.map_editor.layer_resources.get(drawing_layer.layer_id, []))}")
        print(f"图像图层资源数量: {len(self.map_editor.layer_resources.get(image_layer.layer_id, []))}")
        
        return drawing_layer, image_layer
    
    def save_map(self):
        """保存地图"""
        print("\n=== 保存地图 ===")
        map_path = os.path.join(self.maps_dir, "test_map.info")
        
        # 保存地图
        self.map_editor.current_map_path = map_path
        self.map_editor.save_map()
        
        print(f"地图保存到: {map_path}")
        print(f"地图文件存在: {os.path.exists(map_path)}")
        
        return map_path
    
    def load_map(self, map_path):
        """加载地图"""
        print("\n=== 加载地图 ===")
        
        # 清空之前的资源
        self.map_editor.layer_resources.clear()
        
        # 加载地图
        self.map_editor.load_map_from_path(map_path)
        
        print(f"加载地图: {map_path}")
        print(f"图层数量: {len(self.map_editor.layer_manager.layers)}")
        
        for i, layer in enumerate(self.map_editor.layer_manager.layers):
            layer_resources = self.map_editor.layer_resources.get(layer.layer_id, [])
            print(f"图层 {i}: {layer.name}, 类型: {layer.layer_type}, 资源数量: {len(layer_resources)}")
            for j, resource in enumerate(layer_resources):
                print(f"  资源 {j}: {resource.get('name', 'unknown')}, 类型: {resource.get('resource_type', 'unknown')}")
        
        return self.map_editor.layer_manager.layers
    
    def test_resource_persistence(self):
        """测试资源持久化"""
        print("\n=== 测试资源持久化 ===")
        
        # 创建测试地图
        drawing_layer, image_layer = self.create_test_map()
        
        # 保存地图
        map_path = self.save_map()
        
        # 加载地图
        layers = self.load_map(map_path)
        
        # 验证资源是否正确加载
        print("\n=== 验证资源加载 ===")
        for layer in layers:
            layer_resources = self.map_editor.layer_resources.get(layer.layer_id, [])
            print(f"图层 {layer.name} 资源数量: {len(layer_resources)}")
            
            # 检查资源类型是否正确
            for resource in layer_resources:
                resource_type = resource.get('resource_type', 'unknown')
                print(f"  资源: {resource.get('name', 'unknown')}, 类型: {resource_type}")
                
                # 验证资源类型与图层类型匹配
                if layer.layer_type == "drawing":
                    assert resource_type == "tileset", f"绘制图层应该只包含tileset资源，实际是: {resource_type}"
                elif layer.layer_type == "image":
                    assert resource_type == "image", f"图像图层应该只包含image资源，实际是: {resource_type}"
        
        print("\n✅ 资源持久化测试通过!")
    
    def cleanup(self):
        """清理测试环境"""
        print(f"\n清理临时目录: {self.temp_dir}")
        shutil.rmtree(self.temp_dir)
        self.app.quit()

if __name__ == "__main__":
    print("=== 开始测试图层资源保存和加载 ===")
    
    test = TestLayerResources()
    
    try:
        test.test_resource_persistence()
    finally:
        test.cleanup()
    
    print("=== 测试完成 ===")
