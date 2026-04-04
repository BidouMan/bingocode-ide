#!/usr/bin/env python3
"""测试地图编辑器场景创建"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsRectItem
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtCore import Qt

def test_map_scene():
    """测试创建地图场景"""
    app = QApplication(sys.argv)
    
    # 创建主窗口
    window = QMainWindow()
    window.setWindowTitle("地图场景测试")
    window.resize(800, 600)
    
    # 创建QGraphicsView
    view = QGraphicsView(window)
    view.setGeometry(50, 50, 700, 500)
    
    # 创建场景
    scene = QGraphicsScene()
    view.setScene(scene)
    
    # 设置场景大小
    width, height = 100, 100
    tile_size = 16
    scene_width = width * tile_size
    scene_height = height * tile_size
    scene.setSceneRect(0, 0, scene_width, scene_height)
    
    # 创建灰色背景
    background = QGraphicsRectItem(0, 0, scene_width, scene_height)
    background.setBrush(QBrush(QColor(200, 200, 200)))
    background.setPen(Qt.NoPen)
    scene.addItem(background)
    
    # 绘制网格
    pen = QPen(QColor(100, 100, 100, 50), 1)
    for x in range(width + 1):
        scene.addLine(x * tile_size, 0, x * tile_size, scene_height, pen)
    for y in range(height + 1):
        scene.addLine(0, y * tile_size, scene_width, y * tile_size, pen)
    
    # 显示窗口
    window.show()
    
    print(f"场景创建成功！")
    print(f"地图尺寸: {width}x{height}")
    print(f"瓦片大小: {tile_size}")
    print(f"场景大小: {scene_width}x{scene_height}")
    
    # 运行应用
    sys.exit(app.exec())

if __name__ == "__main__":
    test_map_scene()
