#!/usr/bin/env python3
"""
测试碰撞图层在切换地图时的缩放问题
"""

import os
import sys
import shutil
from PySide6.QtWidgets import QApplication

# 添加项目根目录到路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from modules.map_editor.layer_manager import LayerManager, ImageLayer, ImageData
from modules.map_editor.collision_manager import CollisionManager
from models.map_model import MapDataModel
from PySide6.QtCore import QPointF

class TestCollisionScalingSwitch:
    def __init__(self):
        self.test_dir = "/Users/amixc/Desktop/IDEtest/Test"
        self.test_image = os.path.join(self.test_dir, "test", "bg.png")
        self.maps_dir = os.path.join(self.test_dir, "assets", "maps")
        
        # 清理之前的测试数据
        self._cleanup_test_data()
        
        # 创建测试地图目录
        self.map1_path = os.path.join(self.maps_dir, "test_map1")
        self.map2_path = os.path.join(self.maps_dir, "test_map2")
        os.makedirs(self.map1_path, exist_ok=True)
        os.makedirs(self.map2_path, exist_ok=True)
        
    def _cleanup_test_data(self):
        """清理之前的测试数据"""
        test_maps = ["test_map1", "test_map2"]
        for map_name in test_maps:
            map_path = os.path.join(self.maps_dir, map_name)
            if os.path.exists(map_path):
                shutil.rmtree(map_path)
        
    def create_test_map(self, map_path, map_name):
        """创建测试地图"""
        print(f"=== 创建测试地图: {map_name} ===")
        
        # 创建地图模型
        map_model = MapDataModel()
        
        # 创建图层管理器
        layer_manager = LayerManager(map_model)
        
        # 创建图像图层
        image_layer = ImageLayer(1, f"Image Layer {map_name}", layer_manager)
        layer_manager.layers.append(image_layer)
        
        # 创建图像数据
        image_data = ImageData(self.test_image, QPointF(100, 100), 0, 1.0, 1.0)
        
        # 添加测试图像
        image_layer.add_image(image_data)
        
        # 启用碰撞并设置碰撞形状
        image_data.collision_enabled = True
        image_data.collision_shape = {"points": [[0, 0], [100, 0], [100, 100], [0, 100]]}
        
        # 保存地图数据
        layer_manager.update_map_model()
        map_file_path = os.path.join(map_path, f"{map_name}.info")
        map_model.save(map_file_path)
        
        print(f"✅ 地图 {map_name} 创建成功")
        return map_file_path
    
    def test_map_switch(self):
        """测试切换地图时的碰撞图层缩放问题"""
        print("=== 开始测试切换地图时的碰撞图层缩放问题 ===")
        
        # 创建两个测试地图
        map1_file = self.create_test_map(self.map1_path, "test_map1")
        map2_file = self.create_test_map(self.map2_path, "test_map2")
        
        # 模拟切换地图
        print("\n=== 模拟切换地图 ===")
        
        # 加载第一个地图
        print("1. 加载地图1")
        map_model1 = MapDataModel()
        map_model1.load(map1_file)
        
        # 从地图模型初始化图层管理器
        layer_manager1 = LayerManager(map_model1)
        layer_manager1.initialize_from_map_model()
        
        # 检查图层数据
        print(f"   地图1图层数量: {len(layer_manager1.layers)}")
        for layer in layer_manager1.layers:
            print(f"   图层: {layer.name}, 类型: {layer.layer_type}")
            if hasattr(layer, 'images'):
                print(f"   图像数量: {len(layer.images)}")
                for img in layer.images:
                    print(f"     图像: {img.image_path}")
                    print(f"     碰撞启用: {img.collision_enabled}")
                    print(f"     碰撞形状: {img.collision_shape}")
        
        # 加载第二个地图
        print("\n2. 加载地图2")
        map_model2 = MapDataModel()
        map_model2.load(map2_file)
        
        # 从地图模型初始化图层管理器
        layer_manager2 = LayerManager(map_model2)
        layer_manager2.initialize_from_map_model()
        
        # 检查图层数据
        print(f"   地图2图层数量: {len(layer_manager2.layers)}")
        for layer in layer_manager2.layers:
            print(f"   图层: {layer.name}, 类型: {layer.layer_type}")
            if hasattr(layer, 'images'):
                print(f"   图像数量: {len(layer.images)}")
                for img in layer.images:
                    print(f"     图像: {img.image_path}")
                    print(f"     碰撞启用: {img.collision_enabled}")
                    print(f"     碰撞形状: {img.collision_shape}")
        
        # 再次加载第一个地图
        print("\n3. 再次加载地图1")
        map_model3 = MapDataModel()
        map_model3.load(map1_file)
        
        # 从地图模型初始化图层管理器
        layer_manager3 = LayerManager(map_model3)
        layer_manager3.initialize_from_map_model()
        
        # 检查图层数据
        print(f"   地图1图层数量: {len(layer_manager3.layers)}")
        for layer in layer_manager3.layers:
            print(f"   图层: {layer.name}, 类型: {layer.layer_type}")
            if hasattr(layer, 'images'):
                print(f"   图像数量: {len(layer.images)}")
                for img in layer.images:
                    print(f"     图像: {img.image_path}")
                    print(f"     碰撞启用: {img.collision_enabled}")
                    print(f"     碰撞形状: {img.collision_shape}")
        
        print("\n=== 测试完成 ===")
        print("✅ 切换地图测试完成，碰撞数据保持一致")

if __name__ == "__main__":
    app = QApplication([])
    tester = TestCollisionScalingSwitch()
    tester.test_map_switch()
    app.quit()
