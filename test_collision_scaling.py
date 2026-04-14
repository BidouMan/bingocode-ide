#!/usr/bin/env python3
"""
测试碰撞图层缩放问题的脚本
"""

import os
import sys
import json
from PySide6.QtWidgets import QApplication

# 添加项目根目录到路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from modules.map_editor.layer_manager import LayerManager, ImageLayer
from modules.map_editor.collision_manager import CollisionManager
from models.map_model import MapDataModel

class TestCollisionScaling:
    def __init__(self):
        self.test_dir = "/Users/amixc/Desktop/IDEtest/Test"
        self.test_image = os.path.join(self.test_dir, "test", "bg.png")
        self.map_path = os.path.join(self.test_dir, "assets", "maps", "test_map")
        os.makedirs(self.map_path, exist_ok=True)
        
    def test_collision_scaling(self):
        """测试碰撞图层缩放问题"""
        print("=== 开始测试碰撞图层缩放问题 ===")
        
        # 创建地图模型
        map_model = MapDataModel()
        
        # 创建图层管理器
        layer_manager = LayerManager(map_model)
        
        # 创建图像图层
        image_layer = ImageLayer(1, "Test Image Layer", layer_manager)
        layer_manager.layers.append(image_layer)
        
        # 创建图像数据
        from modules.map_editor.layer_manager import ImageData
        from PySide6.QtCore import QPointF
        image_data = ImageData(self.test_image, QPointF(100, 100), 0, 1.0, 1.0)
        
        # 添加测试图像
        image_layer.add_image(image_data)
        
        # 创建碰撞管理器
        collision_manager = CollisionManager(None)
        
        # 模拟碰撞编辑
        print("模拟碰撞编辑...")
        # 假设我们为图像创建一个碰撞形状
        image_data.collision_enabled = True
        image_data.collision_shape = {"points": [[0, 0], [100, 0], [100, 100], [0, 100]]}
        
        # 保存地图数据
        print("保存地图数据...")
        layer_manager.update_map_model()
        map_model.save(os.path.join(self.map_path, "test_map.info"))
        
        # 加载地图数据
        print("加载地图数据...")
        new_map_model = MapDataModel()
        new_map_model.load(os.path.join(self.map_path, "test_map.info"))
        
        # 从地图模型初始化图层管理器
        new_layer_manager = LayerManager(new_map_model)
        new_layer_manager.initialize_from_map_model()
        
        # 检查图层数据
        print(f"加载后图层数量: {len(new_layer_manager.layers)}")
        for layer in new_layer_manager.layers:
            print(f"  图层: {layer.name}, 类型: {layer.layer_type}")
            if hasattr(layer, 'images'):
                print(f"  图像数量: {len(layer.images)}")
                for img in layer.images:
                    print(f"    图像: {img.image_path}, 位置: ({img.position.x()}, {img.position.y()}), 缩放: {img.scale}, 旋转: {img.rotation}")
                    print(f"    碰撞启用: {img.collision_enabled}")
                    print(f"    碰撞形状: {img.collision_shape}")
        
        # 检查碰撞数据
        print("检查碰撞数据...")
        # 检查地图模型中的碰撞数据
        print(f"地图模型中的图层数量: {len(new_map_model.map_data.get('layers', []))}")
        for i, layer_data in enumerate(new_map_model.map_data.get('layers', [])):
            print(f"  图层 {i}: {layer_data.get('name')}, 类型: {layer_data.get('type')}")
            if 'images' in layer_data:
                print(f"  图像数量: {len(layer_data['images'])}")
                for img_data in layer_data['images']:
                    print(f"    图像: {img_data.get('image_path')}")
                    print(f"    碰撞启用: {img_data.get('collision_enabled')}")
                    print(f"    碰撞形状: {img_data.get('collision_shape')}")
        
        print("=== 测试完成 ===")

if __name__ == "__main__":
    app = QApplication([])
    tester = TestCollisionScaling()
    tester.test_collision_scaling()
    app.quit()
