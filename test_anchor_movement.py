#!/usr/bin/env python3
"""
测试锚点移动功能的脚本
用于找出锚点无法移动的原因
"""

from PySide6.QtWidgets import (
    QApplication,
    QGraphicsView,
    QGraphicsScene,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QGraphicsPixmapItem,
    QGraphicsItem,
    QGraphicsRectItem,
    QPushButton,
    QLabel,
    QHBoxLayout
)
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPen, QPainter, QPixmap, QBrush
import sys

from modules.map_editor.transform_tool import TransformHandle, TransformBoxItem


class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Anchor Movement Test")
        self.setGeometry(100, 100, 800, 600)

        # 创建主部件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 创建场景和视图
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(0, 0, 700, 500)

        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        main_layout.addWidget(self.view)

        # 创建控制按钮
        control_layout = QHBoxLayout()
        self.status_label = QLabel("Status: Ready")
        control_layout.addWidget(self.status_label)
        main_layout.addLayout(control_layout)

        # 创建一个测试图像
        self.create_test_image()

        # 显示窗口
        self.show()

    def create_test_image(self):
        """创建测试图像和变换框"""
        # 创建一个绿色的矩形作为测试对象
        self.test_rect = QGraphicsRectItem(100, 100, 100, 100)
        self.test_rect.setBrush(QColor("#98c379"))
        self.test_rect.setZValue(1)
        self.scene.addItem(self.test_rect)

        # 创建变换框
        initial_rect = QRectF(100, 100, 100, 100)
        self.transform_box = TransformBoxItem(
            initial_rect, transform_callback=self.on_transform_changed
        )
        self.scene.addItem(self.transform_box)

        # 移除事件过滤器，改为在 TransformHandle 和 TransformBoxItem 类中添加调试信息

        print("Test image and transform box created")
        print(f"Transform box handles: {list(self.transform_box.handles.keys())}")

    def on_transform_changed(self, rect):
        """处理变换变化"""
        print(f"Transform changed: {rect}")
        print(f"Transform box pos: {self.transform_box.pos()}")

        # 更新绿色矩形的位置和大小
        # 绿色矩形的位置应该是变换框的位置加上矩形的左上角位置
        self.test_rect.setPos(self.transform_box.pos() + rect.topLeft())
        self.test_rect.setRect(0, 0, rect.width(), rect.height())

        # 打印调试信息
        print(f"Image scale: x={rect.width() / 100:.2f}, y={rect.height() / 100:.2f}")
        print(
            f"Image pos: {self.test_rect.pos()}, Image bounding rect: {self.test_rect.boundingRect()}"
        )
        print(
            f"Transform box rect: {rect}, Transform box pos: {self.transform_box.pos()}"
        )
        print(f"Expected image pos: {self.transform_box.pos() + rect.topLeft()}")

    # 移除事件过滤器，改为在 TransformHandle 和 TransformBoxItem 类中添加调试信息


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    print("Test window shown")
    sys.exit(app.exec())
