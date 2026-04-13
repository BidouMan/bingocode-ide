#!/usr/bin/env python3
"""
深度测试图层资源管理
测试地图创建、图层资源保存和加载
使用用户提供的测试图片: grass.png 和 bg.png
"""

import os
import sys
import tempfile
from pathlib import Path

# 创建QGuiApplication实例
from PySide6.QtWidgets import QApplication
app = QApplication([])

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from modules.map_editor.map_editor_manager import MapEditorManager
from modules.map_editor.layer_manager import LayerManager
from models.map_model import MapDataModel

class DeepLayerResourcesTest:
    def __init__(self):
        self.test_dir = "/Users/amixc/Desktop/IDEtest/Test"
        self.test_images_dir = os.path.join(self.test_dir, "test")
        self.maps_dir = os.path.join(self.test_dir, "assets", "maps")
        self.grass_image = os.path.join(self.test_images_dir, "grass.png")
        self.bg_image = os.path.join(self.test_images_dir, "bg.png")
        
        # 确保测试目录存在
        os.makedirs(self.maps_dir, exist_ok=True)
        os.makedirs(self.test_images_dir, exist_ok=True)
        
        # 检查测试图片是否存在
        if not os.path.exists(self.grass_image):
            print(f"错误: 找不到测试图片 {self.grass_image}")
            sys.exit(1)
        if not os.path.exists(self.bg_image):
            print(f"错误: 找不到测试图片 {self.bg_image}")
            sys.exit(1)
        
        print("测试环境准备完成")
        print(f"测试目录: {self.test_dir}")
        print(f"地图目录: {self.maps_dir}")
        print(f"测试图片: {self.grass_image}, {self.bg_image}")
    
    def get_layer_by_name(self, layer_manager, name):
        """通过名称查找图层"""
        for layer in layer_manager.layers:
            if layer.name == name:
                return layer
        return None
    
    def get_layer_by_id(self, layer_manager, layer_id):
        """通过ID查找图层"""
        for layer in layer_manager.layers:
            if layer.layer_id == layer_id:
                return layer
        return None
    
    def run_test(self):
        """运行深度测试"""
        print("\n=== 开始深度测试图层资源管理 ===")
        
        # 测试1: 创建新地图并添加图层
        self.test_create_map_with_layers()
        
        # 测试2: 保存和加载地图
        self.test_save_and_load_map()
        
        # 测试3: 检查文件结构
        self.test_file_structure()
        
        print("\n=== 深度测试完成 ===")
    
    def test_create_map_with_layers(self):
        """测试创建地图和添加图层"""
        print("\n--- 测试1: 创建地图和添加图层 ---")
        
        # 创建地图编辑器
        map_editor = MapEditorManager()
        
        # 创建新地图
        map_editor.new_map()
        
        # 创建图层A (绘制模式)
        print("创建图层A (绘制模式)")
        map_editor.layer_manager.create_layer("drawing", "LayerA")
        
        # 为图层A添加grass.png资源
        print(f"为图层A添加资源: {self.grass_image}")
        # 直接添加资源到layer_resources字典
        layer_a = self.get_layer_by_name(map_editor.layer_manager, "LayerA")
        if layer_a:
            layer_a_id = layer_a.layer_id
            if layer_a_id not in map_editor.layer_resources:
                map_editor.layer_resources[layer_a_id] = []
            
            # 创建资源信息
            resource_info = {
                "name": "grass.png",
                "path": self.grass_image,
                "resource_type": "tileset",
                "tile_size": 16,
                "tile_width": 16,
                "tile_height": 16
            }
            map_editor.layer_resources[layer_a_id].append(resource_info)
            print(f"成功添加资源到图层A: {resource_info['name']}")
        
        # 在图层A绘制一些瓦片
        print("在图层A绘制瓦片")
        map_editor.set_current_layer(1)  # 假设新创建的图层是索引1
        # 获取当前图层并绘制瓦片
        current_layer = map_editor.layer_manager.get_current_layer()
        if current_layer and current_layer.layer_type == "drawing":
            # 绘制一些瓦片
            for x in range(5):
                for y in range(5):
                    current_layer.set_tile(x, y, 1001)  # 假设资源索引为0，瓦片索引为1
            print("成功在图层A绘制瓦片")
        
        # 创建图层B (图像模式)
        print("\n创建图层B (图像模式)")
        map_editor.layer_manager.create_layer("image", "LayerB")
        
        # 为图层B添加bg.png资源
        print(f"为图层B添加资源: {self.bg_image}")
        # 直接添加资源到layer_resources字典
        layer_b = self.get_layer_by_name(map_editor.layer_manager, "LayerB")
        if layer_b:
            layer_b_id = layer_b.layer_id
            if layer_b_id not in map_editor.layer_resources:
                map_editor.layer_resources[layer_b_id] = []
            
            # 创建资源信息
            resource_info = {
                "name": "bg.png",
                "path": self.bg_image,
                "resource_type": "image",
                "tile_size": 16,
                "tile_width": 16,
                "tile_height": 16
            }
            map_editor.layer_resources[layer_b_id].append(resource_info)
            print(f"成功添加资源到图层B: {resource_info['name']}")
        
        # 在图层B创建图像
        print("在图层B创建图像")
        map_editor.set_current_layer(2)  # 假设新创建的图层是索引2
        # 创建图像数据并添加到图层
        from modules.map_editor.layer_manager import ImageData
        layer_b = self.get_layer_by_name(map_editor.layer_manager, "LayerB")
        if layer_b:
            image_data = ImageData(self.bg_image)
            layer_b.add_image(image_data)
            # 更新地图数据模型
            map_editor.layer_manager.update_map_model()
            print(f"成功在图层B创建图像: {self.bg_image}")
        
        # 保存地图
        map_name = "test_map"
        map_path = os.path.join(self.maps_dir, map_name, f"{map_name}.info")
        print(f"\n保存地图到: {map_path}")
        
        # 确保地图目录存在
        os.makedirs(os.path.dirname(map_path), exist_ok=True)
        
        # 保存地图
        map_editor.current_map_path = map_path
        save_result = map_editor.save_map()
        print(f"保存结果: {save_result}")
        
        # 验证图层数量
        print(f"图层数量: {len(map_editor.layer_manager.layers)}")
        for i, layer in enumerate(map_editor.layer_manager.layers):
            print(f"图层 {i}: {layer.name}, 类型: {layer.layer_type}")
        
        # 验证资源
        for layer_id, resources in map_editor.layer_resources.items():
            layer = self.get_layer_by_id(map_editor.layer_manager, layer_id)
            if layer:
                print(f"图层 {layer.name} 的资源数量: {len(resources)}")
                for j, resource in enumerate(resources):
                    print(f"  资源 {j}: {resource.get('name', 'unknown')}, 路径: {resource.get('path', 'unknown')}")
        
        self.map_path = map_path
        self.map_editor = map_editor
    
    def test_save_and_load_map(self):
        """测试保存和加载地图"""
        print("\n--- 测试2: 保存和加载地图 ---")
        
        if not hasattr(self, 'map_path'):
            print("错误: 没有地图路径，测试1失败")
            return
        
        # 创建新的地图编辑器实例
        new_map_editor = MapEditorManager()
        
        # 加载地图
        print(f"加载地图: {self.map_path}")
        load_result = new_map_editor.load_map_from_path(self.map_path)
        print(f"加载结果: {load_result}")
        
        # 验证图层数量
        print(f"加载后图层数量: {len(new_map_editor.layer_manager.layers)}")
        for i, layer in enumerate(new_map_editor.layer_manager.layers):
            print(f"图层 {i}: {layer.name}, 类型: {layer.layer_type}")
        
        # 验证资源
        for layer_id, resources in new_map_editor.layer_resources.items():
            layer = self.get_layer_by_id(new_map_editor.layer_manager, layer_id)
            if layer:
                print(f"图层 {layer.name} 的资源数量: {len(resources)}")
                for j, resource in enumerate(resources):
                    print(f"  资源 {j}: {resource.get('name', 'unknown')}, 路径: {resource.get('path', 'unknown')}")
        
        # 检查图层A的资源
        layer_a = self.get_layer_by_name(new_map_editor.layer_manager, "LayerA")
        if layer_a:
            layer_a_id = layer_a.layer_id
            if layer_a_id in new_map_editor.layer_resources:
                resources = new_map_editor.layer_resources[layer_a_id]
                print(f"\n图层A的资源数量: {len(resources)}")
                if len(resources) == 0:
                    print("错误: 图层A的资源丢失!")
                else:
                    print("图层A的资源正常")
            else:
                print("错误: 图层A的资源不存在!")
        else:
            print("错误: 找不到图层A!")
        
        # 检查图层B的资源
        layer_b = self.get_layer_by_name(new_map_editor.layer_manager, "LayerB")
        if layer_b:
            layer_b_id = layer_b.layer_id
            if layer_b_id in new_map_editor.layer_resources:
                resources = new_map_editor.layer_resources[layer_b_id]
                print(f"图层B的资源数量: {len(resources)}")
                if len(resources) == 0:
                    print("错误: 图层B的资源丢失!")
                else:
                    print("图层B的资源正常")
            else:
                print("错误: 图层B的资源不存在!")
        else:
            print("错误: 找不到图层B!")
        
        self.loaded_map_editor = new_map_editor
    
    def test_file_structure(self):
        """测试文件结构"""
        print("\n--- 测试3: 检查文件结构 ---")
        
        if not hasattr(self, 'map_path'):
            print("错误: 没有地图路径，测试1失败")
            return
        
        map_dir = os.path.dirname(self.map_path)
        print(f"地图目录: {map_dir}")
        
        # 检查文件结构
        expected_files = [
            f"{os.path.basename(map_dir)}.info",
            f"{os.path.basename(map_dir)}.tiles",
            f"{os.path.basename(map_dir)}.collision",
            f"{os.path.basename(map_dir)}.resources",
            "tilesets"
        ]
        
        print("\n预期文件结构:")
        for file in expected_files:
            file_path = os.path.join(map_dir, file)
            exists = os.path.exists(file_path)
            status = "✓" if exists else "✗"
            print(f"{status} {file}")
            if not exists:
                print(f"  错误: 缺失文件 {file}")
        
        # 检查tilesets目录
        tilesets_dir = os.path.join(map_dir, "tilesets")
        if os.path.exists(tilesets_dir):
            print("\ntilesets目录中的文件:")
            for file in os.listdir(tilesets_dir):
                print(f"  - {file}")
        else:
            print("\n错误: tilesets目录不存在!")

if __name__ == "__main__":
    test = DeepLayerResourcesTest()
    test.run_test()
