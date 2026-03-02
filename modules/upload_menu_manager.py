# modules/upload_menu_manager.py
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QEvent, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QCursor
from ui.upload_menu_ui import Ui_upload_menu 

class UploadMenuManager(QWidget):
    def __init__(self, parent_frame):
        super().__init__(parent_frame)
        self.ui = Ui_upload_menu()
        self.ui.setupUi(self)
        
        # 1. 基础属性
        self.fixed_w = 70
        self.fixed_h = 226 
        self.setFixedSize(self.fixed_w, self.fixed_h)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 2. 坐标与层级
        self.ui.menu_frame.setParent(self)
        self.btn_geo = self.ui.btn_upload.geometry()
        
        # 🚀 核心修复：不设宽度，只读宽度。利用偏移量实现 X 轴对齐
        # 此时读取的是 Designer 里设定的高度和宽度
        self.menu_w = self.ui.menu_frame.width()
        self.full_menu_h = 120 
        
        # 计算居中对齐的 X：按钮 X + (按钮宽 - 菜单宽)/2
        self.menu_x = self.btn_geo.x() + (self.btn_geo.width() - self.menu_w) // 2
        
        # 设定底部锚点 Y（按钮顶部 + 10px 重叠）
        self.anchor_y = self.btn_geo.y() + 10 
        
        # 3. 初始位置
        self.ui.menu_frame.move(self.menu_x, self.anchor_y)
        self.ui.menu_frame.setMaximumHeight(0)
        self.ui.menu_frame.setVisible(False)
        self.ui.btn_upload.raise_()
        
        # 4. 动画配置
        self.anim = QPropertyAnimation(self.ui.menu_frame, b"maximumHeight")
        self.anim.setDuration(450) 
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # 5. 信号连接
        self.anim.valueChanged.connect(self._on_value_changed)
        self.anim.finished.connect(self._on_anim_finished)
        
        self.ui.btn_upload.installEventFilter(self)
        self.installEventFilter(self)
        if self.parentWidget():
            self.parentWidget().installEventFilter(self)
        
        self.auto_layout()

    def _on_value_changed(self, h):
        """保持向上滑动感，且 X 坐标始终维持计算好的对齐值"""
        self.ui.menu_frame.move(self.menu_x, self.anchor_y - h)
        self.update()

    def _on_anim_finished(self):
        if self.ui.menu_frame.maximumHeight() == 0:
            self.ui.menu_frame.setVisible(False)

    def toggle_menu(self, show):
        self.anim.stop()
        if show:
            self.ui.menu_frame.setVisible(True)
            self.anim.setEndValue(self.full_menu_h)
        else:
            self.anim.setEndValue(0)
        self.anim.start()
        self.ui.btn_upload.raise_()

    def eventFilter(self, obj, event):
        if obj == self.ui.btn_upload and event.type() == QEvent.Type.Enter:
            self.toggle_menu(True)
        elif obj == self and event.type() == QEvent.Type.Leave:
            local_pos = self.mapFromGlobal(QCursor.pos())
            if not self.rect().contains(local_pos):
                self.toggle_menu(False)
        
        if obj == self.parentWidget() and event.type() == QEvent.Resize:
            self.auto_layout()
        return super().eventFilter(obj, event)

    def auto_layout(self):
        parent = self.parentWidget()
        if not parent: return
        margin = 15
        new_x = parent.width() - self.fixed_w - margin
        new_y = parent.height() - self.fixed_h - margin
        self.move(new_x, new_y)
        self.raise_()