import os
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtWidgets import (
    QGraphicsScene,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsView,
)
from PySide6.QtGui import QPixmap, QBrush, QColor, QPen


class CollisionManager(QObject):
    """碰撞管理器，负责处理碰撞相关的功能"""

    # 信号定义
    collision_changed = Signal(int, int, bool)  # 碰撞状态变化信号

    def __init__(self, map_model, parent=None):
        super().__init__(parent)
        self.map_model = map_model
        self.col_editor_scene = None
        self.col_editor_view = None
        self.current_collision_tile = None
        self.collision_rect_item = None
        self.tile_pixmap_provider = None  # 图块图像获取函数

    def __del__(self):
        """清理资源，避免程序退出时崩溃"""
        try:
            # 清理场景和视图
            if self.col_editor_scene:
                self.col_editor_scene.clear()
            self.col_editor_scene = None
            self.col_editor_view = None
        except Exception:
            pass

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

        # 设置居中对齐
        self.col_editor_view.setAlignment(Qt.AlignCenter)
        self.col_editor_view.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorViewCenter
        )

        print(
            f"碰撞编辑器初始化完成: scene={self.col_editor_scene}, view={self.col_editor_view}"
        )

    def set_current_collision_tile(self, resource_index, tile_index):
        """设置当前选中的碰撞图块"""
        self.current_collision_tile = (resource_index, tile_index)
        self._update_collision_display()

    def _update_collision_display(self):
        """更新碰撞编辑器的显示"""
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
                collision_enabled = self.map_model.get_tile_collision(
                    resource_index, tile_index
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

            # 重新设计变换逻辑：先缩放，后平移到视图中心
            transform = self.col_editor_view.transform()
            transform.reset()

            # 先缩放
            transform.scale(scale, scale)

            # 再平移到视图中心
            transform.translate(view_width / 2, view_height / 2)

            self.col_editor_view.setTransform(transform)

            # 显示视图
            self.col_editor_view.show()
        else:
            # 如果没有pixmap，清空场景
            self.col_editor_scene.clear()
            self.col_editor_view.fitInView(
                self.col_editor_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
            )

    def _get_tile_pixmap(self, resource_index, tile_index):
        """获取图块图像"""
        # 这里需要从外部获取图块图像
        # 暂时返回None，实际使用时需要从MapEditorManager获取
        return None

    def set_collision_enabled(self, enabled):
        """设置碰撞启用状态"""
        if self.current_collision_tile:
            resource_index, tile_index = self.current_collision_tile
            if self.map_model:
                self.map_model.set_tile_collision(resource_index, tile_index, enabled)
                self._update_collision_display()
                self.collision_changed.emit(resource_index, tile_index, enabled)

    def set_tile_pixmap_provider(self, provider):
        """设置图块图像获取函数"""
        self.tile_pixmap_provider = provider

    def _get_tile_pixmap(self, resource_index, tile_index):
        """获取图块图像"""
        if self.tile_pixmap_provider:
            return self.tile_pixmap_provider(resource_index, tile_index)
        return None
