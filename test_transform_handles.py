#!/usr/bin/env python3
"""
测试脚本：测试TransformHandle和TransformBoxItem的功能
"""

import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsItem
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPixmap, QColor, QPen, QBrush, QPainter

class TransformHandle(QGraphicsRectItem):
    def __init__(self, parent, pos_key):
        super().__init__(parent)
        self.pos_key = pos_key
        self.size = 8  # 开启忽略变换后，6像素通常更易点击
        self.setRect(-self.size / 2, -self.size / 2, self.size, self.size)

        self.setBrush(QColor("#61afef"))
        self.setPen(QPen(Qt.GlobalColor.white, 1))

        # --- 核心修复：让手柄不随视图缩放 ---
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        # ----------------------------------

        self.setZValue(1001)
        self.setFlags(
            self.flags()
            | QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)

        # 初始化 enabledSignals 属性
        self.enabledSignals = True

    def paint(self, painter, option, widget):
        """重绘为圆形"""
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)  # 开启抗锯齿
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawEllipse(self.rect())  # 画圆形

    def hoverEnterEvent(self, event):
        """鼠标悬停在手柄上时改变光标样式"""
        print(
            f"DEBUG: TransformHandle.hoverEnterEvent - pos_key: {self.pos_key}, pos: {event.pos()}"
        )
        if self.pos_key == "tl" or self.pos_key == "br":
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif self.pos_key == "tr" or self.pos_key == "bl":
            self.setCursor(Qt.CursorShape.SizeBDiagCursor)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """鼠标离开手柄时恢复光标样式"""
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        """处理鼠标按下事件"""
        print(
            f"DEBUG: TransformHandle.mousePressEvent - button: {event.button()}, pos: {event.pos()}"
        )
        if event.button() == Qt.LeftButton:
            # 保存鼠标按下的位置
            self.button_down_pos = event.pos()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """处理鼠标移动事件"""
        print(
            f"DEBUG: TransformHandle.mouseMoveEvent - buttons: {event.buttons()}, pos: {event.pos()}"
        )
        if event.buttons() & Qt.LeftButton:
            # 计算新位置
            pos = event.pos()
            # 检查self.button_down_pos是否为None
            if not hasattr(self, 'button_down_pos') or self.button_down_pos is None:
                print("DEBUG: self.button_down_pos is None, skipping")
                event.accept()
                return
            # 计算鼠标在父坐标系中的位置
            new_pos = self.mapToParent(pos)
            print(
                f"DEBUG: TransformHandle.mouseMoveEvent - pos: {pos}, button_down_pos: {self.button_down_pos}, new_pos: {new_pos}"
            )
            # 调用 itemChange 方法处理位置变化
            self.setItemPos(new_pos)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def setItemPos(self, pos):
        """设置手柄位置"""
        rect = self.parentItem().rect()
        original_rect = QRectF(rect)
        print(f"DEBUG: TransformHandle.setItemPos - pos: {pos}, pos_key: {self.pos_key}, original rect: {original_rect}")

        # 获取父项的初始宽高比（用于等比缩放）
        initial_ratio = self.parentItem().initial_ratio

        # 检查是否按下了Shift键
        is_shift_pressed = QApplication.keyboardModifiers() & Qt.ShiftModifier

        # 计算新的矩形
        if self.pos_key == "tl":  # 左上角
            new_rect = QRectF(pos, rect.bottomRight())
        elif self.pos_key == "tr":  # 右上角
            # 确保矩形的高度为正数
            top_left = QPointF(rect.left(), min(rect.top(), pos.y()))
            bottom_right = QPointF(pos.x(), max(rect.bottom(), pos.y()))
            new_rect = QRectF(top_left, bottom_right)
        elif self.pos_key == "bl":  # 左下角
            # 确保矩形的高度为正数
            top_left = QPointF(min(rect.left(), pos.x()), rect.top())
            bottom_right = QPointF(max(rect.right(), pos.x()), pos.y())
            new_rect = QRectF(top_left, bottom_right)
        elif self.pos_key == "br":  # 右下角
            new_rect = QRectF(rect.topLeft(), pos)
        else:
            return

        print(f"DEBUG: TransformHandle.setItemPos - new_rect: {new_rect}")

        # 确保矩形大小合理
        if new_rect.width() < 10 or new_rect.height() < 10:
            print(f"DEBUG: TransformHandle.setItemPos - rect too small, skipping")
            return

        # 等比缩放
        if is_shift_pressed:
            current_ratio = new_rect.width() / new_rect.height()
            if current_ratio > initial_ratio:
                # 宽度过大，调整宽度
                new_width = new_rect.height() * initial_ratio
                if self.pos_key == "tl" or self.pos_key == "bl":
                    new_rect.setWidth(new_width)
                elif self.pos_key == "tr" or self.pos_key == "br":
                    new_rect.setLeft(new_rect.right() - new_width)
            else:
                # 高度过大，调整高度
                new_height = new_rect.width() / initial_ratio
                if self.pos_key == "tl" or self.pos_key == "tr":
                    new_rect.setHeight(new_height)
                elif self.pos_key == "bl" or self.pos_key == "br":
                    new_rect.setTop(new_rect.bottom() - new_height)

            print(f"DEBUG: TransformHandle.setItemPos - after aspect ratio adjustment: {new_rect}")

        # 更新父项的矩形
        parent = self.parentItem()
        print(f"DEBUG: TransformHandle.setItemPos - parent before setRect: {parent.rect()}")
        parent.setRect(new_rect)
        print(f"DEBUG: TransformHandle.setItemPos - parent after setRect: {parent.rect()}")
        
        # 更新手柄位置
        print(f"DEBUG: TransformHandle.setItemPos - updating handles pos")
        parent.update_handles_pos()
        
        # 打印所有手柄的位置
        for key, handle in parent.handles.items():
            print(f"DEBUG: TransformHandle.setItemPos - handle {key} pos: {handle.pos()}")

        # 实时更新图像变换
        if hasattr(parent, "update_transform"):
            print(f"DEBUG: TransformHandle.setItemPos - updating transform")
            parent.update_transform()
            
        # 强制重绘
        parent.update()
        self.update()

    def itemChange(self, change, value):
        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionChange
            and self.enabledSignals
        ):
            new_pos = value
            rect = self.parentItem().rect()
            
            # 计算新的矩形
            if self.pos_key == "tl":  # 左上角
                new_rect = QRectF(new_pos, rect.bottomRight())
            elif self.pos_key == "tr":  # 右上角
                new_rect = QRectF(QPointF(rect.left(), rect.top()), new_pos)
            elif self.pos_key == "bl":  # 左下角
                new_rect = QRectF(QPointF(rect.left(), rect.top()), QPointF(rect.right(), new_pos.y()))
                new_rect.setLeft(new_pos.x())
            elif self.pos_key == "br":  # 右下角
                new_rect = QRectF(rect.topLeft(), new_pos)
            else:
                return super().itemChange(change, value)

            # 确保矩形大小合理
            if new_rect.width() < 10 or new_rect.height() < 10:
                # 返回手柄应该在的位置（选框角落）
                if self.pos_key == "tl":
                    return rect.topLeft()
                elif self.pos_key == "tr":
                    return rect.topRight()
                elif self.pos_key == "bl":
                    return rect.bottomLeft()
                elif self.pos_key == "br":
                    return rect.bottomRight()

            # 获取父项的初始宽高比（用于等比缩放）
            initial_ratio = self.parentItem().initial_ratio
            
            # 检查是否按下了Shift键
            is_shift_pressed = QApplication.keyboardModifiers() & Qt.ShiftModifier
            
            # 等比缩放
            if is_shift_pressed:
                current_ratio = new_rect.width() / new_rect.height()
                if current_ratio > initial_ratio:
                    # 宽度过大，调整宽度
                    new_width = new_rect.height() * initial_ratio
                    if self.pos_key == "tl" or self.pos_key == "bl":
                        new_rect.setWidth(new_width)
                    elif self.pos_key == "tr" or self.pos_key == "br":
                        new_rect.setLeft(new_rect.right() - new_width)
                else:
                    # 高度过大，调整高度
                    new_height = new_rect.width() / initial_ratio
                    if self.pos_key == "tl" or self.pos_key == "tr":
                        new_rect.setHeight(new_height)
                    elif self.pos_key == "bl" or self.pos_key == "br":
                        new_rect.setTop(new_rect.bottom() - new_height)

            # 更新父项的矩形
            self.parentItem().setRect(new_rect)
            self.parentItem().update_handles_pos()
            
            # 实时更新图像变换
            if hasattr(self.parentItem(), 'update_transform'):
                self.parentItem().update_transform()
                
            # 返回手柄的新位置（应该是矩形的角落）
            if self.pos_key == "tl":
                return new_rect.topLeft()
            elif self.pos_key == "tr":
                return new_rect.topRight()
            elif self.pos_key == "bl":
                return new_rect.bottomLeft()
            elif self.pos_key == "br":
                return new_rect.bottomRight()

        return super().itemChange(change, value)

class TransformBoxItem(QGraphicsRectItem):
    def __init__(self, initial_rect, parent_item=None, transform_callback=None):
        super().__init__(initial_rect, parent_item)
        pen = QPen(QColor("#61afef"), 1.5)  # 1.5 像素宽，蓝白色
        pen.setCosmetic(True)  # 关键：让线宽不随缩放改变
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)  # 让拐角尖锐
        self.setPen(pen)
        self.setZValue(1000)
        self.transform_callback = transform_callback  # 添加回调函数

        # 保存初始宽高比，用于等比缩放
        self.initial_width = initial_rect.width()
        self.initial_height = initial_rect.height()
        self.initial_ratio = (
            self.initial_width / self.initial_height if self.initial_height > 0 else 1
        )

        # 设置可移动和鼠标事件
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.ArrowCursor)

        self.handles = {}
        for key in ["tl", "tr", "bl", "br"]:
            handle = TransformHandle(self, key)
            handle.enabledSignals = False
            self.handles[key] = handle

        self.update_handles_pos()

        # 鼠标移动相关
        self._is_dragging = False
        self._drag_start_pos = QPointF()

    def update_handles_pos(self):
        """根据当前矩形位置，将4个手柄对齐到顶点"""
        r = self.rect()
        h_map = {
            "tl": r.topLeft(),
            "tr": r.topRight(),
            "bl": r.bottomLeft(),
            "br": r.bottomRight(),
        }
        for key, pos in h_map.items():
            self.handles[key].enabledSignals = False
            # 直接设置手柄位置到矩形的精确角落位置
            self.handles[key].setPos(pos)
            self.handles[key].enabledSignals = True

    def update_transform(self):
        """实时更新图像变换"""
        if self.transform_callback:
            self.transform_callback(self.rect())

    def hoverEnterEvent(self, event):
        """鼠标进入时改变光标样式"""
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        """鼠标离开时恢复光标样式"""
        self.setCursor(Qt.CursorShape.ArrowCursor)
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        """开始拖动"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_start_pos = event.pos()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """拖动过程中"""
        if self._is_dragging:
            # 检查self._drag_start_pos是否为None
            if self._drag_start_pos is None:
                print("DEBUG: _drag_start_pos is None, skipping")
                event.accept()
                return
            # 手动计算坐标差，避免QPointF减法运算符错误
            delta_x = event.pos().x() - self._drag_start_pos.x()
            delta_y = event.pos().y() - self._drag_start_pos.y()
            delta = QPointF(delta_x, delta_y)
            # 手动计算新位置，避免QPointF加法运算符错误
            new_pos_x = self.pos().x() + delta.x()
            new_pos_y = self.pos().y() + delta.y()
            new_pos = QPointF(new_pos_x, new_pos_y)

            # 像素吸附：将位置对齐到整数像素
            new_pos = QPointF(round(new_pos.x()), round(new_pos.y()))
            self.setPos(new_pos)

            # 更新手柄位置
            self.update_handles_pos()

            # 实时更新图像变换
            self.update_transform()

            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """结束拖动"""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            event.accept()
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        """处理位置变化"""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            # 像素吸附：将位置对齐到整数像素
            return QPointF(round(value.x()), round(value.y()))
        return super().itemChange(change, value)

    def paint(self, painter, option, widget):
        r = self.rect()
        painter.save()

        # 绘制主蓝色边框
        painter.setPen(self.pen())
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(r)

        painter.restore()

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Transform Handles Test")
        self.setGeometry(100, 100, 800, 600)
        
        # 创建场景和视图
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.setCentralWidget(self.view)
        
        # 设置场景背景
        self.scene.setBackgroundBrush(QColor(240, 240, 240))
        
        # 创建一个测试图像
        self.test_pixmap = QPixmap(100, 100)
        self.test_pixmap.fill(QColor(100, 200, 100))
        
        # 创建图像项
        from PySide6.QtWidgets import QGraphicsPixmapItem
        self.image_item = QGraphicsPixmapItem(self.test_pixmap)
        self.image_item.setPos(200, 200)
        self.scene.addItem(self.image_item)
        
        # 创建TransformBoxItem
        initial_rect = QRectF(0, 0, 100, 100)
        self.transform_box = TransformBoxItem(initial_rect, None, self.on_transform_changed)
        self.transform_box.setPos(200, 200)
        self.scene.addItem(self.transform_box)
        
        # 测试日志
        print("Test window created")
        print(f"Initial rect: {initial_rect}")
        print(f"Transform box pos: {self.transform_box.pos()}")
    
    def on_transform_changed(self, rect):
        """处理变换变化"""
        print(f"Transform changed: {rect}")
        print(f"Transform box pos: {self.transform_box.pos()}")
        
        # 计算新的图像位置（考虑矩形的偏移）
        new_pos = QPointF(
            self.transform_box.pos().x() + rect.left(),
            self.transform_box.pos().y() + rect.top()
        )
        
        # 更新图像项位置
        self.image_item.setPos(new_pos)
        
        # 更新图像项大小
        initial_width = 100
        initial_height = 100
        
        # 计算缩放因子
        scale_x = rect.width() / initial_width
        scale_y = rect.height() / initial_height
        
        # 重置缩放后再设置新的缩放，避免累积缩放
        self.image_item.setScale(1.0)
        
        # 使用QTransform来同时设置x和y方向的缩放
        from PySide6.QtGui import QTransform
        transform = QTransform()
        transform.scale(scale_x, scale_y)
        self.image_item.setTransform(transform)
        
        # 打印缩放信息，用于调试
        print(f"Image scale: x={scale_x}, y={scale_y}, Image pos: {self.image_item.pos()}, Image bounding rect: {self.image_item.boundingRect()}")
        print(f"Transform box rect: {rect}, Transform box pos: {self.transform_box.pos()}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    print("Test window shown")
    sys.exit(app.exec())
