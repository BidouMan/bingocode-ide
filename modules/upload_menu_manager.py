# modules/upload_menu_manager.py
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QEvent, QPropertyAnimation, QEasingCurve, QRect
from ui.upload_menu_ui import Ui_upload_menu 

class UploadMenuManager(QWidget):
    def __init__(self, list_sprite):
        super().__init__(list_sprite)
        self.ui = Ui_upload_menu()
        self.ui.setupUi(self)
        
        # 1. 基础属性（UI无法设置背景穿透和固定窗口尺寸）
        self.setFixedSize(70, 226)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 🚀 2. 容器迁移 (为了实现局部 Mask，必须在代码中移动 Parent)
        self.menu_container = QWidget(self)
        self.menu_container.setGeometry(0, 0, 70, 226)
        self.menu_container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.ui.menu_frame.setParent(self.menu_container)
        
        # 🚀 3. 核心对齐参数
        # 动画抽出高度：3个30px按钮 + 4px顶边距 + 2个4px间距 + 占位高度 ≈ 140
        self.target_h = 125 
        self.anchor_y = 201 # 按钮圆心位置
        
        # 初始几何状态：高度为 0，位置在圆心
        self.ui.menu_frame.setGeometry(20, self.anchor_y, 30, 0)
        self.ui.menu_frame.setVisible(False)

        # 🚀 4. 按钮层级隔离 (确保主按钮不被 Mask 裁剪)
        self.ui.btn_upload.setParent(self)
        self.ui.btn_upload.setGeometry(10, 176, 50, 50)
        self.ui.btn_upload.raise_() 

        # 🚀 5. 应用遮罩 (UI 无法设置局部 QRegion Mask)
        from PySide6.QtGui import QRegion
        self.menu_container.setMask(QRegion(0, 0, 70, self.anchor_y))

        # 6. 事件监听
        self.anim = None
        self.ui.btn_upload.installEventFilter(self)
        self.installEventFilter(self)
        list_sprite.installEventFilter(self)
        self.auto_layout()

    def anim_menu(self, show=True):
        """形变动画逻辑"""
        if self.anim and self.anim.state() == QPropertyAnimation.State.Running:
            self.anim.stop()

        self.anim = QPropertyAnimation(self.ui.menu_frame, b"geometry")
        self.anim.setDuration(300)
        
        if show:
            self.ui.menu_frame.setVisible(True)
            # 向上伸展
            end_geo = QRect(20, self.anchor_y - self.target_h, 30, self.target_h)
        else:
            # 向下收缩
            end_geo = QRect(20, self.anchor_y, 30, 0)

        self.anim.setStartValue(self.ui.menu_frame.geometry())
        self.anim.setEndValue(end_geo)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        if not show:
            self.anim.finished.connect(lambda: self.ui.menu_frame.setVisible(False))
            
        self.anim.start()

    def eventFilter(self, obj, event):
        if obj == self.ui.btn_upload and event.type() == QEvent.Type.Enter:
            self.anim_menu(True)
        elif obj == self and event.type() == QEvent.Type.Leave:
            self.anim_menu(False)
        
        if event.type() == QEvent.Type.Resize:
            self.auto_layout()
        return super().eventFilter(obj, event)

    def auto_layout(self):
        parent = self.parentWidget()
        if not parent: return
        # 保持在父窗口右下角偏移
        self.move(parent.width() - 70 +5, parent.height() - 226 -5)
        self.raise_()