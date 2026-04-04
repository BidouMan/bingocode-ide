import math
from PySide6.QtWidgets import QGraphicsView, QFrame
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QMouseEvent,
    QWheelEvent,
    QBrush,
    QKeyEvent,
)


class MapCanvas(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._zoom_level = 1.0
        self._max_zoom = 32.0
        self._min_zoom = 0.5  # 增加最小缩放限制，避免缩小后网格线消失
        self._is_panning = False
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # 去掉边框
        self.setFrameStyle(QFrame.NoFrame)
        self._init_settings()
        # 地图模型引用
        self.map_model = None
        self.tile_size = 16
        # 网格显示控制
        self._grid_visible = True

    def _init_settings(self):
        """性能与交互初始设置"""
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)

        # 缩放锚点：以鼠标为中心
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

        # 隐藏滚动条并禁用滚动功能
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # 禁用滚动条的滚轮事件处理
        self.horizontalScrollBar().setDisabled(True)
        self.verticalScrollBar().setDisabled(True)

        # 兼容性修复：由于某些版本不支持 setCenterOnScroll，我们手动通过 ScrollMode 控制
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)

        # 设置背景色（OneDark 深色）
        self.setBackgroundBrush(QBrush(QColor("#21252b")))

    def wheelEvent(self, event: QWheelEvent):
        """缩放逻辑：工业级实现 - 基于点的缩放（Point-based Zooming）"""
        # 1. 记录缩放前的"锚点"场景坐标
        mouse_pos = event.position().toPoint()
        scene_pos = self.mapToScene(mouse_pos)

        # 2. 计算新缩放倍率
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        new_zoom = self._zoom_level * factor

        if self._min_zoom <= new_zoom <= self._max_zoom:
            # 3. 执行物理缩放
            self.scale(factor, factor)
            self._zoom_level = new_zoom

            # 4. 关键：计算补偿位移
            # 缩放后，原来的scene_pos在视口中的新位置
            new_mouse_pos = self.mapFromScene(scene_pos)

            # 计算新位置与实际鼠标位置的偏差
            delta = new_mouse_pos - mouse_pos

            # 5. 调整滚动条，把偏差抵消掉
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() + delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() + delta.y()
            )

            # 刷新视图
            self.viewport().update()

        # 阻止事件传递，避免默认滚动行为
        event.accept()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
            print(f"DEBUG: 开始平移，鼠标位置: {event.pos()}")
            print(f"DEBUG: 平移前视图变换矩阵: {self.transform()}")
            print(
                f"DEBUG: 平移前视图中心点: {self.mapToScene(self.viewport().rect().center())}"
            )
            self._is_panning = True
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            fake_event = QMouseEvent(
                event.type(),
                event.pos(),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                event.modifiers(),
            )
            super().mousePressEvent(fake_event)
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
            print(f"DEBUG: 结束平移，鼠标位置: {event.pos()}")
            print(f"DEBUG: 平移后视图变换矩阵: {self.transform()}")
            print(
                f"DEBUG: 平移后视图中心点: {self.mapToScene(self.viewport().rect().center())}"
            )
            self._is_panning = False
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.unsetCursor()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        """键盘事件处理"""
        # 按空格键重置视图到中心位置
        if event.key() == Qt.Key.Key_Space:
            print("DEBUG: 按空格键重置视图")
            # 重置视图到游戏窗口中心(320, 240)
            self.centerOn(320, 240)
            event.accept()
        else:
            super().keyPressEvent(event)

    def drawBackground(self, painter: QPainter, rect):
        """绘制背景和全画布网格线"""
        # 调用父类的drawBackground
        super().drawBackground(painter, rect)

        # 如果网格可见，绘制全画布网格
        if self._grid_visible:
            self._draw_full_canvas_grid(painter, rect)

    def _draw_full_canvas_grid(self, painter, rect):
        """绘制全画布网格线 - 只渲染可见区域"""
        # 设置网格线样式
        grid_pen = QPen(QColor(196, 93, 41, 64), 0)
        painter.setPen(grid_pen)

        # 计算可见区域的网格线范围
        # 向下取整到最近的瓦片边界
        start_x = int(math.floor(rect.left() / self.tile_size)) * self.tile_size
        start_y = int(math.floor(rect.top() / self.tile_size)) * self.tile_size

        # 向上取整到最近的瓦片边界
        end_x = int(math.ceil(rect.right() / self.tile_size)) * self.tile_size
        end_y = int(math.ceil(rect.bottom() / self.tile_size)) * self.tile_size

        # 绘制垂直线
        x = start_x
        while x <= end_x:
            painter.drawLine(x, rect.top(), x, rect.bottom())
            x += self.tile_size

        # 绘制水平线
        y = start_y
        while y <= end_y:
            painter.drawLine(rect.left(), y, rect.right(), y)
            y += self.tile_size
