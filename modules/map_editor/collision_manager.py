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
            print(f"DEBUG: 初始化碰撞编辑器错误: {e}")
            import traceback

            traceback.print_exc()

    def set_current_collision_tile(self, resource_index, tile_index):
        """设置当前碰撞图块"""
        try:
            print(
                f"DEBUG: 开始设置当前碰撞图块 - 资源索引: {resource_index}, 图块索引: {tile_index}"
            )
            self.current_collision_tile = (resource_index, tile_index)
            self.current_collision_image = None  # 清除当前碰撞图像
            print(f"DEBUG: 当前碰撞图块设置为: {self.current_collision_tile}")
            self._update_collision_display()
            print("DEBUG: 碰撞图块设置完成")
        except Exception as e:
            print(f"DEBUG: 设置碰撞图块错误: {e}")
            import traceback

            traceback.print_exc()

    def set_current_collision_image(self, layer_id, image_index):
        """设置当前碰撞图像"""
        try:
            print(
                f"DEBUG: 开始设置当前碰撞图像 - 图层ID: {layer_id}, 图像索引: {image_index}"
            )
            self.current_collision_image = (layer_id, image_index)
            self.current_collision_tile = None  # 清除当前碰撞图块
            print(f"DEBUG: 当前碰撞图像设置为: {self.current_collision_image}")
            self._update_collision_display()
            print("DEBUG: 碰撞图像设置完成")
        except Exception as e:
            print(f"DEBUG: 设置碰撞图像错误: {e}")
            import traceback

            traceback.print_exc()

    def _update_collision_display(self):
        """更新碰撞编辑器的显示"""
        try:
            print("DEBUG: 开始更新碰撞编辑器显示")
            if (
                not self.col_editor_scene
                or not self.col_editor_view
                or not (self.current_collision_tile or self.current_collision_image)
            ):
                print("DEBUG: 碰撞编辑器组件不完整，返回")
                print(f"  col_editor_scene: {self.col_editor_scene}")
                print(f"  col_editor_view: {self.col_editor_view}")
                print(f"  current_collision_tile: {self.current_collision_tile}")
                print(f"  current_collision_image: {self.current_collision_image}")
                return

            pixmap = None
            collision_shape = None
            collision_enabled = True

            if self.current_collision_tile:
                # 处理绘制图层
                resource_index, tile_index = self.current_collision_tile
                print(
                    f"DEBUG: 当前碰撞图块 - 资源索引: {resource_index}, 图块索引: {tile_index}"
                )

                # 获取图块图像
                print("DEBUG: 获取图块图像")
                pixmap = self._get_tile_pixmap(resource_index, tile_index)
                print(
                    f"DEBUG: 图块图像获取结果: {pixmap is not None and not pixmap.isNull()}"
                )

                # 计算全局资源索引
                global_resource_index = resource_index
                if self.parent_manager and hasattr(self.parent_manager, "layer_manager") and hasattr(self.parent_manager, "layer_resources"):
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
                
                print(f"DEBUG: 局部资源索引: {resource_index}, 全局资源索引: {global_resource_index}")

                # 从地图模型获取碰撞形状（使用全局资源索引）
                print("DEBUG: 从地图模型获取碰撞形状")
                collision_shape = self.map_model.get_tile_collision_shape(
                    global_resource_index, tile_index
                )
                print(f"DEBUG: 获取到的碰撞形状: {collision_shape}")

                # 获取碰撞启用状态（使用全局资源索引）
                collision_enabled = self.map_model.get_tile_collision(
                    global_resource_index, tile_index
                )
                print(f"DEBUG: 碰撞是否启用: {collision_enabled}")
            elif self.current_collision_image:
                # 处理图像图层
                layer_id, image_index = self.current_collision_image
                print(
                    f"DEBUG: 当前碰撞图像 - 图层ID: {layer_id}, 图像索引: {image_index}"
                )

                # 从图层管理器获取图像数据
                if self.parent_manager and hasattr(
                    self.parent_manager, "layer_manager"
                ):
                    layer_manager = self.parent_manager.layer_manager
                    print(f"DEBUG: 图层管理器中的图层数量: {len(layer_manager.layers)}")
                    
                    for layer in layer_manager.layers:
                        print(f"DEBUG: 检查图层 - ID: {layer.layer_id}, 类型: {layer.layer_type}")
                        if layer.layer_id == layer_id:
                            print(f"DEBUG: 找到目标图层 - ID: {layer.layer_id}, 类型: {layer.layer_type}")
                            # 检查图层类型是否为图像图层
                            if hasattr(layer, 'images'):
                                print(f"DEBUG: 图像数量: {len(layer.images)}")
                                if 0 <= image_index < len(layer.images):
                                    image_data = layer.images[image_index]
                                    print(f"DEBUG: 图像数据 - 存在: {image_data is not None}")
                                    if image_data:
                                        pixmap = image_data.pixmap
                                        collision_shape = image_data.collision_shape
                                        collision_enabled = image_data.collision_enabled
                                else:
                                    print(f"DEBUG: 图像索引超出范围 - 索引: {image_index}, 图像数量: {len(layer.images)}, 从资源路径加载图像")
                                    # 从 layer_resources 加载图像
                                    if hasattr(self.parent_manager, "layer_resources"):
                                        layer_resources = self.parent_manager.layer_resources.get(layer_id, [])
                                        if 0 <= image_index < len(layer_resources):
                                            resource = layer_resources[image_index]
                                            resource_path = resource.get("path", "")
                                            # 处理相对路径
                                            if resource_path and not os.path.isabs(resource_path) and hasattr(self.parent_manager, "current_map_path") and self.parent_manager.current_map_path:
                                                map_dir = os.path.dirname(self.parent_manager.current_map_path)
                                                resource_path = os.path.join(map_dir, resource_path)
                                            if resource_path and os.path.exists(resource_path):
                                                loaded_pixmap = QPixmap(resource_path)
                                                if not loaded_pixmap.isNull():
                                                    pixmap = loaded_pixmap
                                            collision_shape = resource.get("collision_shape", None)
                                            collision_enabled = resource.get("collision_enabled", False)
                            else:
                                print(f"DEBUG: 图层类型错误 - 不是图像图层，没有images属性")
                            break
                else:
                    print("DEBUG: 父管理器或图层管理器不存在")

            if pixmap and not pixmap.isNull():
                # 对于图像图层，直接缩放图像本身
                pixmap_width = pixmap.width()
                pixmap_height = pixmap.height()
                print(f"DEBUG: 图块原始尺寸: {pixmap_width}x{pixmap_height}")

                # 获取视图大小
                view_rect = self.col_editor_view.viewport().rect()
                view_width = view_rect.width()
                view_height = view_rect.height()
                print(f"DEBUG: 视图大小: {view_width}x{view_height}")
                
                # 处理图像
                if self.current_collision_image:
                    # 图像图层：直接缩放图像本身
                    # 使用基于视图大小的目标尺寸（视图的80%）
                    target_width = view_width * 0.8
                    target_height = view_height * 0.8
                    print(f"DEBUG: 目标尺寸: {target_width}x{target_height}")
                    
                    # 计算保持比例的缩放因子
                    scale_x = target_width / pixmap_width
                    scale_y = target_height / pixmap_height
                    image_scale = min(scale_x, scale_y)
                    print(f"DEBUG: 图像缩放因子 - x: {scale_x}, y: {scale_y}, 最终: {image_scale}")
                    
                    # 直接缩放图像
                    scaled_width = int(pixmap_width * image_scale)
                    scaled_height = int(pixmap_height * image_scale)
                    display_pixmap = pixmap.scaled(
                        scaled_width,
                        scaled_height,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    print(f"DEBUG: 图像缩放后尺寸: {scaled_width}x{scaled_height}")
                    
                    # 对于图像图层，我们直接缩放图像，所以视图变换不需要缩放
                    view_scale = 1.0
                    print(f"DEBUG: 图像图层视图变换缩放: {view_scale}")
                else:
                    # 绘制图层：保持原有逻辑，使用视图变换
                    display_pixmap = pixmap
                    
                    # 黄金分割尺寸（大约占视图的61.8%）
                    target_width = view_width * 0.618
                    target_height = view_height * 0.618
                    print(f"DEBUG: 目标尺寸: {target_width}x{target_height}")

                    # 计算缩放比例
                    print(f"DEBUG: 图块原始尺寸: {pixmap_width}x{pixmap_height}")

                    # 计算保持比例的缩放因子
                    scale_x = target_width / pixmap_width
                    scale_y = target_height / pixmap_height
                    view_scale = min(scale_x, scale_y)
                    print(f"DEBUG: 缩放因子 - x: {scale_x}, y: {scale_y}, 最终: {view_scale}")

                    # 最小缩放限制（避免图块太小）
                    min_scale = 2.0  # 至少放大到原始大小的2倍
                    view_scale = max(view_scale, min_scale)
                    print(f"DEBUG: 应用最小缩放后: {view_scale}")

                # 清空场景前，先清理所有引用
                print("DEBUG: 清理碰撞相关项")
                self._cleanup_collision_items()

                # 清空场景
                print("DEBUG: 清空场景")
                self.col_editor_scene.clear()

                # 显示图像（放在场景中心位置）
                print("DEBUG: 创建并添加图块图像项")
                pixmap_item = QGraphicsPixmapItem(display_pixmap)
                
                # 使用显示图像的尺寸
                display_pixmap_width = display_pixmap.width()
                display_pixmap_height = display_pixmap.height()
                
                # 将图块放在场景中心位置，使图块中心点对准场景原点
                pixmap_item.setPos(-display_pixmap_width / 2, -display_pixmap_height / 2)
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
                print("DEBUG: 图块图像项添加完成")

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
                    print(f"DEBUG: 碰撞形状是否有效: {valid_collision_shape}")

                    if valid_collision_shape:
                        # 使用自定义多边形碰撞形状（确保是局部坐标）
                        raw_points = collision_shape["points"]
                        # 对于图像图层，需要根据缩放比例调整碰撞点
                        if self.current_collision_image:
                            # 计算原始图像到缩放后图像的缩放比例
                            # display_pixmap已经是缩放后的图像，所以这里的缩放比例是 display_pixmap_width / 原始图像宽度
                            display_scale = display_pixmap_width / pixmap_width if pixmap_width > 0 else 1.0
                            # 确保存储的是相对于图块左上角的局部坐标
                            self.collision_points = [
                                QPointF(p[0] * display_scale, p[1] * display_scale) for p in raw_points
                            ]
                            # 对于图像图层，碰撞点已经是相对于图像左上角的局部坐标
                            # 不需要坐标系转换，直接使用
                            pass
                            print(f"DEBUG: 加载碰撞形状 - 原始图像宽度: {pixmap_width}, 显示图像宽度: {display_pixmap_width}, 缩放比例: {display_scale}, 原始碰撞点: {raw_points}, 调整后碰撞点: {[(p.x(), p.y()) for p in self.collision_points]}")
                        else:
                            # 绘制图层，保持原样
                            self.collision_points = [
                                QPointF(p[0], p[1]) for p in raw_points
                            ]
                        print(
                            f"DEBUG: 使用自定义碰撞形状，顶点数: {len(self.collision_points)}"
                        )
                    else:
                        # 使用默认矩形碰撞形状（转换为多边形）
                        # 使用相对于图块左上角的局部坐标（0到图块大小）
                        if self.current_collision_image:
                            # 图像图层，使用缩放后的图像尺寸
                            self.collision_points = [
                                QPointF(0, 0),
                                QPointF(display_pixmap_width, 0),
                                QPointF(display_pixmap_width, display_pixmap_height),
                                QPointF(0, display_pixmap_height),
                            ]
                        else:
                            # 绘制图层，使用原始图像尺寸
                            self.collision_points = [
                                QPointF(0, 0),
                                QPointF(pixmap.width(), 0),
                                QPointF(pixmap.width(), pixmap.height()),
                                QPointF(0, pixmap.height()),
                            ]
                        print("DEBUG: 使用默认矩形碰撞形状")

                    # 更新碰撞多边形显示
                    print("DEBUG: 更新碰撞多边形显示")
                    self._update_collision_shape()

                    # 更新碰撞锚点
                    print("DEBUG: 更新碰撞锚点")
                    self._update_collision_anchors()

                # 重新设计变换逻辑：先缩放，后平移到视图中心
                print("DEBUG: 设置视图变换")
                transform = self.col_editor_view.transform()
                transform.reset()

                # 先缩放
                transform.scale(view_scale, view_scale)

                # 再平移到视图中心（使用动态获取的视图尺寸）
                transform.translate(view_width / 2, view_height / 2)

                # 应用变换，但确保不会导致画布移动
                self.col_editor_view.setTransform(transform)
                print(f"DEBUG: 变换应用完成，缩放: {view_scale}")

                # 确保场景大小与视图大小匹配，避免滚动
                # 但是保持图块的居中位置
                self.col_editor_scene.setSceneRect(
                    -view_width / 2, -view_height / 2, view_width, view_height
                )
                print(
                    f"DEBUG: 设置场景矩形: (-{view_width / 2}, -{view_height / 2}, {view_width}, {view_height})"
                )
                # 确保视图不会自动滚动
                self.col_editor_view.setSceneRect(
                    -view_width / 2, -view_height / 2, view_width, view_height
                )

                # 显示视图
                self.col_editor_view.show()
                print("DEBUG: 碰撞编辑器显示更新完成")
            else:
                # 如果没有pixmap，清空场景
                print("DEBUG: 没有图块图像，清空场景")
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
            print("DEBUG: 错误处理完成，资源已清理")

    def set_collision_enabled(self, enabled):
        """设置碰撞启用状态"""
        if self.current_collision_tile:
            resource_index, tile_index = self.current_collision_tile
            
            # 计算全局资源索引
            global_resource_index = resource_index
            if self.parent_manager and hasattr(self.parent_manager, "layer_manager") and hasattr(self.parent_manager, "layer_resources"):
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
                self.map_model.set_tile_collision(global_resource_index, tile_index, enabled)
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

    def _cleanup_collision_items(self):
        """清理碰撞相关的项，避免内存泄漏和程序崩溃"""
        try:
            # 从场景中移除并清理碰撞形状项
            if self.collision_shape_item and self.col_editor_scene:
                try:
                    self.col_editor_scene.removeItem(self.collision_shape_item)
                except Exception as e:
                    print(f"DEBUG: 移除碰撞形状项错误: {e}")
            self.collision_shape_item = None

            # 从场景中移除并清理锚点项
            if self.col_editor_scene:
                for anchor in self.anchor_items.values():
                    try:
                        self.col_editor_scene.removeItem(anchor)
                    except Exception as e:
                        print(f"DEBUG: 移除锚点项错误: {e}")
            # 清空锚点项字典
            self.anchor_items.clear()

            # 从场景中移除并清理图块项
            if self.tile_item and self.col_editor_scene:
                try:
                    self.col_editor_scene.removeItem(self.tile_item)
                except Exception as e:
                    print(f"DEBUG: 移除图块项错误: {e}")
            self.tile_item = None

            # 清空碰撞点列表
            self.collision_points = []

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
                anchor_radius = 6  # 增大锚点半径，使其更明显
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
                # 设置锚点忽略变换，保持固定大小
                anchor.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
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
                # 设置Z值，确保碰撞形状在图像上面
                self.collision_shape_item.setZValue(1)
                self.collision_shape_item.setBrush(
                    QBrush(QColor(100, 149, 237, 100))
                )  # 半透明淡蓝色
                # 设置碰撞形状的线条宽度，并确保不随缩放变化
                pen = QPen(QColor(100, 149, 237), 1.0)  # 增加线条宽度到1.0
                pen.setCosmetic(True)  # 线条宽度不随缩放变化
                self.collision_shape_item.setPen(pen)
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
            except Exception as e:
                print(f"DEBUG: 访问viewport错误: {e}")
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
                except Exception as e:
                    print(f"DEBUG: 处理鼠标事件错误: {e}")
                    return True  # 即使出错也返回True，防止事件传递
        except Exception as e:
            print(f"DEBUG: 事件过滤器错误: {e}")
        return False  # 其他事件不处理

    def _handle_mouse_press(self, event):
        """处理鼠标按下事件"""
        try:
            # 检查参数和对象是否有效
            if not event:
                return False

            if not hasattr(self, "col_editor_view") or not self.col_editor_view:
                return False

            if not hasattr(self, "anchor_items"):
                return False

            if event.button() == Qt.LeftButton:
                # 将鼠标位置转换为场景坐标
                try:
                    scene_pos = self.col_editor_view.mapToScene(event.pos())
                except Exception as e:
                    print(f"DEBUG: 转换鼠标坐标错误: {e}")
                    return False

                # 检查是否点击了锚点
                for anchor_name, anchor in self.anchor_items.items():
                    try:
                        if not anchor:
                            continue
                        # 扩大点击判定范围，即使鼠标没点进圆圈，只要在圆心附近就能抓取
                        click_rect = anchor.sceneBoundingRect().adjusted(-5, -5, 5, 5)
                        if click_rect.contains(scene_pos):
                            self.dragging_anchor = anchor_name
                            self.drag_start_pos = scene_pos
                            if self.col_editor_view:
                                try:
                                    self.col_editor_view.setCursor(
                                        QCursor(Qt.SizeAllCursor)
                                    )
                                except Exception as e:
                                    print(f"DEBUG: 设置光标错误: {e}")
                            return True
                    except Exception as e:
                        print(f"DEBUG: 检查锚点点击错误: {e}")
                        continue
        except Exception as e:
            print(f"DEBUG: 鼠标按下事件错误: {e}")
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
            except Exception as e:
                print(f"DEBUG: 转换鼠标坐标错误: {e}")
                return False

            # 关键：减去图块在场景中的起始位置，转换为局部坐标
            try:
                tile_item_pos = self.tile_item.pos()
                local_x = scene_pos.x() - tile_item_pos.x()
                local_y = scene_pos.y() - tile_item_pos.y()
            except Exception as e:
                print(f"DEBUG: 获取图块位置错误: {e}")
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
                        except Exception as e:
                            print(f"DEBUG: 更新碰撞形状错误: {e}")

                        try:
                            self._update_collision_anchors()
                        except Exception as e:
                            print(f"DEBUG: 更新锚点位置错误: {e}")

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
                            except Exception as e:
                                print(f"DEBUG: 更新数据模型错误: {e}")
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
                                                # 计算缩放比例，将碰撞点转换为相对于原始图像的坐标
                                                display_to_original_scale = 1.0
                                                if hasattr(self, "tile_item") and self.tile_item:
                                                    # 获取原始图像尺寸
                                                    pixmap = image_data.pixmap
                                                    if pixmap and not pixmap.isNull():
                                                        original_width = pixmap.width()
                                                        original_height = pixmap.height()
                                                        # 获取显示图像尺寸
                                                        display_width = self.tile_item.boundingRect().width()
                                                        display_height = self.tile_item.boundingRect().height()
                                                        # 计算缩放比例：原始图像尺寸 / 显示图像尺寸
                                                        if display_width > 0:
                                                            display_to_original_scale = original_width / display_width
                                                        elif display_height > 0:
                                                            display_to_original_scale = original_height / display_height
                                                        print(f"DEBUG: 保存碰撞形状 - 原始图像尺寸: {original_width}x{original_height}, 显示图像尺寸: {display_width}x{display_height}, 缩放比例: {display_to_original_scale}")
                                                # 确保缩放比例不为0
                                                if display_to_original_scale <= 0:
                                                    display_to_original_scale = 1.0
                                                # 对于图像图层，碰撞点已经是相对于图像左上角的局部坐标
                                                # 不需要坐标系转换，直接使用
                                                adjusted_points = self.collision_points
                                                # 将碰撞点转换为相对于原始图像的坐标
                                                points_data = [
                                                    [p.x() * display_to_original_scale, p.y() * display_to_original_scale]
                                                    for p in adjusted_points
                                                ]
                                                image_data.collision_shape = {
                                                    "points": points_data
                                                }
                                                print(f"DEBUG: 保存碰撞形状 - 缩放比例: {display_to_original_scale}, 碰撞点: {points_data}")
                                                break
                            except Exception as e:
                                print(f"DEBUG: 更新图像碰撞数据错误: {e}")

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
                                        # 计算缩放比例，将碰撞点转换为相对于原始图像的坐标
                                        display_to_original_scale = 1.0
                                        if hasattr(self, "tile_item") and self.tile_item:
                                            # 获取原始图像尺寸
                                            pixmap = image_data.pixmap
                                            if pixmap and not pixmap.isNull():
                                                original_width = pixmap.width()
                                                original_height = pixmap.height()
                                                # 获取显示图像尺寸
                                                display_width = self.tile_item.boundingRect().width()
                                                display_height = self.tile_item.boundingRect().height()
                                                # 计算缩放比例：原始图像尺寸 / 显示图像尺寸
                                                if display_width > 0:
                                                    display_to_original_scale = original_width / display_width
                                                elif display_height > 0:
                                                    display_to_original_scale = original_height / display_height
                                                print(f"DEBUG: 保存碰撞形状(释放鼠标) - 原始图像尺寸: {original_width}x{original_height}, 显示图像尺寸: {display_width}x{display_height}, 缩放比例: {display_to_original_scale}")
                                        # 确保缩放比例不为0
                                        if display_to_original_scale <= 0:
                                            display_to_original_scale = 1.0
                                        # 将碰撞点转换为相对于原始图像的坐标
                                        points_data = [
                                            [p.x() * display_to_original_scale, p.y() * display_to_original_scale]
                                            for p in self.collision_points
                                        ]
                                        shape_data = {"points": points_data}
                                        image_data.collision_shape = shape_data
                                        image_data.collision_enabled = True
                                        print(f"DEBUG: 保存碰撞形状(释放鼠标) - 缩放比例: {display_to_original_scale}, 碰撞点: {points_data}")
                                        # 自动保存地图数据
                                        if (
                                            self.parent_manager
                                            and hasattr(
                                                self.parent_manager, "current_map_path"
                                            )
                                            and self.parent_manager.current_map_path
                                        ):
                                            # 同步 ImageData 到 map_data 再保存
                                            if hasattr(self.parent_manager, "layer_manager"):
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
