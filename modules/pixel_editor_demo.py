import sys
import os
from PySide6.QtWidgets import (QApplication, QGraphicsView, QGraphicsScene, 
                             QGraphicsRectItem, QMainWindow, QVBoxLayout, QWidget)
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPen, QBrush, QPainter

class PixelScene(QGraphicsScene):
    """
    像素场景：负责管理所有的像素格点。
    """
    def __init__(self, width=32, height=32, pixel_size=20):
        super().__init__()
        self.p_width = width
        self.p_height = height
        self.p_size = pixel_size
        
        # 1. 设置场景范围
        self.setSceneRect(0, 0, width * pixel_size, height * pixel_size)
        
        # 2. 存储像素图元，方便后续通过坐标快速找到对应的格子上色
        self.pixels = {} 
        
        # 3. 初始化背景网格
        self._init_grid()

    def _init_grid(self):
        """
        初始化像素格点图元。每个像素都是一个 QGraphicsRectItem。
        """
        for y in range(self.p_height):
            for x in range(self.p_width):
                # 创建矩形格子
                rect = QGraphicsRectItem(x * self.p_size, y * self.p_size, self.p_size, self.p_size)
                # 设置细边框线（浅灰色，半透明）
                rect.setPen(QPen(QColor(200, 200, 200, 50), 0.5)) 
                # 初始颜色为透明
                rect.setBrush(Qt.GlobalColor.transparent)
                
                self.addItem(rect)
                self.pixels[(x, y)] = rect

    def paint_pixel(self, scene_pos, color):
        """
        根据场景中的物理坐标计算对应的像素索引并着色。
        """
        # 计算格子坐标 (x, y)
        x = int(scene_pos.x() // self.p_size)
        y = int(scene_pos.y() // self.p_size)
        
        # 只有在画布范围内才涂色
        if (x, y) in self.pixels:
            self.pixels[(x, y)].setBrush(QBrush(color))

class PixelView(QGraphicsView):
    """
    像素视图：负责处理交互（缩放、绘制、拖拽）。
    """
    def __init__(self, scene):
        super().__init__(scene)
        
        # --- 性能与显示设置 ---
        # 1. 像素画不需要抗锯齿，禁用它让边缘更锐利 (修正后的写法)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        
        # 2. 设置更新模式为“局部更新”，这在老电脑上性能极好
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        
        # 3. 背景颜色
        self.setBackgroundBrush(QColor(33, 33, 33))
        
        # 4. 交互开关
        self.is_drawing = False

    def wheelEvent(self, event):
        """
        滚轮缩放功能。
        """
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor
        
        # 获取滚轮方向并缩放
        if event.angleDelta().y() > 0:
            self.scale(zoom_in_factor, zoom_in_factor)
        else:
            self.scale(zoom_out_factor, zoom_out_factor)

    def mousePressEvent(self, event):
        """
        鼠标按下开始绘画。
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing = True
            self.apply_paint(event.pos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """
        鼠标移动持续绘画。
        """
        if self.is_drawing:
            self.apply_paint(event.pos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """
        鼠标松开停止绘画。
        """
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing = False
        super().mouseReleaseEvent(event)

    def apply_paint(self, view_pos):
        """
        将视图里的鼠标坐标映射到场景中，并执行涂色逻辑。
        """
        # 关键点：将 View 坐标 (屏幕像素) 映射为 Scene 坐标 (画布逻辑单位)
        scene_pos = self.mapToScene(view_pos)
        # 涂上 IDE 标志性的蓝色
        self.scene().paint_pixel(scene_pos, QColor("#007acc"))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("IDE 角色编辑器核心 - 像素画板")
        self.resize(1000, 700)
        
        # 实例化场景 (32x32 像素)
        self.scene = PixelScene(32, 32, 20)
        # 实例化视图
        self.view = PixelView(self.scene)
        
        # 设置为主窗口中心部件
        self.setCentralWidget(self.view)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 设置软件整体风格（可选）
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec())