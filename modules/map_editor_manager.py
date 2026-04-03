import os
from PySide6.QtCore import QObject, Signal, Qt
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
            if self.is_deleted:
                return
            if event.button() == Qt.LeftButton:
                self.manager.select_tile(self.resource_info, self.tile_index)
            super().mousePressEvent(event)
        except Exception as e:
            print(f"图块点击事件错误: {e}")

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
            if self.is_deleted:
                return
            if event.button() == Qt.LeftButton:
                self.manager.select_resource(self.index)
            super().mousePressEvent(event)
        except Exception as e:
            print(f"资源点击事件错误: {e}")

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

    def _initialize_map_model(self):
        """初始化地图数据模型"""
        self.map_model = MapDataModel()
        # 连接数据变化信号
        self.map_model.data_changed.connect(self._on_map_data_changed)

    def _initialize_canvas_manager(self):
        """初始化画布管理器"""
        self.canvas_manager = SmartCanvas(self.canvas_widget)
        # 设置画布属性
        # SmartCanvas已经内置了网格和背景绘制

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
        if self.canvas_manager:
            # 这里将在后续实现地图绘制逻辑
            pass

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
        self.canvas_widget = canvas_widget
        self._initialize_canvas_manager()

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
            return

        # 弹出导入对话框
        dialog = MapResourceImportDialog()

        if dialog.exec() == QDialog.Accepted:
            # 获取导入数据
            import_data = dialog.get_import_data()
            files = import_data["files"]
            resource_type = import_data["resource_type"]
            tile_size = import_data["tile_size"]

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

            # 更新资源列表显示
            self._update_res_list_display()

    def select_resource(self, index):
        """选择资源"""
        try:
            if 0 <= index < len(self.uploaded_resources):
                self.selected_resource_index = index
                self.selected_tile_index = -1  # 重置图块选择
                print(f"选中资源: {self.uploaded_resources[index]['name']}")
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
                print(f"选中图块: 资源={resource_info['name']}, 图块索引={tile_index}")
                self._update_res_list_display()
        except Exception as e:
            print(f"选择图块错误: {e}")

    def _update_res_list_display(self):
        """更新资源列表显示"""
        if not self.res_list_view:
            return

        # 创建场景
        scene = QGraphicsScene()

        # 添加资源到场景
        y_pos = 10

        for i, resource in enumerate(self.uploaded_resources):
            try:
                # 加载原始图片
                original_pixmap = QPixmap(resource["path"])
                if original_pixmap.isNull():
                    continue

                # 获取资源类型和图块尺寸
                resource_type = resource.get("resource_type", "image")
                tile_size = resource.get("tile_size", 32)

                # 计算图块数量（仅图块集合模式）
                image_width = original_pixmap.width()
                image_height = original_pixmap.height()
                tiles_per_row = 0
                tiles_per_col = 0

                if resource_type == "tileset":
                    tiles_per_row = image_width // tile_size
                    tiles_per_col = image_height // tile_size

                # 计算显示区域大小 - 撑满256宽度
                display_width = 256  # 整个视图宽度
                margin = 0  # 不添加额外边距

                # 计算缩放比例 - 小于256宽度的图片保持原始尺寸
                if image_width < display_width:
                    scale = 1.0  # 保持原始尺寸
                else:
                    scale = display_width / image_width  # 大于等于256宽度的图片缩放

                # 创建缩放后的图片
                scaled_width = int(image_width * scale)
                scaled_height = int(image_height * scale)

                scaled_pixmap = original_pixmap.scaled(
                    scaled_width,
                    scaled_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.FastTransformation,
                )

                # 计算显示位置
                pixmap_x = 0
                pixmap_y = y_pos

                # 添加缩放后的图片
                pixmap_item = QGraphicsPixmapItem(scaled_pixmap)
                pixmap_item.setPos(pixmap_x, pixmap_y)
                scene.addItem(pixmap_item)

                # 创建可点击的区域（仅图像模式）
                image_rect = QGraphicsRectItem(
                    pixmap_x, pixmap_y, scaled_width, scaled_height
                )

                # 设置选中状态样式（仅图像模式）
                if resource_type == "image":
                    is_resource_selected = i == self.selected_resource_index
                    if is_resource_selected:
                        image_rect.setBrush(QBrush(QColor(100, 149, 237, 50)))
                        image_rect.setPen(Qt.NoPen)
                    else:
                        image_rect.setPen(Qt.NoPen)
                        image_rect.setBrush(Qt.NoBrush)
                else:
                    # 图块集合模式，不显示资源级别的选中状态
                    image_rect.setPen(Qt.NoPen)
                    image_rect.setBrush(Qt.NoBrush)

                scene.addItem(image_rect)

                # 创建资源项（用于点击事件）
                resource_item = ResourceItem(image_rect.rect(), resource, i, self)
                scene.addItem(resource_item)

                # 绘制图块网格（仅图块集合模式）
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

                # 更新位置 - 根据实际图片高度调整间距
                y_pos += scaled_height

            except Exception as e:
                print(f"创建资源缩略图失败: {e}")

        # 设置场景大小
        scene_height = max(500, y_pos)
        scene.setSceneRect(0, 0, 256, scene_height)

        # 设置场景到视图
        self.res_list_view.setScene(scene)
        self.res_list_view.show()
        self.res_list_view.repaint()
