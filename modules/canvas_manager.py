import math
from PySide6.QtWidgets import QGraphicsView
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QColor, QPen, QMouseEvent, QWheelEvent

class SmartCanvas(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._zoom_level = 1.0
        self._max_zoom = 32.0
        self._min_zoom = 0.1
        self._is_panning = False
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._init_settings()

    def _init_settings(self):
        """性能与交互初始设置"""
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        
        # 缩放锚点：以鼠标为中心
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        
        # 隐藏滚动条
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # 🚀 兼容性修复：由于某些版本不支持 setCenterOnScroll，我们手动通过 ScrollMode 控制
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        
        # 确保背景透明，接管渲染
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def update_scene_range(self):
        """
        🚀 完美的 PS 边界限制逻辑：
        确保图片中心点最多只能移动到视口边缘，
        这意味着图片始终会有一半（或你设定的比例）留在视口内。
        """
        if not self.scene(): return
        items = self.scene().items()
        if not items or not items[0]: return

        # 1. 获取素材原始矩形 (Scene 坐标)
        content_rect = items[0].boundingRect()
        
        # 2. 获取当前的缩放倍率
        s_x = self.transform().m11()
        s_y = self.transform().m22()

        # 3. 获取视口(窗口)的像素尺寸
        view_w = self.viewport().width()
        view_h = self.viewport().height()

        # 4. 核心逻辑修改：
        # 我们希望图片中心点最多到达边缘，所以边距只需要视口的一半。
        # 如果你希望留在里面的部分更多，就把 0.5 改成 0.3
        keep_ratio = 0.8
        margin_w = (view_w * keep_ratio) / s_x
        margin_h = (view_h * keep_ratio) / s_y

        # 5. 构造滚动边界
        # 此时 limit_rect 的大小正好能让内容在滑动到一半时撞到滚动的“墙”
        limit_rect = content_rect.adjusted(-margin_w, -margin_h, margin_w, margin_h)
        
        self.setSceneRect(limit_rect)
        
    

    def resizeEvent(self, event):
        """当 Designer 里的布局拉伸窗口时，实时更新平移限制"""
        super().resizeEvent(event)
        self.update_scene_range()

    def wheelEvent(self, event: QWheelEvent):
        """缩放逻辑"""
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor
        zoom_factor = zoom_in_factor if event.angleDelta().y() > 0 else zoom_out_factor

        new_zoom = self._zoom_level * zoom_factor
        if self._min_zoom <= new_zoom <= self._max_zoom:
            self.scale(zoom_factor, zoom_factor)
            self._zoom_level = new_zoom
            
            # 🚀 关键：缩放后立即重新计算合法的平移边界
            self.update_scene_range() 
            self.viewport().update()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = True
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            fake_event = QMouseEvent(
                event.type(), event.pos(), Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton, event.modifiers()
            )
            super().mousePressEvent(fake_event)
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_panning = False
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.unsetCursor()
        super().mouseReleaseEvent(event)

    def drawBackground(self, painter: QPainter, rect):
        """绘制深灰工作区 + 素材区棋盘格"""
        painter.fillRect(rect, QColor("#212121")) 

        if not self.scene(): return
        items = self.scene().items()
        if not items: return

        content_rect = items[0].boundingRect()
        visible_content_area = rect.intersected(content_rect)
        
        if not visible_content_area.isEmpty():
            painter.save()
            painter.setClipRect(visible_content_area)
            grid_step = 8 if self._zoom_level > 2.0 else 16
            self._render_checkerboard(painter, visible_content_area, grid_step)
            painter.restore()

            if self._zoom_level > 8.0:
                self._draw_pixel_grid(painter, content_rect)

    def _render_checkerboard(self, painter, rect, step):
        """高性能棋盘格绘制"""
        c1, c2 = QColor("#FFFFFF"), QColor("#DCDCDC")
        start_x = math.floor(rect.left() / step) * step
        start_y = math.floor(rect.top() / step) * step
        
        painter.setPen(Qt.PenStyle.NoPen)
        curr_y = start_y
        while curr_y < rect.bottom():
            row_idx = int(round(curr_y / step))
            curr_x = start_x
            while curr_x < rect.right():
                col_idx = int(round(curr_x / step))
                color = c1 if (row_idx + col_idx) % 2 == 0 else c2
                painter.fillRect(QRectF(curr_x, curr_y, step, step), color)
                curr_x += step
            curr_y += step

    def _draw_pixel_grid(self, painter, scene_rect):
        """像素网格线"""
        painter.save()
        grid_pen = QPen(QColor(200, 200, 200, 80))
        grid_pen.setWidth(0)
        painter.setPen(grid_pen)
        l, t, r, b = int(scene_rect.left()), int(scene_rect.top()), int(scene_rect.right()), int(scene_rect.bottom())
        for x in range(l, r + 1): painter.drawLine(x, t, x, b)
        for y in range(t, b + 1): painter.drawLine(l, y, r, y)
        painter.restore()