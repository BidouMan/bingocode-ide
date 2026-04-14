#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试图像模式图层的碰撞形状缩放问题
"""

import os
import sys
import time
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtCore import QTimer

# 添加项目根目录到Python路径
sys.path.append('/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from modules.map_editor.map_editor_manager import MapEditorManager
from modules.map_editor.layer_manager import LayerManager
from models.map_model import MapDataModel

class TestApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("测试图像模式图层碰撞形状缩放")
        self.setGeometry(100, 100, 1200, 800)
        
        # 初始化地图编辑器管理器
        self.map_editor = MapEditorManager()
        
        # 设置UI组件（这里简化处理，实际项目中会有真实的UI组件）
        class MockUI:
            def __init__(self):
                self.res_list_view = None
                self.col_editor_view = None
                self.map_collision = None
                self.tile_size_input = None
                self.map_width_input = None
                self.map_height_input = None
                self.map_offset_x_input = None
                self.map_offset_y_input = None
                self.tile_label_input = None
                self.collision_type_combo = None
        
        self.map_editor.ui = MockUI()
        
        # 初始化地图数据模型
        self.map_model = MapDataModel()
        
        # 测试方法
        QTimer.singleShot(1000, self.test_image_layer_collision)
    
    def test_image_layer_collision(self):
        """测试图像模式图层的碰撞形状缩放"""
        print("=== 开始测试图像模式图层碰撞形状缩放 ===")
        
        # 创建测试地图目录
        test_map_dir = "/Users/amixc/Desktop/IDEtest/Test/assets/maps/测试地图"
        os.makedirs(test_map_dir, exist_ok=True)
        
        # 创建新地图
        map_path = os.path.join(test_map_dir, "测试地图.info")
        self.map_editor.new_map()
        self.map_editor.current_map_path = map_path
        
        # 创建图像图层
        print("1. 创建图像图层")
        self.map_editor.layer_manager.create_layer("Image Layer", "image")
        
        # 选择图像图层
        print("2. 选择图像图层")
        self.map_editor.layer_manager.select_layer(1)
        
        # 上传测试图像
        test_image_path = "/Users/amixc/Desktop/IDEtest/Test/test/bg.png"
        print(f"3. 上传测试图像: {test_image_path}")
        self.map_editor.handle_resource_upload(test_image_path, "image", 32)
        
        # 等待资源上传完成
        time.sleep(1)
        
        # 选择上传的图像资源
        print("4. 选择上传的图像资源")
        if hasattr(self.map_editor, "resource_items") and len(self.map_editor.resource_items) > 0:
            resource_item = list(self.map_editor.resource_items.values())[0]
            self.map_editor.select_resource(0, 0)
        
        # 等待碰撞编辑器更新
        time.sleep(1)
        
        # 打开碰撞属性
        print("5. 打开碰撞属性")
        if hasattr(self.map_editor, "ui") and hasattr(self.map_editor.ui, "map_collision"):
            # 模拟打开碰撞属性
            self.map_editor.collision_manager.set_collision_enabled(True)
        
        # 等待碰撞编辑器更新
        time.sleep(1)
        
        # 保存地图
        print("6. 保存地图")
        self.map_editor.save_map()
        
        # 等待保存完成
        time.sleep(1)
        
        # 加载地图
        print("7. 加载地图")
        self.map_editor.load_map_from_path(map_path)
        
        # 等待加载完成
        time.sleep(1)
        
        # 选择图像图层
        print("8. 选择图像图层")
        self.map_editor.layer_manager.select_layer(1)
        
        # 等待碰撞编辑器更新
        time.sleep(1)
        
        # 检查碰撞形状
        print("9. 检查碰撞形状")
        if hasattr(self.map_editor.collision_manager, "collision_points"):
            collision_points = self.map_editor.collision_manager.collision_points
            print(f"碰撞点数量: {len(collision_points)}")
            for i, point in enumerate(collision_points):
                print(f"碰撞点 {i}: ({point.x()}, {point.y()})")
        
        print("=== 测试完成 ===")
        
        # 退出应用
        QTimer.singleShot(1000, self.close)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestApp()
    window.show()
    sys.exit(app.exec())