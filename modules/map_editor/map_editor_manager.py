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
from .map_canvas_manager import MapCanvas
from .collision_manager import CollisionManager
from .property_manager import PropertyManager


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
        self.scene = None

    def setScene(self, scene):
        """设置场景引用"""
        self.scene = scene

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
                        print(f"DEBUG: TileItem点击 - 资源: {self.resource_info.get('name', 'unknown')}, 图块索引: {self.tile_index}")
                        self.manager.select_tile(self.resource_info, self.tile_index)
            # 调用父类方法，但也要检查父类是否存在
            try:
                super().mousePressEvent(event)
            except Exception:
                pass
        except Exception as e:
            print(f"图块点击事件错误: {e}")
            import traceback
            traceback.print_exc()

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
            # 先从场景中移除
            if self.scene:
                try:
                    self.scene.removeItem(self)
                except Exception as e:
                    print(f"从场景移除TileItem错误: {e}")
            # 再调用父类方法
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
        self.scene = None
        # 设置选中状态的样式
        self.setBrush(Qt.NoBrush)
        self.setPen(QPen(QColor(200, 200, 200), 1))

    def setScene(self, scene):
        """设置场景引用"""
        self.scene = scene

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
                    print(f"DEBUG: ResourceItem点击 - 资源索引: {self.index}, 资源: {self.resource_info.get('name', 'unknown')}")
                    self.manager.select_resource(self.index)
            # 调用父类方法，但也要检查父类是否存在
            try:
                super().mousePressEvent(event)
            except Exception:
                pass
        except Exception as e:
            print(f"资源点击事件错误: {e}")
            import traceback
            traceback.print_exc()

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
        # 先从场景中移除
        if self.scene:
            try:
                self.scene.removeItem(self)
            except Exception as e:
                print(f"从场景移除ResourceItem错误: {e}")


class MapEditorManager(QObject):
    """地图编辑器管理器，负责地图编辑的核心逻辑"""

    # 信号定义
    map_loaded = Signal(str)  # 地图加载完成信号
    map_saved = Signal(str)  # 地图保存完成信号
    map_renamed = Signal()  # 地图重命名完成信号
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

        # 初始化碰撞管理器和属性管理器
        self.collision_manager = CollisionManager(self.map_model, self)
        self.property_manager = PropertyManager(self.map_model)

        # 设置图块图像获取函数
        self.collision_manager.set_tile_pixmap_provider(
            self._get_tile_pixmap_for_collision
        )

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

        # 移除瓦片选中信号，避免信号错误

    def __del__(self):
        """清理资源，避免程序退出时崩溃"""
        try:
            # 移除场景事件过滤器
            if hasattr(self, "canvas_scene") and self.canvas_scene:
                try:
                    self.canvas_scene.removeEventFilter(self)
                except Exception as e:
                    print(f"DEBUG: 移除画布场景事件过滤器错误: {e}")
            
            # 不要在这里清理collision_manager，让它自己的__del__方法处理
            # 只清除引用，避免重复清理
            if hasattr(self, "collision_manager"):
                self.collision_manager = None
        except Exception as e:
            print(f"DEBUG: 清理资源错误: {e}")

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
        # 初始化网格纹理以适应瓦片尺寸
        self.canvas_manager._init_grid_texture()

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

    def eventFilter(self, obj, event):
        """场景事件过滤器，确保绘制事件被正确处理"""
        try:
            # 检查对象是否有效
            if not obj or not event:
                return super().eventFilter(obj, event)

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
        except Exception:
            # 避免在程序退出时崩溃
            return False

    def _clear_resource_items(self):
        """清理资源项（只清理资源列表视图中的项，不清理地图画布上的图块）"""
        try:
            print("DEBUG: 开始清理资源项")
            # 从资源列表视图场景中移除所有资源项
            if self.res_list_view:
                print("DEBUG: res_list_view 存在")
                scene = self.res_list_view.scene()
                if scene:
                    print(f"DEBUG: 场景存在，资源项数量: {len(self.resource_items)}, 图块项数量: {len(self.resource_tile_items)}")
                    # 从场景中移除所有资源项
                    for i, resource_item in enumerate(self.resource_items):
                        try:
                            print(f"DEBUG: 移除资源项 {i}")
                            scene.removeItem(resource_item)
                            resource_item.is_deleted = True
                        except Exception as e:
                            print(f"从场景移除资源项错误: {e}")

                    # 从场景中移除所有资源列表视图中的图块项
                    for i, (key, tile_item) in enumerate(self.resource_tile_items.items()):
                        try:
                            print(f"DEBUG: 移除图块项 {i}, 键: {key}")
                            scene.removeItem(tile_item)
                            tile_item.is_deleted = True
                        except Exception as e:
                            print(f"从场景移除资源列表图块项错误: {e}")

        except Exception as e:
            print(f"清理资源项和图块项错误: {e}")
            import traceback
            traceback.print_exc()

        # 清空列表
        print("DEBUG: 清空资源项和图块项列表")
        self.resource_items.clear()
        self.resource_tile_items.clear()
        print(f"DEBUG: 清理完成，资源项数量: {len(self.resource_items)}, 图块项数量: {len(self.resource_tile_items)}")

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

                # 清空上传资源列表，准备重新加载
                self.uploaded_resources.clear()

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
                # 清空上传资源列表，准备重新加载
                self.uploaded_resources.clear()
                
                for i, tile_set in enumerate(tile_sets):
                    resource_name = tile_set.get("name")
                    image_path = tile_set.get("image_path")
                    
                    # 修复：确保tile_width/tile_height有默认值
                    tile_width = tile_set.get("tile_width", 16)
                    tile_height = tile_set.get("tile_height", 16)
                    resource_type = "tileset" if tile_width and tile_height else "image"
                    
                    # 初始化资源信息
                    resource_info = {
                        "name": resource_name,
                        "path": "",  # 默认空路径
                        "resource_type": resource_type,
                        "tile_width": tile_width,
                        "tile_height": tile_height,
                        "tile_size": tile_width if resource_type == "tileset" else tile_width,
                        "width": tile_width,  # 默认宽度
                        "height": tile_height,  # 默认高度
                        "frames": 1,
                    }
                    if resource_type == "tileset":
                        resource_info["tiles"] = []
                        # 从tile_set中获取碰撞形状数据
                        tiles_data = tile_set.get("tiles", [])
                        # 初始化collisions数组
                        resource_info["collisions"] = []
                        for j, tile_data in enumerate(tiles_data):
                            # 确保collisions数组足够大
                            while len(resource_info["collisions"]) <= j:
                                resource_info["collisions"].append({})
                            # 保存碰撞形状数据
                            if "collision_shape" in tile_data and tile_data["collision_shape"]:
                                resource_info["collisions"][j]["points"] = tile_data["collision_shape"].get("points", [])
                    
                    # 尝试加载图片
                    if image_path:
                        # 修复：优先使用绝对路径，避免相对路径解析错误
                        if not os.path.isabs(image_path):
                            image_path = os.path.join(map_dir, image_path)

                        # 检查文件是否存在
                        if os.path.exists(image_path):
                            # 加载图片获取真实尺寸
                            from PySide6.QtGui import QPixmap

                            pixmap = QPixmap(image_path)
                            if not pixmap.isNull():
                                resource_info["path"] = os.path.relpath(image_path, map_dir)  # 存储相对路径
                                resource_info["width"] = pixmap.width()
                                resource_info["height"] = pixmap.height()
                            else:
                                print(f"⚠️ 图片加载失败: {image_path}")
                        else:
                            print(f"⚠️ 图片文件不存在: {image_path}")
                    else:
                        print(f"⚠️ 瓦片集{resource_name}无图片路径")
                    
                    # 无论图片是否加载成功，都添加到资源列表中，确保与tile_sets顺序一致
                    self.uploaded_resources.append(resource_info)

                # 更新资源列表和画布
                self._update_res_list_display()
                # 地图加载完成后强制完整渲染一次，确保所有瓦片都显示
                self._render_full_map()
                
                # 更新属性面板中的地图名称
                if hasattr(self, "ui") and hasattr(self.ui, "att_map_name"):
                    map_name = self.property_manager.get_map_name()
                    self.ui.att_map_name.blockSignals(True)
                    self.ui.att_map_name.setText(map_name)
                    self.ui.att_map_name.blockSignals(False)
                
                # 更新属性面板中的地图尺寸
                self._update_map_size_display()
                
                # 更新属性面板中的瓦片大小
                self._update_tile_size_display()
            else:
                self.error_occurred.emit("加载地图失败")

    def save_map(self):
        """保存地图"""
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

            # 保存地图数据
            if self.map_model.save(file_path):
                self.current_map_path = file_path
                self.is_map_modified = False
                self.map_saved.emit(file_path)
            else:
                self.error_occurred.emit("保存地图失败")

    def load_map(self):
        """加载地图"""
        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            None, "加载地图", "", "Map Files (*.info *.json)"
        )

        if file_path:
            if self.map_model.load(file_path):
                self.current_map_path = file_path
                self.is_map_modified = False
                self.map_loaded.emit(file_path)

                self._update_canvas()
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

        # 检查地图尺寸是否变化，如果变化了就更新显示
        current_width, current_height = self.map_model.get_map_size()
        if not hasattr(self, '_last_map_size') or self._last_map_size != (current_width, current_height):
            self._update_map_size_display()
            self._last_map_size = (current_width, current_height)

        # 清除变化记录
        self.map_model.clear_changed_area()

    def _update_canvas(self):
        """更新画布显示"""
        if self.canvas_manager and self.map_model:
            # 使用视口裁剪渲染，提高性能
            self._render_map()

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
                # 图块集合模式，图块ID格式：(resource_index + 1) * 1000 + tile_index + 1
                if tile_id // 1000 == resource_index + 1:
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
                # 单张图片模式，图块ID格式：(resource_index + 1) * 1000 + 1
                if tile_id == (resource_index + 1) * 1000 + 1:
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

    def _render_full_map(self):
        """渲染整个地图，不使用视口裁剪"""
        try:
            if not self.canvas_manager or not self.map_model:
                return

            scene = self.canvas_manager.scene()
            if not scene:
                return

            # 获取当前图层数据
            layer = self.map_model.get_layer(self.current_layer)
            if not layer or not layer.get("visible", True):
                print(f"警告: 图层 {self.current_layer} 不可见或不存在")
                return

            # 清理所有现有的瓦片项
            for item in list(self.tile_items.values()):
                self._recycle_item(item)
            self.tile_items.clear()

            # 获取图层中的所有瓦片数据
            tiles = layer.get("tiles", {})

            # 渲染所有瓦片
            for (tx, ty), tile_id in tiles.items():
                if tile_id > 0:
                    self._update_single_tile(tx, ty, tile_id)

            print(f"✅ 完整地图渲染完成，瓦片数量: {len(tiles)}")

        except Exception as e:
            print(f"完整地图渲染失败: {e}")
            import traceback

            traceback.print_exc()

    def _render_map(self):
        """根据模型数据渲染视口内的地图图层"""
        try:
            scene = self.canvas_manager.scene()

            # 获取视口范围
            view_rect = self.canvas_manager.viewport().rect()
            scene_rect = self.canvas_manager.mapToScene(view_rect).boundingRect()

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
            if not self.canvas_manager or not self.map_model:
                return
                
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
            if not self.canvas_manager or not self.map_model:
                return
                
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
                # 格式：(resource_index + 1) * 1000 + tile_index + 1
                # 这样确保图块集模式的tile_id始终大于等于1000，避免与单张图片模式混淆
                tile_index = self.selected_tile_index
                # 如果没有选择图块索引，使用默认值0
                if tile_index < 0:
                    tile_index = 0

                tile_id = (self.selected_resource_index + 1) * 1000 + tile_index + 1
                print(f"DEBUG: 图块集模式 - 生成tile_id: {tile_id}")
            else:
                # 单张图片模式，使用统一的资源ID格式
                tile_id = (self.selected_resource_index + 1) * 1000 + 1
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
            # 检查 canvas_manager 是否存在
            if not self.canvas_manager:
                return

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
        self.collision_manager.initialize_collision_editor(col_editor_view)

    def set_current_collision_tile(self, resource_index, tile_index):
        """设置当前选中的碰撞图块"""
        try:
            print(f"DEBUG: 开始设置当前碰撞图块 - 资源索引: {resource_index}, 图块索引: {tile_index}")
            
            # 检查参数有效性
            if resource_index < 0:
                print("DEBUG: 资源索引无效: {resource_index}")
                return
            
            if not hasattr(self, 'uploaded_resources'):
                print("DEBUG: uploaded_resources 不存在")
                return
            
            if resource_index >= len(self.uploaded_resources):
                print(f"DEBUG: 资源索引越界 - 资源索引: {resource_index}, 资源数量: {len(self.uploaded_resources)}")
                return
            
            # 调用碰撞管理器设置当前碰撞图块
            print(f"DEBUG: 调用 collision_manager.set_current_collision_tile")
            if hasattr(self, 'collision_manager'):
                self.collision_manager.set_current_collision_tile(
                    resource_index, tile_index
                )
                print("DEBUG: collision_manager.set_current_collision_tile 调用成功")
            else:
                print("DEBUG: collision_manager 不存在")
            
            # 调用属性管理器设置当前瓦片
            print(f"DEBUG: 调用 property_manager.set_current_tile")
            if hasattr(self, 'property_manager'):
                self.property_manager.set_current_tile(resource_index, tile_index)
                print("DEBUG: property_manager.set_current_tile 调用成功")
            else:
                print("DEBUG: property_manager 不存在")
            
            # 更新map_collision checkbox的状态
            print(f"DEBUG: 更新 map_collision checkbox 状态")
            if hasattr(self, "ui") and hasattr(self.ui, "map_collision"):
                if self.map_model:
                    collision_enabled = self.map_model.get_tile_collision(
                        resource_index, tile_index
                    )
                    print(f"DEBUG: 碰撞启用状态: {collision_enabled}")
                    self.ui.map_collision.setChecked(collision_enabled)
                    print("DEBUG: map_collision checkbox 状态更新成功")
                else:
                    print("DEBUG: map_model 不存在")
            else:
                print("DEBUG: ui 或 map_collision 不存在")

            # 更新标签输入框的状态
            print(f"DEBUG: 更新标签输入框状态")
            if hasattr(self, "ui") and hasattr(self.ui, "att_tag"):
                if self.map_model:
                    tile_tag = self.map_model.get_tile_tag(resource_index, tile_index)
                    print(f"DEBUG: 瓦片标签: {tile_tag}")
                    # 阻塞信号，防止触发标签变化处理
                    self.ui.att_tag.blockSignals(True)
                    self.ui.att_tag.setText(tile_tag)
                    self.ui.att_tag.blockSignals(False)
                    print("DEBUG: 标签输入框状态更新成功")
                else:
                    print("DEBUG: map_model 不存在")
            else:
                print("DEBUG: ui 或 att_tag 不存在")
            
            # 更新碰撞类型选择框的状态
            print(f"DEBUG: 更新碰撞类型选择框状态")
            if hasattr(self, "ui") and hasattr(self.ui, "att_col_type"):
                if self.map_model:
                    collision_enabled = self.map_model.get_tile_collision(resource_index, tile_index)
                    print(f"DEBUG: 碰撞启用状态: {collision_enabled}")
                    # 根据碰撞状态设置碰撞类型
                    # 墙体 -> 碰撞开启
                    # 其他类型 -> 碰撞关闭
                    self.ui.att_col_type.blockSignals(True)
                    if collision_enabled:
                        self.ui.att_col_type.setCurrentText("墙体")
                        print("DEBUG: 碰撞类型设置为: 墙体")
                    else:
                        self.ui.att_col_type.setCurrentText("背景")
                        print("DEBUG: 碰撞类型设置为: 背景")
                    self.ui.att_col_type.blockSignals(False)
                    print("DEBUG: 碰撞类型选择框状态更新成功")
                else:
                    print("DEBUG: map_model 不存在")
            else:
                print("DEBUG: ui 或 att_col_type 不存在")
                
            print("DEBUG: 设置当前碰撞图块完成")
        except Exception as e:
            print(f"DEBUG: 设置当前碰撞图块错误: {e}")
            import traceback
            traceback.print_exc()

    def set_collision_enabled(self, enabled):
        """设置碰撞启用状态"""
        self.collision_manager.set_collision_enabled(enabled)

    def set_collision_snap_to_pixel(self, enabled):
        """设置碰撞锚点是否吸附到像素网格"""
        self.collision_manager.set_snap_to_pixel(enabled)

    def _on_tag_changed(self, tag):
        """处理标签变化"""
        self.property_manager.set_tile_tag(tag)
        
    def _on_col_type_changed(self):
        """处理碰撞类型变化"""
        if not hasattr(self, "ui") or not hasattr(self.ui, "att_col_type"):
            return
            
        # 获取选择的碰撞类型
        col_type = self.ui.att_col_type.currentText()
        print(f"碰撞类型变化: {col_type}")
        
        # 根据碰撞类型设置碰撞状态
        # 墙体 -> 碰撞开启
        # 其他类型 -> 碰撞关闭
        collision_enabled = col_type == "墙体"
        
        # 设置碰撞状态
        self.property_manager.set_tile_collision(collision_enabled)
        
    def _on_map_name_changed(self, name):
        """处理地图名称变化"""
        print(f"=== 地图名称变化: {name} ===")
        print(f"当前地图路径: {self.current_map_path}")
        
        # 更新地图模型中的名称
        self.property_manager.set_map_name(name)
        print(f"地图模型名称已更新: {self.property_manager.get_map_name()}")
        
        # 如果有当前地图路径，更新目录名称
        if self.current_map_path:
            print(f"开始重命名目录...")
            self._rename_map_directory(name)
            print(f"重命名后路径: {self.current_map_path}")
            
            # 保存前打印地图数据
            print(f"保存前地图数据:")
            print(f"  尺寸: {self.map_model.get_map_size()}")
            print(f"  图层数: {self.map_model.get_layer_count()}")
            for i, layer in enumerate(self.map_model.map_data['layers']):
                print(f"  图层 {i}: {len(layer['tiles'])} 个瓦片")
            
            # 重命名后保存地图数据到新的文件路径
            print(f"开始保存地图...")
            self.save_map()
            print(f"地图保存完成")
            
            # 发出地图重命名完成信号，通知资源管理器刷新地图列表
            self.map_renamed.emit()
            
    def _update_map_size_display(self):
        """更新属性面板中的地图尺寸显示"""
        if hasattr(self, "ui"):
            # 获取地图尺寸
            width, height = self.map_model.get_map_size()
            
            # 更新地图宽度显示
            if hasattr(self.ui, "att_mapsize_x"):
                self.ui.att_mapsize_x.blockSignals(True)
                self.ui.att_mapsize_x.setText(str(width))
                self.ui.att_mapsize_x.setReadOnly(True)
                self.ui.att_mapsize_x.blockSignals(False)
            
            # 更新地图高度显示
            if hasattr(self.ui, "att_mapsize_y"):
                self.ui.att_mapsize_y.blockSignals(True)
                self.ui.att_mapsize_y.setText(str(height))
                self.ui.att_mapsize_y.setReadOnly(True)
                self.ui.att_mapsize_y.blockSignals(False)
    
    def _update_tile_size_display(self):
        """更新属性面板中的瓦片大小显示"""
        if hasattr(self, "ui") and hasattr(self.ui, "att_tile_size"):
            # 获取当前瓦片大小
            tile_size = self.map_model.get_tile_size()
            
            # 查找匹配的瓦片大小选项
            for i in range(self.ui.att_tile_size.count()):
                item_text = self.ui.att_tile_size.itemText(i)
                if item_text.startswith(f"{tile_size}x"):
                    self.ui.att_tile_size.blockSignals(True)
                    self.ui.att_tile_size.setCurrentIndex(i)
                    self.ui.att_tile_size.blockSignals(False)
                    break
    
    def _on_tile_size_changed(self):
        """处理瓦片尺寸变化事件"""
        if not hasattr(self, "ui") or not hasattr(self.ui, "att_tile_size"):
            return
            
        # 获取新的瓦片尺寸
        size_text = self.ui.att_tile_size.currentText()
        new_tile_size = int(size_text.split("x")[0])
        
        # 如果尺寸没有变化，不进行处理
        if self.map_model.get_tile_size() == new_tile_size:
            return
            
        print(f"DEBUG: 瓦片尺寸变化: {self.map_model.get_tile_size()} -> {new_tile_size}")
        
        # 更新地图模型的全局tile_size（这是格子大小，不是图块大小）
        self.map_model.set_tile_size(new_tile_size)
        
        # 更新画布管理器的tile_size（网格大小）
        if self.canvas_manager:
            self.canvas_manager.tile_size = new_tile_size
            # 重新初始化网格纹理以适应新的瓦片尺寸
            self.canvas_manager._init_grid_texture()
            # 强制重新渲染地图
            self._render_full_map()
            # 更新视图
            self.canvas_manager.viewport().update()
        
        # 注意：不重新切割图块，不修改资源和tile_sets的尺寸属性
        # 图块保持原来的大小和位置，只有格子大小发生变化
        
        # 更新资源列表显示（刷新视图）
        self._update_res_list_display()
        
        # 自动保存地图
        if self.current_map_path:
            print(f"DEBUG: 瓦片尺寸变化后自动保存地图到: {self.current_map_path}")
            save_result = self.map_model.save(self.current_map_path)
            print(f"DEBUG: 保存结果: {save_result}")

    def _get_tile_pixmap_for_collision(self, resource_index, tile_index):
        """为碰撞管理器提供图块图像"""
        if resource_index < 0 or resource_index >= len(self.uploaded_resources):
            return None

        resource = self.uploaded_resources[resource_index]
        
        # 获取图块图像
        pixmap = None
        if resource["resource_type"] == "tileset":
            tile_id = (resource_index + 1) * 1000 + tile_index + 1
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

        return pixmap
        
    def _rename_map_directory(self, new_name):
        """重命名地图目录和内部文件"""
        try:
            # 获取当前地图目录路径
            current_dir = os.path.dirname(self.current_map_path)
            parent_dir = os.path.dirname(current_dir)
            old_dir_name = os.path.basename(current_dir)
            
            # 创建新的目录名称
            new_dir_name = new_name
            new_dir_path = os.path.join(parent_dir, new_dir_name)
            
            # 如果目录名称没有变化，不需要重命名
            if old_dir_name == new_dir_name:
                return
                
            # 检查新目录是否已存在
            if os.path.exists(new_dir_path):
                print(f"⚠️ 目录已存在: {new_dir_path}")
                return
                
            # 获取当前地图文件名（不带扩展名）
            old_filename = os.path.basename(self.current_map_path)
            old_base_name = os.path.splitext(old_filename)[0]
            
            # 创建新的文件名
            new_base_name = new_name
            new_filename = f"{new_base_name}.info"
            
            # 更新地图模型中瓦片集的路径（将旧目录名替换为新目录名）
            old_tilesets_path = os.path.join(current_dir, "tilesets")
            new_tilesets_path = os.path.join(new_dir_path, "tilesets")
            
            for tile_set in self.map_model.map_data["tile_sets"]:
                image_path = tile_set.get("image_path", "")
                if image_path:
                    # 如果路径包含旧目录名，替换为新目录名
                    if old_tilesets_path in image_path:
                        new_image_path = image_path.replace(old_tilesets_path, new_tilesets_path)
                        tile_set["image_path"] = new_image_path
                        print(f"✅ 更新瓦片集路径: {image_path} -> {new_image_path}")
            
            # 重命名目录内的所有相关文件
            for ext in [".info", ".tiles", ".collision", ".resources"]:
                old_file_path = os.path.join(current_dir, f"{old_base_name}{ext}")
                new_file_path = os.path.join(current_dir, f"{new_base_name}{ext}")
                if os.path.exists(old_file_path):
                    os.rename(old_file_path, new_file_path)
                    print(f"✅ 文件重命名成功: {old_base_name}{ext} -> {new_base_name}{ext}")
            
            # 重命名目录
            os.rename(current_dir, new_dir_path)
            print(f"✅ 目录重命名成功: {old_dir_name} -> {new_dir_name}")
            
            # 更新当前地图路径
            self.current_map_path = os.path.join(new_dir_path, new_filename)
            print(f"✅ 更新地图路径: {self.current_map_path}")
            
        except Exception as e:
            print(f"❌ 目录重命名失败: {e}")

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
            
        # 直接调用系统文件选择器
        from PySide6.QtWidgets import QFileDialog
        
        files, _ = QFileDialog.getOpenFileNames(
            self.parent(),
            "选择图像资源",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp);;所有文件 (*)",
        )
        
        if not files:
            return
            
        # 获取属性面板中选择的瓦片尺寸
        tile_size = 32  # 默认值
        if hasattr(self, "ui") and hasattr(self.ui, "att_tile_size"):
            size_text = self.ui.att_tile_size.currentText()
            tile_size = int(size_text.split("x")[0])
        
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

                # 获取图片尺寸并进行切割处理
                from PySide6.QtGui import QPixmap
                
                # 初始化默认值
                width = tile_size
                height = tile_size
                resource_type = "tileset"

                # 使用复制后的文件路径加载图片
                pixmap = QPixmap(dest_path)
                if not pixmap.isNull():
                    original_width = pixmap.width()
                    original_height = pixmap.height()
                    width = original_width
                    height = original_height

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

        # 更新地图模型的全局tile_size
        self.map_model.set_tile_size(tile_size)

        # 更新画布管理器的tile_size
        if self.canvas_manager:
            self.canvas_manager.tile_size = tile_size

        # 清理缓存，确保新上传的资源能正确加载
        self._pixmap_cache.clear()
        self._source_image_cache.clear()

        # 更新资源列表显示
        self._update_res_list_display()

        # 强制重新渲染地图，确保新上传的图块能正常显示
        self._render_full_map()

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
            print(f"DEBUG: 开始选择图块 - resource_info: {resource_info}, tile_index: {tile_index}")
            
            # 检查参数有效性
            if resource_info is None:
                print("DEBUG: resource_info 为 None，选择图块失败")
                return
            
            if not hasattr(self, 'uploaded_resources'):
                print("DEBUG: uploaded_resources 不存在，选择图块失败")
                return
            
            # 查找资源索引
            resource_index = -1
            print(f"DEBUG: uploaded_resources 长度: {len(self.uploaded_resources)}")
            for i, res in enumerate(self.uploaded_resources):
                print(f"DEBUG: 检查资源 {i}: {res.get('name', 'unknown')}")
                if res == resource_info:
                    resource_index = i
                    print(f"DEBUG: 找到资源索引: {resource_index}")
                    break

            if resource_index != -1:
                self.selected_resource_index = resource_index
                self.selected_tile_index = tile_index
                print(
                    f"DEBUG: 选中图块: 资源={resource_info['name']}, 图块索引={tile_index}, 资源索引={resource_index}"
                )
                
                # 确保资源的碰撞数据结构存在
                if 'collisions' not in resource_info:
                    print("DEBUG: 资源中不存在 collisions 字段，创建新的")
                    resource_info['collisions'] = []
                # 确保collisions数组足够大
                while len(resource_info['collisions']) <= tile_index:
                    print(f"DEBUG: collisions 数组长度不足，添加新元素")
                    resource_info['collisions'].append({})
                
                # 从地图模型获取最新的碰撞形状数据
                if self.map_model:
                    print(f"DEBUG: 从地图模型获取碰撞形状 - 资源索引: {resource_index}, 图块索引: {tile_index}")
                    collision_shape = self.map_model.get_tile_collision_shape(resource_index, tile_index)
                    print(f"DEBUG: 获取到的碰撞形状: {collision_shape}")
                    if collision_shape and 'points' in collision_shape:
                        resource_info['collisions'][tile_index]['points'] = collision_shape['points']
                        print(f"DEBUG: 从地图模型同步碰撞形状数据: {collision_shape}")
                else:
                    print("DEBUG: map_model 不存在")
                
                # 打印当前内存中的碰撞形状类型
                if 'collisions' in resource_info and tile_index < len(resource_info['collisions']):
                    collision_data = resource_info['collisions'][tile_index]
                    if 'points' in collision_data:
                        print(f"DEBUG: 当前内存中的碰撞形状类型是: polygon, 顶点数: {len(collision_data['points'])}")
                    else:
                        print(f"DEBUG: 当前内存中的碰撞形状类型是: default rectangle")
                else:
                    print("DEBUG: 无法访问碰撞数据")

                # 更新碰撞编辑器显示
                print(f"DEBUG: 调用 set_current_collision_tile - 资源索引: {resource_index}, 图块索引: {tile_index}")
                self.set_current_collision_tile(resource_index, tile_index)
            else:
                print(f"DEBUG: 资源未找到 - resource_info: {resource_info}")
            
            # 更新资源列表显示
            print(f"DEBUG: 更新资源列表显示")
            self._update_res_list_display()
        except Exception as e:
            print(f"DEBUG: 选择图块错误: {e}")
            import traceback
            traceback.print_exc()

    def _update_res_list_display(self):
        """更新资源列表显示"""
        try:
            print("DEBUG: 开始更新资源列表显示")
            if not self.res_list_view:
                print("DEBUG: res_list_view 不存在，返回")
                return

            # 清理旧的资源项和图块项
            print("DEBUG: 清理旧的资源项和图块项")
            self._clear_resource_items()

            # 获取旧场景并清理
            print("DEBUG: 获取旧场景并清理")
            old_scene = self.res_list_view.scene()
            if old_scene:
                # 清除旧场景中的所有项
                old_scene.clear()
                print("DEBUG: 旧场景已清理")
            
            # 创建场景
            print("DEBUG: 创建新场景")
            scene = QGraphicsScene()
            # 设置新场景到资源列表视图
            print("DEBUG: 设置场景到资源列表视图")
            self.res_list_view.setScene(scene)

            # 添加资源到场景
            y_pos = 0  # 移除顶部边距
            print(f"DEBUG: 开始添加资源，资源数量: {len(self.uploaded_resources)}")

            for i, resource in enumerate(self.uploaded_resources):
                try:
                    print(f"DEBUG: 处理资源 {i}: {resource.get('name', 'unknown')}")
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
                        print(f"DEBUG: 图块集合 - 行列数: {tiles_per_row}x{tiles_per_col}")

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
                    print(f"DEBUG: 图片位置: ({pixmap_x}, {pixmap_y})")

                    # 添加缩放后的图片
                    pixmap_item = QGraphicsPixmapItem(scaled_pixmap)
                    pixmap_item.setPos(pixmap_x, pixmap_y)
                    scene.addItem(pixmap_item)

                    # 绘制图块网格或创建单张图片的可点击区域
                    if resource_type == "tileset":
                        for row in range(tiles_per_col):
                            for col in range(tiles_per_row):
                                tile_index = row * tiles_per_row + col
                                print(f"DEBUG: 创建图块 {tile_index} (行: {row}, 列: {col})")

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
                                    print(f"DEBUG: 图块 {tile_index} 被选中")
                                else:
                                    tile_rect.setPen(QPen(QColor(200, 200, 200), 1))
                                    tile_rect.setBrush(Qt.NoBrush)

                                scene.addItem(tile_rect)

                                # 创建图块项（用于点击事件）
                                tile_item = TileItem(
                                    tile_rect.rect(), resource, tile_index, self
                                )
                                # 设置场景引用
                                tile_item.setScene(scene)
                                scene.addItem(tile_item)
                                # 添加到资源列表图块项管理列表
                                self.resource_tile_items[(i, tile_index)] = tile_item
                                print(f"DEBUG: 添加图块项到管理列表，键: ({i}, {tile_index})")
                    else:
                        # 单张图片模式，创建可点击的资源项
                        # 直接创建 ResourceItem，不需要额外的 QGraphicsRectItem
                        resource_item = ResourceItem(
                            QRectF(pixmap_x, pixmap_y, scaled_width, scaled_height),
                            resource,
                            i,
                            self,
                        )
                        # 设置场景引用
                        resource_item.setScene(scene)

                        # 检查是否是选中的资源
                        is_resource_selected = i == self.selected_resource_index
                        if is_resource_selected:
                            resource_item.setBrush(QBrush(QColor(100, 149, 237, 50)))
                            resource_item.setPen(Qt.NoPen)
                            print(f"DEBUG: 资源 {i} 被选中")

                        scene.addItem(resource_item)
                        self.resource_items.append(resource_item)
                        print(f"DEBUG: 添加资源项到管理列表")

                    # 更新位置 - 根据实际图片高度调整间距
                    y_pos += scaled_height
                    print(f"DEBUG: 更新位置到: {y_pos}")

                except Exception as e:
                    print(f"创建资源缩略图失败: {e}")
                    import traceback
                    traceback.print_exc()

            # 设置场景大小
            scene_height = max(500, y_pos)
            scene.setSceneRect(0, 0, 256, scene_height)
            print(f"DEBUG: 设置场景大小: 256x{scene_height}")

            # 设置场景到视图
            self.res_list_view.setScene(scene)
            self.res_list_view.show()
            self.res_list_view.update()  # 添加 update() 方法调用，确保视图刷新
            # 自动滚动到顶部，确保用户可以看到导入的图片
            self.res_list_view.verticalScrollBar().setValue(0)
            print("DEBUG: 资源列表显示更新完成")
        except Exception as e:
            print(f"更新资源列表显示错误: {e}")
            import traceback
            traceback.print_exc()

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
        # 绑定碰撞锚点吸附按钮
        if hasattr(self.ui, "btn_res_col_snap"):
            self.ui.btn_res_col_snap.toggled.connect(self.set_collision_snap_to_pixel)
        # 绑定标签输入框
        if hasattr(self.ui, "att_tag"):
            self.ui.att_tag.textChanged.connect(self._on_tag_changed)
        # 绑定碰撞类型选择框
        if hasattr(self.ui, "att_col_type"):
            self.ui.att_col_type.currentTextChanged.connect(self._on_col_type_changed)
        # 绑定地图名称输入框
        if hasattr(self.ui, "att_map_name"):
            self.ui.att_map_name.textChanged.connect(self._on_map_name_changed)
        # 绑定瓦片尺寸选择框
        if hasattr(self.ui, "att_tile_size"):
            self.ui.att_tile_size.currentIndexChanged.connect(self._on_tile_size_changed)
        # 设置初始工具状态
        self.set_current_tool(self.current_tool)
        print("工具按钮绑定完成")

    def set_current_tool(self, tool):
        """设置当前工具"""
        old_tool = self.current_tool
        self.current_tool = tool
        
        # 当从碰撞模式退出时，强制同步一次模型数据到内存资源池
        if old_tool == "collision":
            self.refresh_resources_from_model()
    
    def refresh_resources_from_model(self):
        """强制从 MapDataModel 同步最新的碰撞数据到 UI 缓存"""
        print("DEBUG: 从地图模型同步资源数据")
        # 遍历所有资源，从地图模型获取最新的碰撞形状数据并更新到资源池缓存
        if self.map_model:
            for resource_index, resource in enumerate(self.uploaded_resources):
                # 检查资源是否是tileset类型
                if resource.get("resource_type") == "tileset":
                    # 从地图模型获取瓦片集
                    tile_set = self.map_model.get_tile_set(resource_index)
                    if tile_set:
                        # 获取瓦片集的瓦片数量
                        tiles = tile_set.get("tiles", [])
                        total_tiles = len(tiles)
                        
                        # 确保collisions数组存在且足够大
                        if "collisions" not in resource:
                            resource["collisions"] = []
                        while len(resource["collisions"]) < total_tiles:
                            resource["collisions"].append({})
                        
                        # 从地图模型获取每个图块的碰撞形状数据
                        for tile_index in range(total_tiles):
                            collision_shape = self.map_model.get_tile_collision_shape(resource_index, tile_index)
                            if collision_shape and "points" in collision_shape:
                                resource["collisions"][tile_index]["points"] = collision_shape["points"]
                                print(f"DEBUG: 同步碰撞形状数据 - 资源索引: {resource_index}, 图块索引: {tile_index}, 形状: {collision_shape}")
                            else:
                                # 如果没有碰撞形状，清除缓存中的数据
                                if "points" in resource["collisions"][tile_index]:
                                    del resource["collisions"][tile_index]["points"]
                                    print(f"DEBUG: 清除碰撞形状数据 - 资源索引: {resource_index}, 图块索引: {tile_index}")
        print("DEBUG: 资源数据同步完成")

        # 更新按钮状态
        if hasattr(self, "ui"):
            self.ui.btn_editor_map_move.setChecked(self.current_tool == "move")
            self.ui.btn_editor_map_draw.setChecked(self.current_tool == "draw")
            self.ui.btn_editor_map_erase.setChecked(self.current_tool == "erase")

        # 切换到移动或擦除模式时移除预览图
        if self.current_tool == "erase" or self.current_tool == "move":
            self._remove_preview()
        # 切换到绘制模式时，如果已选中资源，显示预览
        elif self.current_tool == "draw" and self.selected_resource_index >= 0:
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

    def destroy(self):
        """销毁MapEditorManager，移除事件过滤器"""
        try:
            # 移除画布场景的事件过滤器
            if hasattr(self, 'canvas_scene'):
                try:
                    self.canvas_scene.removeEventFilter(self)
                    print("✅ [MapEditorManager] 画布事件过滤器已移除")
                except:
                    pass
            
            # 清理collision_manager的引用，让它自己的__del__方法处理
            if hasattr(self, 'collision_manager'):
                try:
                    self.collision_manager = None
                    print("✅ [MapEditorManager] collision_manager引用已清除")
                except:
                    pass
        except Exception as e:
            print(f"❌ [MapEditorManager] 清理失败: {e}")
