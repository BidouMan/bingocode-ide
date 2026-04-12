import os
from PySide6.QtCore import QObject, Qt, QEvent, QPointF, QRectF
from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsView,
    QGraphicsEllipseItem,
)
from PySide6.QtGui import QPixmap, QBrush, QColor, QPen, QCursor


class LockedGraphicsView(QGraphicsView):
    """完全锁定的QGraphicsView，禁止任何形式的画布移动"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # 初始设置
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setInteractive(False)
        self.setContextMenuPolicy(Qt.NoContextMenu)
        self.setMouseTracking(False)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAlignment(Qt.AlignCenter)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        # 禁用滚动条
        self.horizontalScrollBar().setEnabled(False)
        self.verticalScrollBar().setEnabled(False)
        # 禁用自动滚动
        self.setAutoScroll(False)

    # 重写所有可能导致画布移动的方法
    def wheelEvent(self, event):
        event.accept()

    def mousePressEvent(self, event):
        event.accept()

    def mouseMoveEvent(self, event):
        event.accept()

    def mouseReleaseEvent(self, event):
        event.accept()

    def mouseDoubleClickEvent(self, event):
        event.accept()

    def keyPressEvent(self, event):
        event.accept()

    def keyReleaseEvent(self, event):
        event.accept()

    def dragEnterEvent(self, event):
        event.accept()

    def dragMoveEvent(self, event):
        event.accept()

    def dropEvent(self, event):
        event.accept()

    def focusInEvent(self, event):
        event.accept()

    def focusOutEvent(self, event):
        event.accept()

    def enterEvent(self, event):
        event.accept()

    def leaveEvent(self, event):
        event.accept()

    # 重写可能导致滚动的方法
    def scrollContentsBy(self, dx, dy):
        # 禁止滚动
        pass

    def ensureVisible(self, item, xmargin=50, ymargin=50, centerOnItem=False):
        # 禁止自动滚动到项目
        pass

    def centerOn(self, item_or_point):
        # 禁止自动居中
        pass

    def fitInView(self, rect, aspectRatioMode=Qt.AspectRatioMode.IgnoreAspectRatio):
        # 禁止自动适应视图
        pass


class CollisionManager(QObject):
    """碰撞管理器，负责处理碰撞相关的功能"""

    def __init__(self, map_model, parent=None):
        super().__init__(parent)
        self.map_model = map_model
        self.parent_manager = parent  # 保存父对象引用
        self.col_editor_scene = None
        self.col_editor_view = None
        self.current_collision_tile = None
        self.collision_shape_item = None
        self.tile_pixmap_provider = None  # 图块图像获取函数
        self.tile_item = None  # 图块图像项，用于坐标转换

        # 碰撞编辑相关属性
        self.anchor_items = {}  # 锚点项字典
        self.dragging_anchor = None  # 当前正在拖动的锚点
        self.drag_start_pos = QPointF()  # 拖动起始位置
        self.collision_points = []  # 当前碰撞多边形的顶点
        self.snap_to_pixel = True  # 是否吸附到像素网格，默认开启

    def __del__(self):
        """清理资源，避免程序退出时崩溃"""
        try:
            # 先清除对锚点项的引用，避免在清理场景时访问已销毁的对象
            if hasattr(self, "anchor_items"):
                try:
                    self.anchor_items.clear()
                except Exception as e:
                    print(f"DEBUG: 清空锚点项错误: {e}")

            # 移除事件过滤器
            if hasattr(self, "col_editor_view") and self.col_editor_view:
                try:
                    viewport = self.col_editor_view.viewport()
                    if viewport:
                        try:
                            viewport.removeEventFilter(self)
                        except Exception as e:
                            print(f"DEBUG: 移除事件过滤器错误: {e}")
                except Exception as e:
                    print(f"DEBUG: 访问视图错误: {e}")

            # 清理场景
            if hasattr(self, "col_editor_scene") and self.col_editor_scene:
                try:
                    self.col_editor_scene.clear()
                except Exception as e:
                    print(f"DEBUG: 清空场景错误: {e}")

            # 清除对所有对象的引用
            if hasattr(self, "col_editor_scene"):
                self.col_editor_scene = None
            if hasattr(self, "col_editor_view"):
                self.col_editor_view = None
            if hasattr(self, "tile_item"):
                self.tile_item = None
            if hasattr(self, "collision_shape_item"):
                self.collision_shape_item = None
            if hasattr(self, "current_collision_tile"):
                self.current_collision_tile = None
            if hasattr(self, "collision_points"):
                self.collision_points = []
            if hasattr(self, "dragging_anchor"):
                self.dragging_anchor = None
            if hasattr(self, "map_model"):
                self.map_model = None
            if hasattr(self, "tile_pixmap_provider"):
                self.tile_pixmap_provider = None
        except Exception as e:
            print(f"DEBUG: 清理资源错误: {e}")

    def initialize_collision_editor(self, col_editor_view):
        """初始化碰撞编辑器"""
        try:
            if not col_editor_view:
                return

            # 直接使用传入的视图，不替换为LockedGraphicsView
            # 因为替换视图可能会导致其他问题，我们通过其他方式确保画布锁定
            self.col_editor_view = col_editor_view

            # 禁用所有可能导致画布移动的功能
            self.col_editor_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.col_editor_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.col_editor_view.setDragMode(QGraphicsView.NoDrag)
            self.col_editor_view.setInteractive(False)
            self.col_editor_view.setContextMenuPolicy(Qt.NoContextMenu)
            self.col_editor_view.setMouseTracking(False)
            self.col_editor_view.setFocusPolicy(Qt.NoFocus)

            # 禁用滚动条
            if self.col_editor_view.horizontalScrollBar():
                self.col_editor_view.horizontalScrollBar().setEnabled(False)
            if self.col_editor_view.verticalScrollBar():
                self.col_editor_view.verticalScrollBar().setEnabled(False)

            # 重写事件处理方法
            self.col_editor_view.wheelEvent = lambda event: event.accept()
            self.col_editor_view.mousePressEvent = lambda event: event.accept()
            self.col_editor_view.mouseMoveEvent = lambda event: event.accept()
            self.col_editor_view.mouseReleaseEvent = lambda event: event.accept()
            self.col_editor_view.mouseDoubleClickEvent = lambda event: event.accept()
            self.col_editor_view.keyPressEvent = lambda event: event.accept()
            self.col_editor_view.keyReleaseEvent = lambda event: event.accept()

            # 初始化场景
            self.col_editor_scene = QGraphicsScene()
            self.col_editor_view.setScene(self.col_editor_scene)

            # 安装事件过滤器
            viewport = self.col_editor_view.viewport()
            if viewport:
                viewport.installEventFilter(self)
                # 也为视图本身安装事件过滤器，确保捕获所有事件
                self.col_editor_view.installEventFilter(self)
        except Exception as e:
            print(f"DEBUG: 初始化碰撞编辑器错误: {e}")
            import traceback

            traceback.print_exc()

    def set_current_collision_tile(self, resource_index, tile_index):
        """设置当前碰撞图块"""
        try:
            self.current_collision_tile = (resource_index, tile_index)
            self._update_collision_display()
        except Exception as e:
            print(f"DEBUG: 设置碰撞图块错误: {e}")

    def _update_collision_display(self):
        """更新碰撞编辑器的显示"""
        try:
            if (
                not self.col_editor_scene
                or not self.col_editor_view
                or not self.current_collision_tile
            ):
                return

            resource_index, tile_index = self.current_collision_tile

            # 获取图块图像
            pixmap = self._get_tile_pixmap(resource_index, tile_index)

            if pixmap and not pixmap.isNull():
                # 获取视图大小
                view_rect = self.col_editor_view.viewport().rect()
                view_width = view_rect.width()
                view_height = view_rect.height()

                # 黄金分割尺寸（大约占视图的61.8%）
                target_width = view_width * 0.618
                target_height = view_height * 0.618

                # 计算缩放比例
                pixmap_width = pixmap.width()
                pixmap_height = pixmap.height()

                # 计算保持比例的缩放因子
                scale_x = target_width / pixmap_width
                scale_y = target_height / pixmap_height
                scale = min(scale_x, scale_y)

                # 最小缩放限制（避免图块太小）
                min_scale = 2.0  # 至少放大到原始大小的2倍
                scale = max(scale, min_scale)

                # 清空场景前，先清理所有引用
                self._cleanup_collision_items()

                # 清空场景
                self.col_editor_scene.clear()

                # 显示原图（放在场景中心位置）
                pixmap_item = QGraphicsPixmapItem(pixmap)
                # 将图块放在场景中心位置，使图块中心点对准场景原点
                pixmap_item.setPos(-pixmap_width / 2, -pixmap_height / 2)
                # 设置为最底层
                pixmap_item.setZValue(-100)
                # 禁用所有鼠标交互
                pixmap_item.setAcceptedMouseButtons(Qt.NoButton)
                pixmap_item.setFlag(QGraphicsPixmapItem.ItemIsSelectable, False)
                pixmap_item.setFlag(QGraphicsPixmapItem.ItemIsMovable, False)
                # 禁用图块项的抗锯齿，减少渲染波动
                pixmap_item.setTransformationMode(Qt.FastTransformation)
                # 禁用图块项的缓存，确保渲染稳定
                from PySide6.QtWidgets import QGraphicsItem

                pixmap_item.setCacheMode(QGraphicsItem.NoCache)
                self.col_editor_scene.addItem(pixmap_item)
                self.tile_item = pixmap_item  # 保存图块图像项

                # 显示碰撞框（多边形）
                if self.map_model:
                    # 从地图模型获取碰撞形状（确保使用最新数据）
                    collision_shape = self.map_model.get_tile_collision_shape(
                        resource_index, tile_index
                    )

                    # 强化读取逻辑：检查数据格式
                    valid_collision_shape = False
                    if collision_shape and isinstance(collision_shape, dict):
                        if "points" in collision_shape:
                            points = collision_shape["points"]
                            if isinstance(points, list) and len(points) > 0:
                                # 检查每个点的格式
                                valid_points = True
                                for p in points:
                                    if not (
                                        isinstance(p, (list, tuple)) and len(p) >= 2
                                    ):
                                        valid_points = False
                                        break
                                if valid_points:
                                    valid_collision_shape = True

                    # 同时更新资源池缓存，确保数据一致性
                    if self.parent_manager and hasattr(
                        self.parent_manager, "uploaded_resources"
                    ):
                        if (
                            0
                            <= resource_index
                            < len(self.parent_manager.uploaded_resources)
                        ):
                            resource = self.parent_manager.uploaded_resources[
                                resource_index
                            ]
                            # 确保collisions数组存在且足够大
                            if "collisions" not in resource:
                                resource["collisions"] = []
                            while len(resource["collisions"]) <= tile_index:
                                resource["collisions"].append({})
                            # 更新资源池缓存中的碰撞形状数据
                            if valid_collision_shape:
                                # 确保数据格式一致，转换为列表格式
                                points_data = [
                                    [p[0], p[1]] for p in collision_shape["points"]
                                ]
                                resource["collisions"][tile_index]["points"] = (
                                    points_data
                                )
                            else:
                                # 如果没有碰撞形状，清除缓存中的数据
                                if "points" in resource["collisions"][tile_index]:
                                    del resource["collisions"][tile_index]["points"]

                    # 如果地图模型中没有，从资源池缓存获取（作为后备）
                    if (
                        not valid_collision_shape
                        and self.parent_manager
                        and hasattr(self.parent_manager, "uploaded_resources")
                    ):
                        if (
                            0
                            <= resource_index
                            < len(self.parent_manager.uploaded_resources)
                        ):
                            resource = self.parent_manager.uploaded_resources[
                                resource_index
                            ]
                            if "collisions" in resource and 0 <= tile_index < len(
                                resource["collisions"]
                            ):
                                collision_data = resource["collisions"][tile_index]
                                if "points" in collision_data:
                                    # 验证资源池缓存中的数据格式
                                    points = collision_data["points"]
                                    if isinstance(points, list) and len(points) > 0:
                                        # 检查每个点的格式
                                        valid_points = True
                                        for p in points:
                                            if not (
                                                isinstance(p, (list, tuple))
                                                and len(p) >= 2
                                            ):
                                                valid_points = False
                                                break
                                        if valid_points:
                                            collision_shape = {"points": points}
                                            valid_collision_shape = True

                    collision_enabled = self.map_model.get_tile_collision(
                        resource_index, tile_index
                    )

                    if collision_enabled:
                        if valid_collision_shape:
                            # 使用自定义多边形碰撞形状（确保是局部坐标）
                            raw_points = collision_shape["points"]
                            # 确保存储的是相对于图块左上角的局部坐标
                            self.collision_points = [
                                QPointF(p[0], p[1]) for p in raw_points
                            ]
                        else:
                            # 使用默认矩形碰撞形状（转换为多边形）
                            # 使用相对于图块左上角的局部坐标（0到图块大小）
                            self.collision_points = [
                                QPointF(0, 0),
                                QPointF(pixmap.width(), 0),
                                QPointF(pixmap.width(), pixmap.height()),
                                QPointF(0, pixmap.height()),
                            ]

                        # 更新碰撞多边形显示
                        self._update_collision_shape()

                        # 更新碰撞锚点
                        self._update_collision_anchors()

                # 重新设计变换逻辑：先缩放，后平移到视图中心
                transform = self.col_editor_view.transform()
                transform.reset()

                # 先缩放
                transform.scale(scale, scale)

                # 再平移到视图中心
                transform.translate(view_width / 2, view_height / 2)

                # 应用变换，但确保不会导致画布移动
                self.col_editor_view.setTransform(transform)

                # 确保场景大小与视图大小匹配，避免滚动
                # 但是保持图块的居中位置
                self.col_editor_scene.setSceneRect(
                    -view_width / 2, -view_height / 2, view_width, view_height
                )

                # 确保视图不会自动滚动
                self.col_editor_view.setSceneRect(
                    -view_width / 2, -view_height / 2, view_width, view_height
                )

                # 显示视图
                self.col_editor_view.show()
            else:
                # 如果没有pixmap，清空场景
                self._cleanup_collision_items()
                self.col_editor_scene.clear()
                self.col_editor_view.fitInView(
                    self.col_editor_scene.sceneRect(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                )
        except Exception as e:
            print(f"DEBUG: 更新碰撞显示错误: {e}")
            import traceback

            traceback.print_exc()
            # 发生错误时清理资源
            self._cleanup_collision_items()
            if self.col_editor_scene:
                self.col_editor_scene.clear()

    def set_collision_enabled(self, enabled):
        """设置碰撞启用状态"""
        if self.current_collision_tile:
            resource_index, tile_index = self.current_collision_tile
            if self.map_model:
                self.map_model.set_tile_collision(resource_index, tile_index, enabled)
                self._update_collision_display()

    def set_tile_pixmap_provider(self, provider):
        """设置图块图像获取函数"""
        self.tile_pixmap_provider = provider

    def set_snap_to_pixel(self, enabled):
        """设置是否吸附到像素网格"""
        self.snap_to_pixel = enabled
        print(f"碰撞锚点吸附功能: {'开启' if enabled else '关闭'}")

    def _get_tile_pixmap(self, resource_index, tile_index):
        """获取图块图像"""
        if self.tile_pixmap_provider:
            return self.tile_pixmap_provider(resource_index, tile_index)
        return None

    def _cleanup_collision_items(self):
        """清理碰撞相关的项，避免内存泄漏和程序崩溃"""
        try:
            # 重置碰撞形状项
            self.collision_shape_item = None

            # 清空锚点项字典
            self.anchor_items.clear()

            # 清空碰撞点列表
            self.collision_points = []

            # 重置图块项
            self.tile_item = None

            # 重置拖动状态
            self.dragging_anchor = None
        except Exception as e:
            print(f"DEBUG: 清理碰撞项错误: {e}")

    def _update_collision_anchors(self):
        """更新碰撞锚点位置"""
        try:
            if not self.collision_points or not self.tile_item:
                return

            # 确保锚点数量与碰撞点数量一致
            while len(self.anchor_items) < len(self.collision_points):
                i = len(self.anchor_items)
                anchor_radius = 4 / 3  # 锚点半径，增加1/3大小
                # 创建椭圆，设置为场景的直接子项，而不是图块项的子项
                # 这样当锚点移动时不会影响图块项的边界框，避免图块抖动
                # 创建菱形锚点，使用多边形而不是椭圆
                from PySide6.QtWidgets import QGraphicsPolygonItem
                from PySide6.QtGui import QPolygonF

                diamond = QPolygonF()
                diamond.append(QPointF(0, -anchor_radius))  # 上顶点
                diamond.append(QPointF(anchor_radius, 0))  # 右顶点
                diamond.append(QPointF(0, anchor_radius))  # 下顶点
                diamond.append(QPointF(-anchor_radius, 0))  # 左顶点
                anchor = QGraphicsPolygonItem(diamond)
                # 添加到场景中，而不是作为图块的子项
                self.col_editor_scene.addItem(anchor)
                # 设置锚点填充颜色为白色
                anchor.setBrush(QBrush(QColor(255, 255, 255)))
                # 设置锚点描边颜色为黑色，线条宽度恢复默认值1.5
                pen = QPen(QColor(0, 0, 0), 3.5)  # 恢复默认描边宽度
                pen.setCosmetic(True)  # 线条宽度不随缩放变化
                anchor.setPen(pen)
                anchor.setZValue(100)  # 确保在最顶层
                anchor.setData(0, f"point_{i}")  # 存储锚点名称
                self.anchor_items[f"point_{i}"] = anchor

            # 移除多余的锚点
            while len(self.anchor_items) > len(self.collision_points):
                i = len(self.collision_points)
                anchor_name = f"point_{i}"
                if anchor_name in self.anchor_items:
                    del self.anchor_items[anchor_name]

            # 每一帧只需要更新它们的位置
            for i, point in enumerate(self.collision_points):
                anchor_name = f"point_{i}"
                if anchor_name in self.anchor_items:
                    # 因为anchor现在是场景的直接子项，所以需要加上图块的位置
                    anchor = self.anchor_items[anchor_name]
                    tile_pos = self.tile_item.pos() if self.tile_item else QPointF(0, 0)
                    # 锚点位置 = 图块位置 + 局部坐标点
                    anchor.setPos(tile_pos.x() + point.x(), tile_pos.y() + point.y())
        except Exception as e:
            print(f"DEBUG: 更新锚点位置错误: {e}")
            import traceback

            traceback.print_exc()

    def _update_collision_shape(self):
        """更新碰撞多边形显示"""
        try:
            if not self.collision_points or not self.tile_item:
                return

            if not self.collision_shape_item:
                # 如果还没有创建多边形项，创建一个并设为场景的直接子项
                # 这样当碰撞形状更新时不会影响图块项的边界框，避免图块抖动
                from PySide6.QtWidgets import QGraphicsPolygonItem
                from PySide6.QtGui import QPolygonF

                self.collision_shape_item = QGraphicsPolygonItem()
                # 添加到场景中，而不是作为图块的子项
                self.col_editor_scene.addItem(self.collision_shape_item)
                self.collision_shape_item.setBrush(
                    QBrush(QColor(100, 149, 237, 100))
                )  # 半透明淡蓝色
                # 将碰撞形状的线条宽度改细一点
                self.collision_shape_item.setPen(QPen(QColor(100, 149, 237), 0.5))
                # 核心修复：让多边形不响应鼠标，点击事件会直接穿透到下层的锚点
                self.collision_shape_item.setAcceptedMouseButtons(Qt.NoButton)
                self.collision_shape_item.setFlag(
                    QGraphicsPolygonItem.ItemIsSelectable, False
                )

            if self.collision_shape_item:
                from PySide6.QtGui import QPolygonF

                # 碰撞形状现在是场景的直接子项，所以需要设置其位置为图块的位置
                if self.tile_item:
                    self.collision_shape_item.setPos(self.tile_item.pos())

                polygon = QPolygonF(self.collision_points)
                self.collision_shape_item.setPolygon(polygon)
        except Exception as e:
            print(f"DEBUG: 更新碰撞形状错误: {e}")
            import traceback

            traceback.print_exc()

    def eventFilter(self, obj, event):
        """事件过滤器，处理鼠标事件"""
        try:
            if not obj or not event or not self.col_editor_view:
                return super().eventFilter(obj, event)

            if obj == self.col_editor_view.viewport():
                try:
                    if event.type() == QEvent.MouseButtonPress:
                        # 完全控制鼠标按下事件，防止画布移动
                        self._handle_mouse_press(event)
                        return True
                    elif event.type() == QEvent.MouseMove:
                        # 完全控制鼠标移动事件，防止画布移动
                        self._handle_mouse_move(event)
                        return True
                    elif event.type() == QEvent.MouseButtonRelease:
                        # 完全控制鼠标释放事件，防止画布移动
                        self._handle_mouse_release(event)
                        return True
                except Exception as e:
                    print(f"DEBUG: 处理鼠标事件错误: {e}")
                    return True  # 即使出错也返回True，防止事件传递
        except Exception as e:
            print(f"DEBUG: 事件过滤器错误: {e}")
        return False  # 其他事件不处理

    def _handle_mouse_press(self, event):
        """处理鼠标按下事件"""
        try:
            if not event or not self.col_editor_view:
                return False

            if event.button() == Qt.LeftButton:
                scene_pos = self.col_editor_view.mapToScene(event.pos())

                # 检查是否点击了锚点
                for anchor_name, anchor in self.anchor_items.items():
                    try:
                        # 扩大点击判定范围，即使鼠标没点进圆圈，只要在圆心附近就能抓取
                        click_rect = anchor.sceneBoundingRect().adjusted(-5, -5, 5, 5)
                        if click_rect.contains(scene_pos):
                            self.dragging_anchor = anchor_name
                            self.drag_start_pos = scene_pos
                            if self.col_editor_view:
                                self.col_editor_view.setCursor(
                                    QCursor(Qt.SizeAllCursor)
                                )
                            return True
                    except Exception as e:
                        print(f"DEBUG: 检查锚点点击错误: {e}")
        except Exception as e:
            print(f"DEBUG: 鼠标按下事件错误: {e}")
        return False

    def _handle_mouse_move(self, event):
        """处理鼠标移动事件"""
        try:
            if not event or not self.col_editor_view:
                return False

            if self.dragging_anchor and self.tile_item:
                # 将鼠标位置转换为场景坐标
                scene_pos = self.col_editor_view.mapToScene(event.pos())

                # 关键：减去图块在场景中的起始位置，转换为局部坐标
                tile_item_pos = self.tile_item.pos()
                local_x = scene_pos.x() - tile_item_pos.x()
                local_y = scene_pos.y() - tile_item_pos.y()

                # 如果开启了像素吸附功能，将坐标吸附到最近的像素点（整数坐标）
                if self.snap_to_pixel:
                    local_x = round(local_x)
                    local_y = round(local_y)

                # 解析锚点名称，获取顶点索引
                if self.dragging_anchor.startswith("point_"):
                    try:
                        point_index = int(self.dragging_anchor.split("_")[1])
                        if 0 <= point_index < len(self.collision_points):
                            # 更新多边形顶点位置（使用局部坐标）
                            self.collision_points[point_index] = QPointF(
                                local_x, local_y
                            )

                            # 更新碰撞多边形和锚点
                            self._update_collision_shape()
                            self._update_collision_anchors()

                            # 实时更新数据模型，这样即使程序意外退出，数据也是最新的
                            if self.current_collision_tile and self.map_model:
                                resource_index, tile_index = self.current_collision_tile
                                points_data = [
                                    [p.x(), p.y()] for p in self.collision_points
                                ]
                                self.map_model.set_tile_collision_shape(
                                    resource_index, tile_index, {"points": points_data}
                                )

                            # 完全阻止事件传递，防止画布移动
                            event.accept()
                            return True
                    except (ValueError, IndexError) as e:
                        print(f"DEBUG: 解析锚点错误: {e}")
        except Exception as e:
            print(f"DEBUG: 鼠标移动事件错误: {e}")
        # 即使没有拖动锚点，也返回True以防止画布移动
        event.accept()
        return True

    def _handle_mouse_release(self, event):
        """处理鼠标释放事件"""
        try:
            if not event:
                return False

            if event.button() == Qt.LeftButton:
                if self.dragging_anchor:
                    # 保存碰撞形状到地图模型
                    if (
                        self.collision_points
                        and self.current_collision_tile
                        and self.map_model
                    ):
                        resource_index, tile_index = self.current_collision_tile
                        # 将QPointF转换为列表格式
                        points_data = [
                            [point.x(), point.y()] for point in self.collision_points
                        ]
                        shape_data = {"points": points_data}
                        success = self.map_model.set_tile_collision_shape(
                            resource_index, tile_index, shape_data
                        )
                        if success:
                            # 强制更新资源池缓存
                            if self.parent_manager and hasattr(
                                self.parent_manager, "uploaded_resources"
                            ):
                                # 确保资源索引有效
                                if (
                                    0
                                    <= resource_index
                                    < len(self.parent_manager.uploaded_resources)
                                ):
                                    # 确保碰撞数据结构存在
                                    resource = self.parent_manager.uploaded_resources[
                                        resource_index
                                    ]
                                    if "collisions" not in resource:
                                        resource["collisions"] = []
                                    # 确保collisions数组足够大
                                    while len(resource["collisions"]) <= tile_index:
                                        resource["collisions"].append({})
                                    # 更新碰撞数据
                                    resource["collisions"][tile_index]["points"] = (
                                        points_data
                                    )
                            # 自动保存地图数据，确保实时编辑的碰撞形状能够立即保存到文件
                            if (
                                self.parent_manager
                                and hasattr(self.parent_manager, "current_map_path")
                                and self.parent_manager.current_map_path
                            ):
                                self.map_model.save(
                                    self.parent_manager.current_map_path
                                )

                    self.dragging_anchor = None
                    if self.col_editor_view:
                        self.col_editor_view.setCursor(QCursor(Qt.ArrowCursor))
                    return True
        except Exception as e:
            print(f"DEBUG: 鼠标释放事件错误: {e}")
            import traceback

            traceback.print_exc()
        return False
