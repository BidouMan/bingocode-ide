import os
from PySide6.QtCore import QObject, Signal, Qt, QRectF
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsView,
    QGraphicsRectItem,
    QGraphicsLineItem,
    QDialog,
)
from PySide6.QtGui import QPixmap, QPen, QBrush, QColor
from models.map_model import MapDataModel
from modules.canvas_manager import SmartCanvas
from modules.map_resource_import_dialog import MapResourceImportDialog


class TileItem(QGraphicsRectItem):
    """图块项图形类，支持点击事件"""

    def __init__(self, rect, resource_info, tile_index, manager):
        super().__init__(rect)
        self.resource_info = resource_info
        self.tile_index = tile_index
        self.manager = manager
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsRectItem.ItemIsSelectable)
        self.is_deleted = False

    def mousePressEvent(self, event):
        """处理鼠标点击事件"""
        try:
            # 检查对象是否已删除
            if getattr(self, "is_deleted", True):
                return
            # 检查事件是否有效
            if not event:
                return
            if event.button() == Qt.LeftButton:
                # 检查manager是否有效
                if (
                    hasattr(self, "manager")
                    and self.manager
                    and not getattr(self.manager, "is_deleted", False)
                ):
                    # 检查resource_info是否有效
                    if hasattr(self, "resource_info") and self.resource_info:
                        self.manager.select_tile(self.resource_info, self.tile_index)
            # 调用父类方法，但也要检查父类是否存在
            try:
                super().mousePressEvent(event)
            except Exception:
                pass
        except Exception as e:
            print(f"图块点击事件错误: {e}")

    def hoverEnterEvent(self, event):
        """处理鼠标悬停进入事件"""
        try:
            if getattr(self, "is_deleted", True):
                return
            super().hoverEnterEvent(event)
        except Exception as e:
            print(f"图块悬停进入事件错误: {e}")

    def hoverLeaveEvent(self, event):
        """处理鼠标悬停离开事件"""
        try:
            if getattr(self, "is_deleted", True):
                return
            super().hoverLeaveEvent(event)
        except Exception as e:
            print(f"图块悬停离开事件错误: {e}")

    def deleteLater(self):
        """安全删除对象"""
        self.is_deleted = True
        try:
            super().deleteLater()
        except Exception as e:
            print(f"图块deleteLater错误: {e}")

    def delete(self):
        """标记为已删除"""
        self.is_deleted = True


class ResourceItem(QGraphicsRectItem):
    """资源项图形类，支持点击事件"""

    def __init__(self, rect, resource_info, index, manager):
        super().__init__(rect)
        self.resource_info = resource_info
        self.index = index
        self.manager = manager
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsRectItem.ItemIsSelectable)
        self.is_deleted = False

    def mousePressEvent(self, event):
        """处理鼠标点击事件"""
        try:
            # 检查对象是否已删除
            if getattr(self, "is_deleted", True):
                return
            # 检查事件是否有效
            if not event:
                return
            if event.button() == Qt.LeftButton:
                # 检查manager是否有效
                if (
                    hasattr(self, "manager")
                    and self.manager
                    and not getattr(self.manager, "is_deleted", False)
                ):
                    self.manager.select_resource(self.index)
            # 调用父类方法，但也要检查父类是否存在
            try:
                super().mousePressEvent(event)
            except Exception:
                pass
        except Exception as e:
            print(f"资源点击事件错误: {e}")

    def hoverEnterEvent(self, event):
        """处理鼠标悬停进入事件"""
        try:
            if getattr(self, "is_deleted", True):
                return
            super().hoverEnterEvent(event)
        except Exception as e:
            print(f"资源悬停进入事件错误: {e}")

    def hoverLeaveEvent(self, event):
        """处理鼠标悬停离开事件"""
        try:
            if getattr(self, "is_deleted", True):
                return
            super().hoverLeaveEvent(event)
        except Exception as e:
            print(f"资源悬停离开事件错误: {e}")

    def delete(self):
        """标记为已删除"""
        self.is_deleted = True


class MapEditorManager(QObject):
    """地图编辑器管理器，负责地图编辑的核心逻辑"""

    # 信号定义
    map_loaded = Signal(str)  # 地图加载完成信号
    map_saved = Signal(str)  # 地图保存完成信号
    error_occurred = Signal(str)  # 错误发生信号

    def __init__(self, canvas_widget=None, parent=None):
        super().__init__(parent)
        self.canvas_widget = canvas_widget
        self.map_model = None
        self.canvas_manager = None
        self.current_tool = "brush"  # 当前工具：brush, eraser, select
        self.current_tile_id = 1  # 当前选中的瓦片ID
        self.current_layer = 0  # 当前选中的图层

        # 初始化地图模型
        self._initialize_map_model()

        # 初始化画布管理器
        if self.canvas_widget:
            self._initialize_canvas_manager()

        # 设置按键绑定
        self._setup_key_bindings()

        # 资源列表相关
        self.res_list_view = None
        self.uploaded_resources = []  # 存储上传的资源
        self.selected_resource_index = -1  # 当前选中的资源索引
        self.selected_tile_index = -1  # 当前选中的图块索引
        self.resource_items = []  # 存储资源项的图形项
        self.tile_items = []  # 存储图块项的图形项

        # 预览相关
        self.preview_item = None  # 预览图块项
        self.preview_tile_pos = None  # 预览图块位置

        # 鼠标状态
        self.is_drawing = False
        self.last_tile_pos = None

    def _initialize_map_model(self):
        """初始化地图数据模型"""
        self.map_model = MapDataModel()
        # 连接数据变化信号
        self.map_model.data_changed.connect(self._on_map_data_changed)

    def _initialize_canvas_manager(self):
        """初始化画布管理器"""
        if not self.canvas_widget:
            return

        # 使用现有的QGraphicsView作为画布管理器
        self.canvas_manager = self.canvas_widget

        # 导入必要的类
        from PySide6.QtWidgets import QGraphicsScene, QGraphicsRectItem
        from PySide6.QtGui import QBrush, QColor, QPen

        # 创建场景
        scene = QGraphicsScene()

        # 设置场景到视图
        self.canvas_manager.setScene(scene)

        # 设置视图属性
        self.canvas_manager.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.canvas_manager.setResizeAnchor(QGraphicsView.AnchorViewCenter)
        self.canvas_manager.setTransformationAnchor(QGraphicsView.AnchorViewCenter)
        self.canvas_manager.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.canvas_manager.setMouseTracking(True)  # 启用鼠标追踪

        # 获取地图数据
        width, height = self.map_model.get_map_size()
        tile_size = self.map_model.get_tile_size()

        # 设置场景大小
        scene_width = width * tile_size
        scene_height = height * tile_size
        scene.setSceneRect(0, 0, scene_width, scene_height)

        # 创建灰色背景矩形
        background = QGraphicsRectItem(0, 0, scene_width, scene_height)
        background.setBrush(QBrush(QColor(200, 200, 200)))  # 灰色背景
        background.setPen(Qt.NoPen)
        scene.addItem(background)

        # 绘制瓦片网格
        pen = QPen(QColor(100, 100, 100, 50), 1)
        for x in range(width + 1):
            scene.addLine(x * tile_size, 0, x * tile_size, scene_height, pen)
        for y in range(height + 1):
            scene.addLine(0, y * tile_size, scene_width, y * tile_size, pen)

        # 绑定鼠标事件
        self._bind_mouse_events()

        # 刷新视图
        self.canvas_manager.viewport().update()

    def _bind_mouse_events(self):
        """绑定鼠标事件"""
        # 保存原始的鼠标事件处理函数
        self.original_mousePressEvent = self.canvas_manager.mousePressEvent
        self.original_mouseMoveEvent = self.canvas_manager.mouseMoveEvent
        self.original_mouseReleaseEvent = self.canvas_manager.mouseReleaseEvent

        # 绑定自定义的鼠标事件处理函数
        self.canvas_manager.mousePressEvent = self._handle_mouse_press
        self.canvas_manager.mouseMoveEvent = self._handle_mouse_move
        self.canvas_manager.mouseReleaseEvent = self._handle_mouse_release

        print("鼠标事件绑定完成")

    def _clear_resource_items(self):
        """清理资源项和图块项"""
        try:
            # 从场景中移除所有图块项
            if self.res_list_view:
                scene = self.res_list_view.scene()
                if scene:
                    # 从场景中移除所有图块项
                    for tile_item in self.tile_items:
                        try:
                            scene.removeItem(tile_item)
                            tile_item.is_deleted = True
                        except Exception as e:
                            print(f"从场景移除图块项错误: {e}")

                    # 从场景中移除所有资源项
                    for resource_item in self.resource_items:
                        try:
                            scene.removeItem(resource_item)
                            resource_item.is_deleted = True
                        except Exception as e:
                            print(f"从场景移除资源项错误: {e}")

        except Exception as e:
            print(f"清理资源项和图块项错误: {e}")

        # 清空列表
        self.resource_items.clear()
        self.tile_items.clear()

    def _setup_key_bindings(self):
        """设置按键绑定"""
        # 暂时注释掉快捷键设置，避免程序启动问题
        # 快捷键功能将在后续实现
        pass

    def set_tool(self, tool_name):
        """设置当前编辑工具"""
        self.current_tool = tool_name
        print(f"当前工具: {tool_name}")

    def set_current_tile(self, tile_id):
        """设置当前选中的瓦片ID"""
        self.current_tile_id = tile_id
        print(f"当前瓦片ID: {tile_id}")

    def set_current_layer(self, layer_index):
        """设置当前选中的图层"""
        if 0 <= layer_index < self.map_model.get_layer_count():
            self.current_layer = layer_index
            print(f"当前图层: {layer_index}")

    def new_map(self):
        """创建新地图"""
        self._initialize_map_model()
        self._update_canvas()

    def save_map(self):
        """保存地图"""
        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getSaveFileName(
            None, "保存地图", "", "JSON Files (*.json)"
        )

        if file_path:
            if self.map_model.save(file_path):
                self.map_saved.emit(file_path)
                print(f"地图已保存到: {file_path}")
            else:
                self.error_occurred.emit("保存地图失败")

    def load_map(self):
        """加载地图"""
        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            None, "加载地图", "", "JSON Files (*.json)"
        )

        if file_path:
            if self.map_model.load(file_path):
                self.map_loaded.emit(file_path)
                self._update_canvas()
                print(f"地图已从: {file_path} 加载")
            else:
                self.error_occurred.emit("加载地图失败")

    def undo(self):
        """撤销操作"""
        print("撤销操作")
        # 这里将在后续实现撤销/重做功能

    def redo(self):
        """重做操作"""
        print("重做操作")
        # 这里将在后续实现撤销/重做功能

    def _on_map_data_changed(self):
        """地图数据变化时的处理"""
        self._update_canvas()

    def _update_canvas(self):
        """更新画布显示"""
        print("=== 更新画布显示 ===")
        if self.canvas_manager and self.map_model:
            print("调用渲染地图")
            self._render_map()
        else:
            print(f"画布管理器: {self.canvas_manager}")
            print(f"地图模型: {self.map_model}")

    def _render_map(self):
        """渲染地图"""
        try:
            if not self.canvas_manager:
                return

            scene = self.canvas_manager.scene()
            if not scene:
                return

            # 获取地图数据
            width, height = self.map_model.get_map_size()
            tile_size = self.map_model.get_tile_size()

            # 移除所有图块项（保留背景和网格）
            items = scene.items()
            for item in items:
                # 只移除QPixmapItem类型的图块
                from PySide6.QtWidgets import QGraphicsPixmapItem

                if isinstance(item, QGraphicsPixmapItem) and item != self.preview_item:
                    scene.removeItem(item)

            # 绘制所有已绘制的瓦片
            layer = self.map_model.get_layer(self.current_layer)
            if layer and layer["visible"]:
                tile_data = layer["tiles"]
                if tile_data is not None:
                    # 导入numpy
                    import numpy as np

                    # 获取所有非零的瓦片位置
                    y_indices, x_indices = np.where(tile_data > 0)

                    for y, x in zip(y_indices, x_indices):
                        stored_tile_id = tile_data[y, x]

                        # 遍历所有资源，查找匹配的资源
                        for resource_index, resource in enumerate(
                            self.uploaded_resources
                        ):
                            resource_type = resource.get("resource_type", "image")

                            if resource_type == "tileset":
                                # 图块集合模式，渲染所有图块，而不仅仅是当前选中的图块
                                # 加载资源图片
                                from PySide6.QtGui import QPixmap

                                pixmap = QPixmap(resource["path"])
                                if not pixmap.isNull():
                                    tile_size_resource = resource["tile_size"]

                                    # 计算图块在原图中的位置
                                    tiles_per_row = pixmap.width() // tile_size_resource
                                    # 图块集合模式，图块ID格式：resource_index * 1000 + tile_index + 1
                                    if stored_tile_id // 1000 == resource_index:
                                        # 提取图块索引
                                        tile_index = (stored_tile_id % 1000) - 1
                                        if tile_index >= 0:
                                            tile_row = tile_index // tiles_per_row
                                            tile_col = tile_index % tiles_per_row
                                        else:
                                            continue
                                    else:
                                        continue

                                    # 裁剪图块
                                    from PySide6.QtCore import QRectF

                                    tile_rect = QRectF(
                                        tile_col * tile_size_resource,
                                        tile_row * tile_size_resource,
                                        tile_size_resource,
                                        tile_size_resource,
                                    )

                                    # 创建图块的QPixmap
                                    tile_pixmap = pixmap.copy(tile_rect.toRect())

                                    # 添加到场景（保持原始尺寸）
                                    from PySide6.QtWidgets import (
                                        QGraphicsPixmapItem,
                                    )

                                    pixmap_item = QGraphicsPixmapItem(tile_pixmap)
                                    pixmap_item.setPos(x * tile_size, y * tile_size)
                                    scene.addItem(pixmap_item)
                            else:
                                # 单张图片模式，图块ID格式：resource_index + 1
                                if stored_tile_id == resource_index + 1:
                                    # 加载资源图片
                                    from PySide6.QtGui import QPixmap

                                    pixmap = QPixmap(resource["path"])
                                    if not pixmap.isNull():
                                        # 添加到场景（保持原始尺寸）
                                        from PySide6.QtWidgets import (
                                            QGraphicsPixmapItem,
                                        )

                                        pixmap_item = QGraphicsPixmapItem(pixmap)
                                        pixmap_item.setPos(x * tile_size, y * tile_size)
                                        scene.addItem(pixmap_item)

            # 刷新视图
            self.canvas_manager.viewport().update()

        except Exception as e:
            print(f"渲染地图错误: {e}")

    def _draw_tile_grid(self, scene, width, height, tile_size):
        """绘制瓦片网格"""
        from PySide6.QtGui import QPen

        # 创建网格线
        pen = QPen(QColor(100, 100, 100, 50), 1)

        # 绘制垂直线
        for x in range(width + 1):
            scene.addLine(x * tile_size, 0, x * tile_size, height * tile_size, pen)

        # 绘制水平线
        for y in range(height + 1):
            scene.addLine(0, y * tile_size, width * tile_size, y * tile_size, pen)

    def _draw_tiles(self, scene):
        """绘制瓦片内容"""
        try:
            # 获取当前图层
            layer = self.map_model.get_layer(self.current_layer)
            if not layer or not layer["visible"]:
                return

            tile_data = layer["tiles"]
            if tile_data is None:
                return

            tile_size = self.map_model.get_tile_size()

            # 获取选中的资源和图块
            if self.selected_resource_index >= 0 and self.selected_tile_index >= 0:
                resource = self.uploaded_resources[self.selected_resource_index]

                # 加载资源图片
                pixmap = QPixmap(resource["path"])
                if pixmap.isNull():
                    return

                # 如果是图块集合，获取图块尺寸
                if resource["resource_type"] == "tileset":
                    tile_size_resource = resource["tile_size"]

                    # 计算图块在原图中的位置
                    tiles_per_row = pixmap.width() // tile_size_resource
                    tile_row = self.selected_tile_index // tiles_per_row
                    tile_col = self.selected_tile_index % tiles_per_row

                    # 裁剪图块
                    tile_rect = QRectF(
                        tile_col * tile_size_resource,
                        tile_row * tile_size_resource,
                        tile_size_resource,
                        tile_size_resource,
                    )

                    # 创建图块的QPixmap
                    tile_pixmap = pixmap.copy(tile_rect.toRect())

                    # 缩放图块到目标尺寸
                    scaled_tile = tile_pixmap.scaled(
                        tile_size,
                        tile_size,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )

                    # 绘制所有标记为当前图块ID的位置
                    tile_id = self.selected_tile_index + 1
                    y_indices, x_indices = np.where(tile_data == tile_id)

                    for y, x in zip(y_indices, x_indices):
                        pixmap_item = QGraphicsPixmapItem(scaled_tile)
                        pixmap_item.setPos(x * tile_size, y * tile_size)
                        scene.addItem(pixmap_item)

        except Exception as e:
            print(f"绘制瓦片内容错误: {e}")

    def _screen_to_tile(self, screen_pos):
        """将屏幕坐标转换为瓦片坐标"""
        if not self.canvas_manager or not self.map_model:
            return None

        # 获取视图变换
        transform = self.canvas_manager.transform()

        # 转换为场景坐标
        scene_pos = self.canvas_manager.mapToScene(screen_pos)

        # 获取瓦片大小
        tile_size = self.map_model.get_tile_size()

        # 计算瓦片坐标
        tile_x = int(scene_pos.x() / tile_size)
        tile_y = int(scene_pos.y() / tile_size)

        # 检查边界
        width, height = self.map_model.get_map_size()
        if 0 <= tile_x < width and 0 <= tile_y < height:
            return (tile_x, tile_y)

        return None

    def _handle_mouse_press(self, event):
        """处理鼠标按下事件"""
        try:
            if event.button() == Qt.LeftButton:
                # 获取瓦片坐标
                tile_pos = self._screen_to_tile(event.pos())
                if tile_pos:
                    self.is_drawing = True
                    self.last_tile_pos = tile_pos
                    self._draw_tile(tile_pos)
                    # 移除预览
                    self._remove_preview()
        except Exception as e:
            print(f"鼠标按下事件错误: {e}")

    def _handle_mouse_move(self, event):
        """处理鼠标移动事件"""
        try:
            print(f"DEBUG: 鼠标移动事件，位置: {event.pos()}")
            if self.is_drawing and event.buttons() & Qt.LeftButton:
                tile_pos = self._screen_to_tile(event.pos())
                if tile_pos and tile_pos != self.last_tile_pos:
                    self._draw_tile(tile_pos)
                    self.last_tile_pos = tile_pos
            else:
                # 显示预览图块
                self._update_preview(event.pos())

        except Exception as e:
            print(f"鼠标移动事件错误: {e}")

    def _handle_mouse_release(self, event):
        """处理鼠标释放事件"""
        try:
            if event.button() == Qt.LeftButton:
                self.is_drawing = False
                self.last_tile_pos = None
            else:
                # 调用父类的鼠标释放事件处理
                SmartCanvas.mouseReleaseEvent(self.canvas_manager, event)
        except Exception as e:
            print(f"鼠标释放事件错误: {e}")

    def _draw_tile(self, tile_pos):
        """绘制瓦片"""
        try:
            if self.selected_resource_index >= 0:
                # 获取选中的资源
                resource = self.uploaded_resources[self.selected_resource_index]
                resource_type = resource.get("resource_type", "image")

                # 根据资源类型确定图块ID
                if resource_type == "tileset":
                    # 图块集合模式，使用资源索引和图块索引的组合作为图块ID
                    # 格式：resource_index * 1000 + tile_index + 1
                    if self.selected_tile_index >= 0:
                        tile_id = (
                            self.selected_resource_index * 1000
                            + self.selected_tile_index
                            + 1
                        )
                    else:
                        return
                else:
                    # 单张图片模式，使用资源索引作为图块ID
                    tile_id = self.selected_resource_index + 1

                x, y = tile_pos
                # 更新地图数据
                self.map_model.set_tile(self.current_layer, x, y, tile_id)
        except Exception as e:
            print(f"绘制瓦片错误: {e}")

    def _update_preview(self, screen_pos):
        """更新预览图块"""
        try:
            if not self.canvas_manager or not self.map_model:
                print("DEBUG: 画布管理器或地图模型未初始化")
                return

            # 获取瓦片坐标
            tile_pos = self._screen_to_tile(screen_pos)
            if not tile_pos:
                print("DEBUG: 鼠标不在画布范围内")
                # 鼠标不在画布范围内，移除预览
                self._remove_preview()
                return

            # 如果位置没有变化，不需要更新
            if tile_pos == self.preview_tile_pos:
                return

            # 更新预览位置
            self.preview_tile_pos = tile_pos

            # 如果没有选中资源，移除预览
            if self.selected_resource_index < 0:
                print(f"DEBUG: 未选中资源，资源索引: {self.selected_resource_index}")
                self._remove_preview()
                return

            # 获取选中的资源
            resource = self.uploaded_resources[self.selected_resource_index]
            resource_type = resource.get("resource_type", "image")

            # 检查是否需要图块索引
            if resource_type == "tileset" and self.selected_tile_index < 0:
                print(
                    f"DEBUG: 图块集合需要选中图块，图块索引: {self.selected_tile_index}"
                )
                self._remove_preview()
                return

            print(
                f"DEBUG: 更新预览，位置: {tile_pos}, 资源索引: {self.selected_resource_index}, 图块索引: {self.selected_tile_index}"
            )

            # 加载资源图片
            from PySide6.QtGui import QPixmap

            pixmap = QPixmap(resource["path"])
            if pixmap.isNull():
                print("DEBUG: 图片加载失败")
                return

            # 获取目标瓦片大小
            tile_size = self.map_model.get_tile_size()
            print(f"DEBUG: 目标瓦片大小: {tile_size}")

            # 根据资源类型处理图片
            if resource_type == "tileset":
                # 图块集合模式，裁剪特定图块
                tile_size_resource = resource["tile_size"]
                print(f"DEBUG: 图块大小: {tile_size_resource}")

                # 计算图块在原图中的位置
                tiles_per_row = pixmap.width() // tile_size_resource
                tile_row = self.selected_tile_index // tiles_per_row
                tile_col = self.selected_tile_index % tiles_per_row
                print(f"DEBUG: 图块位置: 行={tile_row}, 列={tile_col}")

                # 裁剪图块
                from PySide6.QtCore import QRectF

                tile_rect = QRectF(
                    tile_col * tile_size_resource,
                    tile_row * tile_size_resource,
                    tile_size_resource,
                    tile_size_resource,
                )

                # 创建图块的QPixmap
                scaled_tile = pixmap.copy(tile_rect.toRect())
            else:
                # 单张图片模式，直接使用整张图片（不缩放，保持原始尺寸）
                scaled_tile = pixmap

            # 移除旧的预览
            self._remove_preview()

            # 创建新的预览项
            scene = self.canvas_manager.scene()
            if scene:
                from PySide6.QtWidgets import QGraphicsPixmapItem

                self.preview_item = QGraphicsPixmapItem(scaled_tile)
                x, y = tile_pos
                self.preview_item.setPos(x * tile_size, y * tile_size)
                self.preview_item.setOpacity(0.5)  # 半透明效果
                scene.addItem(self.preview_item)
                print(
                    f"DEBUG: 预览项添加到场景，位置: ({x * tile_size}, {y * tile_size})"
                )

        except Exception as e:
            print(f"更新预览错误: {e}")

    def _remove_preview(self):
        """移除预览图块"""
        try:
            if self.preview_item:
                scene = self.canvas_manager.scene()
                if scene:
                    scene.removeItem(self.preview_item)
                self.preview_item = None
            self.preview_tile_pos = None
        except Exception as e:
            print(f"移除预览错误: {e}")

    def get_map_model(self):
        """获取地图数据模型"""
        return self.map_model

    def get_canvas_manager(self):
        """获取画布管理器"""
        return self.canvas_manager

    def get_current_tool(self):
        """获取当前工具"""
        return self.current_tool

    def get_current_tile_id(self):
        """获取当前瓦片ID"""
        return self.current_tile_id

    def get_current_layer(self):
        """获取当前图层"""
        return self.current_layer

    def set_canvas_widget(self, canvas_widget):
        """设置画布控件"""
        print(f"设置画布控件: {canvas_widget}")
        self.canvas_widget = canvas_widget
        self._initialize_canvas_manager()
        # 初始化后立即渲染地图
        self._update_canvas()

    def update_map_size(self, width, height):
        """更新地图尺寸"""
        self.map_model.set_map_size(width, height)
        self._update_canvas()

    def add_layer(self, name="new_layer"):
        """添加新图层"""
        layer_index = self.map_model.add_layer(name)
        self.set_current_layer(layer_index)
        return layer_index

    def remove_layer(self, layer_index):
        """删除图层"""
        if self.map_model.remove_layer(layer_index):
            # 如果删除的是当前图层，切换到其他图层
            if self.current_layer >= layer_index and self.current_layer > 0:
                self.current_layer -= 1
            return True
        return False

    def add_tile_set(self, name, image_path, tile_width, tile_height):
        """添加瓦片集"""
        return self.map_model.add_tile_set(name, image_path, tile_width, tile_height)

    def set_res_list_view(self, res_list_view):
        """设置资源列表视图"""
        self.res_list_view = res_list_view
        # 初始化资源列表显示
        self._update_res_list_display()

    def handle_resource_upload(self):
        """处理资源上传按钮点击事件"""
        # 检查资源列表视图是否已初始化
        if not self.res_list_view:
            print("DEBUG: res_list_view 未设置，无法上传资源")
            return

        # 弹出导入对话框
        dialog = MapResourceImportDialog()

        if dialog.exec() == QDialog.Accepted:
            # 获取导入数据
            import_data = dialog.get_import_data()
            files = import_data["files"]
            resource_type = import_data["resource_type"]
            tile_size = import_data["tile_size"]

            print(f"DEBUG: 导入数据: 文件数量={len(files)}, 资源类型={resource_type}")

            # 保存上传的资源
            for file_path in files:
                if os.path.exists(file_path):
                    resource_info = {
                        "name": os.path.basename(file_path),
                        "path": file_path,
                        "resource_type": resource_type,
                    }

                    # 如果是图块集合，添加图块尺寸信息
                    if resource_type == "tileset":
                        resource_info["tile_size"] = tile_size
                        resource_info["tiles"] = []  # 存储切割后的图块信息

                    self.uploaded_resources.append(resource_info)
                    print(f"DEBUG: 添加资源: {resource_info['name']}")

            # 更新资源列表显示
            print(f"DEBUG: 上传完成，资源总数: {len(self.uploaded_resources)}")
            self._update_res_list_display()

    def select_resource(self, index):
        """选择资源"""
        try:
            if 0 <= index < len(self.uploaded_resources):
                self.selected_resource_index = index
                self.selected_tile_index = -1  # 重置图块选择
                print(f"DEBUG: 选中资源: {self.uploaded_resources[index]['name']}")
                print(
                    f"DEBUG: 资源索引: {self.selected_resource_index}, 图块索引: {self.selected_tile_index}"
                )
                self._update_res_list_display()
        except Exception as e:
            print(f"选择资源错误: {e}")

    def select_tile(self, resource_info, tile_index):
        """选择图块"""
        try:
            # 查找资源索引
            resource_index = -1
            for i, res in enumerate(self.uploaded_resources):
                if res == resource_info:
                    resource_index = i
                    break

            if resource_index != -1:
                self.selected_resource_index = resource_index
                self.selected_tile_index = tile_index
                print(
                    f"DEBUG: 选中图块: 资源={resource_info['name']}, 图块索引={tile_index}"
                )
                print(
                    f"DEBUG: 资源索引: {self.selected_resource_index}, 图块索引: {self.selected_tile_index}"
                )
                self._update_res_list_display()
        except Exception as e:
            print(f"选择图块错误: {e}")

    def _update_res_list_display(self):
        """更新资源列表显示"""
        if not self.res_list_view:
            print("DEBUG: res_list_view 未设置")
            return

        # 清理旧的资源项和图块项
        self._clear_resource_items()

        # 创建场景
        scene = QGraphicsScene()

        # 添加资源到场景
        y_pos = 0  # 移除顶部边距

        print(f"DEBUG: 更新资源列表，资源数量: {len(self.uploaded_resources)}")

        for i, resource in enumerate(self.uploaded_resources):
            try:
                print(
                    f"DEBUG: 处理资源 {i}: {resource['name']}, 类型: {resource.get('resource_type', 'unknown')}"
                )
                print(f"DEBUG: 资源路径: {resource['path']}")
                print(f"DEBUG: 文件是否存在: {os.path.exists(resource['path'])}")

                # 加载原始图片
                original_pixmap = QPixmap(resource["path"])
                print(f"DEBUG: 图片加载结果: {not original_pixmap.isNull()}")
                if original_pixmap.isNull():
                    print(f"DEBUG: 图片加载失败: {resource['path']}")
                    continue

                # 获取资源类型和图块尺寸
                resource_type = resource.get("resource_type", "image")
                tile_size = resource.get("tile_size", 32)
                print(f"DEBUG: 资源类型: {resource_type}, 图块尺寸: {tile_size}")

                # 计算图块数量（仅图块集合模式）
                image_width = original_pixmap.width()
                image_height = original_pixmap.height()
                tiles_per_row = 0
                tiles_per_col = 0
                print(f"DEBUG: 图片尺寸: {image_width}x{image_height}")

                if resource_type == "tileset":
                    tiles_per_row = image_width // tile_size
                    tiles_per_col = image_height // tile_size
                    print(f"DEBUG: 图块数量: {tiles_per_row}x{tiles_per_col}")

                # 计算显示区域大小 - 撑满256宽度
                display_width = 256  # 整个视图宽度
                margin = 0  # 不添加额外边距

                # 计算缩放比例 - 小于256宽度的图片保持原始尺寸
                if image_width < display_width:
                    scale = 1.0  # 保持原始尺寸
                else:
                    scale = display_width / image_width  # 大于等于256宽度的图片缩放
                print(f"DEBUG: 缩放比例: {scale}")

                # 创建缩放后的图片
                scaled_width = int(image_width * scale)
                scaled_height = int(image_height * scale)
                print(f"DEBUG: 缩放后尺寸: {scaled_width}x{scaled_height}")

                scaled_pixmap = original_pixmap.scaled(
                    scaled_width,
                    scaled_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )

                # 计算显示位置
                pixmap_x = 0
                pixmap_y = y_pos
                print(f"DEBUG: 显示位置: ({pixmap_x}, {pixmap_y})")

                # 添加缩放后的图片
                pixmap_item = QGraphicsPixmapItem(scaled_pixmap)
                pixmap_item.setPos(pixmap_x, pixmap_y)
                scene.addItem(pixmap_item)
                print(f"DEBUG: 添加图片到场景")

                # 绘制图块网格或创建单张图片的可点击区域
                if resource_type == "tileset":
                    for row in range(tiles_per_col):
                        for col in range(tiles_per_row):
                            tile_index = row * tiles_per_row + col

                            # 计算图块在原始图片中的位置
                            tile_x = col * tile_size
                            tile_y = row * tile_size

                            # 计算图块在显示图片中的位置
                            display_tile_x = pixmap_x + tile_x * scale
                            display_tile_y = pixmap_y + tile_y * scale
                            display_tile_width = tile_size * scale
                            display_tile_height = tile_size * scale

                            # 检查是否是选中的图块
                            is_tile_selected = (
                                i == self.selected_resource_index
                                and self.selected_tile_index == tile_index
                            )

                            # 创建图块边框（调整坐标避免浮点精度问题）
                            tile_rect = QGraphicsRectItem(
                                int(display_tile_x),
                                int(display_tile_y),
                                int(display_tile_width),
                                int(display_tile_height),
                            )

                            if is_tile_selected:
                                tile_rect.setBrush(QBrush(QColor(100, 149, 237, 50)))
                                tile_rect.setPen(Qt.NoPen)
                            else:
                                tile_rect.setPen(QPen(QColor(200, 200, 200), 1))
                                tile_rect.setBrush(Qt.NoBrush)

                            scene.addItem(tile_rect)

                            # 创建图块项（用于点击事件）
                            tile_item = TileItem(
                                tile_rect.rect(), resource, tile_index, self
                            )
                            scene.addItem(tile_item)
                else:
                    # 单张图片模式，创建可点击的资源项
                    # 直接创建 ResourceItem，不需要额外的 QGraphicsRectItem
                    resource_item = ResourceItem(
                        QRectF(pixmap_x, pixmap_y, scaled_width, scaled_height),
                        resource,
                        i,
                        self,
                    )
                    scene.addItem(resource_item)
                    self.resource_items.append(resource_item)
                    print(f"DEBUG: 添加资源项到场景")

                # 更新位置 - 根据实际图片高度调整间距
                y_pos += scaled_height
                print(f"DEBUG: 更新位置到: {y_pos}")

            except Exception as e:
                print(f"创建资源缩略图失败: {e}")

        # 设置场景大小
        scene_height = max(500, y_pos)
        scene.setSceneRect(0, 0, 256, scene_height)
        print(f"DEBUG: 场景大小: 256x{scene_height}")

        # 设置场景到视图
        self.res_list_view.setScene(scene)
        self.res_list_view.show()
        self.res_list_view.update()  # 添加 update() 方法调用，确保视图刷新
        # 自动滚动到顶部，确保用户可以看到导入的图片
        self.res_list_view.verticalScrollBar().setValue(0)
        print(f"DEBUG: 场景设置到视图，已滚动到顶部")
