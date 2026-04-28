import os
from PySide6.QtCore import QObject, Qt, QEvent, QPointF, QRectF
from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsView,
    QGraphicsEllipseItem,
    QGraphicsItem,
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
        self.current_collision_tile = None  # 用于绘制图层
        self.current_collision_image = None  # 用于图像图层
        self.collision_shape_item = None
        self.tile_pixmap_provider = None  # 图块图像获取函数
        self.tile_item = None  # 图块图像项，用于坐标转换

        # 碰撞编辑相关属性
        self.anchor_items = {}  # 锚点项字典
        self.dragging_anchor = None  # 当前正在拖动的锚点
        self.drag_start_pos = QPointF()  # 拖动起始位置
        self.collision_points = []  # 当前碰撞多边形的顶点
        self.snap_to_pixel = True  # 是否吸附到像素网格，默认开启
        self.collision_tool = "move"  # 碰撞编辑工具: "move", "add", "delete"
        self.polygon_closed = True  # 碰撞多边形是否已闭合

    def __del__(self):
        """清理资源，避免程序退出时崩溃"""
        try:
            # 先清除对锚点项的引用，避免在清理场景时访问已销毁的对象
            if hasattr(self, "anchor_items"):
                try:
                    self.anchor_items.clear()
                except Exception:
                    pass

            # 移除事件过滤器（安静模式，不打印调试信息）
            if hasattr(self, "col_editor_view") and self.col_editor_view:
                try:
                    # 检查col_editor_view是否存在且有效
                    if hasattr(self, "col_editor_view") and self.col_editor_view:
                        # 先移除viewport的事件过滤器
                        try:
                            viewport = self.col_editor_view.viewport()
                            if viewport:
                                try:
                                    viewport.removeEventFilter(self)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                        # 再移除视图本身的事件过滤器
                        try:
                            self.col_editor_view.removeEventFilter(self)
                        except Exception:
                            pass
                except Exception:
                    pass

            # 清理场景（安静模式，不打印调试信息）
            if hasattr(self, "col_editor_scene") and self.col_editor_scene:
                try:
                    self.col_editor_scene.clear()
                except Exception:
                    pass

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
        except Exception:
            pass

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
            pass

    def set_current_collision_tile(self, resource_index, tile_index):
        """设置当前碰撞图块"""
        try:
            self.current_collision_tile = (resource_index, tile_index)
            self.current_collision_image = None  # 清除当前碰撞图像
            self._update_collision_display()
        except Exception as e:
            pass

    def set_current_collision_image(self, layer_id, image_index):
        """设置当前碰撞图像"""
        try:
            self.current_collision_image = (layer_id, image_index)
            self.current_collision_tile = None  # 清除当前碰撞图块
            self._update_collision_display()
        except Exception as e:
            pass

    def _update_collision_display(self):
        """更新碰撞编辑器的显示"""
        try:
            if (
                not self.col_editor_scene
                or not self.col_editor_view
                or not (self.current_collision_tile or self.current_collision_image)
            ):
                return

            pixmap = None
            collision_shape = None
            collision_enabled = True

            if self.current_collision_tile:
                # 处理绘制图层
                resource_index, tile_index = self.current_collision_tile

                # 获取图块图像
                pixmap = self._get_tile_pixmap(resource_index, tile_index)

                # 计算全局资源索引
                global_resource_index = resource_index
                if (
                    self.parent_manager
                    and hasattr(self.parent_manager, "layer_manager")
                    and hasattr(self.parent_manager, "layer_resources")
                ):
                    layer_manager = self.parent_manager.layer_manager
                    current_layer = layer_manager.get_current_layer()
                    if current_layer:
                        layer_resources = self.parent_manager.layer_resources
                        global_resource_index = 0
                        # 遍历所有图层的资源，找到当前资源的全局索引
                        for layer_id, resources in layer_resources.items():
                            if layer_id == current_layer.layer_id:
                                # 找到当前图层，加上当前资源在图层内的索引
                                global_resource_index += resource_index
                                break
                            # 加上其他图层的资源数量
                            global_resource_index += len(resources)

                # 从地图模型获取碰撞形状（使用全局资源索引）
                collision_shape = self.map_model.get_tile_collision_shape(
                    global_resource_index, tile_index
                )

                # 获取碰撞启用状态（使用全局资源索引）
                collision_enabled = self.map_model.get_tile_collision(
                    global_resource_index, tile_index
                )
            elif self.current_collision_image:
                # 处理图像图层
                layer_id, image_index = self.current_collision_image

                # 从图层管理器获取图像数据
                if self.parent_manager and hasattr(
                    self.parent_manager, "layer_manager"
                ):
                    layer_manager = self.parent_manager.layer_manager

                    for layer in layer_manager.layers:
                        if layer.layer_id == layer_id:
                            # 检查图层类型是否为图像图层
                            if hasattr(layer, "images"):
                                if 0 <= image_index < len(layer.images):
                                    image_data = layer.images[image_index]
                                    if image_data:
                                        pixmap = image_data.pixmap
                                        collision_shape = image_data.collision_shape
                                        collision_enabled = image_data.collision_enabled
                                else:
                                    # 从 layer_resources 加载图像
                                    if hasattr(self.parent_manager, "layer_resources"):
                                        layer_resources = (
                                            self.parent_manager.layer_resources.get(
                                                layer_id, []
                                            )
                                        )
                                        if 0 <= image_index < len(layer_resources):
                                            resource = layer_resources[image_index]
                                            resource_path = resource.get("path", "")
                                            # 处理相对路径
                                            if (
                                                resource_path
                                                and not os.path.isabs(resource_path)
                                                and hasattr(
                                                    self.parent_manager,
                                                    "current_map_path",
                                                )
                                                and self.parent_manager.current_map_path
                                            ):
                                                map_dir = os.path.dirname(
                                                    self.parent_manager.current_map_path
                                                )
                                                resource_path = os.path.join(
                                                    map_dir, resource_path
                                                )
                                            if resource_path and os.path.exists(
                                                resource_path
                                            ):
                                                loaded_pixmap = QPixmap(resource_path)
                                                if not loaded_pixmap.isNull():
                                                    pixmap = loaded_pixmap
                                            collision_shape = resource.get(
                                                "collision_shape", None
                                            )
                                            collision_enabled = resource.get(
                                                "collision_enabled", False
                                            )
                            break

            if pixmap and not pixmap.isNull():
                pixmap_width = pixmap.width()
                pixmap_height = pixmap.height()

                # 获取视图大小
                view_rect = self.col_editor_view.viewport().rect()
                view_width = view_rect.width()
                view_height = view_rect.height()

                # 处理图像
                if self.current_collision_image:
                    # 图像图层：自适应缩放，大图缩小适配视图，小图适当放大
                    display_pixmap = pixmap

                    target_width = view_width * 0.8
                    target_height = view_height * 0.8

                    scale_x = target_width / pixmap_width
                    scale_y = target_height / pixmap_height
                    view_scale = min(scale_x, scale_y)

                    # 小图像适当放大，但不超过原始尺寸的4倍
                    max_scale = 4.0
                    view_scale = min(view_scale, max_scale)
                else:
                    # 绘制图层：保持原有逻辑，使用视图变换
                    display_pixmap = pixmap

                    # 黄金分割尺寸（大约占视图的61.8%）
                    target_width = view_width * 0.618
                    target_height = view_height * 0.618

                    # 计算保持比例的缩放因子
                    scale_x = target_width / pixmap_width
                    scale_y = target_height / pixmap_height
                    view_scale = min(scale_x, scale_y)

                    # 最小缩放限制（避免图块太小）
                    min_scale = 2.0  # 至少放大到原始大小的2倍
                    view_scale = max(view_scale, min_scale)

                # 清空场景前，先清理所有引用
                self._cleanup_collision_items()

                # 清空场景
                self.col_editor_scene.clear()

                # 显示图像（放在场景中心位置）
                pixmap_item = QGraphicsPixmapItem(display_pixmap)

                # 使用显示图像的尺寸
                display_pixmap_width = display_pixmap.width()
                display_pixmap_height = display_pixmap.height()

                # 将图块放在场景中心位置，使图块中心点对准场景原点
                pixmap_item.setPos(
                    -display_pixmap_width / 2, -display_pixmap_height / 2
                )
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
                if collision_enabled:
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

                    if valid_collision_shape:
                        raw_points = collision_shape["points"]
                        self.collision_points = [
                            QPointF(p[0], p[1]) for p in raw_points
                        ]
                        self.polygon_closed = True
                    else:
                        self.collision_points = [
                            QPointF(0, 0),
                            QPointF(pixmap.width(), 0),
                            QPointF(pixmap.width(), pixmap.height()),
                            QPointF(0, pixmap.height()),
                        ]
                        self.polygon_closed = True

                    # 更新碰撞多边形显示
                    self._update_collision_shape()

                    # 更新碰撞锚点
                    self._update_collision_anchors()

                # 重新设计变换逻辑：先缩放，后平移到视图中心
                transform = self.col_editor_view.transform()
                transform.reset()

                # 先缩放
                transform.scale(view_scale, view_scale)

                # 再平移到视图中心（使用动态获取的视图尺寸）
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
            # 发生错误时清理资源
            self._cleanup_collision_items()
            if self.col_editor_scene:
                self.col_editor_scene.clear()

    def set_collision_enabled(self, enabled):
        """设置碰撞启用状态"""
        if self.current_collision_tile:
            resource_index, tile_index = self.current_collision_tile

            # 计算全局资源索引
            global_resource_index = resource_index
            if (
                self.parent_manager
                and hasattr(self.parent_manager, "layer_manager")
                and hasattr(self.parent_manager, "layer_resources")
            ):
                layer_manager = self.parent_manager.layer_manager
                current_layer = layer_manager.get_current_layer()
                if current_layer:
                    layer_resources = self.parent_manager.layer_resources
                    global_resource_index = 0
                    # 遍历所有图层的资源，找到当前资源的全局索引
                    for layer_id, resources in layer_resources.items():
                        if layer_id == current_layer.layer_id:
                            # 找到当前图层，加上当前资源在图层内的索引
                            global_resource_index += resource_index
                            break
                        # 加上其他图层的资源数量
                        global_resource_index += len(resources)

            if self.map_model:
                self.map_model.set_tile_collision(
                    global_resource_index, tile_index, enabled
                )
                self._update_collision_display()
        elif self.current_collision_image:
            layer_id, image_index = self.current_collision_image
            if self.parent_manager and hasattr(self.parent_manager, "layer_manager"):
                layer_manager = self.parent_manager.layer_manager
                for layer in layer_manager.layers:
                    if layer.layer_id == layer_id:
                        if 0 <= image_index < len(layer.images):
                            image_data = layer.images[image_index]
                            image_data.collision_enabled = enabled
                            self._update_collision_display()
                            break

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

    def set_collision_tool(self, tool_name):
        """设置碰撞编辑工具"""
        if tool_name != self.collision_tool:
            if (
                tool_name != "add"
                and not self.polygon_closed
                and len(self.collision_points) >= 3
            ):
                self.polygon_closed = True
                self._update_collision_shape()
                self._save_collision_data()
            self.collision_tool = tool_name

    def reset_collision_shape(self):
        """重置碰撞形状为默认矩形"""
        try:
            if not self.tile_item or not self.col_editor_scene:
                return
            pixmap = self.tile_item.pixmap()
            if not pixmap or pixmap.isNull():
                return
            w = pixmap.width()
            h = pixmap.height()
            self.collision_points = [
                QPointF(0, 0),
                QPointF(w, 0),
                QPointF(w, h),
                QPointF(0, h),
            ]
            self.polygon_closed = True
            self._rebuild_anchor_items()
            self._update_collision_shape()
            self._update_collision_anchors()
            self._save_collision_data()
        except Exception as e:
            print(f"重置碰撞形状错误: {e}")

    def _point_to_segment_distance(self, px, py, x1, y1, x2, y2):
        """计算点到线段的距离，返回 (距离, 最近点x, 最近点y)"""
        dx = x2 - x1
        dy = y2 - y1
        length_sq = dx * dx + dy * dy
        if length_sq < 1e-10:
            dist = ((px - x1) ** 2 + (py - y1) ** 2) ** 0.5
            return dist, x1, y1
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / length_sq))
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy
        dist = ((px - closest_x) ** 2 + (py - closest_y) ** 2) ** 0.5
        return dist, closest_x, closest_y

    def _find_nearest_edge(self, local_x, local_y, threshold=5.0):
        """找到最近的边框线段，返回 (线段索引, 插入位置x, 插入位置y) 或 None"""
        if len(self.collision_points) < 2:
            return None
        min_dist = float("inf")
        best_edge = -1
        best_pos = None
        n = len(self.collision_points)
        edge_count = n if self.polygon_closed else n - 1
        for i in range(edge_count):
            p1 = self.collision_points[i]
            p2 = self.collision_points[(i + 1) % n]
            dist, cx, cy = self._point_to_segment_distance(
                local_x, local_y, p1.x(), p1.y(), p2.x(), p2.y()
            )
            if dist < min_dist:
                min_dist = dist
                best_edge = i
                best_pos = QPointF(cx, cy)
        if min_dist <= threshold and best_edge >= 0:
            return best_edge, best_pos
        return None

    def _is_click_on_first_anchor(self, scene_pos, pixel_threshold=15):
        """检测点击是否在第一个锚点附近（用于闭合多边形）"""
        if not self.collision_points or not self.anchor_items:
            return False
        first_anchor = self.anchor_items.get("point_0")
        if not first_anchor:
            return False
        anchor_screen = self.col_editor_view.mapFromScene(first_anchor.pos())
        click_screen = self.col_editor_view.mapFromScene(scene_pos)
        dx = anchor_screen.x() - click_screen.x()
        dy = anchor_screen.y() - click_screen.y()
        return (dx * dx + dy * dy) <= pixel_threshold * pixel_threshold

    def _find_clicked_anchor(self, scene_pos, pixel_threshold=15):
        """找到被点击的锚点名称，使用屏幕像素距离检测"""
        if not self.col_editor_view:
            return None
        best_name = None
        best_dist_sq = pixel_threshold * pixel_threshold
        for anchor_name, anchor in self.anchor_items.items():
            if not anchor:
                continue
            try:
                anchor_screen = self.col_editor_view.mapFromScene(anchor.pos())
                click_screen = self.col_editor_view.mapFromScene(scene_pos)
                dx = anchor_screen.x() - click_screen.x()
                dy = anchor_screen.y() - click_screen.y()
                dist_sq = dx * dx + dy * dy
                if dist_sq < best_dist_sq:
                    best_dist_sq = dist_sq
                    best_name = anchor_name
            except Exception:
                continue
        return best_name

    def _add_point_on_edge(self, edge_index, point):
        """在指定边的位置插入新锚点"""
        self.collision_points.insert(edge_index + 1, point)
        self._rebuild_anchor_items()
        self._update_collision_shape()
        self._update_collision_anchors()
        self._save_collision_data()

    def _add_point_create(self, point):
        """创建新锚点（不自动闭合）"""
        if len(self.collision_points) == 0:
            self.polygon_closed = False
        self.collision_points.append(point)
        self._rebuild_anchor_items()
        if self.polygon_closed and len(self.collision_points) >= 3:
            self._update_collision_shape()
        elif not self.polygon_closed and len(self.collision_points) >= 2:
            self._update_collision_shape()
        self._update_collision_anchors()
        self._save_collision_data()

    def _delete_anchor_point(self, anchor_name):
        """删除指定锚点"""
        if not anchor_name.startswith("point_"):
            return
        try:
            point_index = int(anchor_name.split("_")[1])
        except (ValueError, IndexError):
            return
        if point_index < 0 or point_index >= len(self.collision_points):
            return
        self.collision_points.pop(point_index)
        if len(self.collision_points) < 3:
            self.collision_points.clear()
            self.polygon_closed = False
            self._clear_collision_shape()
            if self.parent_manager and hasattr(self.parent_manager, "ui"):
                ui = self.parent_manager.ui
                if hasattr(ui, "btn_res_col_add"):
                    ui.btn_res_col_add.setChecked(True)
                if hasattr(ui, "btn_res_col_del"):
                    ui.btn_res_col_del.setChecked(False)
            self.collision_tool = "add"
        self._rebuild_anchor_items()
        if len(self.collision_points) >= 3 and self.polygon_closed:
            self._update_collision_shape()
        self._update_collision_anchors()
        self._save_collision_data()

    def _rebuild_anchor_items(self):
        """重建所有锚点项"""
        if not self.col_editor_scene:
            return
        for anchor_name, anchor in list(self.anchor_items.items()):
            try:
                self.col_editor_scene.removeItem(anchor)
            except Exception:
                pass
        self.anchor_items.clear()

    def _clear_collision_shape(self):
        """清空碰撞形状显示"""
        if self.collision_shape_item and self.col_editor_scene:
            try:
                self.col_editor_scene.removeItem(self.collision_shape_item)
            except Exception:
                pass
            self.collision_shape_item = None

    def _save_collision_data(self):
        """保存碰撞数据到模型"""
        try:
            if not self.collision_points:
                return
            if self.current_collision_tile and self.map_model:
                resource_index, tile_index = self.current_collision_tile
                points_data = [[p.x(), p.y()] for p in self.collision_points]
                self.map_model.set_tile_collision_shape(
                    resource_index, tile_index, {"points": points_data}
                )
                if (
                    self.parent_manager
                    and hasattr(self.parent_manager, "current_map_path")
                    and self.parent_manager.current_map_path
                ):
                    self.map_model.save(self.parent_manager.current_map_path)
            elif self.current_collision_image:
                layer_id, image_index = self.current_collision_image
                if self.parent_manager and hasattr(
                    self.parent_manager, "layer_manager"
                ):
                    layer_manager = self.parent_manager.layer_manager
                    for layer in layer_manager.layers:
                        if layer.layer_id == layer_id:
                            if 0 <= image_index < len(layer.images):
                                image_data = layer.images[image_index]
                                points_data = [
                                    [p.x(), p.y()] for p in self.collision_points
                                ]
                                image_data.collision_shape = {"points": points_data}
                                image_data.collision_enabled = True
                                if (
                                    self.parent_manager
                                    and hasattr(self.parent_manager, "current_map_path")
                                    and self.parent_manager.current_map_path
                                ):
                                    self.parent_manager.layer_manager.update_map_model()
                                    self.map_model.save(
                                        self.parent_manager.current_map_path
                                    )
                            break
        except Exception as e:
            print(f"保存碰撞数据错误: {e}")

    def _cleanup_collision_items(self):
        """清理碰撞相关的项，避免内存泄漏和程序崩溃"""
        try:
            # 从场景中移除并清理碰撞形状项
            if self.collision_shape_item and self.col_editor_scene:
                try:
                    self.col_editor_scene.removeItem(self.collision_shape_item)
                except Exception:
                    pass
            self.collision_shape_item = None

            # 从场景中移除并清理锚点项
            if self.col_editor_scene:
                for anchor in self.anchor_items.values():
                    try:
                        self.col_editor_scene.removeItem(anchor)
                    except Exception:
                        pass
            # 清空锚点项字典
            self.anchor_items.clear()

            # 从场景中移除并清理图块项
            if self.tile_item and self.col_editor_scene:
                try:
                    self.col_editor_scene.removeItem(self.tile_item)
                except Exception:
                    pass
            self.tile_item = None

            self.collision_points = []
            self.polygon_closed = True

            # 重置拖动状态
            self.dragging_anchor = None
        except Exception:
            pass

    def _update_collision_anchors(self):
        """更新碰撞锚点位置"""
        try:
            if not self.tile_item:
                return

            if not self.collision_points:
                for anchor_name, anchor in list(self.anchor_items.items()):
                    try:
                        if anchor and self.col_editor_scene:
                            self.col_editor_scene.removeItem(anchor)
                    except Exception:
                        pass
                self.anchor_items.clear()
                return

            while len(self.anchor_items) < len(self.collision_points):
                i = len(self.anchor_items)
                anchor_radius = 6
                from PySide6.QtWidgets import QGraphicsPolygonItem
                from PySide6.QtGui import QPolygonF

                diamond = QPolygonF()
                diamond.append(QPointF(0, -anchor_radius))
                diamond.append(QPointF(anchor_radius, 0))
                diamond.append(QPointF(0, anchor_radius))
                diamond.append(QPointF(-anchor_radius, 0))
                anchor = QGraphicsPolygonItem(diamond)
                self.col_editor_scene.addItem(anchor)
                anchor.setBrush(QBrush(QColor(255, 255, 255)))
                pen = QPen(QColor(0, 0, 0), 3.5)
                pen.setCosmetic(True)
                anchor.setPen(pen)
                anchor.setZValue(100)
                anchor.setData(0, f"point_{i}")
                anchor.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
                self.anchor_items[f"point_{i}"] = anchor

            while len(self.anchor_items) > len(self.collision_points):
                i = len(self.collision_points)
                anchor_name = f"point_{i}"
                if anchor_name in self.anchor_items:
                    anchor = self.anchor_items.pop(anchor_name)
                    try:
                        if anchor and self.col_editor_scene:
                            self.col_editor_scene.removeItem(anchor)
                    except Exception:
                        pass

            for i, point in enumerate(self.collision_points):
                anchor_name = f"point_{i}"
                if anchor_name in self.anchor_items:
                    anchor = self.anchor_items[anchor_name]
                    tile_pos = self.tile_item.pos() if self.tile_item else QPointF(0, 0)
                    anchor.setPos(tile_pos.x() + point.x(), tile_pos.y() + point.y())
        except Exception:
            pass

    def _update_collision_shape(self):
        """更新碰撞多边形显示"""
        try:
            if not self.collision_points or not self.tile_item:
                return

            if not self.collision_shape_item:
                from PySide6.QtWidgets import QGraphicsPolygonItem
                from PySide6.QtGui import QPolygonF

                self.collision_shape_item = QGraphicsPolygonItem()
                self.col_editor_scene.addItem(self.collision_shape_item)
                self.collision_shape_item.setZValue(1)
                pen = QPen(QColor(100, 149, 237), 1.0)
                pen.setCosmetic(True)
                self.collision_shape_item.setPen(pen)
                self.collision_shape_item.setAcceptedMouseButtons(Qt.NoButton)
                self.collision_shape_item.setFlag(
                    QGraphicsPolygonItem.ItemIsSelectable, False
                )

            if self.collision_shape_item:
                from PySide6.QtGui import QPolygonF

                if self.tile_item:
                    self.collision_shape_item.setPos(self.tile_item.pos())

                polygon = QPolygonF(self.collision_points)
                self.collision_shape_item.setPolygon(polygon)
                if self.polygon_closed:
                    self.collision_shape_item.setBrush(
                        QBrush(QColor(100, 149, 237, 100))
                    )
                else:
                    self.collision_shape_item.setBrush(Qt.NoBrush)
        except Exception:
            pass

    def eventFilter(self, obj, event):
        """事件过滤器，处理鼠标事件"""
        try:
            # 检查对象是否有效
            if not obj or not event:
                return False

            # 检查col_editor_view是否存在且有效
            if not hasattr(self, "col_editor_view") or not self.col_editor_view:
                return False

            # 检查viewport是否存在且有效
            try:
                viewport = self.col_editor_view.viewport()
                if not viewport:
                    return False
            except Exception:
                return False

            if obj == viewport:
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
                except Exception:
                    return True  # 即使出错也返回True，防止事件传递
        except Exception:
            pass
        return False  # 其他事件不处理

    def _handle_mouse_press(self, event):
        """处理鼠标按下事件"""
        try:
            if not event:
                return False

            if not hasattr(self, "col_editor_view") or not self.col_editor_view:
                return False

            if not hasattr(self, "anchor_items"):
                return False

            if not hasattr(self, "tile_item") or not self.tile_item:
                return False

            if event.button() == Qt.LeftButton:
                try:
                    scene_pos = self.col_editor_view.mapToScene(event.pos())
                except Exception:
                    return False

                tile_item_pos = self.tile_item.pos()
                local_x = scene_pos.x() - tile_item_pos.x()
                local_y = scene_pos.y() - tile_item_pos.y()

                if self.snap_to_pixel:
                    local_x = round(local_x)
                    local_y = round(local_y)

                if self.collision_tool == "add":
                    if not self.polygon_closed and len(self.collision_points) >= 3:
                        if self._is_click_on_first_anchor(scene_pos):
                            self.polygon_closed = True
                            self._update_collision_shape()
                            self._update_collision_anchors()
                            self._save_collision_data()
                            return True

                    if not self.polygon_closed:
                        self._add_point_create(QPointF(local_x, local_y))
                    else:
                        result = self._find_nearest_edge(local_x, local_y)
                        if result:
                            edge_index, insert_pos = result
                            self._add_point_on_edge(edge_index, insert_pos)
                    return True

                elif self.collision_tool == "delete":
                    clicked_anchor = self._find_clicked_anchor(scene_pos)
                    if clicked_anchor:
                        self._delete_anchor_point(clicked_anchor)
                    return True

                else:
                    clicked_anchor = self._find_clicked_anchor(scene_pos)
                    if clicked_anchor:
                        self.dragging_anchor = clicked_anchor
                        self.drag_start_pos = scene_pos
                        if self.col_editor_view:
                            try:
                                self.col_editor_view.setCursor(
                                    QCursor(Qt.SizeAllCursor)
                                )
                            except Exception:
                                pass
                        return True
        except Exception:
            pass
        return False

    def _handle_mouse_move(self, event):
        """处理鼠标移动事件"""
        try:
            # 检查参数和对象是否有效
            if not event:
                return False

            if not hasattr(self, "col_editor_view") or not self.col_editor_view:
                return False

            # 检查必要的属性是否存在
            if not hasattr(self, "dragging_anchor") or not self.dragging_anchor:
                return False

            if not hasattr(self, "tile_item") or not self.tile_item:
                return False

            # 将鼠标位置转换为场景坐标
            try:
                scene_pos = self.col_editor_view.mapToScene(event.pos())
            except Exception:
                return False

            # 关键：减去图块在场景中的起始位置，转换为局部坐标
            try:
                tile_item_pos = self.tile_item.pos()
                local_x = scene_pos.x() - tile_item_pos.x()
                local_y = scene_pos.y() - tile_item_pos.y()
            except Exception:
                return False

            # 如果开启了像素吸附功能，将坐标吸附到最近的像素点（整数坐标）
            if hasattr(self, "snap_to_pixel") and self.snap_to_pixel:
                local_x = round(local_x)
                local_y = round(local_y)

            # 解析锚点名称，获取顶点索引
            if self.dragging_anchor.startswith("point_"):
                try:
                    point_index = int(self.dragging_anchor.split("_")[1])

                    # 检查collision_points是否存在且索引有效
                    if not hasattr(self, "collision_points"):
                        return False

                    if 0 <= point_index < len(self.collision_points):
                        # 更新多边形顶点位置（使用局部坐标）
                        self.collision_points[point_index] = QPointF(local_x, local_y)

                        # 更新碰撞多边形和锚点
                        try:
                            self._update_collision_shape()
                        except Exception:
                            pass

                        try:
                            self._update_collision_anchors()
                        except Exception:
                            pass

                        # 实时更新数据模型，这样即使程序意外退出，数据也是最新的
                        if (
                            hasattr(self, "current_collision_tile")
                            and self.current_collision_tile
                            and hasattr(self, "map_model")
                            and self.map_model
                        ):
                            try:
                                resource_index, tile_index = self.current_collision_tile
                                points_data = [
                                    [p.x(), p.y()] for p in self.collision_points
                                ]
                                self.map_model.set_tile_collision_shape(
                                    resource_index, tile_index, {"points": points_data}
                                )
                            except Exception:
                                pass
                        elif (
                            hasattr(self, "current_collision_image")
                            and self.current_collision_image
                        ):
                            try:
                                layer_id, image_index = self.current_collision_image
                                if self.parent_manager and hasattr(
                                    self.parent_manager, "layer_manager"
                                ):
                                    layer_manager = self.parent_manager.layer_manager
                                    for layer in layer_manager.layers:
                                        if layer.layer_id == layer_id:
                                            if 0 <= image_index < len(layer.images):
                                                image_data = layer.images[image_index]
                                                points_data = [
                                                    [p.x(), p.y()]
                                                    for p in self.collision_points
                                                ]
                                                image_data.collision_shape = {
                                                    "points": points_data
                                                }
                                                break
                            except Exception:
                                pass

                        # 完全阻止事件传递，防止画布移动
                        event.accept()
                        return True
                except (ValueError, IndexError):
                    pass
        except Exception:
            pass
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
                    # 处理绘制图层的碰撞保存
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
                    # 处理图像图层的碰撞保存
                    elif self.collision_points and self.current_collision_image:
                        layer_id, image_index = self.current_collision_image
                        if self.parent_manager and hasattr(
                            self.parent_manager, "layer_manager"
                        ):
                            layer_manager = self.parent_manager.layer_manager
                            for layer in layer_manager.layers:
                                if layer.layer_id == layer_id:
                                    if 0 <= image_index < len(layer.images):
                                        image_data = layer.images[image_index]
                                        points_data = [
                                            [p.x(), p.y()]
                                            for p in self.collision_points
                                        ]
                                        shape_data = {"points": points_data}
                                        image_data.collision_shape = shape_data
                                        image_data.collision_enabled = True
                                        if (
                                            self.parent_manager
                                            and hasattr(
                                                self.parent_manager, "current_map_path"
                                            )
                                            and self.parent_manager.current_map_path
                                        ):
                                            # 同步 ImageData 到 map_data 再保存
                                            if hasattr(
                                                self.parent_manager, "layer_manager"
                                            ):
                                                self.parent_manager.layer_manager.update_map_model()
                                            self.map_model.save(
                                                self.parent_manager.current_map_path
                                            )
                                        break

                    self.dragging_anchor = None
                    if self.col_editor_view:
                        self.col_editor_view.setCursor(QCursor(Qt.ArrowCursor))
                    return True
        except Exception as e:
            print(f"DEBUG: 鼠标释放事件错误: {e}")
            import traceback

            traceback.print_exc()
        return False
