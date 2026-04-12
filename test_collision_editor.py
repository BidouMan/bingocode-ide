#!/usr/bin/env python3
"""
测试碰撞编辑器的功能，看看为什么预览面板不显示信息
"""

import sys
import os
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PySide6.QtCore import Qt

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.map_model import MapDataModel
from modules.map_editor.collision_manager import CollisionManager

class TestCollisionEditor(QMainWindow):
    """测试碰撞编辑器的窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("碰撞编辑器测试")
        self.setGeometry(100, 100, 800, 600)
        
        # 创建中心部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建布局
        layout = QVBoxLayout(central_widget)
        
        # 导入QGraphicsView
        from PySide6.QtWidgets import QGraphicsView
        
        # 创建一个QGraphicsView作为碰撞编辑器的视图
        self.col_editor_view = QGraphicsView()
        layout.addWidget(self.col_editor_view)
        
        # 初始化地图模型
        self.map_model = MapDataModel()
        
        # 加载测试地图
        map_path = "/Users/amixc/Desktop/IDEtest/Test/assets/maps/地图1/地图1.info"
        print(f"加载地图: {map_path}")
        success = self.map_model.load(map_path)
        print(f"加载地图结果: {success}")
        
        # 初始化碰撞管理器
        self.collision_manager = CollisionManager(self.map_model, self)
        
        # 初始化碰撞编辑器
        self.collision_manager.initialize_collision_editor(self.col_editor_view)
        
        # 设置图块图像获取函数
        def tile_pixmap_provider(resource_index, tile_index):
            print(f"获取图块图像 - resource_index: {resource_index}, tile_index: {tile_index}")
            # 这里应该返回实际的图块图像
            # 暂时返回一个空白图像
            from PySide6.QtGui import QPixmap
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.gray)
            return pixmap
        
        self.collision_manager.set_tile_pixmap_provider(tile_pixmap_provider)
        
        # 设置当前碰撞图块
        self.collision_manager.set_current_collision_tile(0, 0)
        
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestCollisionEditor()
    window.show()
    sys.exit(app.exec())
