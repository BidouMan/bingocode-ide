import os
import math
from PySide6.QtCore import QObject, Signal, Qt, QRectF, QPoint, QPointF, QMimeData
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
    QDrag,
    QTransform,
)
from models.map_model import MapDataModel
from .map_canvas_manager import MapCanvas
from .collision_manager import CollisionManager
from .property_manager import PropertyManager
from .layer_manager import LayerManager
from .layer_list_view import LayerListView
from .transform_tool import TransformBoxItem


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
                        print(
                            f"DEBUG: TileItem点击 - 资源: {self.resource_info.get('name', 'unknown')}, 图块索引: {self.tile_index}"
                        )
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
        self.setFlag(QGraphicsRectItem.ItemIsMovable, False)
        self.setFlag(QGraphicsRectItem.ItemSendsScenePositionChanges, True)
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
                # 记录起点
                self.drag_start_pos = event.pos()
                # 检查manager是否有效
                if (
                    hasattr(self, "manager")
                    and self.manager
                    and not getattr(self.manager, "is_deleted", False)
                ):
                    print(
                        f"DEBUG: ResourceItem点击 - 资源索引: {self.index}, 资源: {self.resource_info.get('name', 'unknown')}"
                    )
                    self.manager.select_resource(self.index)
                    # 顺便通知 manager 记录当前索引
                    self.manager.selected_resource_index = self.index
                    print(f"DEBUG: ResourceItem Press - 准备拖拽索引: {self.index}")
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

    def mouseMoveEvent(self, event):
        """处理鼠标移动事件，实现拖拽功能"""
        try:
            # 检查对象是否已删除
            if hasattr(self, "is_deleted") and self.is_deleted:
                return
            # 检查事件是否有效
            if not event:
                return
            # 检查是否按下了左键
            if event.buttons() & Qt.LeftButton:
                # 1. 检查距离
                if not hasattr(self, "drag_start_pos"):
                    return
                if (
                    event.pos() - self.drag_start_pos
                ).manhattanLength() < QApplication.startDragDistance():
                    return

                # 2. 暴力弹窗确认（这是给老师看的证据）
                # from PySide6.QtWidgets import QMessageBox
                # QMessageBox.information(None, "DEBUG", "QDrag 正在启动！")

                # 3. 启动 QDrag
                print(f"🚀 [REAL START] 正在从 Item 启动拖拽: {self.index}")
                mime_data = QMimeData()
                mime_data.setData(
                    "application/x-bingo-resource", str(self.index).encode()
                )

                drag = QDrag(event.widget())
                drag.setMimeData(mime_data)
                drag.setPixmap(
                    self.pixmap().scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio)
                )
                drag.setHotSpot(QPoint(32, 32))

                drag.exec_(Qt.DropAction.CopyAction)
                return
            # 调用父类方法
            super().mouseMoveEvent(event)
        except Exception as e:
            print(f"资源移动事件错误: {e}")
            import traceback

            traceback.print_exc()


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

        # 初始化图层管理器
        self.layer_manager = LayerManager(self.map_model, self)
        self.layer_list_view = None
        # 监听图层变化信号
        self.layer_manager.current_layer_changed.connect(self._on_layer_changed)

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
        # 图层独立的资源管理
        self.layer_resources = {}  # {layer_id: [resources]}
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

        # 图像变换相关
        self.selected_image_data = None  # 当前选中的图像数据
        self.selected_image_index = -1  # 当前选中的图像索引
        self.selected_layer_id = -1  # 当前选中的图层ID

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

        # 图像图层的图像项缓存
        self._image_items = {}  # 格式：{(layer_id, image_index): QGraphicsPixmapItem}

        # 变换框相关
        self.transform_box = None  # 当前的变换框

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
        # 设置父管理器引用
        self.canvas_manager.parent_manager = self
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
        """绑定鼠标事件 - 使用事件过滤器"""
        # ❶ 移除所有直接重写控件事件方法的代码
        # 不再直接重写 canvas_manager 的鼠标事件方法

        # ❷ 正确安装事件过滤器：给 canvas_manager (QGraphicsView) 安装（而非 scene）
        if self.canvas_manager:
            self.canvas_manager.installEventFilter(
                self
            )  # 核心修复：绑定到 View 而非 Scene
            self.canvas_manager.viewport().installEventFilter(
                self
            )  # 兼容 Qt 视图port 事件

        # ❸ 资源列表的事件过滤器保留
        if self.res_list_view:
            self.res_list_view.installEventFilter(self)
            self.res_list_view.viewport().installEventFilter(self)
            self.drag_start_pos = None

        # ❹ 保留原生事件的备份（如果后续需要调用）
        if self.canvas_manager:
            self.original_canvas_mousePress = self.canvas_manager.mousePressEvent
            self.original_canvas_mouseMove = self.canvas_manager.mouseMoveEvent
            self.original_canvas_mouseRelease = self.canvas_manager.mouseReleaseEvent
            self.original_canvas_wheel = self.canvas_manager.wheelEvent

    def eventFilter(self, watched, event):
        try:
            # 检查对象是否有效
            if not watched or not event:
                return super().eventFilter(watched, event)

            from PySide6.QtCore import QEvent

            # ======================
            # 移除前置判断：锚点显示时放行所有事件
            # 因为这会导致点击其他图像时无法切换选择
            # ======================

            # 注意：这里判断的是 viewport 或者 view
            if (
                hasattr(self, "ui")
                and hasattr(self.ui, "res_list_view")
                and self.ui.res_list_view
            ):
                res_list_view = self.ui.res_list_view
                if watched in [res_list_view, res_list_view.viewport()]:
                    if event.type() == QEvent.MouseButtonPress:
                        if event.button() == Qt.LeftButton:
                            self.drag_start_pos = event.pos()
                            print(f"🎯 [DEBUG] 捕获到按下事件: {self.drag_start_pos}")
                        return False  # 必须返回 False，让底层的 ResourceItem 还能被选中

                    elif event.type() == QEvent.MouseMove:
                        if not (event.buttons() & Qt.LeftButton):
                            return False

                        # 这里的距离判断要稳
                        pos_diff = (
                            event.pos() - getattr(self, "drag_start_pos", event.pos())
                        ).manhattanLength()
                        if pos_diff < QApplication.startDragDistance():
                            return False

                        if self.selected_resource_index >= 0:
                            # 强制弹窗，如果没弹窗，就说明 MouseMove 还是没进来！
                            # from PySide6.QtWidgets import QMessageBox
                            # QMessageBox.information(None, "DEBUG", "执行起飞代码")

                            print(
                                f"🚀 [CRITICAL] 启动拖拽流程，资源: {self.selected_resource_index}"
                            )

                            drag = QDrag(self.ui.res_list_view)
                            mime = QMimeData()
                            mime.setData(
                                "application/x-bingo-resource",
                                str(self.selected_resource_index).encode(),
                            )
                            drag.setMimeData(mime)

                            # 设置预览图
                            pix = self.get_resource_pixmap(
                                self.selected_resource_index
                            ).scaled(64, 64, Qt.KeepAspectRatio)
                            drag.setPixmap(pix)
                            drag.setHotSpot(QPoint(32, 32))

                            drag.exec_(Qt.CopyAction)
                            return True

            # ======================
            # 2. 画布事件（修复：改用 canvas_manager + 调用原生方法）
            # ======================
            if hasattr(self, "canvas_manager") and watched in [
                self.canvas_manager,
                self.canvas_manager.viewport(),
            ]:
                # 处理所有工具的鼠标按下事件，特别是图像模式下的选择
                if event.type() == QEvent.MouseButtonPress:
                    if event.button() == Qt.LeftButton:
                        # 调用鼠标按下处理方法
                        self._handle_mouse_press(event)
                        # 只有在绘制模式下才拦截事件，其他模式（如图像模式）放行
                        if self.current_tool == "draw":
                            return True

                # 处理所有工具的鼠标移动事件
                elif event.type() == QEvent.MouseMove:
                    # 调用鼠标移动处理方法
                    self._handle_mouse_move(event)
                    # 只在绘制模式下且正在绘制时拦截事件
                    if (
                        self.current_tool == "draw"
                        and self.is_drawing
                        and (event.buttons() & Qt.LeftButton)
                    ):
                        return True

                # 处理所有工具的鼠标释放事件
                elif event.type() == QEvent.MouseButtonRelease:
                    # 调用鼠标释放处理方法
                    self._handle_mouse_release(event)
                    # 只在绘制模式下拦截事件
                    if self.current_tool == "draw" and event.button() == Qt.LeftButton:
                        return True

            # 所有未匹配的事件，调用原生逻辑并放行
            return super().eventFilter(watched, event)
        except Exception as e:
            print(f"事件过滤器错误: {e}")
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
                    print(
                        f"DEBUG: 场景存在，资源项数量: {len(self.resource_items)}, 图块项数量: {len(self.resource_tile_items)}"
                    )
                    # 从场景中移除所有资源项
                    for i, resource_item in enumerate(self.resource_items):
                        try:
                            print(f"DEBUG: 移除资源项 {i}")
                            scene.removeItem(resource_item)
                            resource_item.is_deleted = True
                        except Exception as e:
                            print(f"从场景移除资源项错误: {e}")

                    # 从场景中移除所有资源列表视图中的图块项
                    for i, (key, tile_item) in enumerate(
                        self.resource_tile_items.items()
                    ):
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
        print(
            f"DEBUG: 清理完成，资源项数量: {len(self.resource_items)}, 图块项数量: {len(self.resource_tile_items)}"
        )

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
        if self.layer_manager.set_current_layer(layer_index):
            self.current_layer = layer_index
            print(f"当前图层: {layer_index}")

            # 重置资源选择状态
            self.selected_resource_index = -1
            self.selected_tile_index = -1

            # 更新资源列表显示
            self._update_res_list_display()

            # 移除预览
            self._remove_preview()

            # 清理编辑框
            self._remove_transform_box()

            # 重置图像选择状态
            self.selected_image_data = None
            self.selected_image_index = -1
            self.selected_layer_id = None
            self.selected_item = None

    def import_image_to_layer(self):
        """导入图像到当前图像图层"""
        from PySide6.QtWidgets import QFileDialog

        # 检查当前图层是否是图像图层
        current_layer = self.layer_manager.get_current_layer()
        if not current_layer or current_layer.layer_type != "image":
            print("错误: 当前图层不是图像图层")
            return

        # 打开文件对话框选择图像文件
        file_path, _ = QFileDialog.getOpenFileName(
            None, "导入图像", "", "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)"
        )

        if file_path:
            # 创建图像数据对象
            from .layer_manager import ImageData

            image_data = ImageData(file_path)

            # 添加到当前图层
            current_layer.add_image(image_data)

            # 更新地图数据模型
            self.layer_manager.update_map_model()

            # 渲染图像
            self._render_image_layer(current_layer)

            # 设置地图为已修改状态
            self.is_map_modified = True

            print(f"成功导入图像: {file_path}")

    def create_new_layer(self, layer_type):
        """创建新图层"""
        layer = self.layer_manager.create_layer(layer_type)
        print(f"创建新{layer_type}图层: {layer.name}")
        # 更新地图数据模型
        self.layer_manager.update_map_model()
        # 设置地图为已修改状态
        self.is_map_modified = True
        # 自动保存地图（如果当前地图有文件路径）
        if self.current_map_path:
            save_result = self.map_model.save(self.current_map_path)
            print(f"自动保存地图: {save_result}")
        return layer

    def delete_current_layer(self):
        """删除当前图层"""
        current_index = self.layer_manager.current_layer_index
        if self.layer_manager.delete_layer(current_index):
            print(f"删除图层: {current_index}")
            # 更新地图数据模型
            self.layer_manager.update_map_model()
            # 设置地图为已修改状态
            self.is_map_modified = True
            # 自动保存地图（如果当前地图有文件路径）
            if self.current_map_path:
                save_result = self.map_model.save(self.current_map_path)
                print(f"自动保存地图: {save_result}")
            return True
        return False

    def move_layer_up(self):
        """将当前图层上移"""
        current_index = self.layer_manager.current_layer_index
        if self.layer_manager.move_layer_up(current_index):
            print(f"图层上移: {current_index} -> {current_index - 1}")
            # 更新地图数据模型
            self.layer_manager.update_map_model()
            # 设置地图为已修改状态
            self.is_map_modified = True
            # 自动保存地图（如果当前地图有文件路径）
            if self.current_map_path:
                save_result = self.map_model.save(self.current_map_path)
                print(f"自动保存地图: {save_result}")
            return True
        return False

    def move_layer_down(self):
        """将当前图层下移"""
        current_index = self.layer_manager.current_layer_index
        if self.layer_manager.move_layer_down(current_index):
            print(f"图层下移: {current_index} -> {current_index + 1}")
            # 更新地图数据模型
            self.layer_manager.update_map_model()
            # 设置地图为已修改状态
            self.is_map_modified = True
            # 自动保存地图（如果当前地图有文件路径）
            if self.current_map_path:
                save_result = self.map_model.save(self.current_map_path)
                print(f"自动保存地图: {save_result}")
            return True
        return False

    def new_map(self):
        """创建新地图"""
        import os

        self._initialize_map_model()
        # 重新初始化图层管理器，使用新的地图数据模型
        self.layer_manager = LayerManager(self.map_model, self)
        # 重新连接信号
        self.layer_manager.current_layer_changed.connect(self._on_layer_changed)

        # 自动为新地图分配一个默认路径，避免后续自动保存时生成新地图
        if hasattr(self, "project_manager") and self.project_manager:
            project_path = self.project_manager.project_root
            if project_path:
                maps_dir = os.path.join(project_path, "assets", "maps")
                os.makedirs(maps_dir, exist_ok=True)
                # 生成默认地图名称
                map_name = "地图1"
                counter = 1
                while os.path.exists(os.path.join(maps_dir, map_name)):
                    counter += 1
                    map_name = f"地图{counter}"
                # 创建与地图同名的文件夹
                map_dir = os.path.join(maps_dir, map_name)
                os.makedirs(map_dir, exist_ok=True)
                # 文件路径指向文件夹内的.info文件
                file_path = os.path.join(map_dir, f"{map_name}.info")
                self.current_map_path = file_path
                print(f"DEBUG: 为新地图分配默认路径: {file_path}")

        self._update_canvas()

    def load_map_from_path(self, file_path):
        """从指定路径加载地图 - 修复资源加载逻辑"""
        import os

        print(f"=== 开始加载地图: {file_path} ===")
        if file_path:
            # 清除之前的状态
            self.selected_resource_index = -1
            self.selected_tile_index = -1
            self._remove_preview()
            self.layer_resources.clear()
            print("DEBUG: 清除之前的状态")

            # 加载地图数据
            print("DEBUG: 开始加载地图数据")
            if self.map_model.load(file_path):
                self.current_map_path = file_path
                self.is_map_modified = False
                self.map_loaded.emit(file_path)
                print(f"DEBUG: 地图加载成功: {file_path}")
                print(
                    f"DEBUG: 地图数据 - 图层数: {len(self.map_model.map_data.get('layers', []))}"
                )
                print(
                    f"DEBUG: 地图数据 - 瓦片集数: {len(self.map_model.map_data.get('tile_sets', []))}"
                )
                print(
                    f"DEBUG: 地图数据 - 图层资源映射: {self.map_model.map_data.get('layer_resources_map', {})}"
                )

                # 打印图层详细信息
                for i, layer in enumerate(self.map_model.map_data.get("layers", [])):
                    print(
                        f"DEBUG: 图层 {i}: {layer.get('name', 'unknown')}, 类型: {layer.get('type', 'drawing')}, 可见: {layer.get('visible', True)}"
                    )
                    if "images" in layer:
                        print(f"DEBUG:   图像数量: {len(layer['images'])}")
                        for j, image in enumerate(layer["images"]):
                            print(
                                f"DEBUG:   图像 {j}: {image.get('image_path', 'unknown')}"
                            )
                    if "tiles" in layer:
                        print(f"DEBUG:   瓦片数量: {len(layer['tiles'])}")

                # 清空上传资源列表，准备重新加载
                self.layer_resources.clear()

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

                # 初始化图层管理系统
                print("DEBUG: 初始化图层管理系统")
                self.layer_manager.initialize_from_map_model()
                print(
                    f"DEBUG: 图层管理系统初始化完成，图层数量: {len(self.layer_manager.layers)}"
                )
                for i, layer in enumerate(self.layer_manager.layers):
                    print(
                        f"DEBUG: 图层 {i}: {layer.name}, 类型: {layer.layer_type}, ID: {layer.layer_id}"
                    )
                    if hasattr(layer, "images"):
                        print(f"DEBUG:   图像数量: {len(layer.images)}")
                    if hasattr(layer, "tiles"):
                        print(f"DEBUG:   瓦片数量: {len(layer.tiles)}")

                # 加载瓦片集资源
                tile_sets = self.map_model.get_tile_sets()
                print(f"DEBUG: 加载的瓦片集数量: {len(tile_sets)}")

                map_dir = os.path.dirname(file_path)
                # 清空上传资源列表，准备重新加载
                self.layer_resources.clear()
                self.uploaded_resources.clear()

                # 分配资源给图层
                if "tile_sets" in self.map_model.map_data:
                    tile_sets = self.map_model.map_data["tile_sets"]
                    print(f"DEBUG: 加载的瓦片集数量: {len(tile_sets)}")
                    # 转换资源格式，确保每个资源都有path和resource_type字段
                    converted_resources = []
                    for i, resource in enumerate(tile_sets):
                        # 检查资源格式是否正确
                        if "image_path" in resource:
                            # 从加载的格式转换为我们期望的格式
                            image_path = resource.get("image_path", "")
                            # 确保路径完整，不被截断
                            if image_path and not os.path.isabs(image_path):
                                # 如果是相对路径，转换为绝对路径
                                image_path = os.path.join(map_dir, image_path)
                            # 确保路径完整，包含文件名
                            if image_path and os.path.isdir(image_path):
                                # 如果路径是目录，添加文件名
                                image_path = os.path.join(
                                    image_path, resource.get("name", "")
                                )
                            # 确保路径正确指向tilesets目录
                            if image_path and not image_path.endswith(
                                "tilesets" + os.sep + resource.get("name", "")
                            ):
                                # 如果路径不包含tilesets目录，添加它
                                tilesets_path = os.path.join(map_dir, "tilesets")
                                image_path = os.path.join(
                                    tilesets_path, resource.get("name", "")
                                )
                            converted_resource = {
                                "name": resource.get("name", ""),
                                "path": image_path,
                                "resource_type": resource.get(
                                    "resource_type", "tileset"
                                ),  # 保留原始资源类型
                                "tile_size": resource.get("tile_width", 32),
                                "tile_width": resource.get("tile_width", 32),
                                "tile_height": resource.get("tile_height", 32),
                                "collisions": [],  # 初始化碰撞数据
                            }
                            # 计算图块数量
                            if "tiles" in resource:
                                converted_resource["total_tiles"] = len(
                                    resource["tiles"]
                                )
                            converted_resources.append(converted_resource)
                            print(
                                f"DEBUG: 转换资源 {i}: {converted_resource['name']}, 路径: {converted_resource['path']}"
                            )
                        else:
                            # 资源格式已经正确，直接添加
                            # 确保路径完整，不被截断
                            if (
                                "path" in resource
                                and resource["path"]
                                and not os.path.isabs(resource["path"])
                            ):
                                resource["path"] = os.path.join(
                                    map_dir, resource["path"]
                                )
                            # 确保路径完整，包含文件名
                            if (
                                "path" in resource
                                and resource["path"]
                                and os.path.isdir(resource["path"])
                            ):
                                # 如果路径是目录，添加文件名
                                resource["path"] = os.path.join(
                                    resource["path"], resource.get("name", "")
                                )
                            converted_resources.append(resource)
                            print(
                                f"DEBUG: 直接添加资源 {i}: {resource.get('name', 'unknown')}, 路径: {resource.get('path', 'unknown')}"
                            )

                    # 添加图像图层的图像资源
                    print("DEBUG: 检查图像图层的图像资源")
                    for layer in self.layer_manager.layers:
                        if layer.layer_type == "image":
                            print(
                                f"DEBUG: 处理图像图层: {layer.name}, 图像数量: {len(layer.images)}"
                            )
                            for image_data in layer.images:
                                image_path = image_data.image_path
                                print(f"DEBUG: 图像路径: {image_path}")

                                # 确保图像路径是完整的绝对路径
                                if not os.path.isabs(image_path):
                                    # 如果是相对路径，转换为绝对路径
                                    image_path = os.path.join(map_dir, image_path)
                                    image_data.image_path = image_path
                                    print(f"DEBUG: 转换为绝对路径: {image_path}")

                                # 重新加载图像
                                image_data._load_pixmap()
                                if image_data.pixmap:
                                    print(f"DEBUG: 成功加载图像: {image_path}")
                                else:
                                    print(f"DEBUG: 图像加载失败: {image_path}")

                                # 检查该图像资源是否已经在converted_resources中
                                found = False
                                for resource in converted_resources:
                                    if (
                                        resource.get("path") == image_path
                                        or resource.get("image_path") == image_path
                                    ):
                                        print(
                                            f"DEBUG: 图像资源已存在: {resource.get('name', 'unknown')}"
                                        )
                                        found = True
                                        break
                                # 如果不在，添加到converted_resources中
                                if not found:
                                    # 创建图像资源对象
                                    image_resource = {
                                        "name": os.path.basename(image_path),
                                        "path": image_path,
                                        "resource_type": "image",
                                        "tile_size": 1,
                                        "tile_width": 1,
                                        "tile_height": 1,
                                        "collisions": [],
                                    }
                                    converted_resources.append(image_resource)
                                    print(
                                        f"DEBUG: 添加图像资源: {image_resource['name']}, 路径: {image_resource['path']}"
                                    )

                    # 为每个图层分配资源
                    layer_resources_map = self.map_model.map_data.get(
                        "layer_resources_map", {}
                    )
                    print(f"DEBUG: 图层资源映射: {layer_resources_map}")

                    # 检查layer_resources_map的类型和内容
                    print(
                        f"DEBUG: layer_resources_map 类型: {type(layer_resources_map)}"
                    )
                    print(
                        f"DEBUG: layer_resources_map 长度: {len(layer_resources_map)}"
                    )
                    print(f"DEBUG: layer_resources_map 内容: {layer_resources_map}")

                    # 如果layer_resources_map为空，根据每个图层的瓦片数据或图像数据来确定需要哪些资源
                    if not layer_resources_map:
                        print(
                            "DEBUG: layer_resources_map为空，根据瓦片数据或图像数据确定资源分配"
                        )
                        # 为每个图层收集所需的资源
                        for layer in self.layer_manager.layers:
                            layer_id = layer.layer_id
                            print(f"DEBUG: 处理图层 {layer.name} (ID: {layer_id})")
                            if layer_id not in self.layer_resources:
                                self.layer_resources[layer_id] = []

                            # 收集该图层需要的资源
                            required_resources = []
                            if layer.layer_type == "drawing":
                                # 检查该图层的瓦片数据
                                print(
                                    f"DEBUG: 图层 {layer.name} 是绘制图层，瓦片数量: {len(layer.tiles)}"
                                )
                                for (x, y), tile_id in layer.tiles.items():
                                    if tile_id > 0:
                                        # 解析tile_id获取资源索引
                                        resource_index = (tile_id // 1000) - 1
                                        print(
                                            f"DEBUG: 瓦片 [{x}, {y}] -> ID: {tile_id}, 资源索引: {resource_index}"
                                        )
                                        if (
                                            0
                                            <= resource_index
                                            < len(converted_resources)
                                        ):
                                            resource = converted_resources[
                                                resource_index
                                            ]
                                            print(
                                                f"DEBUG: 找到资源: {resource.get('name', 'unknown')}, 路径: {resource.get('path', 'unknown')}"
                                            )
                                            # 检查资源是否已经在required_resources中
                                            if resource not in required_resources:
                                                required_resources.append(resource)
                                                print(
                                                    f"DEBUG: 添加资源到列表: {resource.get('name', 'unknown')}"
                                                )
                                for i, ((x, y), tile_id) in enumerate(
                                    list(layer.tiles.items())[:3]
                                ):
                                    print(
                                        f"DEBUG:   瓦片 {i}: [{x}, {y}] -> ID: {tile_id}, 资源索引: {(tile_id // 1000) - 1}"
                                    )
                            elif layer.layer_type == "image":
                                # 检查该图层的图像数据
                                print(
                                    f"DEBUG: 图层 {layer.name} 是图像图层，图像数量: {len(layer.images)}"
                                )
                                for image_data in layer.images:
                                    image_path = image_data.image_path
                                    print(f"DEBUG: 图像路径: {image_path}")
                                    # 查找对应的资源
                                    for resource in converted_resources:
                                        resource_path = resource.get("path", "")
                                        resource_image_path = resource.get(
                                            "image_path", ""
                                        )
                                        # 比较路径，处理绝对路径和相对路径的情况
                                        if (
                                            resource_path == image_path
                                            or resource_image_path == image_path
                                        ):
                                            print(
                                                f"DEBUG: 找到图像资源: {resource.get('name', 'unknown')}"
                                            )
                                            # 检查资源是否已经在required_resources中
                                            if resource not in required_resources:
                                                required_resources.append(resource)
                                                print(
                                                    f"DEBUG: 添加图像资源到列表: {resource.get('name', 'unknown')}"
                                                )
                                        else:
                                            # 尝试比较文件名
                                            import os

                                            resource_filename = (
                                                os.path.basename(resource_path)
                                                if resource_path
                                                else os.path.basename(
                                                    resource_image_path
                                                )
                                            )
                                            image_filename = os.path.basename(
                                                image_path
                                            )
                                            if resource_filename == image_filename:
                                                print(
                                                    f"DEBUG: 找到图像资源 (使用文件名匹配): {resource.get('name', 'unknown')}"
                                                )
                                                # 检查资源是否已经在required_resources中
                                                if resource not in required_resources:
                                                    required_resources.append(resource)
                                                    print(
                                                        f"DEBUG: 添加图像资源到列表: {resource.get('name', 'unknown')}"
                                                    )
                                for i, img_data in enumerate(layer.images[:3]):
                                    print(
                                        f"DEBUG:   图像 {i}: 路径: {img_data.image_path}"
                                    )

                                # 同时检查layer_resources中是否有该图层的资源
                                if layer_id in self.layer_resources:
                                    print(
                                        f"DEBUG: 图像图层 {layer.name} 在 layer_resources 中，资源数量: {len(self.layer_resources[layer_id])}"
                                    )
                                    # 注意：这里不再直接添加layer_resources中的资源，因为这些资源会通过图像数据或后续的默认分配来添加
                                    # 这样可以避免资源重复添加

                            # 分配资源给图层
                            if required_resources:
                                self.layer_resources[layer_id] = required_resources
                                print(
                                    f"DEBUG: 为图层 {layer.name} (ID: {layer_id}) 分配资源，数量: {len(required_resources)}"
                                )
                                for i, res in enumerate(self.layer_resources[layer_id]):
                                    print(
                                        f"DEBUG:   资源 {i}: {res.get('name', 'unknown')}, 路径: {res.get('path', 'unknown')}"
                                    )
                            else:
                                # 即使没有使用的资源，也要检查是否有上传但未使用的资源
                                # 对于图像图层，分配所有图像资源
                                if layer.layer_type == "image":
                                    # 为图像图层分配所有图像资源
                                    for resource in converted_resources:
                                        if resource.get("resource_type") == "image":
                                            required_resources.append(resource)
                                            print(
                                                f"DEBUG: 为图像图层 {layer.name} 添加未使用的图像资源: {resource.get('name', 'unknown')}"
                                            )
                                # 对于绘制图层，分配所有图块资源
                                else:
                                    # 为绘制图层分配所有图块资源
                                    for resource in converted_resources:
                                        if resource.get("resource_type") == "tileset":
                                            required_resources.append(resource)
                                            print(
                                                f"DEBUG: 为绘制图层 {layer.name} 添加未使用的图块资源: {resource.get('name', 'unknown')}"
                                            )

                                if required_resources:
                                    self.layer_resources[layer_id] = required_resources
                                    print(
                                        f"DEBUG: 为图层 {layer.name} (ID: {layer_id}) 分配未使用的资源，数量: {len(required_resources)}"
                                    )
                                    for i, res in enumerate(
                                        self.layer_resources[layer_id]
                                    ):
                                        print(
                                            f"DEBUG:   资源 {i}: {res.get('name', 'unknown')}, 路径: {res.get('path', 'unknown')}"
                                        )
                                else:
                                    # 如果没有需要的资源，分配空列表
                                    self.layer_resources[layer_id] = []
                                    print(
                                        f"DEBUG: 为图层 {layer.name} (ID: {layer_id}) 分配空资源列表"
                                    )
                    else:
                        # 如果layer_resources_map不为空，根据保存的资源索引范围分配资源
                        for layer in self.layer_manager.layers:
                            layer_id = layer.layer_id
                            if layer_id not in self.layer_resources:
                                self.layer_resources[layer_id] = []

                            # 获取该图层的资源索引范围
                            layer_id_str = str(layer_id)
                            if layer_id_str in layer_resources_map:
                                start_idx, end_idx = layer_resources_map[layer_id_str]
                                print(
                                    f"DEBUG: 为图层 {layer.name} (ID: {layer_id}) 分配资源，索引范围: {start_idx}-{end_idx}"
                                )

                                # 分配资源给图层
                                layer_resources = []
                                for i in range(start_idx, end_idx):
                                    if i < len(converted_resources):
                                        resource = converted_resources[i]
                                        layer_resources.append(resource)
                                        print(
                                            f"DEBUG:   资源 {i}: {resource.get('name', 'unknown')}, 路径: {resource.get('path', 'unknown')}"
                                        )

                                if layer_resources:
                                    self.layer_resources[layer_id] = layer_resources
                                else:
                                    print(
                                        f"DEBUG: 图层 {layer.name} (ID: {layer_id}) 没有分配到资源"
                                    )

                # 更新图层列表组件
                if (
                    hasattr(self, "editor_map_layer_list")
                    and self.editor_map_layer_list
                ):
                    print("DEBUG: 更新图层列表组件")
                    self._update_editor_map_layer_list()

                # 默认选择第一个图层
                if self.layer_manager.layers:
                    print(f"DEBUG: 默认选择第一个图层，索引: 0")
                    self.layer_manager.set_current_layer(0)

                # 将转换后的资源添加到上传资源列表
                self.uploaded_resources.extend(converted_resources)
                print(f"DEBUG: 上传资源列表数量: {len(self.uploaded_resources)}")

                # 更新资源列表和画布
                print("DEBUG: 更新资源列表和画布")
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
                print("=== 地图加载完成 ===")
            else:
                print("DEBUG: 加载地图失败")
                self.error_occurred.emit("加载地图失败")

    def save_map(self):
        """保存地图"""
        print("=== 开始保存地图 ===")
        import os
        from PySide6.QtWidgets import QFileDialog

        # 如果没有正在编辑的地图，直接返回，不创建新地图
        if not self.current_map_path:
            print("DEBUG: 没有正在编辑的地图，跳过保存")
            return False

        # 使用现有地图路径
        file_path = self.current_map_path
        print(f"DEBUG: 使用现有地图路径: {file_path}")

        if file_path:
            # 如果没有扩展名，添加.info（二进制格式）
            if not file_path.endswith((".info", ".json")):
                file_path += ".info"
                print(f"DEBUG: 添加扩展名后的路径: {file_path}")

            # 更新图层管理系统数据到地图数据模型
            print("DEBUG: 更新图层数据到地图模型")
            self.layer_manager.update_map_model()
            print(f"DEBUG: 图层数量: {len(self.layer_manager.layers)}")
            for i, layer in enumerate(self.layer_manager.layers):
                print(
                    f"DEBUG: 图层 {i}: {layer.name}, 类型: {layer.layer_type}, ID: {layer.layer_id}"
                )
                if hasattr(layer, "images"):
                    print(f"DEBUG:   图像数量: {len(layer.images)}")
                if hasattr(layer, "tiles"):
                    print(f"DEBUG:   瓦片数量: {len(layer.tiles)}")

            # 收集所有图层的资源，保存到地图模型的tile_sets中
            print("DEBUG: 收集所有图层的资源")
            all_resources = []
            resource_path_to_index = {}
            layer_resources_map = {}

            # 首先收集所有唯一的资源
            # 1. 从layer_resources中收集所有类型的资源（包括绘制图层和图像图层）
            print("DEBUG: 1. 从layer_resources中收集所有类型的资源")
            for layer_id, layer_resources in self.layer_resources.items():
                print(f"DEBUG: 图层 ID: {layer_id}, 资源数量: {len(layer_resources)}")
                for i, resource in enumerate(layer_resources):
                    resource_path = resource.get("path", "")
                    resource_type = resource.get("resource_type", "tileset")
                    print(
                        f"DEBUG:   资源 {i}: {resource.get('name', 'unknown')}, 路径: {resource_path}, 类型: {resource_type}"
                    )
                    if resource_path not in resource_path_to_index:
                        # 确保资源对象有正确的字段
                        if resource_type == "image":
                            # 确保图像资源有tile_width和tile_height字段
                            if "tile_width" not in resource:
                                resource["tile_width"] = 1
                            if "tile_height" not in resource:
                                resource["tile_height"] = 1
                        # 确保所有资源都有tiles字段
                        if "tiles" not in resource:
                            resource["tiles"] = []

                        # 处理资源路径，确保文件被复制到tilesets目录
                        if self.current_map_path:
                            map_dir = os.path.dirname(self.current_map_path)
                            tilesets_dir = os.path.join(map_dir, "tilesets")
                            os.makedirs(tilesets_dir, exist_ok=True)

                            # 复制文件到tilesets目录
                            file_name = os.path.basename(resource_path)
                            dest_path = os.path.join(tilesets_dir, file_name)

                            # 只有当源文件存在且目标文件不存在时才复制
                            if os.path.exists(resource_path) and not os.path.exists(
                                dest_path
                            ):
                                import shutil

                                shutil.copy2(resource_path, dest_path)
                                print(f"DEBUG: 复制资源到tilesets目录: {dest_path}")

                            # 使用相对路径
                            relative_path = os.path.join("tilesets", file_name)
                            resource["path"] = relative_path
                            resource_path = relative_path

                        resource_path_to_index[resource_path] = len(all_resources)
                        all_resources.append(resource)
                        print(
                            f"DEBUG:   添加到唯一资源列表，索引: {resource_path_to_index[resource_path]}"
                        )

            # 2. 从图像图层中收集图像资源
            print("DEBUG: 2. 从图像图层中收集图像资源")
            for layer in self.layer_manager.layers:
                if layer.layer_type == "image":
                    print(
                        f"DEBUG: 图像图层: {layer.name}, 图像数量: {len(layer.images)}"
                    )
                    for i, image_data in enumerate(layer.images):
                        image_path = image_data.image_path
                        print(f"DEBUG:   图像 {i}: 路径: {image_path}")
                        if image_path and image_path not in resource_path_to_index:
                            # 处理资源路径，确保文件被复制到tilesets目录
                            processed_path = image_path
                            if self.current_map_path:
                                map_dir = os.path.dirname(self.current_map_path)
                                tilesets_dir = os.path.join(map_dir, "tilesets")
                                os.makedirs(tilesets_dir, exist_ok=True)

                                # 复制文件到tilesets目录
                                file_name = os.path.basename(image_path)
                                dest_path = os.path.join(tilesets_dir, file_name)

                                # 只有当源文件存在且目标文件不存在时才复制
                                if os.path.exists(image_path) and not os.path.exists(
                                    dest_path
                                ):
                                    import shutil

                                    shutil.copy2(image_path, dest_path)
                                    print(
                                        f"DEBUG: 复制图像资源到tilesets目录: {dest_path}"
                                    )

                                # 使用相对路径
                                processed_path = os.path.join("tilesets", file_name)
                                # 更新图像数据中的路径
                                image_data.image_path = processed_path

                            # 创建图像资源对象
                            image_resource = {
                                "name": os.path.basename(image_path),
                                "path": processed_path,
                                "resource_type": "image",
                                "tile_width": 1,  # 图像资源不需要瓦片大小
                                "tile_height": 1,  # 图像资源不需要瓦片大小
                                "tiles": [],  # 图像资源不需要瓦片数据
                            }
                            resource_path_to_index[processed_path] = len(all_resources)
                            all_resources.append(image_resource)
                            print(
                                f"DEBUG:   添加到唯一资源列表，索引: {resource_path_to_index[processed_path]}"
                            )
                        elif image_path and image_path in resource_path_to_index:
                            print(
                                f"DEBUG:   图像资源已存在，索引: {resource_path_to_index[image_path]}"
                            )
                # 检查绘制图层的资源
                elif layer.layer_type == "drawing":
                    layer_id = layer.layer_id
                    if layer_id in self.layer_resources:
                        print(
                            f"DEBUG: 绘制图层: {layer.name}, 资源数量: {len(self.layer_resources[layer_id])}"
                        )
                        for i, resource in enumerate(self.layer_resources[layer_id]):
                            resource_path = resource.get("path", "")
                            if (
                                resource_path
                                and resource_path not in resource_path_to_index
                            ):
                                # 确保资源对象有正确的字段
                                if "tile_width" not in resource:
                                    resource["tile_width"] = 32
                                if "tile_height" not in resource:
                                    resource["tile_height"] = 32
                                if "tiles" not in resource:
                                    resource["tiles"] = []
                                resource_path_to_index[resource_path] = len(
                                    all_resources
                                )
                                all_resources.append(resource)
                                print(
                                    f"DEBUG:   添加到唯一资源列表，索引: {resource_path_to_index[resource_path]}"
                                )
                            elif (
                                resource_path
                                and resource_path in resource_path_to_index
                            ):
                                print(
                                    f"DEBUG:   资源已存在，索引: {resource_path_to_index[resource_path]}"
                                )

            print(f"DEBUG: 收集到的唯一资源总数: {len(all_resources)}")
            for i, res in enumerate(all_resources):
                print(
                    f"DEBUG:   唯一资源 {i}: {res.get('name', 'unknown')}, 路径: {res.get('path', 'unknown')}, 类型: {res.get('resource_type', 'unknown')}"
                )

            # 为每个图层分配资源索引范围
            print("DEBUG: 为每个图层分配资源索引范围")
            for layer in self.layer_manager.layers:
                layer_id = layer.layer_id
                layer_resource_indices = []

                # 1. 为绘制图层添加资源索引
                if layer.layer_type == "drawing":
                    print(f"DEBUG: 处理绘制图层: {layer.name}, ID: {layer_id}")
                    if layer_id in self.layer_resources:
                        for resource in self.layer_resources[layer_id]:
                            resource_path = resource.get("path", "")
                            if resource_path in resource_path_to_index:
                                index = resource_path_to_index[resource_path]
                                layer_resource_indices.append(index)
                                print(
                                    f"DEBUG:   资源: {resource.get('name', 'unknown')}, 索引: {index}"
                                )
                    else:
                        print(f"DEBUG: 绘制图层 {layer.name} 不在 layer_resources 中")

                # 2. 为图像图层添加资源索引
                elif layer.layer_type == "image":
                    print(f"DEBUG: 处理图像图层: {layer.name}, ID: {layer_id}")
                    # 首先检查layer_resources中是否有该图层的资源
                    if layer_id in self.layer_resources:
                        print(
                            f"DEBUG: 图像图层 {layer.name} 在 layer_resources 中，资源数量: {len(self.layer_resources[layer_id])}"
                        )
                        for resource in self.layer_resources[layer_id]:
                            resource_path = resource.get("path", "")
                            if resource_path in resource_path_to_index:
                                index = resource_path_to_index[resource_path]
                                layer_resource_indices.append(index)
                                print(
                                    f"DEBUG:   资源: {resource.get('name', 'unknown')}, 索引: {index}"
                                )
                    else:
                        print(
                            f"DEBUG: 图像图层 {layer.name} 不在 layer_resources 中，检查图像数据"
                        )
                        # 如果layer_resources中没有，检查图像数据
                        for image_data in layer.images:
                            image_path = image_data.image_path
                            if image_path in resource_path_to_index:
                                index = resource_path_to_index[image_path]
                                layer_resource_indices.append(index)
                                print(f"DEBUG:   图像: {image_path}, 索引: {index}")

                # 计算索引范围
                if layer_resource_indices:
                    start_index = min(layer_resource_indices)
                    end_index = max(layer_resource_indices) + 1
                else:
                    start_index = 0
                    end_index = 0

                layer_resources_map[str(layer_id)] = (start_index, end_index)
                print(
                    f"DEBUG: 保存图层 {layer_id} ({layer.name}, {layer.layer_type}) 的资源索引范围: {start_index}-{end_index}"
                )

            # 更新地图模型的tile_sets
            print("DEBUG: 更新地图模型的tile_sets")
            self.map_model.map_data["tile_sets"] = all_resources
            # 保存每个图层的资源索引范围
            print("DEBUG: 保存每个图层的资源索引范围")
            self.map_model.map_data["layer_resources_map"] = layer_resources_map
            # 确保layers字段存在
            if "layers" not in self.map_model.map_data:
                self.map_model.map_data["layers"] = []

            # 保存地图数据
            print(f"DEBUG: 开始保存地图到: {file_path}")
            if self.map_model.save(file_path):
                self.current_map_path = file_path
                self.is_map_modified = False
                self.map_saved.emit(file_path)
                print(f"地图保存成功: {file_path}")
                # 打印保存后的地图数据
                print(
                    f"DEBUG: 保存后地图数据 - 图层数: {len(self.map_model.map_data.get('layers', []))}"
                )
                print(
                    f"DEBUG: 保存后地图数据 - 瓦片集数: {len(self.map_model.map_data.get('tile_sets', []))}"
                )
                print(
                    f"DEBUG: 保存后地图数据 - 图层资源映射: {self.map_model.map_data.get('layer_resources_map', {})}"
                )
            else:
                print("DEBUG: 保存地图失败")
                self.error_occurred.emit("保存地图失败")
        else:
            print("DEBUG: 取消保存")
        print("=== 保存地图操作完成 ===")

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
        if not hasattr(self, "_last_map_size") or self._last_map_size != (
            current_width,
            current_height,
        ):
            self._update_map_size_display()
            self._last_map_size = (current_width, current_height)

        # 清除变化记录
        self.map_model.clear_changed_area()

    def _update_canvas(self):
        """更新画布显示"""
        if self.canvas_manager and self.map_model:
            # 渲染所有可见图层
            self._render_all_layers()

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
            current_layer = self.layer_manager.get_current_layer()
            if current_layer and current_layer.layer_type == "drawing":
                current_layer.set_tile(gx, gy, 0)  # 0 代表空
                # 更新地图数据模型
                self.layer_manager.update_map_model()

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

            # 检查是否已有瓦片
            tile_exists = (x, y) in self.tile_items
            existing_item = None
            if tile_exists:
                existing_item = self.tile_items[(x, y)]
                existing_tile_id = existing_item.data(1)
                existing_layer_index = existing_item.data(2)

                # 如果瓦片属于当前图层且ID相同，不需要更新
                if (
                    existing_layer_index == self.current_layer
                    and existing_tile_id == tile_id
                ):
                    return

            # 获取图块图像
            pixmap = self.get_cached_pixmap(tile_id)
            if not pixmap:
                return

            # 如果位置已有瓦片但不属于当前图层，先移除它
            if (
                tile_exists
                and existing_item
                and existing_item.data(2) != self.current_layer
            ):
                self.tile_items.pop((x, y))
                self._recycle_item(existing_item)
                tile_exists = False

            # 创建或更新瓦片
            if tile_exists:
                # 更新现有瓦片
                existing_item.setPixmap(pixmap)
                existing_item.setData(1, tile_id)
                existing_item.setData(2, self.current_layer)
                existing_item.setZValue(self.current_layer + 10)
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
                # 存储图层索引，方便删除图层时清理
                item.setData(2, self.current_layer)

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
        # 获取所有图层的资源列表
        all_resources = []
        for layer_resources in self.layer_resources.values():
            all_resources.extend(layer_resources)

        # 查找匹配的资源
        for resource_index, resource in enumerate(all_resources):
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
        # 调用_render_all_layers方法，渲染所有可见图层
        self._render_all_layers()

    def _render_image_layer(self, layer):
        """渲染图像图层"""
        try:
            if not self.canvas_manager:
                return

            scene = self.canvas_manager.scene()
            if not scene:
                return

            # 清理该图层的旧图像项
            for key in list(self._image_items.keys()):
                if key[0] == layer.layer_id:
                    item = self._image_items.pop(key)
                    try:
                        scene.removeItem(item)
                        item.deleteLater()
                    except Exception as e:
                        print(f"移除图像项错误: {e}")

            # 渲染新图像
            print(f"DEBUG: 开始渲染图像图层，图像数量: {len(layer.images)}")
            for i, image_data in enumerate(layer.images):
                print(
                    f"DEBUG: 处理图像 {i}: 路径={image_data.image_path}, pixmap={image_data.pixmap}"
                )
                if image_data.pixmap:
                    print(
                        f"DEBUG: 图像 {i} 的 pixmap 尺寸: {image_data.pixmap.width()}x{image_data.pixmap.height()}"
                    )
                    # 创建图像项
                    pixmap_item = QGraphicsPixmapItem(image_data.pixmap)

                    # 应用变换
                    # 注意：由于 QGraphicsItem 的变换是相对于 item 原点的，我们需要直接设置 item 的位置
                    # 而不是通过变换来设置位置
                    print(
                        f"DEBUG: 渲染图像 - 位置: {image_data.position}, 缩放: {image_data.scale}"
                    )
                    pixmap_item.setPos(image_data.position)
                    # 然后应用缩放和旋转
                    transform = QTransform()
                    transform.scale(image_data.scale_x, image_data.scale_y)
                    transform.rotate(image_data.rotation)
                    pixmap_item.setTransform(transform)
                    print(f"DEBUG: 图像项场景位置: {pixmap_item.scenePos()}")

                    # 设置透明度
                    pixmap_item.setOpacity(image_data.opacity)

                    # 设置层级
                    pixmap_item.setZValue(layer.layer_id + 10)

                    # 允许鼠标事件，以便能够选中图像
                    pixmap_item.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)

                    # 添加到场景
                    scene.addItem(pixmap_item)

                    # 添加到缓存
                    self._image_items[(layer.layer_id, i)] = pixmap_item
                else:
                    print(f"DEBUG: 图像 {i} 的 pixmap 为 None")
        except Exception as e:
            print(f"渲染图像图层错误: {e}")
            import traceback

            traceback.print_exc()

    def _render_all_layers(self):
        """渲染所有可见图层"""
        try:
            if not self.canvas_manager or not self.map_model:
                return

            scene = self.canvas_manager.scene()
            if not scene:
                return

            # 清理所有瓦片项和图像项
            for item in list(self.tile_items.values()):
                self._recycle_item(item)
            self.tile_items.clear()

            for (layer_id, image_index), item in list(self._image_items.items()):
                try:
                    scene.removeItem(item)
                    item.deleteLater()
                except Exception as e:
                    pass
            self._image_items.clear()

            # 渲染所有可见图层
            for i, layer in enumerate(self.layer_manager.layers):
                if layer.visible:
                    if layer.layer_type == "drawing":
                        # 渲染绘制图层
                        tiles = layer.tiles
                        for (tx, ty), tile_id in tiles.items():
                            if tile_id > 0:
                                # 临时设置current_layer为当前图层索引，确保瓦片项的图层索引正确
                                old_current_layer = self.current_layer
                                self.current_layer = i
                                self._update_single_tile(tx, ty, tile_id)
                                self.current_layer = old_current_layer
                    elif layer.layer_type == "image":
                        # 渲染图像图层
                        self._render_image_layer(layer)

            print(f"✅ 所有图层渲染完成，图层数量: {len(self.layer_manager.layers)}")

        except Exception as e:
            print(f"渲染所有图层失败: {e}")
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
            current_layer = self.layer_manager.get_current_layer()
            if (
                not current_layer
                or not current_layer.visible
                or current_layer.layer_type != "drawing"
            ):
                print(
                    f"警告: 图层 {current_layer.name if current_layer else 'None'} 不可见或不是绘制图层"
                )
                return

            tile_size = self.map_model.get_tile_size()

            # 计算视口内的瓦片范围
            min_tile_x = int(scene_rect.left() // tile_size) - 1  # 扩展一个瓦片边界
            max_tile_x = int(scene_rect.right() // tile_size) + 2  # 扩展一个瓦片边界
            min_tile_y = int(scene_rect.top() // tile_size) - 1  # 扩展一个瓦片边界
            max_tile_y = int(scene_rect.bottom() // tile_size) + 2  # 扩展一个瓦片边界

            # 获取图层中的瓦片数据
            tiles = current_layer.tiles

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

            # 确保事件有 button() 和 pos() 方法
            if not hasattr(event, "button") or not hasattr(event, "pos"):
                return

            if event.button() == Qt.LeftButton:
                # 获取当前图层
                current_layer = self.layer_manager.get_current_layer()
                if not current_layer:
                    return

                # 获取场景坐标
                scene_pos = self.canvas_manager.mapToScene(event.pos())
                items = self.canvas_manager.scene().items(scene_pos)

                # 检查是否点击了变换框或其锚点
                clicked_transform_box = False
                transform_box_item = None
                if self.transform_box:
                    for item in items:
                        if item == self.transform_box or (
                            hasattr(self.transform_box, "handles")
                            and item in self.transform_box.handles.values()
                        ):
                            clicked_transform_box = True
                            transform_box_item = item
                            break

                # 检查点击的是否是其他图像
                clicked_other_image = False
                for item in items:
                    if (
                        isinstance(item, QGraphicsPixmapItem)
                        and item != self.preview_item
                        and item != self.selected_item
                    ):
                        # 找到了其他图像，继续执行选择逻辑
                        clicked_other_image = True
                        break

                if clicked_transform_box and not clicked_other_image:
                    # 只点击了变换框，没有点击其他图像
                    if hasattr(self, "original_canvas_mousePress"):
                        self.original_canvas_mousePress(event)  # 调用原生方法
                    return

                # 检查是否在图像模式下
                if current_layer.layer_type == "image":
                    # 图像模式：处理图像选择
                    item_found = False
                    print(f"DEBUG: 点击位置的项数量: {len(items)}")
                    for i, item in enumerate(items):
                        print(
                            f"DEBUG: 项 {i}: {type(item).__name__}, zValue: {item.zValue()}"
                        )
                        if (
                            isinstance(item, QGraphicsPixmapItem)
                            and item != self.preview_item
                        ):
                            # 查找图像项
                            print(f"DEBUG: 找到 QGraphicsPixmapItem: {item}")
                            print(
                                f"DEBUG: _image_items 中的项数量: {len(self._image_items)}"
                            )
                            for j, ((layer_id, image_index), image_item) in enumerate(
                                self._image_items.items()
                            ):
                                print(
                                    f"DEBUG: _image_items[{j}]: (layer_id={layer_id}, image_index={image_index}), item={image_item}"
                                )
                                if image_item == item:
                                    # 找到图像项
                                    print(
                                        f"DEBUG: 找到匹配的图像项: layer_id={layer_id}, image_index={image_index}"
                                    )
                                    if current_layer.layer_id == layer_id:
                                        # 从图层中获取图像数据
                                        print(
                                            f"DEBUG: 图层 ID 匹配: {current_layer.layer_id}"
                                        )
                                        for i, image_data in enumerate(
                                            current_layer.images
                                        ):
                                            if i == image_index:
                                                # 清除之前的变换框
                                                print(f"DEBUG: 清除之前的变换框")
                                                self._remove_transform_box()

                                                # 设置选中状态
                                                self.selected_image_data = image_data
                                                self.selected_image_index = image_index
                                                self.selected_layer_id = layer_id
                                                self.selected_item = item
                                                # 注意：这里不再设置 drag_start_pos，因为变换框会处理拖动
                                                item_found = True
                                                print(
                                                    f"选中图像: {image_data.image_path}"
                                                )

                                                # 创建变换框
                                                print(f"DEBUG: 创建变换框")
                                                self._create_transform_box(
                                                    image_data, item
                                                )
                                                break
                                        break
                                if item_found:
                                    break
                            if item_found:
                                break

                    # 如果没有找到任何项，清除选中状态和变换框
                    if not item_found:
                        # 移除变换框
                        self._remove_transform_box()

                        # 取消选中状态
                        self.selected_item = None
                        self.drag_start_pos = None
                        self.original_tile_pos = None
                        self.selected_image_data = None
                        self.selected_image_index = -1
                        self.selected_layer_id = -1
                else:
                    # 绘制模式：处理图块选择
                    if self.current_tool == "move":
                        # 查找可移动的图块项
                        item_found = False
                        for item in items:
                            if (
                                isinstance(item, QGraphicsPixmapItem)
                                and item != self.preview_item
                            ):
                                # 检查是否是图块项（不是图像项）
                                is_image_item = False
                                for (
                                    layer_id,
                                    image_index,
                                ), image_item in self._image_items.items():
                                    if image_item == item:
                                        is_image_item = True
                                        break
                                if not is_image_item:
                                    # 处理图块项
                                    self.selected_image_data = None
                                    self.selected_item = item
                                    self.drag_start_pos = scene_pos - item.pos()

                                    # 保存原始位置
                                    tile_size = self.map_model.get_tile_size()
                                    original_x = int(item.pos().x() / tile_size)
                                    original_y = int(item.pos().y() / tile_size)
                                    self.original_tile_pos = (original_x, original_y)
                                    item_found = True
                                    break

                        # 清除变换框（绘制模式不需要）
                        self._remove_transform_box()

                        # 取消选中状态（绘制模式只在拖动时保持选中）
                        if not item_found:
                            self.selected_item = None
                            self.drag_start_pos = None
                            self.original_tile_pos = None
                            self.selected_image_data = None
                            self.selected_image_index = -1
                            self.selected_layer_id = -1
                    elif self.current_tool == "draw":
                        # 绘制工具：绘制瓦片
                        if scene_pos:
                            self.is_drawing = True
                            # 获取网格位置
                            tile_pos = self._get_grid_pos_from_scene_pos(scene_pos)
                            self.last_tile_pos = tile_pos
                            # 调用绘制函数，但只在绘制图层上绘制
                            if current_layer and current_layer.layer_type == "drawing":
                                self._draw_tile(scene_pos)
                                # 移除预览
                                self._remove_preview()
                    elif self.current_tool == "erase":
                        # 擦除工具：删除瓦片
                        self._erase_tile(scene_pos)
            elif event.button() == Qt.RightButton:
                # 右键点击：检查是否点击了图像
                scene_pos = self.canvas_manager.mapToScene(event.pos())
                items = self.canvas_manager.scene().items(scene_pos)

                for item in items:
                    if (
                        isinstance(item, QGraphicsPixmapItem)
                        and item != self.preview_item
                    ):
                        # 检查是否是图像图层的图像项
                        for (
                            layer_id,
                            image_index,
                        ), image_item in self._image_items.items():
                            if image_item == item:
                                # 找到图像项
                                current_layer = self.layer_manager.get_current_layer()
                                if current_layer and current_layer.layer_id == layer_id:
                                    # 从图层中获取图像数据
                                    for i, image_data in enumerate(
                                        current_layer.images
                                    ):
                                        if i == image_index:
                                            self.selected_image_data = image_data
                                            self.selected_image_index = image_index
                                            self.selected_layer_id = layer_id
                                            self.selected_item = item
                                            # 保存旋转开始的位置
                                            self.drag_start_pos = scene_pos
                                            print(
                                                f"开始旋转图像: {image_data.image_path}"
                                            )
                                            return
            else:
                # 其他鼠标按钮（包括中键）交给MapCanvas处理
                self.original_mousePressEvent(event)
        except Exception as e:
            print(f"鼠标按下事件错误: {e}")
            import traceback

            traceback.print_exc()

    def _handle_mouse_move(self, event):
        """处理鼠标移动事件"""
        try:
            if not self.canvas_manager or not self.map_model:
                return

            # 确保事件有 buttons() 方法
            if not hasattr(event, "buttons"):
                return

            # 锚点显示时，直接调用原生方法并返回
            if (
                hasattr(self, "transform_box")
                and self.transform_box
                and self.transform_box.isVisible()
            ):
                if hasattr(self, "original_canvas_mouseMove"):
                    self.original_canvas_mouseMove(event)
                return

            # 获取当前图层
            current_layer = self.layer_manager.get_current_layer()
            if not current_layer:
                return

            if event.buttons() & Qt.LeftButton:
                # 检查是否在图像模式下且选中了图像
                if current_layer.layer_type == "image" and self.selected_image_data:
                    # 图像模式：不处理图像移动，因为变换框会处理
                    # 所有的移动和缩放都由变换框的回调函数处理
                    pass
                elif (
                    self.current_tool == "move"
                    and self.selected_item
                    and not self.selected_image_data
                ):
                    # 绘制模式：移动图块项
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
                        # 只在绘制图层上绘制
                        if current_layer.layer_type == "drawing":
                            self._draw_tile(scene_pos)
                            self.last_tile_pos = tile_pos
                elif self.current_tool == "erase":
                    # 擦除工具：删除瓦片
                    scene_pos = self.canvas_manager.mapToScene(event.pos())
                    self._erase_tile(scene_pos)
            elif event.buttons() & Qt.RightButton:
                # 右键拖动：旋转图像
                if self.selected_image_data:
                    scene_pos = self.canvas_manager.mapToScene(event.pos())

                    # 计算旋转角度
                    dx_start = (
                        self.drag_start_pos.x() - self.selected_image_data.position.x()
                    )
                    dy_start = (
                        self.drag_start_pos.y() - self.selected_image_data.position.y()
                    )
                    dx_current = scene_pos.x() - self.selected_image_data.position.x()
                    dy_current = scene_pos.y() - self.selected_image_data.position.y()

                    # 计算角度（弧度）
                    import math

                    angle_start = math.atan2(dy_start, dx_start)
                    angle_current = math.atan2(dy_current, dx_current)

                    # 计算角度差（度）
                    angle_diff = math.degrees(angle_current - angle_start)

                    # 更新图像旋转
                    new_rotation = self.selected_image_data.rotation + angle_diff
                    # 归一化到0-360度
                    new_rotation = new_rotation % 360
                    self.selected_image_data.rotation = new_rotation

                    # 更新图像项
                    transform = self.selected_image_data.get_transform()
                    self.selected_item.setTransform(transform)

                    # 更新拖拽开始位置
                    self.drag_start_pos = scene_pos
            else:
                # 如果是中键拖动，交给MapCanvas处理
                if event.buttons() & Qt.MiddleButton:
                    if hasattr(self, "original_canvas_mouseMove"):
                        self.original_canvas_mouseMove(event)
                else:
                    # 显示预览图块（仅绘制工具）
                    if self.current_tool == "draw":
                        self._update_preview(event.pos())

        except Exception as e:
            print(f"鼠标移动事件错误: {e}")
            import traceback

            traceback.print_exc()

    def _handle_mouse_release(self, event):
        """处理鼠标释放事件"""
        try:
            # 确保事件有 button() 方法
            if not hasattr(event, "button"):
                return

            # 锚点显示时，直接调用原生方法并返回
            if (
                hasattr(self, "transform_box")
                and self.transform_box
                and self.transform_box.isVisible()
            ):
                if hasattr(self, "original_canvas_mouseRelease"):
                    self.original_canvas_mouseRelease(event)
                return

            if event.button() == Qt.LeftButton:
                # 获取当前图层
                current_layer = self.layer_manager.get_current_layer()
                if not current_layer:
                    return

                if current_layer.layer_type == "image":
                    # 图像模式：处理图像释放
                    if self.selected_image_data:
                        # 移动图像完成
                        # 更新地图数据模型
                        if current_layer.layer_id == self.selected_layer_id:
                            self.layer_manager.update_map_model()

                            # 重新渲染图像图层
                            self._render_image_layer(current_layer)

                            # 设置地图为已修改状态
                            self.is_map_modified = True

                            # 自动保存地图（如果当前地图有文件路径）
                            if self.current_map_path:
                                save_result = self.map_model.save(self.current_map_path)

                    # 对于图像图层，保持选中状态和变换框
                    if self.selected_image_data:
                        # 保持选中状态，不移除变换框
                        pass
                else:
                    # 绘制模式：处理图块释放
                    if (
                        self.current_tool == "move"
                        and self.selected_item
                        and not self.selected_image_data
                    ):
                        # 移动图块完成
                        # 获取图块位置并更新地图数据
                        tile_size = self.map_model.get_tile_size()
                        new_x = int(self.selected_item.pos().x() / tile_size)
                        new_y = int(self.selected_item.pos().y() / tile_size)
                        original_x, original_y = self.original_tile_pos

                        # 获取原始位置的图块ID
                        if current_layer.layer_type == "drawing":
                            tile_id = current_layer.get_tile(original_x, original_y)
                            if tile_id > 0:
                                # 先清除原始位置
                                current_layer.set_tile(original_x, original_y, 0)
                                # 然后设置新位置
                                current_layer.set_tile(new_x, new_y, tile_id)

                                # 更新地图数据模型
                                self.layer_manager.update_map_model()

                                # 更新tile_items字典，确保擦除功能正常工作
                                if (original_x, original_y) in self.tile_items:
                                    item = self.tile_items.pop((original_x, original_y))
                                    self.tile_items[(new_x, new_y)] = item

                                # 设置地图为已修改状态
                                self.is_map_modified = True

                                # 自动保存地图（如果当前地图有文件路径）
                                if self.current_map_path:
                                    save_result = self.map_model.save(
                                        self.current_map_path
                                    )

                    # 对于绘制图层，取消选中状态
                    self.selected_item = None
                    self.drag_start_pos = None
                    self.original_tile_pos = None
                    self.selected_image_data = None
                    self.selected_image_index = -1
                    self.selected_layer_id = -1
                    # 移除变换框
                    self._remove_transform_box()
            elif event.button() == Qt.RightButton:
                # 右键释放：旋转图像完成
                if self.selected_image_data:
                    # 更新地图数据模型
                    current_layer = self.layer_manager.get_current_layer()
                    if (
                        current_layer
                        and current_layer.layer_id == self.selected_layer_id
                    ):
                        self.layer_manager.update_map_model()

                        # 重新渲染图像图层
                        self._render_image_layer(current_layer)

                        # 设置地图为已修改状态
                        self.is_map_modified = True

                        # 自动保存地图（如果当前地图有文件路径）
                        if self.current_map_path:
                            save_result = self.map_model.save(self.current_map_path)

                    # 取消选中状态
                    self.selected_item = None
                    self.drag_start_pos = None
                    self.selected_image_data = None
                    self.selected_image_index = -1
                    self.selected_layer_id = -1
                    # 移除变换框
                    self._remove_transform_box()
                elif self.current_tool == "draw":
                    # 绘制工具：结束绘制
                    self.is_drawing = False
                    self.last_tile_pos = None
            else:
                # 其他鼠标按钮交给MapCanvas处理
                if hasattr(self, "original_canvas_mouseRelease"):
                    self.original_canvas_mouseRelease(event)
        except Exception as e:
            print(f"鼠标释放事件错误: {e}")
            import traceback

            traceback.print_exc()

    def _handle_wheel_event(self, event):
        """处理滚轮事件 - 调用原始的wheelEvent方法"""
        try:
            # 如果选中了图像，使用滚轮进行缩放
            if self.selected_image_data:
                # 获取缩放因子
                if event.angleDelta().y() > 0:
                    scale_factor = 1.1
                else:
                    scale_factor = 0.9

                # 更新图像缩放
                new_scale = self.selected_image_data.scale * scale_factor
                # 设置缩放范围
                if 0.1 <= new_scale <= 10.0:
                    self.selected_image_data.scale = new_scale

                    # 更新图像项
                    transform = self.selected_image_data.get_transform()
                    self.selected_item.setTransform(transform)

                    # 更新地图数据模型
                    current_layer = self.layer_manager.get_current_layer()
                    if (
                        current_layer
                        and current_layer.layer_id == self.selected_layer_id
                    ):
                        self.layer_manager.update_map_model()

                        # 设置地图为已修改状态
                        self.is_map_modified = True

                        # 自动保存地图（如果当前地图有文件路径）
                        if self.current_map_path:
                            save_result = self.map_model.save(self.current_map_path)
            else:
                # 调用原始的wheelEvent方法，让MapCanvas自己处理缩放
                self.original_wheelEvent(event)
        except Exception as e:
            print(f"滚轮事件错误: {e}")

    def _draw_tile(self, scene_pos):
        """绘制瓦片 - 简化流程版本"""
        try:
            # 获取当前图层
            current_layer = self.layer_manager.get_current_layer()
            if not current_layer:
                print("DEBUG: 当前图层不存在")
                return

            # 获取当前图层的资源列表
            layer_resources = self.layer_resources.get(current_layer.layer_id, [])

            # 检查必要条件
            if self.selected_resource_index < 0 or self.selected_resource_index >= len(
                layer_resources
            ):
                print(f"DEBUG: 资源索引无效: {self.selected_resource_index}")
                return

            # 获取选中的资源
            resource = layer_resources[self.selected_resource_index]
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
            print(f"DEBUG: 资源列表长度: {len(layer_resources)}")

            # 计算全局资源索引
            # 收集所有图层的资源
            all_resources = []
            for layer_resources in self.layer_resources.values():
                all_resources.extend(layer_resources)

            # 查找当前资源在全局资源列表中的索引
            global_resource_index = -1
            for i, res in enumerate(all_resources):
                if res.get("path") == resource.get("path"):
                    global_resource_index = i
                    break

            # 如果找不到，使用当前图层中的索引
            if global_resource_index == -1:
                global_resource_index = self.selected_resource_index

            # 根据资源类型确定图块ID
            if resource_type == "tileset":
                # 图块集合模式，使用资源索引和图块索引的组合作为图块ID
                # 格式：(resource_index + 1) * 1000 + tile_index + 1
                # 这样确保图块集模式的tile_id始终大于等于1000，避免与单张图片模式混淆
                tile_index = self.selected_tile_index
                # 如果没有选择图块索引，使用默认值0
                if tile_index < 0:
                    tile_index = 0

                tile_id = (global_resource_index + 1) * 1000 + tile_index + 1
                print(
                    f"DEBUG: 图块集模式 - 生成tile_id: {tile_id}, 全局资源索引: {global_resource_index}"
                )
            else:
                # 单张图片模式，使用统一的资源ID格式
                tile_id = (global_resource_index + 1) * 1000 + 1
                print(
                    f"DEBUG: 单张图片模式 - 生成tile_id: {tile_id}, 全局资源索引: {global_resource_index}"
                )

            # 获取纯粹的网格索引 (0, 1, 2...)
            grid_pos = self._get_grid_pos_from_scene_pos(scene_pos, tile_id)
            if grid_pos is None:
                print("DEBUG: 无法获取网格位置")
                return
            gx, gy = grid_pos
            print(f"DEBUG: 网格坐标: ({gx}, {gy})")

            # 检查当前图层是否有效
            current_layer = self.layer_manager.get_current_layer()
            print(f"DEBUG: 当前图层: {current_layer.name if current_layer else 'None'}")
            if not current_layer:
                print(f"DEBUG: 图层无效，返回")
                return

            # 处理不同类型的图层
            if current_layer.layer_type == "drawing":
                # 绘制图层：绘制瓦片
                # 检查是否重复绘制
                current_tile_id = current_layer.get_tile(gx, gy)
                print(f"DEBUG: 当前位置图块ID: {current_tile_id}, 新图块ID: {tile_id}")
                if current_tile_id == tile_id:
                    print("DEBUG: 图块ID相同，跳过绘制")
                    return

                # 记录日志 (使用网格坐标)
                self._record_coordinates(
                    "Draw Tile", coordinates=(gx, gy), tile_id=tile_id
                )

                # 设置瓦片
                current_layer.set_tile(gx, gy, tile_id)

                # 更新地图数据模型
                self.layer_manager.update_map_model()

                # 手动更新这一个瓦片即可，这样速度最快且不会冲突
                self._update_single_tile(gx, gy, tile_id)

                # 设置地图为已修改状态
                self.is_map_modified = True

                # 自动保存地图（如果当前地图有文件路径）
                if self.current_map_path:
                    save_result = self.map_model.save(self.current_map_path)

                return
            elif current_layer.layer_type == "image":
                # 图像图层：不直接创建图像，而是通过拖拽功能创建
                print("DEBUG: 图像图层不支持直接绘制，使用拖拽功能添加图像")
                return

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

            # 获取当前图层
            current_layer = self.layer_manager.get_current_layer()
            if not current_layer:
                self._remove_preview()
                return

            # 图像图层不显示预览
            if current_layer.layer_type == "image":
                self._remove_preview()
                return

            # 获取当前图层的资源列表
            layer_id = current_layer.layer_id
            layer_resources = self.layer_resources.get(layer_id, [])

            # 获取选中的资源
            if self.selected_resource_index < 0 or self.selected_resource_index >= len(
                layer_resources
            ):
                self._remove_preview()
                return

            resource = layer_resources[self.selected_resource_index]
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

    def _create_transform_box(self, image_data, image_item):
        """创建变换框"""
        # 移除之前的变换框
        self._remove_transform_box()

        # 获取图像的实际尺寸
        if image_data.pixmap:
            width = image_data.pixmap.width() * image_data.scale_x
            height = image_data.pixmap.height() * image_data.scale_y
        else:
            # 如果没有 pixmap，使用默认尺寸
            width = 100
            height = 100

        # 创建变换框，使用图像的实际尺寸
        rect = QRectF(0, 0, width, height)
        self.transform_box = TransformBoxItem(
            rect, transform_callback=self._on_transform_changed
        )

        # 设置变换框的位置为图像的实际位置
        # 注意：由于图像的变换顺序是 "缩放 -> 旋转 -> 平移"，所以变换框的位置应该与图像的位置一致
        # 但是，由于 QGraphicsItem 的变换是相对于 item 原点的，所以我们需要确保变换框的位置与图像的实际位置一致
        # 使用 image_data.position 来设置变换框的位置，确保与图像数据一致
        self.transform_box.setPos(image_data.position)
        print(f"DEBUG: 图像数据位置: {image_data.position}")

        # 添加到场景
        if self.canvas_manager:
            self.canvas_manager.scene().addItem(self.transform_box)

    def _remove_transform_box(self):
        """移除变换框"""
        if self.transform_box and self.canvas_manager:
            try:
                self.canvas_manager.scene().removeItem(self.transform_box)
                self.transform_box = None
            except Exception as e:
                pass

    def _on_transform_changed(self, rect, is_shift_pressed=False):
        """处理变换框的变换"""
        if self.selected_image_data and self.selected_item and self.transform_box:
            print(
                f"DEBUG: _on_transform_changed - rect={rect}, transform_box.pos={self.transform_box.pos()}, is_shift_pressed={is_shift_pressed}"
            )

            # 更新图像的位置
            # 图像的位置应该是变换框的位置加上矩形的左上角位置
            new_pos = self.transform_box.pos() + rect.topLeft()
            self.selected_image_data.position = new_pos
            print(f"DEBUG: 更新图像位置: {new_pos}")

            # 更新图像的缩放
            if self.selected_image_data.pixmap:
                original_width = self.selected_image_data.pixmap.width()
                original_height = self.selected_image_data.pixmap.height()
                if original_width > 0 and original_height > 0:
                    if is_shift_pressed:
                        # 按住Shift键时，等比缩放图像
                        # 计算宽度的缩放比例
                        new_scale = rect.width() / original_width
                        self.selected_image_data.scale = new_scale
                        self.selected_image_data.scale_x = new_scale
                        self.selected_image_data.scale_y = new_scale
                        print(
                            f"DEBUG: 更新图像缩放: {new_scale}, 编辑框宽度: {rect.width()}, 原始宽度: {original_width}"
                        )

                        # 确保编辑框的尺寸与图像的尺寸一致
                        new_height = original_height * new_scale
                        self.transform_box.setRect(0, 0, rect.width(), new_height)
                        self.transform_box.update_handles_pos()
                        print(f"DEBUG: 更新编辑框尺寸: {rect.width()}x{new_height}")
                    else:
                        # 不按Shift键时，自由缩放图像，与编辑框比例一致
                        # 计算宽度和高度的缩放比例
                        width_scale = rect.width() / original_width
                        height_scale = rect.height() / original_height

                        # 保存宽度和高度的缩放比例
                        self.selected_image_data.scale_x = width_scale
                        self.selected_image_data.scale_y = height_scale
                        # 保持scale属性为平均值，向后兼容
                        self.selected_image_data.scale = (
                            width_scale + height_scale
                        ) / 2
                        print(
                            f"DEBUG: 图像缩放: 宽度缩放={width_scale}, 高度缩放={height_scale}, 编辑框宽度: {rect.width()}, 编辑框高度: {rect.height()}, 原始宽度: {original_width}, 原始高度: {original_height}"
                        )

            # 更新图像项
            # 注意：由于 QGraphicsItem 的变换是相对于 item 原点的，我们需要直接设置 item 的位置
            # 而不是通过变换来设置位置
            self.selected_item.setPos(new_pos)
            # 然后应用缩放和旋转
            transform = QTransform()
            if self.selected_image_data.pixmap:
                original_width = self.selected_image_data.pixmap.width()
                original_height = self.selected_image_data.pixmap.height()
                if original_width > 0 and original_height > 0:
                    if not is_shift_pressed:
                        # 不按Shift键时，自由缩放图像，与编辑框比例一致
                        transform.scale(
                            self.selected_image_data.scale_x,
                            self.selected_image_data.scale_y,
                        )
                    else:
                        # 按住Shift键时，等比缩放图像
                        transform.scale(
                            self.selected_image_data.scale_x,
                            self.selected_image_data.scale_y,
                        )
            else:
                # 如果没有pixmap，使用默认缩放
                transform.scale(
                    self.selected_image_data.scale, self.selected_image_data.scale
                )
            transform.rotate(self.selected_image_data.rotation)
            self.selected_item.setTransform(transform)
            print(f"DEBUG: 更新图像位置: {new_pos}")
            print(f"DEBUG: 更新图像变换: {transform}")

            # 更新地图数据模型
            current_layer = self.layer_manager.get_current_layer()
            if current_layer and current_layer.layer_id == self.selected_layer_id:
                self.layer_manager.update_map_model()
                self.is_map_modified = True

                # 自动保存地图（如果当前地图有文件路径）
                if self.current_map_path:
                    self.map_model.save(self.current_map_path)

    def initialize_collision_editor(self, col_editor_view):
        """初始化碰撞编辑器"""
        self.collision_manager.initialize_collision_editor(col_editor_view)

    def set_current_collision_tile(self, resource_index, tile_index):
        """设置当前选中的碰撞图块"""
        try:
            print(
                f"DEBUG: 开始设置当前碰撞图块 - 资源索引: {resource_index}, 图块索引: {tile_index}"
            )

            # 检查参数有效性
            if resource_index < 0:
                print("DEBUG: 资源索引无效: {resource_index}")
                return

            # 获取当前图层
            current_layer = self.layer_manager.get_current_layer()
            if not current_layer:
                print("DEBUG: 当前图层不存在")
                return

            # 获取当前图层的资源列表
            layer_resources = self.layer_resources.get(current_layer.layer_id, [])

            if resource_index >= len(layer_resources):
                print(
                    f"DEBUG: 资源索引越界 - 资源索引: {resource_index}, 资源数量: {len(layer_resources)}"
                )
                return

            # 计算全局资源索引
            global_resource_index = 0
            # 遍历所有图层的资源，找到当前资源的全局索引
            for layer_id, resources in self.layer_resources.items():
                if layer_id == current_layer.layer_id:
                    # 找到当前图层，加上当前资源在图层内的索引
                    global_resource_index += resource_index
                    break
                # 加上其他图层的资源数量
                global_resource_index += len(resources)

            print(
                f"DEBUG: 局部资源索引: {resource_index}, 全局资源索引: {global_resource_index}"
            )

            # 调用碰撞管理器设置当前碰撞图块（传递局部资源索引，碰撞管理器会通过provider获取正确的图像）
            print(f"DEBUG: 调用 collision_manager.set_current_collision_tile")
            if hasattr(self, "collision_manager"):
                self.collision_manager.set_current_collision_tile(
                    resource_index, tile_index
                )
                print("DEBUG: collision_manager.set_current_collision_tile 调用成功")
            else:
                print("DEBUG: collision_manager 不存在")

            # 调用属性管理器设置当前瓦片（传递全局资源索引）
            print(f"DEBUG: 调用 property_manager.set_current_tile")
            if hasattr(self, "property_manager"):
                self.property_manager.set_current_tile(
                    global_resource_index, tile_index
                )
                print("DEBUG: property_manager.set_current_tile 调用成功")
            else:
                print("DEBUG: property_manager 不存在")

            # 更新map_collision checkbox的状态（使用全局资源索引）
            print(f"DEBUG: 更新 map_collision checkbox 状态")
            if hasattr(self, "ui") and hasattr(self.ui, "map_collision"):
                if self.map_model:
                    collision_enabled = self.map_model.get_tile_collision(
                        global_resource_index, tile_index
                    )
                    print(f"DEBUG: 碰撞启用状态: {collision_enabled}")
                    self.ui.map_collision.setChecked(collision_enabled)
                    print("DEBUG: map_collision checkbox 状态更新成功")
                    print(
                        f"DEBUG: 成功获取碰撞状态 - tile_set_index: {global_resource_index}, tile_index: {tile_index}, collision: {collision_enabled}"
                    )
                else:
                    print("DEBUG: map_model 不存在")
            else:
                print("DEBUG: ui 或 map_collision 不存在")

            # 更新标签输入框的状态（使用全局资源索引）
            print(f"DEBUG: 更新标签输入框状态")
            if hasattr(self, "ui") and hasattr(self.ui, "att_tag"):
                if self.map_model:
                    tile_tag = self.map_model.get_tile_tag(
                        global_resource_index, tile_index
                    )
                    print(f"DEBUG: 瓦片标签: {tile_tag}")
                    print(
                        f"DEBUG: 成功获取标签 - tile_set_index: {global_resource_index}, tile_index: {tile_index}, tag: {tile_tag}"
                    )
                    # 阻塞信号，防止触发标签变化处理
                    self.ui.att_tag.blockSignals(True)
                    self.ui.att_tag.setText(tile_tag)
                    self.ui.att_tag.blockSignals(False)
                    print("DEBUG: 标签输入框状态更新成功")
                else:
                    print("DEBUG: map_model 不存在")
            else:
                print("DEBUG: ui 或 att_tag 不存在")

            # 更新碰撞类型选择框的状态（使用全局资源索引）
            print(f"DEBUG: 更新碰撞类型选择框状态")
            if hasattr(self, "ui") and hasattr(self.ui, "att_col_type"):
                if self.map_model:
                    collision_enabled = self.map_model.get_tile_collision(
                        global_resource_index, tile_index
                    )
                    print(f"DEBUG: 碰撞启用状态: {collision_enabled}")
                    print(
                        f"DEBUG: 成功获取碰撞状态 - tile_set_index: {global_resource_index}, tile_index: {tile_index}, collision: {collision_enabled}"
                    )
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
            for i, layer in enumerate(self.map_model.map_data["layers"]):
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

        print(
            f"DEBUG: 瓦片尺寸变化: {self.map_model.get_tile_size()} -> {new_tile_size}"
        )

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
        # 获取当前图层
        current_layer = self.layer_manager.get_current_layer()
        if not current_layer:
            return None

        # 获取当前图层的资源列表
        layer_resources = self.layer_resources.get(current_layer.layer_id, [])

        if resource_index < 0 or resource_index >= len(layer_resources):
            return None

        resource = layer_resources[resource_index]

        # 获取图块图像
        pixmap = None
        if resource["resource_type"] == "tileset":
            # 计算全局资源索引
            global_resource_index = 0
            # 遍历所有图层的资源，找到当前资源的全局索引
            for layer_id, resources in self.layer_resources.items():
                if layer_id == current_layer.layer_id:
                    # 找到当前图层，加上当前资源在图层内的索引
                    global_resource_index += resource_index
                    break
                # 加上其他图层的资源数量
                global_resource_index += len(resources)

            # 使用全局资源索引计算tile_id
            tile_id = (global_resource_index + 1) * 1000 + tile_index + 1
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
                        new_image_path = image_path.replace(
                            old_tilesets_path, new_tilesets_path
                        )
                        tile_set["image_path"] = new_image_path
                        print(f"✅ 更新瓦片集路径: {image_path} -> {new_image_path}")

            # 重命名目录内的所有相关文件
            for ext in [".info", ".tiles", ".collision", ".resources"]:
                old_file_path = os.path.join(current_dir, f"{old_base_name}{ext}")
                new_file_path = os.path.join(current_dir, f"{new_base_name}{ext}")
                if os.path.exists(old_file_path):
                    os.rename(old_file_path, new_file_path)
                    print(
                        f"✅ 文件重命名成功: {old_base_name}{ext} -> {new_base_name}{ext}"
                    )

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

    def get_resource_pixmap(self, resource_index):
        """获取资源的 pixmap"""
        try:
            # 获取当前图层
            current_layer = self.layer_manager.get_current_layer()
            if not current_layer:
                return QPixmap()

            # 获取当前图层的资源列表
            layer_resources = self.layer_resources.get(current_layer.layer_id, [])

            if resource_index < 0 or resource_index >= len(layer_resources):
                return QPixmap()

            resource = layer_resources[resource_index]
            image_path = resource["path"]

            # 处理相对路径
            if not os.path.isabs(image_path):
                if self.current_map_path:
                    map_dir = os.path.dirname(self.current_map_path)
                    image_path = os.path.join(map_dir, image_path)

            # 加载图片
            if os.path.exists(image_path):
                return QPixmap(image_path)
            return QPixmap()
        except Exception as e:
            print(f"获取资源 pixmap 错误: {e}")
            return QPixmap()

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
        # 安装事件过滤器到 viewport
        if self.res_list_view:
            self.res_list_view.viewport().installEventFilter(self)  # 必须加 .viewport()
            # 保存拖拽起始位置
            self.drag_start_pos = None
        # 初始化资源列表显示
        self._update_res_list_display()

    def set_layer_list_view(self, layer_list_view):
        """设置图层列表视图"""
        self.layer_list_view = layer_list_view
        # 初始化图层列表显示
        if self.layer_list_view:
            self.layer_list_view.set_layer_manager(self.layer_manager)

    def set_editor_map_layer_list(self, tree_widget):
        """设置editor_map_layer_list组件"""
        self.editor_map_layer_list = tree_widget
        # 初始化图层列表显示
        if self.editor_map_layer_list:
            # 清空现有项
            self.editor_map_layer_list.clear()
            # 设置列数
            self.editor_map_layer_list.setColumnCount(3)
            # 设置列标题
            self.editor_map_layer_list.setHeaderLabels(["可见", "名称", "类型"])
            # 设置列宽
            self.editor_map_layer_list.setColumnWidth(0, 40)
            self.editor_map_layer_list.setColumnWidth(1, 150)
            self.editor_map_layer_list.setColumnWidth(2, 80)
            # 连接信号
            self.editor_map_layer_list.itemClicked.connect(self._on_layer_item_clicked)
            # 监听图层变化信号
            self.layer_manager.layers_changed.connect(
                self._update_editor_map_layer_list
            )
            self.layer_manager.current_layer_changed.connect(self._on_layer_changed)
            # 初始更新
            self._update_editor_map_layer_list()

    def create_drawing_layer(self):
        """创建绘制图层"""
        layer = self.layer_manager.create_layer("drawing")
        if layer:
            # 更新图层列表显示
            if self.layer_list_view:
                self.layer_list_view.update_layer_list()
            # 更新editor_map_layer_list组件
            if hasattr(self, "editor_map_layer_list") and self.editor_map_layer_list:
                self._update_editor_map_layer_list()

    def create_image_layer(self):
        """创建图像图层"""
        layer = self.layer_manager.create_layer("image")
        if layer:
            # 更新图层列表显示
            if self.layer_list_view:
                self.layer_list_view.update_layer_list()
            # 更新editor_map_layer_list组件
            if hasattr(self, "editor_map_layer_list") and self.editor_map_layer_list:
                self._update_editor_map_layer_list()

    def delete_current_layer(self):
        """删除当前图层"""
        current_index = self.layer_manager.current_layer_index
        if self.layer_manager.delete_layer(current_index):
            # 清理属于该图层的资源
            for layer_id in list(self.layer_resources.keys()):
                if layer_id == current_index:
                    del self.layer_resources[layer_id]

            # 重新渲染所有可见图层
            self._render_all_layers()

            # 更新资源列表显示
            self._update_res_list_display()

            # 更新图层列表显示
            if self.layer_list_view:
                self.layer_list_view.update_layer_list()
            # 更新editor_map_layer_list组件
            if hasattr(self, "editor_map_layer_list") and self.editor_map_layer_list:
                self._update_editor_map_layer_list()
                # 更新当前选中项
                new_current_index = self.layer_manager.current_layer_index
                if (
                    0
                    <= new_current_index
                    < self.editor_map_layer_list.topLevelItemCount()
                ):
                    self.editor_map_layer_list.setCurrentItem(
                        self.editor_map_layer_list.topLevelItem(new_current_index)
                    )
                    # 触发图层切换事件，确保碰撞编辑器状态更新
                    self._on_layer_changed(new_current_index)

    def _move_layer_up(self):
        """将当前图层上移"""
        current_index = self.layer_manager.current_layer_index
        if self.layer_manager.move_layer_up(current_index):
            # 重新渲染所有可见图层，以更新图层的渲染顺序
            self._render_all_layers()
            # 更新图层列表显示
            if self.layer_list_view:
                self.layer_list_view.update_layer_list()
            # 更新editor_map_layer_list组件
            if hasattr(self, "editor_map_layer_list") and self.editor_map_layer_list:
                self._update_editor_map_layer_list()

    def _move_layer_down(self):
        """将当前图层下移"""
        current_index = self.layer_manager.current_layer_index
        if self.layer_manager.move_layer_down(current_index):
            # 重新渲染所有可见图层，以更新图层的渲染顺序
            self._render_all_layers()
            # 更新图层列表显示
            if self.layer_list_view:
                self.layer_list_view.update_layer_list()
            # 更新editor_map_layer_list组件
            if hasattr(self, "editor_map_layer_list") and self.editor_map_layer_list:
                self._update_editor_map_layer_list()

    def _on_layer_changed(self, index):
        """处理图层切换事件"""
        print(f"DEBUG: 图层切换到索引: {index}")
        # 更新当前图层索引
        self.current_layer = index

        # 获取当前图层
        current_layer = self.layer_manager.get_current_layer()
        if not current_layer:
            return

        # 更新资源列表显示（只显示当前图层的资源）
        self._update_res_list_display()
        # 清除预览，避免预览干扰
        self._remove_preview()
        # 清理编辑框
        self._remove_transform_box()
        # 重置图像选择状态
        self.selected_image_data = None
        self.selected_image_index = -1
        self.selected_layer_id = None
        self.selected_item = None
        # 更新editor_map_layer_list组件的当前选中项
        if hasattr(self, "editor_map_layer_list") and self.editor_map_layer_list:
            if 0 <= index < self.editor_map_layer_list.topLevelItemCount():
                self.editor_map_layer_list.setCurrentItem(
                    self.editor_map_layer_list.topLevelItem(index)
                )

        # 检查当前图层的类型，设置碰撞编辑器的碰撞属性
        if hasattr(self, "ui") and hasattr(self.ui, "map_collision"):
            # 对于图像图层，默认关闭碰撞属性，但如果用户手动打开过，保持打开状态
            if current_layer.layer_type == "image":
                # 图像图层：保持当前的碰撞属性状态
                print("DEBUG: 切换到图像图层，保持当前碰撞属性状态")
            else:
                # 绘制图层：保持当前的碰撞属性状态
                print("DEBUG: 切换到绘制图层，保持当前碰撞属性状态")

        # 更新碰撞编辑器显示，选择当前图层的第一个资源
        layer_resources = self.layer_resources.get(current_layer.layer_id, [])
        if layer_resources:
            # 选择第一个资源和第一个图块
            self.selected_resource_index = 0
            self.selected_tile_index = 0
            # 根据当前图层类型更新碰撞编辑器显示
            if current_layer.layer_type == "drawing":
                # 绘制图层：使用碰撞图块
                self.set_current_collision_tile(0, 0)
                print(f"DEBUG: 更新碰撞编辑器显示，选择资源0和图块0")
            elif current_layer.layer_type == "image":
                # 图像图层：使用碰撞图像
                self.collision_manager.set_current_collision_image(
                    current_layer.layer_id, 0
                )
                print(f"DEBUG: 更新碰撞编辑器显示，选择图像0")

        # 更新工具栏状态
        self._update_toolbar_state(current_layer.layer_type)

    def _update_toolbar_state(self, layer_type):
        """根据图层类型更新工具栏状态"""
        print(f"DEBUG: 更新工具栏状态，图层类型: {layer_type}")

        # 检查UI元素是否存在
        if not hasattr(self, "ui"):
            print("DEBUG: UI对象不存在，跳过工具栏状态更新")
            return

        # 检查图层类型
        is_image = layer_type == "image"

        # 瓦片组按钮
        if hasattr(self.ui, "btn_editor_map_move"):
            self.ui.btn_editor_map_move.setVisible(not is_image)
        if hasattr(self.ui, "btn_editor_map_draw"):
            self.ui.btn_editor_map_draw.setVisible(not is_image)
        if hasattr(self.ui, "btn_editor_map_erase"):
            self.ui.btn_editor_map_erase.setVisible(not is_image)

        # 图像组按钮
        if hasattr(self.ui, "btn_editor_map_image_move"):
            self.ui.btn_editor_map_image_move.setVisible(is_image)
        if hasattr(self.ui, "btn_editor_map_image_scale"):
            self.ui.btn_editor_map_image_scale.setVisible(is_image)
        if hasattr(self.ui, "btn_editor_map_image_rotate"):
            self.ui.btn_editor_map_image_rotate.setVisible(is_image)

        # 默认工具激活
        if is_image:
            # 切换到图像层时，激活移动工具
            if hasattr(self.ui, "btn_editor_map_image_move"):
                self.ui.btn_editor_map_image_move.setChecked(True)
                self.current_tool = "move"
        else:
            # 切换到绘制层时，激活移动工具
            if hasattr(self.ui, "btn_editor_map_move"):
                self.ui.btn_editor_map_move.setChecked(True)
                self.current_tool = "move"

    def _on_layer_item_clicked(self, item, column):
        """处理图层项点击事件"""
        if column == 0:
            # 点击可见性列
            layer_index = self.editor_map_layer_list.indexOfTopLevelItem(item)
            if 0 <= layer_index < self.layer_manager.get_layer_count():
                layer = self.layer_manager.get_layer(layer_index)
                layer.set_visible(not layer.visible)
                # 重新渲染所有可见图层
                self._render_all_layers()
        else:
            # 点击其他列，切换当前图层
            layer_index = self.editor_map_layer_list.indexOfTopLevelItem(item)
            if 0 <= layer_index < self.layer_manager.get_layer_count():
                self.layer_manager.set_current_layer(layer_index)

    def _update_editor_map_layer_list(self):
        """更新editor_map_layer_list组件"""
        if hasattr(self, "editor_map_layer_list") and self.editor_map_layer_list:
            # 清空现有项
            self.editor_map_layer_list.clear()
            # 添加图层项
            for i, layer in enumerate(self.layer_manager.layers):
                from PySide6.QtWidgets import QTreeWidgetItem, QCheckBox

                # 创建图层项
                item = QTreeWidgetItem(["", layer.name, layer.layer_type.capitalize()])
                # 设置可见性复选框
                checkbox = QCheckBox()
                checkbox.setChecked(layer.visible)
                checkbox.stateChanged.connect(
                    lambda state, layer=layer: layer.set_visible(state == 2)
                )
                self.editor_map_layer_list.setItemWidget(item, 0, checkbox)
                # 设置图层索引为数据
                item.setData(0, 1, i)
                # 添加到树控件
                self.editor_map_layer_list.addTopLevelItem(item)
            # 设置当前选中项
            current_index = self.layer_manager.current_layer_index
            if 0 <= current_index < self.editor_map_layer_list.topLevelItemCount():
                self.editor_map_layer_list.setCurrentItem(
                    self.editor_map_layer_list.topLevelItem(current_index)
                )

    def handle_drop_resource(self, resource_index, scene_pos):
        """处理从资源列表拖拽到画布的事件"""
        # 调用 add_image_to_layer 方法
        self.add_image_to_layer(resource_index, scene_pos)

    def add_image_to_layer(self, res_index, pos):
        """真正将图像添加到当前图层并同步数据模型"""
        try:
            print(f"DEBUG: 开始添加图像到图层 - 资源索引: {res_index}, 位置: {pos}")
            # 获取当前图层
            current_layer = self.layer_manager.get_current_layer()
            print(
                f"DEBUG: 当前图层: {current_layer}, 图层类型: {current_layer.layer_type if current_layer else 'None'}"
            )
            if not current_layer or current_layer.layer_type != "image":
                print("⚠️ 只能向图像图层添加图片")
                return

            # 获取当前图层的资源列表
            layer_resources = self.layer_resources.get(current_layer.layer_id, [])
            print(f"DEBUG: 图层资源数量: {len(layer_resources)}")

            # 检查资源索引是否有效
            if res_index < 0 or res_index >= len(layer_resources):
                print(f"⚠️ 资源索引无效: {res_index}")
                return

            # 获取选中的资源
            resource = layer_resources[res_index]
            print(f"DEBUG: 选中的资源: {resource}")

            # 处理资源路径（转换为绝对路径）
            image_path = resource["path"]
            print(f"DEBUG: 资源路径: {image_path}")
            if not os.path.isabs(image_path):
                if self.current_map_path:
                    map_dir = os.path.dirname(self.current_map_path)
                    image_path = os.path.join(map_dir, image_path)
                    print(f"DEBUG: 转换为绝对路径: {image_path}")

            # 检查文件是否存在
            print(f"DEBUG: 检查文件是否存在: {image_path}")
            if not os.path.exists(image_path):
                print(f"⚠️ 资源文件不存在: {image_path}")
                return

            # 创建图像数据
            from .layer_manager import ImageData

            print(f"DEBUG: 创建 ImageData - 路径: {image_path}, 位置: {pos}")
            image_data = ImageData(image_path, pos)
            print(f"DEBUG: ImageData 创建成功, pixmap: {image_data.pixmap}")

            # 设置默认碰撞属性为关闭
            image_data.collision_enabled = False

            # 添加到当前图层
            print(f"DEBUG: 添加图像到图层前, 图层图像数量: {len(current_layer.images)}")
            current_layer.add_image(image_data)
            print(f"DEBUG: 添加图像到图层后, 图层图像数量: {len(current_layer.images)}")

            # 重新渲染图像图层
            print(f"DEBUG: 开始渲染图像图层")
            self._render_image_layer(current_layer)

            # 更新地图数据模型
            self.layer_manager.update_map_model()

            # 设置地图为已修改状态
            self.is_map_modified = True

            # 自动保存地图（如果当前地图有文件路径）
            if self.current_map_path:
                save_result = self.map_model.save(self.current_map_path)
                print(f"DEBUG: 自动保存地图结果: {save_result}")

            print(f"✅ 资源 {res_index} 已成功持久化到图层 {current_layer.name}")

        except Exception as e:
            print(f"处理拖拽资源错误: {e}")
            import traceback

            traceback.print_exc()

    def handle_resource_upload(self):
        """处理资源上传按钮点击事件"""
        # 检查资源列表视图是否已初始化
        if not self.res_list_view:
            return

        # 获取当前图层
        current_layer = self.layer_manager.get_current_layer()
        if not current_layer:
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

        # 获取属性面板中选择的瓦片尺寸（仅用于绘制图层）
        tile_size = 32  # 默认值
        if (
            current_layer.layer_type == "drawing"
            and hasattr(self, "ui")
            and hasattr(self.ui, "att_tile_size")
        ):
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

                # 获取图片尺寸
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

                if current_layer.layer_type == "image":
                    # 图像图层：使用完整图像
                    resource_type = "image"

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

                # 确保图层资源字典存在
                if current_layer.layer_id not in self.layer_resources:
                    self.layer_resources[current_layer.layer_id] = []

                # 添加到图层资源列表
                self.layer_resources[current_layer.layer_id].append(resource_info)

                # 添加到上传资源列表
                self.uploaded_resources.append(resource_info)

                # 图像图层：只添加到资源列表，不自动创建图像
                if current_layer.layer_type == "image":
                    print(f"DEBUG: 图像资源添加到图层资源列表 - 路径: {relative_path}")

                # 绘制图层：添加到地图模型的tile_sets中
                if (
                    current_layer.layer_type == "drawing"
                    and self.project_manager
                    and self.current_map_path
                ):
                    map_dir = os.path.dirname(self.current_map_path)
                    full_image_path = os.path.join(map_dir, relative_path)
                    # 统一使用用户设置的tile_size作为图块尺寸
                    self.map_model.add_tile_set(
                        name=resource_info["name"],
                        image_path=full_image_path,
                        tile_width=tile_size,
                        tile_height=tile_size,
                    )

        # 绘制图层：更新地图模型的全局tile_size
        if current_layer.layer_type == "drawing":
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
            # 获取当前图层
            current_layer = self.layer_manager.get_current_layer()
            if not current_layer:
                return

            # 获取当前图层的资源列表
            layer_resources = self.layer_resources.get(current_layer.layer_id, [])

            if 0 <= index < len(layer_resources):
                self.selected_resource_index = index
                resource = layer_resources[index]

                if resource["resource_type"] == "tileset":
                    # tileset资源默认选择第一个图块
                    self.selected_tile_index = 0
                else:
                    # 单张图片模式，设置默认图块索引为0
                    self.selected_tile_index = 0

                # 根据当前图层类型更新碰撞编辑器显示
                if current_layer.layer_type == "drawing":
                    # 绘制图层：使用碰撞图块
                    self.set_current_collision_tile(index, self.selected_tile_index)
                elif current_layer.layer_type == "image":
                    # 图像图层：使用碰撞图像
                    self.collision_manager.set_current_collision_image(
                        current_layer.layer_id, index
                    )

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
            print(
                f"DEBUG: 开始选择图块 - resource_info: {resource_info}, tile_index: {tile_index}"
            )

            # 检查参数有效性
            if resource_info is None:
                print("DEBUG: resource_info 为 None，选择图块失败")
                return

            # 获取当前图层
            current_layer = self.layer_manager.get_current_layer()
            if not current_layer:
                print("DEBUG: 当前图层不存在，选择图块失败")
                return

            # 获取当前图层的资源列表
            layer_resources = self.layer_resources.get(current_layer.layer_id, [])

            # 查找资源索引
            resource_index = -1
            print(f"DEBUG: layer_resources 长度: {len(layer_resources)}")
            for i, res in enumerate(layer_resources):
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
                if "collisions" not in resource_info:
                    print("DEBUG: 资源中不存在 collisions 字段，创建新的")
                    resource_info["collisions"] = []
                # 确保collisions数组足够大
                while len(resource_info["collisions"]) <= tile_index:
                    print(f"DEBUG: collisions 数组长度不足，添加新元素")
                    resource_info["collisions"].append({})

                # 从地图模型获取最新的碰撞形状数据
                if self.map_model:
                    print(
                        f"DEBUG: 从地图模型获取碰撞形状 - 资源索引: {resource_index}, 图块索引: {tile_index}"
                    )
                    collision_shape = self.map_model.get_tile_collision_shape(
                        resource_index, tile_index
                    )
                    print(f"DEBUG: 获取到的碰撞形状: {collision_shape}")
                    if collision_shape and "points" in collision_shape:
                        resource_info["collisions"][tile_index]["points"] = (
                            collision_shape["points"]
                        )
                        print(f"DEBUG: 从地图模型同步碰撞形状数据: {collision_shape}")
                else:
                    print("DEBUG: map_model 不存在")

                # 打印当前内存中的碰撞形状类型
                if "collisions" in resource_info and tile_index < len(
                    resource_info["collisions"]
                ):
                    collision_data = resource_info["collisions"][tile_index]
                    if "points" in collision_data:
                        print(
                            f"DEBUG: 当前内存中的碰撞形状类型是: polygon, 顶点数: {len(collision_data['points'])}"
                        )
                    else:
                        print(f"DEBUG: 当前内存中的碰撞形状类型是: default rectangle")
                else:
                    print("DEBUG: 无法访问碰撞数据")

                # 更新碰撞编辑器显示
                print(
                    f"DEBUG: 调用 set_current_collision_tile - 资源索引: {resource_index}, 图块索引: {tile_index}"
                )
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

            # 获取当前图层
            current_layer = self.layer_manager.get_current_layer()
            if not current_layer:
                print("DEBUG: 当前图层不存在，返回")
                return

            # 获取当前图层的资源列表
            layer_id = current_layer.layer_id
            print(f"DEBUG: 当前图层ID: {layer_id}")
            print(
                f"DEBUG: layer_resources 字典的键: {list(self.layer_resources.keys())}"
            )
            layer_resources = self.layer_resources.get(layer_id, [])
            print(f"DEBUG: 当前图层的资源数量: {len(layer_resources)}")

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
            print(f"DEBUG: 开始添加资源，资源数量: {len(layer_resources)}")

            for i, resource in enumerate(layer_resources):
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
                    tile_size = resource.get(
                        "tile_size", resource.get("tile_width", 16)
                    )

                    # 计算图块数量（仅图块集合模式）
                    image_width = original_pixmap.width()
                    image_height = original_pixmap.height()
                    tiles_per_row = 0
                    tiles_per_col = 0

                    if resource_type == "tileset":
                        # 修复：兼容图片尺寸小于图块尺寸的情况
                        tiles_per_row = max(1, image_width // tile_size)
                        tiles_per_col = max(1, image_height // tile_size)
                        print(
                            f"DEBUG: 图块集合 - 行列数: {tiles_per_row}x{tiles_per_col}"
                        )

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
                                print(
                                    f"DEBUG: 创建图块 {tile_index} (行: {row}, 列: {col})"
                                )

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
                                    tile_rect.setBrush(
                                        QBrush(QColor(100, 149, 237, 50))
                                    )
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
                                print(
                                    f"DEBUG: 添加图块项到管理列表，键: ({i}, {tile_index})"
                                )
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
        # 绑定图像移动工具按钮
        if hasattr(self.ui, "btn_editor_map_image_move"):
            self.ui.btn_editor_map_image_move.clicked.connect(
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
            self.ui.att_tile_size.currentIndexChanged.connect(
                self._on_tile_size_changed
            )
        # 绑定图层管理按钮
        if hasattr(self.ui, "btn_editor_map_layer_tiled"):
            self.ui.btn_editor_map_layer_tiled.clicked.connect(
                self.create_drawing_layer
            )
        if hasattr(self.ui, "btn_editor_map_layer_image"):
            self.ui.btn_editor_map_layer_image.clicked.connect(self.create_image_layer)
        if hasattr(self.ui, "btn_editor_map_layer_del"):
            self.ui.btn_editor_map_layer_del.clicked.connect(self.delete_current_layer)
        if hasattr(self.ui, "btn_editor_map_layer_up"):
            self.ui.btn_editor_map_layer_up.clicked.connect(self._move_layer_up)
        if hasattr(self.ui, "btn_editor_map_layer_down"):
            self.ui.btn_editor_map_layer_down.clicked.connect(self._move_layer_down)
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
        # 遍历所有图层的资源，从地图模型获取最新的碰撞形状数据并更新到资源池缓存
        if self.map_model:
            for layer_id, layer_resources in self.layer_resources.items():
                for resource_index, resource in enumerate(layer_resources):
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
                                collision_shape = (
                                    self.map_model.get_tile_collision_shape(
                                        resource_index, tile_index
                                    )
                                )
                                if collision_shape and "points" in collision_shape:
                                    resource["collisions"][tile_index]["points"] = (
                                        collision_shape["points"]
                                    )
                                    print(
                                        f"DEBUG: 同步碰撞形状数据 - 资源索引: {resource_index}, 图块索引: {tile_index}, 形状: {collision_shape}"
                                    )
                                else:
                                    # 如果没有碰撞形状，清除缓存中的数据
                                    if "points" in resource["collisions"][tile_index]:
                                        del resource["collisions"][tile_index]["points"]
                                        print(
                                            f"DEBUG: 清除碰撞形状数据 - 资源索引: {resource_index}, 图块索引: {tile_index}"
                                        )
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
            # 获取当前图层的资源列表
            current_layer = self.layer_manager.get_current_layer()
            if not current_layer:
                return
            layer_id = current_layer.layer_id
            layer_resources = self.layer_resources.get(layer_id, [])

            # 检查是否需要图块索引
            resource = layer_resources[self.selected_resource_index]
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
            if hasattr(self, "canvas_scene"):
                try:
                    self.canvas_scene.removeEventFilter(self)
                    print("✅ [MapEditorManager] 画布事件过滤器已移除")
                except:
                    pass

            # 清理collision_manager的引用，让它自己的__del__方法处理
            if hasattr(self, "collision_manager"):
                try:
                    self.collision_manager = None
                    print("✅ [MapEditorManager] collision_manager引用已清除")
                except:
                    pass
        except Exception as e:
            print(f"❌ [MapEditorManager] 清理失败: {e}")
