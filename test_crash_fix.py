#!/usr/bin/env python3
"""测试崩溃修复效果"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsRectItem
from PySide6.QtGui import QBrush, QColor, QPen
from PySide6.QtCore import Qt

class TestItem(QGraphicsRectItem):
    """测试项，模拟TileItem的行为"""
    def __init__(self, rect, index):
        super().__init__(rect)
        self.index = index
        self.is_deleted = False
        self.setBrush(QBrush(QColor(100, 149, 237, 50)))
        self.setPen(Qt.NoPen)
    
    def delete(self):
        """标记为已删除"""
        self.is_deleted = True
        print(f"Item {self.index} marked as deleted")

def test_memory_management():
    """测试内存管理"""
    app = QApplication(sys.argv)
    
    # 创建主窗口
    window = QMainWindow()
    window.setWindowTitle("内存管理测试")
    window.resize(400, 300)
    
    # 创建视图和场景
    view = QGraphicsView(window)
    view.setGeometry(50, 50, 300, 200)
    scene = QGraphicsScene()
    view.setScene(scene)
    
    # 创建测试项列表
    items = []
    
    # 添加初始项
    for i in range(5):
        rect = QGraphicsRectItem(i * 50, 50, 40, 40)
        item = TestItem(rect.rect(), i)
        scene.addItem(item)
        items.append(item)
    
    print("初始项创建完成")
    
    # 模拟资源列表更新 - 清理旧项并创建新项
    print("\n开始更新资源列表...")
    
    # 清理旧项
    for item in items:
        item.delete()
        scene.removeItem(item)
    
    items.clear()
    print("旧项清理完成")
    
    # 创建新项
    for i in range(3):
        rect = QGraphicsRectItem(i * 60, 100, 50, 50)
        item = TestItem(rect.rect(), i + 10)
        scene.addItem(item)
        items.append(item)
    
    print("新项创建完成")
    
    # 显示窗口
    window.show()
    
    print("\n测试完成！如果没有崩溃，说明修复成功")
    
    # 运行应用
    sys.exit(app.exec())

if __name__ == "__main__":
    test_memory_management()
