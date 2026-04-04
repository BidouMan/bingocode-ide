import math
from PySide6.QtWidgets import QGraphicsView, QFrame
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
        # 去掉边框
        self.setFrameStyle(QFrame.NoFrame)
        self._init_settings()
        # 地图模型引用
        self.map_model = None
        self.tile_size = 16

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
        if not self.scene():
            return
        items = self.scene().items()
        if not items or not items[0]:
            return

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
        print(f"DEBUG: 滚轮事件触发，角度变化: {event.angleDelta().y()}")
        print(f"DEBUG: 当前缩放级别: {self._zoom_level}")
        
        zoom_in_factor = 1.15
        zoom_out_factor = 1 / zoom_in_factor
        zoom_factor = zoom_in_factor if event.angleDelta().y() > 0 else zoom_out_factor
        
        print(f"DEBUG: 缩放因子: {zoom_factor}")

        new_zoom = self._zoom_level * zoom_factor
        print(f"DEBUG: 新缩放级别: {new_zoom}")
        
        if self._min_zoom <= new_zoom <= self._max_zoom:
            print(f"DEBUG: 执行缩放")
            self.scale(zoom_factor, zoom_factor)
            self._zoom_level = new_zoom

            # 🚀 关键：缩放后立即重新计算合法的平移边界
            self.update_scene_range()
            self.viewport().update()
            print(f"DEBUG: 缩放完成，新缩放级别: {self._zoom_level}")
        else:
            print(f"DEBUG: 缩放超出限制范围")
        
        # 阻止滚轮事件传递给父类，避免触发默认的滚动行为
        event.accept()
        print(f"DEBUG: 滚轮事件已处理")

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.MiddleButton:
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
            self._is_panning = False
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
            self.unsetCursor()
        super().mouseReleaseEvent(event)

    def drawBackground(self, painter: QPainter, rect):
        """绘制背景和动态网格线"""
        painter.fillRect(rect, QColor(30, 30, 30))
        
        # 如果有地图模型，绘制动态网格线
        if self.map_model:
            self._draw_dynamic_grid(painter, rect)

    def _render_checkerboard(self, painter, rect, step):
        """高性能棋盘格绘制"""
        c1, c2 = QColor("#C4C4C4"), QColor("#797979")
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

    def _draw_dynamic_grid(self, painter, rect):
        """绘制动态网格线 - 只显示绘制区域周围的网格"""
        import numpy as np
        
        # 获取当前图层的瓦片数据
        layer = self.map_model.get_layer(0)
        if not layer or layer["tiles"] is None:
            return
        
        tile_data = layer["tiles"]
        
        # 获取所有非零的瓦片位置
        y_indices, x_indices = np.where(tile_data > 0)
        
        # 设置网格线样式
        grid_pen = QPen(QColor(196, 93, 41, 64), 0)
        painter.setPen(grid_pen)
        
        if len(y_indices) > 0:
            # 有绘制内容时，显示绘制区域周围的网格
            # 计算绘制区域的边界
            min_x = np.min(x_indices) - self.map_model.coord_offset
            max_x = np.max(x_indices) - self.map_model.coord_offset
            min_y = np.min(y_indices) - self.map_model.coord_offset
            max_y = np.max(y_indices) - self.map_model.coord_offset
            
            # 向外扩展4个格子
            expand_size = 4
            grid_min_x = min_x - expand_size
            grid_max_x = max_x + expand_size
            grid_min_y = min_y - expand_size
            grid_max_y = max_y + expand_size
            
            # 绘制垂直线
            for x in range(grid_min_x, grid_max_x + 1):
                line_x = x * self.tile_size
                painter.drawLine(line_x, grid_min_y * self.tile_size, line_x, grid_max_y * self.tile_size)
            
            # 绘制水平线
            for y in range(grid_min_y, grid_max_y + 1):
                line_y = y * self.tile_size
                painter.drawLine(grid_min_x * self.tile_size, line_y, grid_max_x * self.tile_size, line_y)
        else:
            # 没有绘制内容时，显示中心区域的网格
            # 显示以原点为中心的20x20网格
            center_size = 10  # 中心10x10个格子
            grid_min_x = -center_size
            grid_max_x = center_size
            grid_min_y = -center_size
            grid_max_y = center_size
            
            # 绘制垂直线
            for x in range(grid_min_x, grid_max_x + 1):
                line_x = x * self.tile_size
                painter.drawLine(line_x, grid_min_y * self.tile_size, line_x, grid_max_y * self.tile_size)
            
            # 绘制水平线
            for y in range(grid_min_y, grid_max_y + 1):
                line_y = y * self.tile_size
                painter.drawLine(grid_min_x * self.tile_size, line_y, grid_max_x * self.tile_size, line_y)
    
    def _draw_pixel_grid(self, painter, scene_rect):
        """像素网格线"""
        painter.save()
        grid_pen = QPen(QColor(200, 200, 200, 80))
        grid_pen.setWidth(0)
        painter.setPen(grid_pen)
        l, t, r, b = (
            int(scene_rect.left()),
            int(scene_rect.top()),
            int(scene_rect.right()),
            int(scene_rect.bottom()),
        )
        for x in range(l, r + 1, 1):
            painter.drawLine(x, t, x, b)
        for y in range(t, b + 1, 1):
            painter.drawLine(l, y, r, y)
        painter.restore()
