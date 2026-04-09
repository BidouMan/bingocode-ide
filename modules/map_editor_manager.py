import os
import math
from PySide6.QtCore import QObject, Signal, Qt, QRectF, QPoint, QPointF
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
    QImage,
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
        self.current_tool = "move"  # 当前工具：draw, eraser, move
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
        # 按地图路径存储资源，实现资源隔离
        self.map_resources = {}  # {map_path: [resources]}
        self.uploaded_resources = []  # 当前地图的资源
        self.selected_resource_index = -1  # 当前选中的资源索引
        self.selected_tile_index = -1  # 当前选中的图块索引
        self.resource_items = []  # 存储资源项的图形项
        self.tile_items = {}  # 存储地图画布上的图块项，格式：{(x, y): QGraphicsPixmapItem}
        self.resource_tile_items = {}  # 存储资源列表视图中的图块项，格式：{(resource_index, tile_index): TileItem}

        # 预览相关
        self.preview_item = None  # 预览图块项
        self.preview_tile_pos = None  # 预览图块位置
        self._is_updating_preview = False  # 防止预览更新无限循环的标志
        self.preview_resource_index = -1  # 预览资源索引，用于检测资源变化
        self.preview_tile_index = -1  # 预览图块索引，用于检测图块变化

        # 网格线相关
        self.grid_lines = []  # 存储网格线对象，用于控制显示/隐藏

        # 鼠标状态
        self.is_drawing = False
        self.last_tile_pos = None

        # 移动工具相关
        self.selected_item = None
        self.drag_start_pos = None
        self.original_tile_pos = None  # 原始瓦片位置

        # 地图路径相关
        self.current_map_path = None  # 当前地图文件路径
        self.is_map_modified = False  # 地图是否被修改

        # 资源管理
        self.uploaded_resources = []  # 上传的资源列表

        # 核心缓存字典
        # Key: tile_id (或是 "resource_index_tile_index" 字符串)
        # Value: QPixmap 对象
        self._pixmap_cache = {}

        # 原始资源图集缓存 (避免重复读取大图)
        self._source_image_cache = {}

        # 对象池 (Object Pool) —— 老机器的救星
        self._item_pool = []  # 存放闲置的 QGraphicsPixmapItem

        # 碰撞编辑器相关
        self.col_editor_scene = None  # 碰撞编辑器场景
        self.col_editor_view = None  # 碰撞编辑器视图引用
        self.current_collision_tile = None  # 当前选中的碰撞图块
        self.collision_rect_item = None  # 碰撞框图形项

    def _initialize_map_model(self):
        """初始化地图数据模型"""
        self.map_model = MapDataModel()
        # 连接数据变化信号
        self.map_model.data_changed.connect(self._on_map_data_changed)

    def _initialize_canvas_manager(self):
        """初始化画布管理器 - 完全按照sprite_editor的模式"""
        if not self.canvas_widget:
            return

        # 1. 替换画布控件 (只做一次，不要覆盖)
        parent_widget = self.canvas_widget.parentWidget()
        parent_layout = parent_widget.layout()

        self.canvas_manager = MapCanvas(parent_widget)
        parent_layout.replaceWidget(self.canvas_widget, self.canvas_manager)
        old_canvas = self.canvas_widget
        old_canvas.hide()
        old_canvas.deleteLater()
        # 清除对已删除对象的引用
        self.canvas_widget = None

        # 2. 绑定场景，设置无限画布范围
        # 坐标原点：左上角(0,0)，但允许显示负坐标，实现真正的无限画布效果
        self.canvas_scene = QGraphicsScene(
            -10000, -10000, 20000, 20000
        )  # 包含正负坐标的大场景，实现无限画布
        self.canvas_manager.setScene(self.canvas_scene)

        # 设置地图模型和瓦片大小
        width, height = self.map_model.get_map_size()
        tile_size = self.map_model.get_tile_size()

        # 设置地图模型引用给画布管理器，用于动态网格绘制
        self.canvas_manager.map_model = self.map_model
        self.canvas_manager.tile_size = tile_size

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

        # 6. 创建一个容器项，用于包含所有地图元素
        from PySide6.QtWidgets import QGraphicsItemGroup

        map_container = QGraphicsItemGroup()
        self.canvas_scene.addItem(map_container)

        # 7. 绘制可见的瓦片网格，以游戏引擎坐标系统（左上角(0,0)）为原点
        # 网格线现在在画布的drawBackground中动态绘制

        # 9. 添加x/y轴线（像Godot一样）
        # x轴线（红色，水平方向）
        x_axis_pen = QPen(QColor(200, 50, 50), 0)  # 降低饱和度的红色，最细
        x_axis = self.canvas_scene.addLine(-10000, 0, 10000, 0, x_axis_pen)
        map_container.addToGroup(x_axis)

        # y轴线（绿色，垂直方向）
        y_axis_pen = QPen(QColor(50, 200, 50), 0)  # 降低饱和度的绿色，最细
        y_axis = self.canvas_scene.addLine(0, -10000, 0, 10000, y_axis_pen)
        map_container.addToGroup(y_axis)

        # 7. 彻底重置所有变换（非常重要）
        self.canvas_manager.resetTransform()

        # 8. 设置默认缩放为160%（与游戏引擎一致）
        initial_scale = 1.6
        self.canvas_manager.scale(initial_scale, initial_scale)
        self.canvas_manager._zoom_level = initial_scale

        # 10. 让红色网格完整显示在画布范围内
        # 设置视图中心点为红色网格的中心位置(80,80)，这样整个网格都能显示
        self.canvas_manager.centerOn(80, 80)

        # 10. 绑定鼠标事件
        self._bind_mouse_events()

    def _bind_mouse_events(self):
        """绑定鼠标事件 - 使用场景事件过滤器"""
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

        # 设置场景事件过滤器
        if self.canvas_scene:
            self.canvas_scene.installEventFilter(self)

        print("鼠标事件绑定完成")

    def eventFilter(self, obj, event):
        """场景事件过滤器，确保绘制事件被正确处理"""
        from PySide6.QtCore import QEvent

        if obj == self.canvas_scene:
            if event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton and self.current_tool == "draw":
                    scene_pos = event.scenePos()
                    # 调用鼠标按下处理方法，确保逻辑一致
                    self._handle_mouse_press(event)
                    return True
            elif event.type() == QEvent.MouseMove:
                if (
                    event.buttons() & Qt.LeftButton
                    and self.current_tool == "draw"
                    and self.is_drawing
                ):
                    scene_pos = event.scenePos()
                    # 获取网格位置（从场景坐标）
                    tile_pos = self._get_grid_pos_from_scene_pos(scene_pos)
                    if tile_pos and tile_pos != self.last_tile_pos:
                        self._draw_tile(scene_pos)
                        self.last_tile_pos = tile_pos
                    return True
            elif event.type() == QEvent.MouseButtonRelease:
                if event.button() == Qt.LeftButton and self.current_tool == "draw":
                    self.is_drawing = False
                    return True
        return super().eventFilter(obj, event)

    def _clear_resource_items(self):
        """清理资源项（只清理资源列表视图中的项，不清理地图画布上的图块）"""
        try:
            # 从资源列表视图场景中移除所有资源项
            if self.res_list_view:
                scene = self.res_list_view.scene()
                if scene:
                    # 从场景中移除所有资源项
                    for resource_item in self.resource_items:
                        try:
                            scene.removeItem(resource_item)
                            resource_item.is_deleted = True
                        except Exception as e:
                            print(f"从场景移除资源项错误: {e}")

                    # 从场景中移除所有资源列表视图中的图块项
                    for tile_item in self.resource_tile_items.values():
                        try:
                            scene.removeItem(tile_item)
                            tile_item.is_deleted = True
                        except Exception as e:
                            print(f"从场景移除资源列表图块项错误: {e}")

        except Exception as e:
            print(f"清理资源项和图块项错误: {e}")

        # 清空列表
        self.resource_items.clear()
        self.resource_tile_items.clear()

    def _setup_key_bindings(self):
        """设置按键绑定"""
        # 暂时注释掉快捷键设置，避免程序启动问题
        # 快捷键功能将在后续实现
        pass

    def set_tool(self, tool_name):
        """设置当前编辑工具"""
        # 切换工具时清除预览
        self._remove_preview()
        self.current_tool = tool_name
        print(f"当前工具: {tool_name}")

    def toggle_grid_visibility(self, visible):
        """控制网格线的显示/隐藏"""
        if self.canvas_manager:
            self.canvas_manager._grid_visible = visible
            self.canvas_manager.viewport().update()
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

    def load_map_from_path(self, file_path):
        """从指定路径加载地图 - 修复资源加载逻辑"""
        if file_path:
            # 清除之前的状态
            self.selected_resource_index = -1
            self.selected_tile_index = -1
            self._remove_preview()
            self.uploaded_resources.clear()

            # 加载地图数据
            if self.map_model.load(file_path):
                self.current_map_path = file_path
                self.is_map_modified = False
                self.map_loaded.emit(file_path)

                # 加载瓦片集资源到uploaded_resources列表
                print(
                    f"DEBUG: 加载瓦片集资源，数量: {len(self.map_model.map_data['tile_sets'])}"
                )
                self.uploaded_resources.clear()
                for tile_set in self.map_model.map_data["tile_sets"]:
                    image_path = tile_set.get("image_path", "")
                    if image_path:
                        if not os.path.isabs(image_path):
                            if self.current_map_path:
                                map_dir = os.path.dirname(self.current_map_path)
                                image_path = os.path.join(map_dir, image_path)
                        # 添加到上传资源列表
                        resource = {
                            "name": tile_set.get("name", "unknown"),
                            "path": image_path,
                            "resource_type": "tileset",
                            "tiles": tile_set.get("tiles", []),
                            "tile_width": tile_set.get("tile_width", 16),
                            "tile_height": tile_set.get("tile_height", 16),
                            "tile_size": tile_set.get("tile_width", 16),
                        }
                        self.uploaded_resources.append(resource)
                        print(
                            f"DEBUG: 加载资源: {resource['name']}, 路径: {resource['path']}"
                        )

                # 更新资源列表显示
                self._update_res_list_display()

                # 强制清理场景中的所有瓦片项（确保切换地图时彻底清空画布）
                if self.canvas_manager and self.canvas_manager.scene():
                    scene = self.canvas_manager.scene()

                    # 清理所有缓存
                    self._pixmap_cache.clear()
                    self._source_image_cache.clear()

                    # 获取场景中的所有项
                    all_items = scene.items()

                    # 移除所有瓦片相关的图形项
                    from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem

                    for item in all_items:
                        # 移除瓦片项（QGraphicsPixmapItem）和TileItem（自定义瓦片项）
                        if isinstance(item, QGraphicsPixmapItem) or hasattr(
                            item, "is_deleted"
                        ):
                            try:
                                scene.removeItem(item)
                                # 安全删除对象
                                if hasattr(item, "deleteLater"):
                                    item.deleteLater()
                            except Exception as e:
                                pass

                    # 清空所有相关数据结构
                    self.tile_items.clear()
                    self.resource_items.clear()

                # 加载瓦片集资源
                tile_sets = self.map_model.get_tile_sets()

                map_dir = os.path.dirname(file_path)
                for tile_set in tile_sets:
                    resource_name = tile_set.get("name")
                    image_path = tile_set.get("image_path")
                    if not image_path:
                        print(f"⚠️ 瓦片集{resource_name}无图片路径，跳过")
                        continue

                    # 修复：优先使用绝对路径，避免相对路径解析错误
                    if not os.path.isabs(image_path):
                        image_path = os.path.join(map_dir, image_path)

                    # 检查文件是否存在
                    if not os.path.exists(image_path):
                        print(f"⚠️ 图片文件不存在: {image_path}，跳过")
                        continue

                    # 加载图片获取真实尺寸
                    from PySide6.QtGui import QPixmap

                    pixmap = QPixmap(image_path)
                    if pixmap.isNull():
                        print(f"⚠️ 图片加载失败: {image_path}，跳过")
                        continue

                    # 修复：确保tile_width/tile_height有默认值
                    tile_width = tile_set.get("tile_width", 16)
                    tile_height = tile_set.get("tile_height", 16)
                    resource_type = "tileset" if tile_width and tile_height else "image"

                    # 构建资源信息（避免重复添加）
                    resource_info = {
                        "name": resource_name,
                        "path": os.path.relpath(image_path, map_dir),  # 存储相对路径
                        "resource_type": resource_type,
                        "tile_width": tile_width,
                        "tile_height": tile_height,
                        "tile_size": tile_width
                        if resource_type == "tileset"
                        else tile_width,
                        "width": pixmap.width(),
                        "height": pixmap.height(),
                        "frames": 1,
                    }
                    if resource_type == "tileset":
                        resource_info["tiles"] = []

                    # 检查重复
                    if not any(
                        res["name"] == resource_name for res in self.uploaded_resources
                    ):
                        self.uploaded_resources.append(resource_info)
                        print(
                            f"✅ 加载资源: {resource_name} | 路径: {resource_info['path']}"
                        )

                # 更新资源列表和画布
                self._update_res_list_display()
                self._update_canvas()
            else:
                print(f"DEBUG: 地图数据加载失败: {file_path}")
                self.error_occurred.emit("加载地图失败")

    def save_map(self):
        """保存地图"""
        print("=== 开始保存地图 ===")
        from PySide6.QtWidgets import QFileDialog

        # 如果已经有当前地图路径，直接使用
        if self.current_map_path:
            file_path = self.current_map_path
        else:
            file_path, _ = QFileDialog.getSaveFileName(
                None, "保存地图", "", "Map Files (*.info *.json)"
            )

        if file_path:
            # 如果没有扩展名，添加.info（二进制格式）
            if not file_path.endswith((".info", ".json")):
                file_path += ".info"

            print(f"DEBUG: 保存地图到: {file_path}")
            print(
                f"DEBUG: 当前地图数据 - 图层数: {len(self.map_model.map_data['layers'])}"
            )

            # 统计每个图层的瓦片数量
            total_tiles = 0
            for i, layer in enumerate(self.map_model.map_data["layers"]):
                tile_count = len(layer.get("tiles", {}))
                total_tiles += tile_count
                print(
                    f"DEBUG: 图层 {i} ({layer.get('name', 'unnamed')}) 瓦片数: {tile_count}"
                )
            print(f"DEBUG: 总瓦片数: {total_tiles}")

            # 保存地图数据
            if self.map_model.save(file_path):
                self.current_map_path = file_path
                self.is_map_modified = False
                self.map_saved.emit(file_path)
                print(f"✅ 地图保存成功: {file_path}")
            else:
                self.error_occurred.emit("保存地图失败")
                print(f"❌ 地图保存失败: {file_path}")

    def load_map(self):
        """加载地图"""
        print("=== 开始加载地图 ===")
        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            None, "加载地图", "", "Map Files (*.info *.json)"
        )

        if file_path:
            print(f"DEBUG: 加载地图: {file_path}")
            if self.map_model.load(file_path):
                self.current_map_path = file_path
                self.is_map_modified = False
                self.map_loaded.emit(file_path)

                # 输出加载后的地图数据信息
                print(
                    f"DEBUG: 加载成功 - 图层数: {len(self.map_model.map_data['layers'])}"
                )
                total_tiles = 0
                for i, layer in enumerate(self.map_model.map_data["layers"]):
                    tile_count = len(layer.get("tiles", {}))
                    total_tiles += tile_count
                    print(
                        f"DEBUG: 图层 {i} ({layer.get('name', 'unnamed')}) 瓦片数: {tile_count}"
                    )
                print(f"DEBUG: 总瓦片数: {total_tiles}")

                self._update_canvas()
                print(f"✅ 地图已从: {file_path} 加载")
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
        """地图数据变化时的处理 - 增量更新"""
        if not self.map_model:
            return

        # 获取变化区域
        changed_area = self.map_model.get_changed_area()
        if not changed_area:
            return

        # 只更新变化的瓦片
        for x, y in changed_area:
            tile_id = self.map_model.get_tile(self.current_layer, x, y)
            self._update_single_tile(x, y, tile_id)

        # 清除变化记录
        self.map_model.clear_changed_area()

    def _update_canvas(self):
        """更新画布显示"""
        print("=== 更新画布显示 ===")
        if self.canvas_manager and self.map_model:
            print("调用渲染地图")
            self._render_map()
        else:
            print(f"画布管理器: {self.canvas_manager}")
            print(f"地图模型: {self.map_model}")

    def _erase_tile(self, scene_pos):
        """物理碰撞拾取擦除方法"""
        try:
            # 1. 获取网格坐标用于清理数据模型（使用全局tile_size）
            gx, gy = self._get_grid_pos_from_scene_pos(scene_pos)

            # 2. 【核心修复】物理拾取：获取鼠标点下的所有图形项
            items = self.canvas_manager.scene().items(scene_pos)
            for item in items:
                # 只删除带有"tile"标签的PixmapItem，防止误伤背景网格
                if isinstance(item, QGraphicsPixmapItem) and item.data(0) == "tile":
                    self.canvas_manager.scene().removeItem(item)
                    # 同时清理字典中的引用（如果有）
                    if (gx, gy) in self.tile_items:
                        del self.tile_items[(gx, gy)]

            # 3. 同步清理数据模型中的数据
            self.map_model.set_tile(self.current_layer, gx, gy, 0)  # 0 代表空

            # 设置地图为已修改状态
            self.is_map_modified = True

            # 自动保存地图（如果当前地图有文件路径）
            if self.current_map_path:
                save_result = self.map_model.save(self.current_map_path)

        except Exception as e:
            print(f"擦除图块错误: {e}")

    def _update_single_tile(self, x, y, tile_id):
        """
        更新单个瓦片 - 优化对象池使用版本
        x, y: 网格索引 (0, 1, 2...)
        """
        try:
            if not self.canvas_manager:
                return

            scene = self.canvas_manager.scene()
            if not scene:
                return

            # 使用地图的全局tile_size计算位置，避免双重缩放
            tile_size = self.map_model.get_tile_size()

            # 如果瓦片ID为0，清除瓦片
            if tile_id == 0:
                if (x, y) in self.tile_items:
                    old_item = self.tile_items.pop((x, y))
                    self._recycle_item(old_item)
                return

            # 检查是否已有瓦片且瓦片ID相同，如果相同则无需更新
            if (x, y) in self.tile_items:
                existing_item = self.tile_items[(x, y)]
                existing_tile_id = existing_item.data(1)
                if existing_tile_id == tile_id:
                    return

            # 获取图块图像
            pixmap = self.get_cached_pixmap(tile_id)
            if not pixmap:
                return

            # 如果位置已有瓦片，更新现有瓦片而不是创建新瓦片
            if (x, y) in self.tile_items:
                existing_item = self.tile_items[(x, y)]
                existing_item.setPixmap(pixmap)
                existing_item.setData(1, tile_id)
            else:
                # 使用对象池获取图块项
                item = self._get_item_from_pool(pixmap)

                # 强制锁定位置：网格索引 * tile_size
                item.setPos(x * tile_size, y * tile_size)

                # 确保图片没有内置偏移
                item.setOffset(0, 0)

                # 设置层级，确保在网格线之上，并且高于预览
                item.setZValue(self.current_layer + 10)

                # 禁用鼠标事件，让事件穿透到画布
                item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

                # 添加到场景
                scene.addItem(item)
                self.tile_items[(x, y)] = item

                # 给图块打标签，方便擦除时识别
                item.setData(0, "tile")
                item.setData(1, tile_id)

            # 记录渲染时的图块位置（世界网格坐标）
            self._record_coordinates(
                f"Render Tile", coordinates=(x, y), tile_id=tile_id
            )

        except Exception as e:
            print(f"更新单个瓦片错误: {e}")

    def get_cached_pixmap(self, tile_id):
        """
        统一获取图块图像的函数
        tile_id: 资源索引。如果是Tileset，建议格式为 "resIdx_tileIdx"
        """
        if tile_id in self._pixmap_cache:
            return self._pixmap_cache[tile_id]

        # 如果缓存没有，则生成
        pixmap = self._generate_pixmap(tile_id)

        if pixmap:
            self._pixmap_cache[tile_id] = pixmap
        return pixmap

    def _get_item_from_pool(self, pixmap):
        """从对象池获取图块项，如果没有则创建新的"""
        if self._item_pool:
            item = self._item_pool.pop()
            item.setPixmap(pixmap)
            item.show()
            return item
        else:
            from PySide6.QtWidgets import QGraphicsPixmapItem

            return QGraphicsPixmapItem(pixmap)

    def _recycle_item(self, item):
        """回收图块项到对象池"""
        item.hide()
        try:
            self.canvas_manager.scene().removeItem(item)
        except:
            pass
        self._item_pool.append(item)

    def _generate_pixmap(self, tile_id):
        """解析资源并生成 QPixmap"""
        # 查找匹配的资源
        for resource_index, resource in enumerate(self.uploaded_resources):
            resource_type = resource.get("resource_type", "image")

            if resource_type == "tileset":
                # 图块集合模式，图块ID格式：resource_index * 1000 + tile_index + 1
                if tile_id // 1000 == resource_index:
                    # 处理资源路径（转换为绝对路径）
                    image_path = resource["path"]
                    if not os.path.isabs(image_path):
                        if self.current_map_path:
                            map_dir = os.path.dirname(self.current_map_path)
                            image_path = os.path.join(map_dir, image_path)

                    # 使用_source_image_cache缓存原始大图，避免重复读取文件
                    if image_path not in self._source_image_cache:
                        if os.path.exists(image_path):
                            from PySide6.QtGui import QPixmap

                            self._source_image_cache[image_path] = QPixmap(image_path)
                        else:
                            continue

                    pixmap = self._source_image_cache[image_path]
                    if pixmap:
                        # 使用资源的tile_width和tile_height进行裁剪
                        tile_width_resource = resource.get(
                            "tile_width", resource.get("width", 16)
                        )
                        tile_height_resource = resource.get(
                            "tile_height", resource.get("height", 16)
                        )
                        tiles_per_row = pixmap.width() // tile_width_resource

                        # 提取图块索引
                        tile_index = (tile_id % 1000) - 1
                        if tile_index >= 0:
                            tile_row = tile_index // tiles_per_row
                            tile_col = tile_index % tiles_per_row
                        else:
                            continue

                        # 裁剪图块
                        from PySide6.QtCore import QRectF

                        tile_rect = QRectF(
                            tile_col * tile_width_resource,
                            tile_row * tile_height_resource,
                            tile_width_resource,
                            tile_height_resource,
                        )
                        return pixmap.copy(tile_rect.toRect())
            else:
                # 单张图片模式，图块ID格式：resource_index * 1000 + 1
                if tile_id == resource_index * 1000 + 1:
                    # 处理资源路径（转换为绝对路径）
                    image_path = resource["path"]
                    if not os.path.isabs(image_path):
                        if self.current_map_path:
                            map_dir = os.path.dirname(self.current_map_path)
                            image_path = os.path.join(map_dir, image_path)

                    # 使用_source_image_cache缓存原始大图，避免重复读取文件
                    if image_path not in self._source_image_cache:
                        if os.path.exists(image_path):
                            from PySide6.QtGui import QPixmap

                            self._source_image_cache[image_path] = QPixmap(image_path)
                        else:
                            continue

                    pixmap = self._source_image_cache[image_path]
                    if pixmap:
                        return pixmap
        return None

    def _render_map(self):
        """根据模型数据渲染视口内的地图图层"""
        try:
            scene = self.canvas_manager.scene()
            view = self.canvas_manager.view()

            # 获取视口范围
            view_rect = view.viewport().rect()
            scene_rect = view.mapToScene(view_rect).boundingRect()

            # 获取当前图层数据
            layer = self.map_model.get_layer(self.current_layer)
            if not layer or not layer.get("visible", True):
                print(f"警告: 图层 {self.current_layer} 不可见或不存在")
                return

            tile_size = self.map_model.get_tile_size()

            # 计算视口内的瓦片范围
            min_tile_x = int(scene_rect.left() // tile_size) - 1  # 扩展一个瓦片边界
            max_tile_x = int(scene_rect.right() // tile_size) + 2  # 扩展一个瓦片边界
            min_tile_y = int(scene_rect.top() // tile_size) - 1  # 扩展一个瓦片边界
            max_tile_y = int(scene_rect.bottom() // tile_size) + 2  # 扩展一个瓦片边界

            # 获取图层中的瓦片数据
            tiles = layer.get("tiles", {})

            # 清理视口外的瓦片项
            tiles_to_remove = []
            for (tx, ty), item in self.tile_items.items():
                if (
                    tx < min_tile_x
                    or tx > max_tile_x
                    or ty < min_tile_y
                    or ty > max_tile_y
                ):
                    tiles_to_remove.append((tx, ty))

            for tx, ty in tiles_to_remove:
                item = self.tile_items.pop((tx, ty))
                self._recycle_item(item)

            # 渲染视口内的瓦片
            for (tx, ty), tile_id in tiles.items():
                if tile_id <= 0:
                    continue

                # 只渲染视口内的瓦片
                if min_tile_x <= tx <= max_tile_x and min_tile_y <= ty <= max_tile_y:
                    self._update_single_tile(tx, ty, tile_id)

        except Exception as e:
            print(f"渲染地图失败: {e}")
            import traceback

            traceback.print_exc()

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

    def _get_grid_pos(self, event_pos):
        """将鼠标事件的视图坐标转换为网格整数坐标 - 统一网格对齐"""
        if not self.canvas_manager or not self.map_model:
            return None

        # 1. 映射到场景坐标 (考虑到缩放和平移)
        scene_pos = self.canvas_manager.mapToScene(event_pos)
        if scene_pos is None:
            return None

        # 2. 使用_get_grid_pos_from_scene_pos方法计算网格位置
        return self._get_grid_pos_from_scene_pos(scene_pos)

    def _screen_to_tile(self, screen_pos):
        """将屏幕坐标转换为瓦片坐标"""
        return self._get_grid_pos(screen_pos)

    def _get_grid_pos_from_scene_pos(self, scene_pos, tile_id=None):
        """直接从场景坐标获取网格位置"""
        if not self.map_model:
            return None

        # 使用全局统一的tile_size计算网格坐标，确保所有图块都对齐到相同的网格
        tile_size = self.map_model.get_tile_size()

        # 使用 floor 确保负坐标也能正确对齐到网格
        grid_x = math.floor(scene_pos.x() / tile_size)
        grid_y = math.floor(scene_pos.y() / tile_size)

        return (grid_x, grid_y)

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
                    # 获取场景坐标
                    scene_pos = self.canvas_manager.mapToScene(event.pos())
                    if scene_pos:
                        self.is_drawing = True
                        # 获取网格位置
                        tile_pos = self._get_grid_pos_from_scene_pos(scene_pos)
                        self.last_tile_pos = tile_pos
                        # 调用绘制函数
                        self._draw_tile(scene_pos)
                        # 移除预览
                        self._remove_preview()
                elif self.current_tool == "erase":
                    # 擦除工具：删除瓦片
                    scene_pos = self.canvas_manager.mapToScene(event.pos())
                    self._erase_tile(scene_pos)
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
                    scene_pos = self.canvas_manager.mapToScene(event.pos())
                    # 使用从场景坐标获取网格位置的方法
                    tile_pos = self._get_grid_pos_from_scene_pos(scene_pos)
                    if scene_pos and tile_pos and tile_pos != self.last_tile_pos:
                        self._draw_tile(scene_pos)
                        self.last_tile_pos = tile_pos
                elif self.current_tool == "erase":
                    # 擦除工具：删除瓦片
                    scene_pos = self.canvas_manager.mapToScene(event.pos())
                    self._erase_tile(scene_pos)
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
                        original_x, original_y = self.original_tile_pos

                        # 获取原始位置的图块ID
                        tile_id = self.map_model.get_tile(
                            self.current_layer, original_x, original_y
                        )
                        if tile_id > 0:
                            # 先清除原始位置
                            self.map_model.set_tile(
                                self.current_layer, original_x, original_y, 0
                            )
                            # 然后设置新位置
                            self.map_model.set_tile(
                                self.current_layer, new_x, new_y, tile_id
                            )

                            # 更新tile_items字典，确保擦除功能正常工作
                            if (original_x, original_y) in self.tile_items:
                                item = self.tile_items.pop((original_x, original_y))
                                self.tile_items[(new_x, new_y)] = item

                            # 设置地图为已修改状态
                            self.is_map_modified = True

                            # 自动保存地图（如果当前地图有文件路径）
                            if self.current_map_path:
                                save_result = self.map_model.save(self.current_map_path)

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

    def _draw_tile(self, scene_pos):
        """绘制瓦片 - 简化流程版本"""
        try:
            # 检查必要条件
            if self.selected_resource_index < 0 or self.selected_resource_index >= len(
                self.uploaded_resources
            ):
                print(f"DEBUG: 资源索引无效: {self.selected_resource_index}")
                return

            # 获取选中的资源
            resource = self.uploaded_resources[self.selected_resource_index]
            resource_type = resource.get("resource_type", "image")
            resource_name = resource.get("name", "unknown")
            tile_width = resource.get("tile_width", 0)
            tile_height = resource.get("tile_height", 0)

            print(
                f"DEBUG: 绘制图块 - 资源类型: {resource_type}, 资源名称: {resource_name}, 尺寸: {tile_width}x{tile_height}"
            )
            print(
                f"DEBUG: 资源索引: {self.selected_resource_index}, 图块索引: {self.selected_tile_index}"
            )
            print(f"DEBUG: 资源列表长度: {len(self.uploaded_resources)}")

            # 根据资源类型确定图块ID
            if resource_type == "tileset":
                # 图块集合模式，使用资源索引和图块索引的组合作为图块ID
                # 格式：resource_index * 1000 + tile_index + 1
                tile_index = self.selected_tile_index
                # 如果没有选择图块索引，使用默认值0
                if tile_index < 0:
                    tile_index = 0

                tile_id = self.selected_resource_index * 1000 + tile_index + 1
                print(f"DEBUG: 图块集模式 - 生成tile_id: {tile_id}")
            else:
                # 单张图片模式，使用统一的资源ID格式
                tile_id = self.selected_resource_index * 1000 + 1
                print(f"DEBUG: 单张图片模式 - 生成tile_id: {tile_id}")

            # 获取纯粹的网格索引 (0, 1, 2...)
            grid_pos = self._get_grid_pos_from_scene_pos(scene_pos, tile_id)
            if grid_pos is None:
                print("DEBUG: 无法获取网格位置")
                return
            gx, gy = grid_pos
            print(f"DEBUG: 网格坐标: ({gx}, {gy})")

            # 检查当前图层是否有效
            layer_count = self.map_model.get_layer_count()
            print(f"DEBUG: 当前图层: {self.current_layer}, 图层总数: {layer_count}")
            if self.current_layer < 0 or self.current_layer >= layer_count:
                print(f"DEBUG: 图层索引无效，返回")
                return

            # 检查是否重复绘制
            current_tile_id = self.map_model.get_tile(self.current_layer, gx, gy)
            print(f"DEBUG: 当前位置图块ID: {current_tile_id}, 新图块ID: {tile_id}")
            if current_tile_id == tile_id:
                print("DEBUG: 图块ID相同，跳过绘制")
                return

            # 记录日志 (使用网格坐标)
            self._record_coordinates("Draw Tile", coordinates=(gx, gy), tile_id=tile_id)

            # 核心修改：在设置模型数据时，暂时阻塞信号，防止触发全量 _render_map
            self.map_model.blockSignals(True)
            self.map_model.set_tile(self.current_layer, gx, gy, tile_id)
            self.map_model.blockSignals(False)

            # 手动更新这一个瓦片即可，这样速度最快且不会冲突
            self._update_single_tile(gx, gy, tile_id)

            # 设置地图为已修改状态
            self.is_map_modified = True

            # 自动保存地图（如果当前地图有文件路径）
            if self.current_map_path:
                save_result = self.map_model.save(self.current_map_path)
        except Exception as e:
            print(f"绘制图块错误: {e}")
            import traceback

            traceback.print_exc()

    def _update_preview(self, screen_pos):
        """更新预览图块 - 统一网格对齐版本"""
        try:
            # 防止无限循环
            if self._is_updating_preview:
                return

            self._is_updating_preview = True

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

            # 获取统一的网格尺寸
            tile_size = self.map_model.get_tile_size()

            # 获取资源的实际尺寸
            if resource_type == "tileset":
                tile_width = resource.get("tile_width", tile_size)
                tile_height = resource.get("tile_height", tile_size)
            else:
                # 获取图片实际大小
                image_path = resource["path"]
                if not os.path.isabs(image_path):
                    if self.current_map_path:
                        map_dir = os.path.dirname(self.current_map_path)
                        image_path = os.path.join(map_dir, image_path)

                # 使用_source_image_cache缓存原始大图，避免重复读取文件
                if image_path not in self._source_image_cache:
                    if os.path.exists(image_path):
                        from PySide6.QtGui import QPixmap

                        self._source_image_cache[image_path] = QPixmap(image_path)
                    else:
                        self._remove_preview()
                        return
                pixmap = self._source_image_cache[image_path]
                if pixmap is None:
                    self._remove_preview()
                    return
                tile_width = pixmap.width()
                tile_height = pixmap.height()

            # 使用资源的实际尺寸计算网格位置
            scene_pos = self.canvas_manager.mapToScene(screen_pos)
            if scene_pos is None:
                return

            # 使用资源的实际尺寸计算网格坐标
            grid_x = math.floor(scene_pos.x() / tile_width)
            grid_y = math.floor(scene_pos.y() / tile_height)
            aligned_tile_pos = (grid_x, grid_y)

            # 【预览节流】只有当位置或资源发生变化时才更新
            if (
                aligned_tile_pos == self.preview_tile_pos
                and self.selected_resource_index == self.preview_resource_index
                and self.selected_tile_index == self.preview_tile_index
            ):
                return

            # 更新预览位置记录
            self.preview_tile_pos = aligned_tile_pos
            self.preview_resource_index = self.selected_resource_index
            self.preview_tile_index = self.selected_tile_index

            # 加载资源图片（处理相对路径）
            image_path = resource["path"]
            if not os.path.isabs(image_path):
                if self.current_map_path:
                    map_dir = os.path.dirname(self.current_map_path)
                    image_path = os.path.join(map_dir, image_path)

            # 使用_source_image_cache缓存原始大图，避免重复读取文件
            if image_path not in self._source_image_cache:
                if os.path.exists(image_path):
                    from PySide6.QtGui import QPixmap

                    self._source_image_cache[image_path] = QPixmap(image_path)
                else:
                    return
            pixmap = self._source_image_cache[image_path]
            if pixmap is None:
                return

            # 根据资源类型处理图片
            if resource_type == "tileset":
                # 图块集合模式，裁剪特定图块
                tile_width_resource = resource.get(
                    "tile_width", resource.get("width", 16)
                )
                tile_height_resource = resource.get(
                    "tile_height", resource.get("height", 16)
                )
                tiles_per_row = pixmap.width() // tile_width_resource
                tile_row = self.selected_tile_index // tiles_per_row
                tile_col = self.selected_tile_index % tiles_per_row

                # 裁剪图块
                from PySide6.QtCore import QRectF

                tile_rect = QRectF(
                    tile_col * tile_width_resource,
                    tile_row * tile_height_resource,
                    tile_width_resource,
                    tile_height_resource,
                )
                scaled_tile = pixmap.copy(tile_rect.toRect())
            else:
                # 单张图片模式，直接使用整张图片
                scaled_tile = pixmap

            scene = self.canvas_manager.scene()
            if scene:
                # 使用资源的实际尺寸计算预览位置
                x, y = aligned_tile_pos

                # 【对象复用】如果预览项已存在，只更新图片和位置
                if self.preview_item:
                    # 更新图片
                    self.preview_item.setPixmap(scaled_tile)
                    # 更新位置 - 严格锁定在网格坐标上，锚点始终为左上角
                    pos_x = x * tile_width
                    pos_y = y * tile_height
                    self.preview_item.setPos(pos_x, pos_y)
                    # 确保大图块也是从这个格子的左上角开始画
                    self.preview_item.setZValue(1000)  # 永远置顶
                else:
                    # 创建新的预览项
                    from PySide6.QtWidgets import QGraphicsPixmapItem

                    self.preview_item = QGraphicsPixmapItem(scaled_tile)
                    # 更新位置 - 严格锁定在网格坐标上，锚点始终为左上角
                    pos_x = x * tile_width
                    pos_y = y * tile_height
                    self.preview_item.setPos(pos_x, pos_y)
                    self.preview_item.setOpacity(0.5)  # 半透明效果
                    self.preview_item.setZValue(1000)  # 永远置顶
                    # 确保没有偏移
                    self.preview_item.setOffset(0, 0)
                    scene.addItem(self.preview_item)

        except Exception as e:
            pass
        finally:
            # 重置标志
            self._is_updating_preview = False

    def _remove_preview(self):
        """移除预览图块"""
        try:
            # 移除当前预览项
            if self.preview_item:
                scene = self.canvas_manager.scene()
                if scene:
                    scene.removeItem(self.preview_item)
                self.preview_item = None

            # 重置预览状态
            self.preview_tile_pos = None
            self.preview_resource_index = -1
            self.preview_tile_index = -1

            # 清理地图场景中所有可能残留的预览项
            scene = self.canvas_manager.scene()
            if scene:
                from PySide6.QtWidgets import QGraphicsPixmapItem

                items = scene.items()
                for item in items:
                    if isinstance(item, QGraphicsPixmapItem) and item.zValue() == 1000:
                        scene.removeItem(item)
        except Exception as e:
            print(f"移除预览图块错误: {e}")

    def initialize_collision_editor(self, col_editor_view):
        """初始化碰撞编辑器"""
        print(f"初始化碰撞编辑器: {col_editor_view}")
        self.col_editor_view = col_editor_view
        self.col_editor_scene = QGraphicsScene()
        self.col_editor_view.setScene(self.col_editor_scene)

        # 禁用滚动条和滚轮滚动
        self.col_editor_view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.col_editor_view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.col_editor_view.setDragMode(QGraphicsView.NoDrag)

        # 设置居中对齐（根据用户分析的核心修复）
        self.col_editor_view.setAlignment(Qt.AlignCenter)
        self.col_editor_view.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorViewCenter
        )

        print(
            f"碰撞编辑器初始化完成: scene={self.col_editor_scene}, view={self.col_editor_view}"
        )

    def set_current_collision_tile(self, resource_index, tile_index):
        """设置当前选中的碰撞图块"""
        if resource_index >= 0 and resource_index < len(self.uploaded_resources):
            self.current_collision_tile = (resource_index, tile_index)
            self._update_collision_display()

            # 更新map_collision checkbox的状态
            if hasattr(self, "ui") and hasattr(self.ui, "map_collision"):
                if self.map_model:
                    collision_enabled = self.map_model.get_tile_collision(
                        resource_index, tile_index
                    )
                    self.ui.map_collision.setChecked(collision_enabled)

            # 更新标签输入框的状态
            if hasattr(self, "ui") and hasattr(self.ui, "att_tag"):
                if self.map_model:
                    tile_tag = self.map_model.get_tile_tag(resource_index, tile_index)
                    # 阻塞信号，防止触发标签变化处理
                    self.ui.att_tag.blockSignals(True)
                    self.ui.att_tag.setText(tile_tag)
                    self.ui.att_tag.blockSignals(False)

    def _update_collision_display(self):
        """更新碰撞编辑器的显示"""
        if (
            not self.col_editor_scene
            or not self.col_editor_view
            or not self.current_collision_tile
        ):
            return

        resource_index, tile_index = self.current_collision_tile
        if resource_index < 0 or resource_index >= len(self.uploaded_resources):
            return

        resource = self.uploaded_resources[resource_index]

        # 获取图块图像
        pixmap = None
        if resource["resource_type"] == "tileset":
            tile_id = resource_index * 1000 + tile_index + 1
            pixmap = self.get_cached_pixmap(tile_id)
        else:
            # 单张图片模式
            image_path = resource["path"]
            if not os.path.isabs(image_path):
                if self.current_map_path:
                    map_dir = os.path.dirname(self.current_map_path)
                    image_path = os.path.join(map_dir, image_path)

            # 使用_source_image_cache缓存原始大图
            if image_path not in self._source_image_cache:
                if os.path.exists(image_path):
                    from PySide6.QtGui import QPixmap

                    self._source_image_cache[image_path] = QPixmap(image_path)

            pixmap = self._source_image_cache.get(image_path)

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

            # 计算保持比例的缩放因子
            scale_x = target_width / pixmap_width
            scale_y = target_height / pixmap_height
            scale = min(scale_x, scale_y)

            # 最小缩放限制（避免图块太小）
            min_scale = 2.0  # 至少放大到原始大小的2倍
            scale = max(scale, min_scale)

            # 清空场景
            self.col_editor_scene.clear()

            # 显示原图（放在场景中心位置）
            pixmap_item = QGraphicsPixmapItem(pixmap)
            # 将图块放在场景中心位置，使图块中心点对准场景原点
            pixmap_item.setPos(-pixmap_width / 2, -pixmap_height / 2)
            self.col_editor_scene.addItem(pixmap_item)

            # 显示碰撞框（半透明淡蓝色矩形）
            if self.map_model:
                collision_enabled = False
                if resource["resource_type"] == "tileset":
                    collision_enabled = self.map_model.get_tile_collision(
                        resource_index, tile_index
                    )
                else:
                    # 单张图片使用瓦片集的碰撞设置
                    collision_enabled = self.map_model.get_tile_set_collision(
                        resource_index
                    )

                if collision_enabled:
                    # 创建半透明淡蓝色碰撞框（放在场景中心位置）
                    rect_item = QGraphicsRectItem(
                        -pixmap_width / 2,
                        -pixmap_height / 2,
                        pixmap.width(),
                        pixmap.height(),
                    )
                    rect_item.setBrush(
                        QBrush(QColor(100, 149, 237, 100))
                    )  # 半透明淡蓝色
                    rect_item.setPen(QPen(QColor(100, 149, 237), 1))
                    self.col_editor_scene.addItem(rect_item)
                    self.collision_rect_item = rect_item

            # 计算图块的中心点
            pixmap_center_x = pixmap_width / 2
            pixmap_center_y = pixmap_height / 2

            # 计算视图需要滚动到的位置，使图块中心对准视图中心
            view_center_x = (
                pixmap_center_x - (view_width / 2 - pixmap_width * scale / 2) / scale
            )
            view_center_y = (
                pixmap_center_y - (view_height / 2 - pixmap_height * scale / 2) / scale
            )

            # 获取视图大小
            view_rect = self.col_editor_view.viewport().rect()
            view_width = view_rect.width()
            view_height = view_rect.height()

            # 黄金分割尺寸（大约占视图的61.8%）
            target_width = view_width * 0.618
            target_height = view_height * 0.618

            # 计算缩放比例
            scale_x = target_width / pixmap_width
            scale_y = target_height / pixmap_height
            scale = min(scale_x, scale_y)

            # 最小缩放限制（避免图块太小）
            min_scale = 2.0
            scale = max(scale, min_scale)

            # 图块已经放在场景中心位置（中心点在(0,0)）
            # 所以现在的平移量就是视图中心点的位置

            # 重新设计变换逻辑：先缩放，后平移到视图中心
            transform = self.col_editor_view.transform()
            transform.reset()

            # 先缩放
            transform.scale(scale, scale)

            # 再平移到视图中心
            transform.translate(view_width / 2, view_height / 2)

            self.col_editor_view.setTransform(transform)

            # 添加详细的调试信息
            print(f"DEBUG 居中计算:")
            print(f"  图块尺寸: {pixmap_width}x{pixmap_height}")
            print(f"  图块中心点: ({pixmap_center_x}, {pixmap_center_y})")
            print(f"  视图尺寸: {view_width}x{view_height}")
            print(f"  缩放比例: {scale}")
            print(f"  平移量: ({view_width / 2}, {view_height / 2})")

            # 计算图块最左边到视图左边的距离
            scaled_width = pixmap_width * scale
            left_distance = (view_width - scaled_width) / 2
            print(f"  缩放后图块宽度: {scaled_width}")
            print(f"  图块最左边到视图左边距离: {left_distance}")
            print(f"  图块最右边到视图右边距离: {left_distance}")

            # 显示视图
            self.col_editor_view.show()
        else:
            # 如果没有pixmap，清空场景
            self.col_editor_scene.clear()
            self.col_editor_view.fitInView(
                self.col_editor_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
            )

    def set_collision_enabled(self, enabled):
        """设置碰撞启用状态"""
        if self.current_collision_tile:
            resource_index, tile_index = self.current_collision_tile
            if self.map_model:
                self.map_model.set_tile_collision(resource_index, tile_index, enabled)
                self._update_collision_display()

    def _on_tag_changed(self, tag):
        """处理标签变化"""
        if self.current_collision_tile:
            resource_index, tile_index = self.current_collision_tile
            if self.map_model:
                self.map_model.set_tile_tag(resource_index, tile_index, tag)

    def _record_coordinates(self, action, coordinates=None, tile_id=None):
        """记录坐标信息到md文件"""
        try:
            import os
            import datetime

            # 创建记录文件路径
            record_dir = (
                "/Volumes/WorkStation/MyWork/CodeStation/MyIDE/MyWorkspace/备份"
            )
            os.makedirs(record_dir, exist_ok=True)
            record_file = os.path.join(record_dir, "coordinate_log.md")

            # 获取当前时间
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # 写入记录
            with open(record_file, "a", encoding="utf-8") as f:
                f.write(f"## {timestamp} - {action}\n\n")
                if coordinates:
                    f.write(f"**Coordinates:** {coordinates}\n")
                if tile_id:
                    f.write(f"**Tile ID:** {tile_id}\n")
                f.write("\n")

        except Exception as e:
            print(f"记录坐标错误: {e}")

            # 清理资源列表视图场景中的预览项
            if self.res_list_view:
                res_scene = self.res_list_view.scene()
                if res_scene:
                    from PySide6.QtWidgets import QGraphicsPixmapItem

                    res_items = res_scene.items()
                    for item in res_items:
                        if (
                            isinstance(item, QGraphicsPixmapItem)
                            and item.zValue() == 100
                        ):
                            res_scene.removeItem(item)

            self.preview_tile_pos = None

            # 强制刷新场景和视图
            if scene:
                scene.update()
            if self.canvas_manager:
                self.canvas_manager.viewport().update()
            if self.res_list_view:
                self.res_list_view.viewport().update()
        except Exception as e:
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
        # 检查传入的canvas_widget是否有效（没有被删除）
        try:
            # 尝试访问对象的属性来检查是否已删除
            if canvas_widget is None or not hasattr(canvas_widget, "parentWidget"):
                return

            # 尝试调用一个方法来进一步验证
            canvas_widget.parentWidget()
        except RuntimeError:
            return

        # 如果画布管理器已经初始化，需要重新初始化以确保地图数据正确切换
        if hasattr(self, "canvas_manager") and self.canvas_manager:
            # 清理旧的瓦片项
            if hasattr(self, "tile_items") and self.canvas_manager:
                old_scene = self.canvas_manager.scene()
                if old_scene:
                    for item in list(self.tile_items.values()):
                        try:
                            old_scene.removeItem(item)
                        except:
                            pass
                self.tile_items.clear()
            # 清理旧的画布管理器
            self.canvas_manager = None
            self.canvas_scene = None

        self.canvas_widget = canvas_widget
        self._initialize_canvas_manager()
        # 不再立即渲染地图，由load_map_from_path方法调用

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
                    # 获取当前地图名称
                    map_name = "未知地图"
                    if self.current_map_path:
                        map_name = os.path.splitext(
                            os.path.basename(self.current_map_path)
                        )[0]

                    # 创建tilesets目录 - 每个地图独立的tilesets目录
                    if self.project_manager and self.current_map_path:
                        # 获取地图文件所在目录（地图文件夹）
                        map_dir = os.path.dirname(self.current_map_path)
                        tilesets_dir = os.path.join(map_dir, "tilesets")
                        os.makedirs(tilesets_dir, exist_ok=True)

                        # 复制文件到当前地图的tilesets目录
                        file_name = os.path.basename(file_path)
                        dest_path = os.path.join(tilesets_dir, file_name)

                        # 复制文件
                        import shutil

                        shutil.copy2(file_path, dest_path)

                        # 使用相对路径（相对于地图文件）
                        relative_path = os.path.join("tilesets", file_name)
                    else:
                        # 如果没有项目管理器，使用原始路径
                        relative_path = file_path

                    # 获取图片尺寸并根据需要缩放
                    from PySide6.QtGui import QPixmap

                    pixmap = QPixmap(file_path)
                    if not pixmap.isNull():
                        original_width = pixmap.width()
                        original_height = pixmap.height()

                        # 如果是单张图片，按照用户选择的tile_size进行缩放
                        if resource_type == "image":
                            # 缩放图片到指定尺寸（使用快速缩放避免像素图模糊）
                            scaled_pixmap = pixmap.scaled(
                                tile_size,
                                tile_size,
                                Qt.AspectRatioMode.IgnoreAspectRatio,
                                Qt.TransformationMode.FastTransformation,
                            )
                            # 保存缩放后的图片
                            scaled_pixmap.save(dest_path)
                            width = tile_size
                            height = tile_size
                        else:
                            width = original_width
                            height = original_height
                    else:
                        # 图片加载失败时使用tile_size作为默认尺寸
                        width = tile_size
                        height = tile_size

                    resource_info = {
                        "name": os.path.basename(file_path),
                        "path": relative_path,
                        "resource_type": resource_type,
                        "tile_size": tile_size,
                        "width": width,
                        "height": height,
                        "frames": 1,
                    }

                    # 添加图块尺寸信息
                    resource_info["tile_width"] = tile_size
                    resource_info["tile_height"] = tile_size

                    print(
                        f"DEBUG: 资源上传 - 名称: {resource_info['name']}, 类型: {resource_type}, 尺寸: {width}x{height}, tile_width: {resource_info.get('tile_width', 0)}"
                    )

                    # 添加到资源列表
                    self.uploaded_resources.append(resource_info)

                    # 更新地图模型的全局tile_size
                    self.map_model.set_tile_size(tile_size)

                    # 更新画布管理器的tile_size
                    if self.canvas_manager:
                        self.canvas_manager.tile_size = tile_size

                    # 添加到地图模型的tile_sets中
                    if self.project_manager and self.current_map_path:
                        map_dir = os.path.dirname(self.current_map_path)
                        full_image_path = os.path.join(map_dir, relative_path)
                        # 统一使用用户设置的tile_size作为图块尺寸
                        self.map_model.add_tile_set(
                            name=resource_info["name"],
                            image_path=full_image_path,
                            tile_width=tile_size,
                            tile_height=tile_size,
                        )

            # 更新资源列表显示
            self._update_res_list_display()

            # 自动保存地图（如果当前地图有文件路径）
            if self.current_map_path:
                print(f"DEBUG: 资源上传后自动保存地图到: {self.current_map_path}")
                save_result = self.map_model.save(self.current_map_path)
                print(f"DEBUG: 保存结果: {save_result}")

    def select_resource(self, index):
        """选择资源"""
        try:
            if 0 <= index < len(self.uploaded_resources):
                self.selected_resource_index = index
                resource = self.uploaded_resources[index]

                if resource["resource_type"] == "tileset":
                    # tileset资源默认选择第一个图块
                    self.selected_tile_index = 0
                else:
                    # 单张图片模式，设置默认图块索引为0
                    self.selected_tile_index = 0

                # 更新碰撞编辑器显示
                self.set_current_collision_tile(index, self.selected_tile_index)

                # 更新预览
                self._remove_preview()
                if self.canvas_manager:
                    cursor_pos = self.canvas_manager.mapFromGlobal(QCursor.pos())
                    self._update_preview(cursor_pos)

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

                # 更新碰撞编辑器显示
                self.set_current_collision_tile(resource_index, tile_index)

                # 更新资源列表显示
                self._update_res_list_display()
        except Exception as e:
            print(f"选择图块错误: {e}")

    def _update_res_list_display(self):
        """更新资源列表显示"""
        if not self.res_list_view:
            return

        # 清理旧的资源项和图块项
        self._clear_resource_items()

        # 创建场景
        scene = QGraphicsScene()
        # 设置新场景到资源列表视图
        self.res_list_view.setScene(scene)

        # 添加资源到场景
        y_pos = 0  # 移除顶部边距

        for i, resource in enumerate(self.uploaded_resources):
            try:
                # 加载原始图片（处理相对路径）
                image_path = resource["path"]
                if not os.path.isabs(image_path):
                    if self.current_map_path:
                        map_dir = os.path.dirname(self.current_map_path)
                        image_path = os.path.join(map_dir, image_path)

                # 检查文件是否存在
                if not os.path.exists(image_path):
                    print(f"⚠️ 资源文件不存在: {image_path}")
                    continue

                original_pixmap = QPixmap(image_path)
                if original_pixmap.isNull():
                    print(f"⚠️ 资源图片加载失败: {image_path}")
                    continue

                # 获取资源类型和图块尺寸
                resource_type = resource.get("resource_type", "image")
                tile_size = resource.get("tile_size", resource.get("tile_width", 16))

                # 计算图块数量（仅图块集合模式）
                image_width = original_pixmap.width()
                image_height = original_pixmap.height()
                tiles_per_row = 0
                tiles_per_col = 0

                if resource_type == "tileset":
                    # 修复：兼容图片尺寸小于图块尺寸的情况
                    tiles_per_row = max(1, image_width // tile_size)
                    tiles_per_col = max(1, image_height // tile_size)

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
                            # 添加到资源列表图块项管理列表
                            self.resource_tile_items[(i, tile_index)] = tile_item
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
        self.res_list_view.update()  # 添加 update() 方法调用，确保视图刷新
        # 自动滚动到顶部，确保用户可以看到导入的图片
        self.res_list_view.verticalScrollBar().setValue(0)

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
        # 绑定碰撞编辑器相关控件
        if hasattr(self.ui, "map_collision"):
            self.ui.map_collision.toggled.connect(self.set_collision_enabled)
        # 绑定标签输入框
        if hasattr(self.ui, "att_tag"):
            self.ui.att_tag.textChanged.connect(self._on_tag_changed)
        # 设置初始工具状态
        self.set_current_tool(self.current_tool)
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

        # 切换到移动或擦除模式时移除预览图
        if tool == "erase" or tool == "move":
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
