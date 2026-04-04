import os
from PySide6.QtCore import QObject, Signal, Qt, QRectF, QPoint
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsView,
    QGraphicsRectItem,
    QGraphicsLineItem,
    QDialog,
)
from PySide6.QtGui import (
    QPixmap,
    QPen,
    QBrush,
    QColor,
    QMouseEvent,
    QWheelEvent,
    QPainter,
    QCursor,
)
from models.map_model import MapDataModel
from modules.map_resource_import_dialog import MapResourceImportDialog
from modules.map_canvas_manager import MapCanvas


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
        # 设置选中状态的样式
        self.setBrush(Qt.NoBrush)
        self.setPen(QPen(QColor(200, 200, 200), 1))

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

        # 网格线相关
        self.grid_lines = []  # 存储网格线对象，用于控制显示/隐藏

        # 鼠标状态
        self.is_drawing = False
        self.last_tile_pos = None

        # 移动工具相关
        self.selected_item = None
        self.drag_start_pos = None
        self.original_tile_pos = None  # 原始瓦片位置

    def _initialize_map_model(self):
        """初始化地图数据模型"""
        self.map_model = MapDataModel()
        # 连接数据变化信号
        self.map_model.data_changed.connect(self._on_map_data_changed)

    def _initialize_canvas_manager(self):
        """初始化画布管理器 - 完全按照sprite_editor的模式"""
        print("DEBUG: 开始初始化画布管理器")
        if not self.canvas_widget:
            print("DEBUG: canvas_widget 为 None")
            return

        # 1. 替换画布控件 (只做一次，不要覆盖)
        parent_widget = self.canvas_widget.parentWidget()
        parent_layout = parent_widget.layout()

        self.canvas_manager = MapCanvas(parent_widget)
        parent_layout.replaceWidget(self.canvas_widget, self.canvas_manager)
        self.canvas_widget.hide()
        self.canvas_widget.deleteLater()

        # 2. 绑定场景，设置无限画布范围
        # 坐标原点：左上角(0,0)，但允许显示负坐标，实现真正的无限画布效果
        self.canvas_scene = QGraphicsScene(
            -10000, -10000, 20000, 20000
        )  # 包含正负坐标的大场景，实现无限画布
        self.canvas_manager.setScene(self.canvas_scene)

        # 3. 获取地图数据
        width, height = self.map_model.get_map_size()
        tile_size = self.map_model.get_tile_size()
        print(f"DEBUG: 地图尺寸: {width}x{height}, 图块大小: {tile_size}")

        # 4. 设置场景大小
        scene_width = width * tile_size
        scene_height = height * tile_size

        # 5. 创建游戏窗口显示范围（640x480）
        game_window_rect = QGraphicsRectItem(0, 0, 640, 480)
        game_window_rect.setPen(
            QPen(QColor(180, 180, 255), 0, Qt.PenStyle.DashLine)
        )  # 淡紫色，最细的虚线
        game_window_rect.setBrush(Qt.NoBrush)
        self.canvas_scene.addItem(game_window_rect)
        print("DEBUG: 添加游戏窗口显示范围(640x480)")

        # 6. 创建一个容器项，用于包含所有地图元素
        from PySide6.QtWidgets import QGraphicsItemGroup

        map_container = QGraphicsItemGroup()
        self.canvas_scene.addItem(map_container)

        # 7. 绘制可见的瓦片网格，以游戏引擎坐标系统（左上角(0,0)）为原点
        pen = QPen(
            QColor(196, 93, 41, 64), 0
        )  # rgb(196, 93, 41)网格线，最细，透明度降低一半
        self.grid_lines.clear()  # 清空之前的网格线
        for x in range(width + 1):
            line_x = x * tile_size
            line = self.canvas_scene.addLine(line_x, 0, line_x, scene_height, pen)
            map_container.addToGroup(line)
            self.grid_lines.append(line)
        for y in range(height + 1):
            line_y = y * tile_size
            line = self.canvas_scene.addLine(0, line_y, scene_width, line_y, pen)
            map_container.addToGroup(line)
            self.grid_lines.append(line)
        print("DEBUG: 添加rgb(196, 93, 41)网格线")

        # 9. 添加x/y轴线（像Godot一样）
        # x轴线（红色，水平方向）
        x_axis_pen = QPen(QColor(200, 50, 50), 0)  # 降低饱和度的红色，最细
        x_axis = self.canvas_scene.addLine(-10000, 0, 10000, 0, x_axis_pen)
        map_container.addToGroup(x_axis)

        # y轴线（绿色，垂直方向）
        y_axis_pen = QPen(QColor(50, 200, 50), 0)  # 降低饱和度的绿色，最细
        y_axis = self.canvas_scene.addLine(0, -10000, 0, 10000, y_axis_pen)
        map_container.addToGroup(y_axis)
        print("DEBUG: 添加x/y轴线")

        # 7. 彻底重置所有变换（非常重要）
        self.canvas_manager.resetTransform()

        # 8. 设置默认缩放为160%（与游戏引擎一致）
        initial_scale = 1.6
        self.canvas_manager.scale(initial_scale, initial_scale)
        self.canvas_manager._zoom_level = initial_scale
        print(f"DEBUG: 设置默认缩放为{initial_scale * 100}%")

        # 10. 让红色网格完整显示在画布范围内
        # 设置视图中心点为红色网格的中心位置(80,80)，这样整个网格都能显示
        self.canvas_manager.centerOn(80, 80)
        print("DEBUG: 红色网格已完整显示在画布范围内")

        # 10. 绑定鼠标事件
        self._bind_mouse_events()

    def _bind_mouse_events(self):
        """绑定鼠标事件 - 完全按照sprite_editor的模式"""
        # 保存原始的鼠标事件处理函数
        self.original_mousePressEvent = self.canvas_manager.mousePressEvent
        self.original_mouseMoveEvent = self.canvas_manager.mouseMoveEvent
        self.original_mouseReleaseEvent = self.canvas_manager.mouseReleaseEvent
        self.original_wheelEvent = self.canvas_manager.wheelEvent

        # 绑定自定义的鼠标事件处理函数
        self.canvas_manager.mousePressEvent = self._handle_mouse_press
        self.canvas_manager.mouseMoveEvent = self._handle_mouse_move
        self.canvas_manager.mouseReleaseEvent = self._handle_mouse_release
        self.canvas_manager.wheelEvent = self._handle_wheel_event

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

    def toggle_grid_visibility(self, visible):
        """控制网格线的显示/隐藏"""
        for line in self.grid_lines:
            line.setVisible(visible)
        print(f"网格线显示状态: {'显示' if visible else '隐藏'}")

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

            print(
                f"DEBUG: 渲染地图 - 地图尺寸: {width}x{height}, 瓦片大小: {tile_size}"
            )

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

                    print(f"DEBUG: 渲染瓦片数量: {len(y_indices)}")
                    for y, x in zip(y_indices, x_indices):
                        stored_tile_id = tile_data[y, x]
                        # 数组坐标减去偏移量得到实际坐标
                        actual_x = x - self.map_model.coord_offset
                        actual_y = y - self.map_model.coord_offset
                        print(
                            f"DEBUG: 渲染瓦片 - 数组坐标: ({x}, {y}), 实际坐标: ({actual_x}, {actual_y}), 瓦片ID: {stored_tile_id}"
                        )

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
                                    # 使用实际坐标
                                    actual_x = x - self.map_model.coord_offset
                                    actual_y = y - self.map_model.coord_offset
                                    pixmap_item.setPos(
                                        actual_x * tile_size, actual_y * tile_size
                                    )
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
                                        # 使用实际坐标
                                        actual_x = x - self.map_model.coord_offset
                                        actual_y = y - self.map_model.coord_offset
                                        pixmap_item.setPos(
                                            actual_x * tile_size, actual_y * tile_size
                                        )
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

        # 计算瓦片坐标（支持负坐标）
        tile_x = int(scene_pos.x() / tile_size)
        tile_y = int(scene_pos.y() / tile_size)

        # 移除边界检查，支持任意坐标
        return (tile_x, tile_y)

    def _handle_mouse_press(self, event):
        """处理鼠标按下事件"""
        try:
            if event.button() == Qt.LeftButton:
                if self.current_tool == "move":
                    # 移动工具：选择并准备拖拽
                    scene_pos = self.canvas_manager.mapToScene(event.pos())
                    items = self.canvas_manager.scene().items(scene_pos)

                    # 查找可移动的图块项
                    for item in items:
                        if (
                            isinstance(item, QGraphicsPixmapItem)
                            and item != self.preview_item
                        ):
                            self.selected_item = item
                            self.drag_start_pos = scene_pos - item.pos()

                            # 保存原始位置
                            tile_size = self.map_model.get_tile_size()
                            original_x = int(item.pos().x() / tile_size)
                            original_y = int(item.pos().y() / tile_size)
                            self.original_tile_pos = (original_x, original_y)
                            break
                elif self.current_tool == "draw":
                    # 绘制工具：绘制瓦片
                    tile_pos = self._screen_to_tile(event.pos())
                    if tile_pos:
                        self.is_drawing = True
                        self.last_tile_pos = tile_pos
                        self._draw_tile(tile_pos)
                        # 移除预览
                        self._remove_preview()
                elif self.current_tool == "erase":
                    # 擦除工具：删除瓦片
                    scene_pos = self.canvas_manager.mapToScene(event.pos())
                    items = self.canvas_manager.scene().items(scene_pos)

                    # 查找并删除图块项
                    for item in items:
                        if (
                            isinstance(item, QGraphicsPixmapItem)
                            and item != self.preview_item
                        ):
                            # 获取图块位置并更新地图数据
                            tile_size = self.map_model.get_tile_size()
                            tile_x = int(item.pos().x() / tile_size)
                            tile_y = int(item.pos().y() / tile_size)
                            self.map_model.set_tile(
                                self.current_layer, tile_x, tile_y, 0
                            )
                            break
            else:
                # 其他鼠标按钮（包括中键）交给MapCanvas处理
                self.original_mousePressEvent(event)
        except Exception as e:
            print(f"鼠标按下事件错误: {e}")

    def _handle_mouse_move(self, event):
        """处理鼠标移动事件"""
        try:
            if event.buttons() & Qt.LeftButton:
                if self.current_tool == "move" and self.selected_item:
                    # 移动工具：拖拽移动选中的图块
                    scene_pos = self.canvas_manager.mapToScene(event.pos())
                    new_pos = scene_pos - self.drag_start_pos

                    # 获取瓦片大小
                    tile_size = self.map_model.get_tile_size()

                    # 对齐到网格
                    aligned_x = round(new_pos.x() / tile_size) * tile_size
                    aligned_y = round(new_pos.y() / tile_size) * tile_size

                    self.selected_item.setPos(aligned_x, aligned_y)
                elif self.current_tool == "draw" and self.is_drawing:
                    # 绘制工具：绘制瓦片
                    tile_pos = self._screen_to_tile(event.pos())
                    if tile_pos and tile_pos != self.last_tile_pos:
                        self._draw_tile(tile_pos)
                        self.last_tile_pos = tile_pos
                elif self.current_tool == "erase":
                    # 擦除工具：删除瓦片
                    scene_pos = self.canvas_manager.mapToScene(event.pos())
                    items = self.canvas_manager.scene().items(scene_pos)

                    # 查找并删除图块项
                    for item in items:
                        if (
                            isinstance(item, QGraphicsPixmapItem)
                            and item != self.preview_item
                        ):
                            # 获取图块位置并更新地图数据
                            tile_size = self.map_model.get_tile_size()
                            tile_x = int(item.pos().x() / tile_size)
                            tile_y = int(item.pos().y() / tile_size)
                            self.map_model.set_tile(
                                self.current_layer, tile_x, tile_y, 0
                            )
                            break
            else:
                # 如果是中键拖动，交给MapCanvas处理
                if event.buttons() & Qt.MiddleButton:
                    self.original_mouseMoveEvent(event)
                else:
                    # 显示预览图块（仅绘制工具）
                    if self.current_tool == "draw":
                        self._update_preview(event.pos())

        except Exception as e:
            print(f"鼠标移动事件错误: {e}")

    def _handle_mouse_release(self, event):
        """处理鼠标释放事件"""
        try:
            if event.button() == Qt.LeftButton:
                if self.current_tool == "move":
                    # 移动工具：保存移动后的位置到地图数据模型
                    if self.selected_item and self.original_tile_pos:
                        # 获取图块位置并更新地图数据
                        tile_size = self.map_model.get_tile_size()
                        new_x = int(self.selected_item.pos().x() / tile_size)
                        new_y = int(self.selected_item.pos().y() / tile_size)

                        # 获取原始位置的图块ID
                        layer = self.map_model.get_layer(self.current_layer)
                        if layer and layer["tiles"] is not None:
                            original_x, original_y = self.original_tile_pos
                            if (
                                0 <= original_x < layer["tiles"].shape[1]
                                and 0 <= original_y < layer["tiles"].shape[0]
                            ):
                                tile_id = layer["tiles"][original_y, original_x]

                                # 清除原始位置
                                self.map_model.set_tile(
                                    self.current_layer, original_x, original_y, 0
                                )

                                # 设置新位置
                                self.map_model.set_tile(
                                    self.current_layer, new_x, new_y, tile_id
                                )

                    # 取消选中状态
                    self.selected_item = None
                    self.drag_start_pos = None
                    self.original_tile_pos = None
                elif self.current_tool == "draw":
                    # 绘制工具：结束绘制
                    self.is_drawing = False
                    self.last_tile_pos = None
            else:
                # 其他鼠标按钮交给MapCanvas处理
                self.original_mouseReleaseEvent(event)
        except Exception as e:
            print(f"鼠标释放事件错误: {e}")

    def _handle_wheel_event(self, event):
        """处理滚轮事件 - 调用原始的wheelEvent方法"""
        try:
            # 调用原始的wheelEvent方法，让MapCanvas自己处理缩放
            self.original_wheelEvent(event)
        except Exception as e:
            print(f"滚轮事件错误: {e}")

    def _draw_tile(self, tile_pos):
        """绘制瓦片"""
        try:
            if self.selected_resource_index >= 0:
                # 获取选中的资源
                resource = self.uploaded_resources[self.selected_resource_index]
                resource_type = resource.get("resource_type", "image")

                # 获取图块大小
                tile_size = self.map_model.get_tile_size()

                # 根据资源类型确定图块ID和大小
                if resource_type == "tileset":
                    # 图块集合模式，使用资源索引和图块索引的组合作为图块ID
                    # 格式：resource_index * 1000 + tile_index + 1
                    if self.selected_tile_index >= 0:
                        tile_id = (
                            self.selected_resource_index * 1000
                            + self.selected_tile_index
                            + 1
                        )
                        # 图块集合使用固定的图块大小
                        tile_width = resource.get("tile_size", tile_size)
                        tile_height = resource.get("tile_size", tile_size)
                    else:
                        return
                else:
                    # 单张图片模式，使用资源索引作为图块ID
                    tile_id = self.selected_resource_index + 1
                    # 获取图片实际大小
                    from PySide6.QtGui import QPixmap

                    pixmap = QPixmap(resource["path"])
                    if pixmap.isNull():
                        return
                    tile_width = pixmap.width()
                    tile_height = pixmap.height()

                # 计算图块在网格中的尺寸（以瓦片为单位）
                tiles_width = max(1, tile_width // tile_size)
                tiles_height = max(1, tile_height // tile_size)

                x, y = tile_pos

                print(
                    f"DEBUG: 绘制位置 - 原始坐标: ({x}, {y}), 瓦片尺寸: {tiles_width}x{tiles_height}"
                )

                # 将图块位置对齐到图块大小的整数倍
                aligned_x = x - (x % tiles_width)
                aligned_y = y - (y % tiles_height)

                print(f"DEBUG: 绘制位置 - 对齐后坐标: ({aligned_x}, {aligned_y})")

                # 检查并清除与新图块重叠的所有已存在图块
                # 获取地图上所有非零的图块位置
                layer = self.map_model.get_layer(self.current_layer)
                if layer and layer["tiles"] is not None:
                    import numpy as np

                    y_indices, x_indices = np.where(layer["tiles"] > 0)

                    # 计算新绘制图块的范围
                    new_tile_rect = (
                        aligned_x,
                        aligned_y,
                        aligned_x + tiles_width,
                        aligned_y + tiles_height,
                    )

                    # 遍历所有已绘制的图块
                    for tile_y, tile_x in zip(y_indices, x_indices):
                        existing_tile_id = layer["tiles"][tile_y, tile_x]

                        # 查找对应的资源
                        found = False
                        for resource_index, resource in enumerate(
                            self.uploaded_resources
                        ):
                            resource_type = resource.get("resource_type", "image")

                            if resource_type == "tileset":
                                # 图块集合模式，图块ID格式：resource_index * 1000 + tile_index + 1
                                if existing_tile_id // 1000 == resource_index:
                                    existing_tile_size = resource.get(
                                        "tile_size", tile_size
                                    )
                                    found = True
                            else:
                                # 单张图片模式，图块ID格式：resource_index + 1
                                if existing_tile_id == resource_index + 1:
                                    # 获取图片实际大小
                                    from PySide6.QtGui import QPixmap

                                    pixmap = QPixmap(resource["path"])
                                    if not pixmap.isNull():
                                        existing_tile_size = max(
                                            pixmap.width(), pixmap.height()
                                        )
                                    else:
                                        existing_tile_size = tile_size
                                    found = True

                            if found:
                                # 计算该图块占用的网格大小
                                existing_tiles_width = max(
                                    1, existing_tile_size // tile_size
                                )
                                existing_tiles_height = max(
                                    1, existing_tile_size // tile_size
                                )

                                # 计算已存在图块的范围
                                existing_tile_rect = (
                                    tile_x,
                                    tile_y,
                                    tile_x + existing_tiles_width,
                                    tile_y + existing_tiles_height,
                                )

                                # 检查两个矩形是否重叠
                                if (
                                    new_tile_rect[0] < existing_tile_rect[2]
                                    and new_tile_rect[2] > existing_tile_rect[0]
                                    and new_tile_rect[1] < existing_tile_rect[3]
                                    and new_tile_rect[3] > existing_tile_rect[1]
                                ):
                                    # 清除整个已存在的图块
                                    for dy in range(existing_tiles_height):
                                        for dx in range(existing_tiles_width):
                                            self.map_model.set_tile(
                                                self.current_layer,
                                                tile_x + dx,
                                                tile_y + dy,
                                                0,
                                            )
                                    break

                # 更新地图数据（只在左上角位置记录图块）
                print(
                    f"DEBUG: 设置瓦片 - 图层: {self.current_layer}, 位置: ({aligned_x}, {aligned_y}), 瓦片ID: {tile_id}"
                )
                result = self.map_model.set_tile(
                    self.current_layer, aligned_x, aligned_y, tile_id
                )
                print(f"DEBUG: 设置瓦片结果: {result}")
        except Exception as e:
            print(f"绘制瓦片错误: {e}")

    def _update_preview(self, screen_pos):
        """更新预览图块"""
        try:
            if not self.canvas_manager or not self.map_model:
                return

            # 获取选中的资源
            if self.selected_resource_index < 0:
                self._remove_preview()
                return

            resource = self.uploaded_resources[self.selected_resource_index]
            resource_type = resource.get("resource_type", "image")

            # 检查是否需要图块索引
            if resource_type == "tileset" and self.selected_tile_index < 0:
                self._remove_preview()
                return

            # 获取图块大小
            tile_size = self.map_model.get_tile_size()

            # 获取图块实际大小
            if resource_type == "tileset":
                tile_width = resource.get("tile_size", tile_size)
                tile_height = resource.get("tile_size", tile_size)
            else:
                # 获取图片实际大小
                from PySide6.QtGui import QPixmap

                pixmap = QPixmap(resource["path"])
                if pixmap.isNull():
                    self._remove_preview()
                    return
                tile_width = pixmap.width()
                tile_height = pixmap.height()

            # 加载资源图片
            from PySide6.QtGui import QPixmap

            pixmap = QPixmap(resource["path"])
            if pixmap.isNull():
                return

            # 根据资源类型处理图片
            if resource_type == "tileset":
                # 图块集合模式，裁剪特定图块
                tile_size_resource = resource["tile_size"]
                tiles_per_row = pixmap.width() // tile_size_resource
                tile_row = self.selected_tile_index // tiles_per_row
                tile_col = self.selected_tile_index % tiles_per_row

                # 裁剪图块
                from PySide6.QtCore import QRectF

                tile_rect = QRectF(
                    tile_col * tile_size_resource,
                    tile_row * tile_size_resource,
                    tile_size_resource,
                    tile_size_resource,
                )
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

                # 使用瓦片坐标
                tile_pos = self._screen_to_tile(screen_pos)
                if not tile_pos:
                    return

                # 计算图块在网格中的尺寸（以瓦片为单位）
                tiles_width = max(1, tile_width // tile_size)
                tiles_height = max(1, tile_height // tile_size)

                # 将预览位置对齐到图块大小的整数倍
                x, y = tile_pos
                aligned_x = x - (x % tiles_width)
                aligned_y = y - (y % tiles_height)

                # 如果位置没有变化，不需要更新
                aligned_tile_pos = (aligned_x, aligned_y)
                if aligned_tile_pos == self.preview_tile_pos:
                    return

                # 更新预览位置
                self.preview_tile_pos = aligned_tile_pos

                preview_pos = (aligned_x * tile_size, aligned_y * tile_size)
                self.preview_item.setPos(preview_pos[0], preview_pos[1])

                self.preview_item.setOpacity(0.5)  # 半透明效果
                # 确保预览项显示在最前面
                self.preview_item.setZValue(100)
                scene.addItem(self.preview_item)

        except Exception as e:
            pass

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

                    # 检查是否是选中的资源
                    is_resource_selected = i == self.selected_resource_index
                    if is_resource_selected:
                        resource_item.setBrush(QBrush(QColor(100, 149, 237, 50)))
                        resource_item.setPen(Qt.NoPen)

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

    def setup_tool_buttons(self, ui):
        """绑定工具按钮到对应的功能"""
        self.ui = ui
        # 绑定移动工具按钮
        self.ui.btn_editor_map_move.clicked.connect(
            lambda: self.set_current_tool("move")
        )
        # 绑定绘制工具按钮
        self.ui.btn_editor_map_draw.clicked.connect(
            lambda: self.set_current_tool("draw")
        )
        # 绑定擦除工具按钮
        self.ui.btn_editor_map_erase.clicked.connect(
            lambda: self.set_current_tool("erase")
        )
        print("工具按钮绑定完成")

    def set_current_tool(self, tool):
        """设置当前工具"""
        self.current_tool = tool
        print(f"当前工具切换为: {tool}")

        # 更新按钮状态
        if hasattr(self, "ui"):
            self.ui.btn_editor_map_move.setChecked(tool == "move")
            self.ui.btn_editor_map_draw.setChecked(tool == "draw")
            self.ui.btn_editor_map_erase.setChecked(tool == "erase")

    def set_current_tool(self, tool):
        """设置当前工具"""
        self.current_tool = tool
        print(f"当前工具切换为: {tool}")

        # 更新按钮状态
        if hasattr(self, "ui"):
            self.ui.btn_editor_map_move.setChecked(tool == "move")
            self.ui.btn_editor_map_draw.setChecked(tool == "draw")
            self.ui.btn_editor_map_erase.setChecked(tool == "erase")

        # 切换到擦除模式时移除预览图
        if tool == "erase":
            self._remove_preview()
        # 切换到绘制模式时，如果已选中资源，显示预览
        elif tool == "draw" and self.selected_resource_index >= 0:
            # 检查是否需要图块索引
            resource = self.uploaded_resources[self.selected_resource_index]
            resource_type = resource.get("resource_type", "image")
            # 图块集合需要选中图块，单张图片不需要
            if (
                resource_type == "tileset" and self.selected_tile_index >= 0
            ) or resource_type != "tileset":
                # 获取鼠标当前位置并更新预览
                if self.canvas_manager:
                    # 尝试获取鼠标位置，如果鼠标不在画布范围内，使用画布中心位置
                    cursor_pos = self.canvas_manager.mapFromGlobal(QCursor.pos())
                    # 强制更新预览，即使位置没有变化
                    self.preview_tile_pos = None
                    self._update_preview(cursor_pos)
