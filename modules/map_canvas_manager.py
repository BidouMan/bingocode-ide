import math
from PySide6.QtWidgets import QGraphicsView, QFrame
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QMouseEvent, QWheelEvent, QBrush, QKeyEvent


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
        """缩放逻辑：完美实现以鼠标位置为中心的缩放"""
        # 使用合适的缩放系数，确保缩放平滑
        zoom_in_factor = 1.1
        zoom_out_factor = 1 / zoom_in_factor
        zoom_factor = zoom_in_factor if event.angleDelta().y() > 0 else zoom_out_factor

        new_zoom = self._zoom_level * zoom_factor

        if self._min_zoom <= new_zoom <= self._max_zoom:
            # 获取鼠标在视图中的位置
            mouse_pos = event.position().toPoint()
            
            # 关键：缩放前记录鼠标指向的场景坐标
            scene_pos_before = self.mapToScene(mouse_pos)
            
            # 临时禁用自动锚点，避免Qt的内置行为干扰
            self.setTransformationAnchor(QGraphicsView.ViewportAnchor.NoAnchor)
            
            # 执行缩放操作
            self.scale(zoom_factor, zoom_factor)
            self._zoom_level = new_zoom
            
            # 缩放后计算鼠标新的场景坐标
            scene_pos_after = self.mapToScene(mouse_pos)
            
            # 计算需要平移的偏移量，确保鼠标位置不变
            offset = scene_pos_before - scene_pos_after
            
            # 应用平移，精确保持鼠标位置
            if not offset.isNull():
                self.translate(offset.x(), offset.y())
            
            # 刷新视图
            self.viewport().update()
        else:
            pass
        
        # 阻止事件传递，避免默认滚动行为
        event.accept()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
            print(f"DEBUG: 开始平移，鼠标位置: {event.pos()}")
            print(f"DEBUG: 平移前视图变换矩阵: {self.transform()}")
            print(f"DEBUG: 平移前视图中心点: {self.mapToScene(self.viewport().rect().center())}")
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
            print(f"DEBUG: 平移后视图中心点: {self.mapToScene(self.viewport().rect().center())}")
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
