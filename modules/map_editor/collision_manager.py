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
            print(f"初始化碰撞编辑器: {col_editor_view}")
            if not col_editor_view:
                print("DEBUG: 无效的视图，初始化失败")
                return
            self.col_editor_view = col_editor_view
            self.col_editor_scene = QGraphicsScene()
            self.col_editor_view.setScene(self.col_editor_scene)

            # 禁用滚动条和滚轮滚动
            self.col_editor_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.col_editor_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.col_editor_view.setDragMode(QGraphicsView.NoDrag)

            # 设置居中对齐
            self.col_editor_view.setAlignment(Qt.AlignCenter)
            self.col_editor_view.setTransformationAnchor(
                QGraphicsView.ViewportAnchor.AnchorViewCenter
            )

            # 安装事件过滤器
            viewport = self.col_editor_view.viewport()
            if viewport:
                viewport.installEventFilter(self)
            print(
                f"碰撞编辑器初始化完成: scene={self.col_editor_scene}, view={self.col_editor_view}"
            )
        except Exception as e:
            print(f"DEBUG: 初始化碰撞编辑器错误: {e}")

    def set_current_collision_tile(self, resource_index, tile_index):
        """设置当前碰撞图块"""
        try:
            print(f"\n=== DEBUG: 选中新的碰撞图块 ===")
            print(
                f"DEBUG: 设置当前碰撞图块 - 资源索引: {resource_index}, 图块索引: {tile_index}"
            )
            print(
                f"DEBUG: 当前状态 - col_editor_view: {self.col_editor_view}, col_editor_scene: {self.col_editor_scene}"
            )
            self.current_collision_tile = (resource_index, tile_index)
            self._update_collision_display()
        except Exception as e:
            print(f"DEBUG: 设置碰撞图块错误: {e}")

    def _update_collision_display(self):
        """更新碰撞编辑器的显示"""
        try:
            print(
                f"DEBUG: 更新碰撞显示 - current_collision_tile: {self.current_collision_tile}"
            )
            print(f"DEBUG: col_editor_scene: {self.col_editor_scene}")
            print(f"DEBUG: col_editor_view: {self.col_editor_view}")

            if (
                not self.col_editor_scene
                or not self.col_editor_view
                or not self.current_collision_tile
            ):
                print("DEBUG: 缺少必要组件，返回")
                return

            resource_index, tile_index = self.current_collision_tile
            print(f"DEBUG: 资源索引: {resource_index}, 图块索引: {tile_index}")

            # 获取图块图像
            pixmap = self._get_tile_pixmap(resource_index, tile_index)
            print(f"DEBUG: 获取的pixmap: {pixmap}")
            if pixmap:
                print(f"DEBUG: pixmap尺寸: {pixmap.size()}")

            if pixmap and not pixmap.isNull():
                # 在更新场景前先隐藏视图，避免闪烁
                self.col_editor_view.hide()

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

                print(
                    f"DEBUG: 图块尺寸: {pixmap_width}x{pixmap_height}, 视图尺寸: {view_width}x{view_height}"
                )

                # 计算保持比例的缩放因子
                scale_x = target_width / pixmap_width
                scale_y = target_height / pixmap_height
                scale = min(scale_x, scale_y)

                print(
                    f"DEBUG: 计算的缩放因子: scale_x={scale_x}, scale_y={scale_y}, scale={scale}"
                )

                # 最小缩放限制（避免图块太小）
                min_scale = 2.0  # 至少放大到原始大小的2倍
                scale = max(scale, min_scale)

                print(f"DEBUG: 应用最小缩放后: scale={scale}")

                # 清空场景前，先清理所有引用
                self._cleanup_collision_items()

                # 清空场景
                self.col_editor_scene.clear()

                # 显示原图（放在场景中心位置）
                pixmap_item = QGraphicsPixmapItem(pixmap)
                # 将图块放在场景中心位置，使图块中心点对准场景原点
                pixmap_item.setPos(-pixmap_width / 2, -pixmap_height / 2)
                self.col_editor_scene.addItem(pixmap_item)
                self.tile_item = pixmap_item  # 保存图块图像项
                print(
                    f"DEBUG: 图块位置: ({pixmap_item.pos().x():.2f}, {pixmap_item.pos().y():.2f})"
                )

                # 显示碰撞框（多边形）
                if self.map_model:
                    # 打印地图模型中的瓦片集数量
                    print(
                        f"DEBUG: 地图模型中的瓦片集数量: {len(self.map_model.map_data['tile_sets'])}"
                    )

                    # 检查资源索引是否有效
                    if 0 <= resource_index < len(self.map_model.map_data["tile_sets"]):
                        tile_set = self.map_model.map_data["tile_sets"][resource_index]
                        print(
                            f"DEBUG: 瓦片集 {resource_index} 的图块数量: {len(tile_set.get('tiles', []))}"
                        )

                        # 检查图块索引是否有效
                        if 0 <= tile_index < len(tile_set.get("tiles", [])):
                            tile = tile_set["tiles"][tile_index]
                            print(
                                f"DEBUG: 图块 {tile_index} 的碰撞形状: {tile.get('collision_shape', 'None')}"
                            )

                    # 从地图模型获取碰撞形状（确保使用最新数据）
                    collision_shape = self.map_model.get_tile_collision_shape(
                        resource_index, tile_index
                    )
                    print(
                        f"DEBUG: 从地图模型获取碰撞形状 - 资源索引: {resource_index}, 图块索引: {tile_index}, 碰撞形状: {collision_shape}"
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
                    print(f"DEBUG: 碰撞形状数据是否有效: {valid_collision_shape}")

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
                                print(f"DEBUG: 更新资源池缓存碰撞形状: {points_data}")
                            else:
                                # 如果没有碰撞形状，清除缓存中的数据
                                if "points" in resource["collisions"][tile_index]:
                                    del resource["collisions"][tile_index]["points"]
                                    print(f"DEBUG: 清除资源池缓存碰撞形状")

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
                                            print(
                                                f"DEBUG: 从资源池缓存获取碰撞形状: {collision_shape}"
                                            )

                    collision_enabled = self.map_model.get_tile_collision(
                        resource_index, tile_index
                    )
                    print(f"DEBUG: 碰撞启用状态: {collision_enabled}")

                    if collision_enabled:
                        if valid_collision_shape:
                            # 使用自定义多边形碰撞形状（确保是局部坐标）
                            raw_points = collision_shape["points"]
                            # 确保存储的是相对于图块左上角的局部坐标
                            self.collision_points = [
                                QPointF(p[0], p[1]) for p in raw_points
                            ]
                            print(f"DEBUG: 加载自定义碰撞形状: {collision_shape}")
                        else:
                            # 使用默认矩形碰撞形状（转换为多边形）
                            # 使用相对于图块左上角的局部坐标（0到图块大小）
                            self.collision_points = [
                                QPointF(0, 0),
                                QPointF(pixmap.width(), 0),
                                QPointF(pixmap.width(), pixmap.height()),
                                QPointF(0, pixmap.height()),
                            ]
                            print(
                                f"DEBUG: 使用默认矩形碰撞形状，局部坐标范围: 0-{pixmap.width()}"
                            )

                        # 更新碰撞多边形显示
                        self._update_collision_shape()

                        # 打印多边形顶点位置用于调试
                        print(f"DEBUG: 多边形顶点位置（场景坐标）:")
                        for i, point in enumerate(self.collision_points):
                            print(
                                f"DEBUG: 顶点 {i}: ({point.x():.2f}, {point.y():.2f})"
                            )

                        # 更新碰撞锚点
                        self._update_collision_anchors()

                        # 打印多边形项的位置和变换
                        if self.collision_shape_item:
                            print(
                                f"DEBUG: 多边形项位置: ({self.collision_shape_item.pos().x():.2f}, {self.collision_shape_item.pos().y():.2f})"
                            )
                            print(
                                f"DEBUG: 多边形项变换: {self.collision_shape_item.transform()}"
                            )

                # 重新设计变换逻辑：先缩放，后平移到视图中心
                transform = self.col_editor_view.transform()
                transform.reset()

                # 先缩放
                transform.scale(scale, scale)
                print(f"DEBUG: 应用缩放变换: scale={scale}")

                # 再平移到视图中心
                transform.translate(view_width / 2, view_height / 2)
                print(
                    f"DEBUG: 应用平移变换: ({view_width / 2:.2f}, {view_height / 2:.2f})"
                )

                self.col_editor_view.setTransform(transform)

                # 显示视图
                self.col_editor_view.show()
                print(f"DEBUG: 视图变换已应用")

                # 再次打印锚点位置，确认变换后的实际位置
                print(f"DEBUG: 变换后锚点实际位置:")
                for anchor_name, anchor in self.anchor_items.items():
                    try:
                        scene_pos = anchor.mapToScene(anchor.boundingRect().center())
                        view_pos = self.col_editor_view.mapFromScene(scene_pos)
                        print(
                            f"DEBUG: {anchor_name} - 场景坐标: ({scene_pos.x():.2f}, {scene_pos.y():.2f}), 视图坐标: ({view_pos.x():.2f}, {view_pos.y():.2f})"
                        )
                    except Exception as e:
                        print(f"DEBUG: 获取锚点位置错误: {e}")
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

            print(f"DEBUG: 更新锚点位置 - 碰撞点数量: {len(self.collision_points)}")

            # 确保锚点数量与碰撞点数量一致
            while len(self.anchor_items) < len(self.collision_points):
                i = len(self.anchor_items)
                anchor_radius = 1  # 锚点半径，缩小1/2
                # 创建椭圆，先不设置父项
                anchor = QGraphicsEllipseItem(
                    -anchor_radius, -anchor_radius, anchor_radius * 2, anchor_radius * 2
                )
                # 然后设置父项
                anchor.setParentItem(self.tile_item)
                anchor.setBrush(QBrush(QColor(255, 0, 0)))
                # 使用抗锯齿笔刷，减少锯齿感
                pen = QPen(QColor(255, 255, 255), 1.5)  # 增加描边宽度
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
                print(
                    f"DEBUG: 更新锚点 {anchor_name} 位置: ({point.x():.2f}, {point.y():.2f})"
                )
                if anchor_name in self.anchor_items:
                    # 因为anchor是tile_item的子项，所以直接赋值局部坐标点即可
                    anchor = self.anchor_items[anchor_name]
                    anchor.setPos(point)
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
                # 如果还没有创建多边形项，创建一个并设为图块的子项
                from PySide6.QtWidgets import QGraphicsPolygonItem
                from PySide6.QtGui import QPolygonF

                self.collision_shape_item = QGraphicsPolygonItem()
                self.collision_shape_item.setParentItem(self.tile_item)
                self.collision_shape_item.setBrush(
                    QBrush(QColor(100, 149, 237, 100))
                )  # 半透明淡蓝色
                self.collision_shape_item.setPen(QPen(QColor(100, 149, 237), 1))
                # 核心修复：让多边形不响应鼠标，点击事件会直接穿透到下层的锚点
                self.collision_shape_item.setAcceptedMouseButtons(Qt.NoButton)
                self.collision_shape_item.setFlag(
                    QGraphicsPolygonItem.ItemIsSelectable, False
                )

            if self.collision_shape_item:
                from PySide6.QtGui import QPolygonF

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
                        return self._handle_mouse_press(event)
                    elif event.type() == QEvent.MouseMove:
                        return self._handle_mouse_move(event)
                    elif event.type() == QEvent.MouseButtonRelease:
                        return self._handle_mouse_release(event)
                except Exception as e:
                    print(f"DEBUG: 处理鼠标事件错误: {e}")
        except Exception as e:
            print(f"DEBUG: 事件过滤器错误: {e}")
        return super().eventFilter(obj, event)

    def _handle_mouse_press(self, event):
        """处理鼠标按下事件"""
        try:
            if not event or not self.col_editor_view:
                return False

            if event.button() == Qt.LeftButton:
                scene_pos = self.col_editor_view.mapToScene(event.pos())
                print(
                    f"DEBUG: 鼠标点击位置: ({scene_pos.x():.2f}, {scene_pos.y():.2f})"
                )

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
                            print(f"DEBUG: 选中锚点: {anchor_name}")
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
                print(
                    f"DEBUG: 拖动锚点 {self.dragging_anchor} - 鼠标场景坐标: ({scene_pos.x():.2f}, {scene_pos.y():.2f})"
                )

                # 关键：减去图块在场景中的起始位置，转换为局部坐标
                tile_item_pos = self.tile_item.pos()
                local_x = scene_pos.x() - tile_item_pos.x()
                local_y = scene_pos.y() - tile_item_pos.y()

                print(f"DEBUG: 转换为局部坐标: ({local_x:.2f}, {local_y:.2f})")

                # 允许碰撞点超出图块范围，提供更大的编辑灵活性
                print(f"DEBUG: 局部坐标: ({local_x:.2f}, {local_y:.2f})")

                # 解析锚点名称，获取顶点索引
                if self.dragging_anchor.startswith("point_"):
                    try:
                        point_index = int(self.dragging_anchor.split("_")[1])
                        if 0 <= point_index < len(self.collision_points):
                            print(
                                f"DEBUG: 更新顶点 {point_index} 位置: ({self.collision_points[point_index].x():.2f}, {self.collision_points[point_index].y():.2f}) -> ({local_x:.2f}, {local_y:.2f})"
                            )

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
                                print(f"DEBUG: 实时保存碰撞形状: {points_data}")

                            return True
                    except (ValueError, IndexError) as e:
                        print(f"DEBUG: 解析锚点错误: {e}")
        except Exception as e:
            print(f"DEBUG: 鼠标移动事件错误: {e}")
        return False

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
                        print(
                            f"DEBUG: 正在保存碰撞形状到资源索引: {resource_index}, 图块索引: {tile_index}"
                        )
                        success = self.map_model.set_tile_collision_shape(
                            resource_index, tile_index, shape_data
                        )
                        if success:
                            print(f"✅ 多边形碰撞形状已保存: {shape_data}")
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
                                    print(
                                        f"DEBUG: 已更新资源池缓存，资源索引: {resource_index}, 图块索引: {tile_index}"
                                    )
                            # 自动保存地图数据，确保实时编辑的碰撞形状能够立即保存到文件
                            if self.parent_manager and hasattr(
                                self.parent_manager, "current_map_path"
                            ) and self.parent_manager.current_map_path:
                                print(f"DEBUG: 自动保存地图数据到: {self.parent_manager.current_map_path}")
                                save_result = self.map_model.save(self.parent_manager.current_map_path)
                                if save_result:
                                    print(f"✅ 地图自动保存成功")
                                else:
                                    print(f"❌ 地图自动保存失败")
                    else:
                        print("DEBUG: 保存失败，缺少必要条件")

                    self.dragging_anchor = None
                    if self.col_editor_view:
                        self.col_editor_view.setCursor(QCursor(Qt.ArrowCursor))
                    return True
        except Exception as e:
            print(f"DEBUG: 鼠标释放事件错误: {e}")
            import traceback

            traceback.print_exc()
        return False
