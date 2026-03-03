# modules/upload_menu_manager.py
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QEvent, QPropertyAnimation, QEasingCurve, QRect
from ui.upload_menu_ui import Ui_upload_menu 

class UploadMenuManager(QWidget):
    def __init__(self, list_sprite):
        super().__init__(list_sprite)
        self.ui = Ui_upload_menu()
        self.ui.setupUi(self)
        
        # 1. 基础属性
        self.setFixedSize(50, 226)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 🚀 2. 容器设置：不要设置鼠标穿透属性，否则子按钮无法响应
        self.menu_container = QWidget(self)
        self.menu_container.setGeometry(0, 0, 50, 226)
        # 移除这行：self.menu_container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        self.ui.menu_frame.setParent(self.menu_container)
        self.menu_container.setObjectName("upload_menu_mask_container")

        # 3. 核心参数
        self.target_h = 120 
        self.anchor_y = 201 
        
        # 给子按钮安装过滤器
        for btn in [self.ui.btn_import, self.ui.btn_paint, self.ui.btn_open]:
            btn.installEventFilter(self)

        self.ui.menu_frame.setGeometry(10, self.anchor_y, 30, 0)
        self.ui.menu_frame.setVisible(False)

        # 🚀 4. 修正主按钮名称 (btn_upload -> btn_upload1)
        self.ui.btn_upload.setParent(self)
        self.ui.btn_upload.setGeometry(0, 176, 50, 50)
        self.ui.btn_upload.raise_() 

        # 5. 应用遮罩
        from PySide6.QtGui import QRegion
        self.menu_container.setMask(QRegion(0, 0, 50, self.anchor_y))

        # 🚀 6. 事件监听：修正 btn_upload1
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
            end_geo = QRect(10, self.anchor_y - self.target_h, 30, self.target_h)
        else:
            # 向下收缩
            end_geo = QRect(10, self.anchor_y, 30, 0)

        self.anim.setStartValue(self.ui.menu_frame.geometry())
        self.anim.setEndValue(end_geo)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        if not show:
            self.anim.finished.connect(lambda: self.ui.menu_frame.setVisible(False))
            
        self.anim.start()

    def eventFilter(self, obj, event):
    

        # 🚀 修正为主按钮 btn_upload1
        if obj == self.ui.btn_upload and event.type() == QEvent.Type.Enter:
            self.anim_menu(True)
        # 当鼠标离开整个 UploadMenuManager 区域时收回
        elif obj == self and event.type() == QEvent.Type.Leave:
            self.anim_menu(False)
        
        if event.type() == QEvent.Type.Resize:
            self.auto_layout()
        return super().eventFilter(obj, event)

    def auto_layout(self):
        parent = self.parentWidget()
        if not parent: return
        # 保持在父窗口右下角偏移
        self.move(parent.width() - 70 +15, parent.height() - 226 -5)
        self.raise_()
