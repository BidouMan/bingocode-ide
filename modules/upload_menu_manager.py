# modules/upload_menu_manager.py
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QEvent, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QCursor
from ui.upload_menu_ui import Ui_upload_menu 

class UploadMenuManager(QWidget):
    def __init__(self, parent_frame):
        super().__init__(parent_frame)
        self.ui = Ui_upload_menu()
        self.ui.setupUi(self)
        
        # 1. 容器固定尺寸
        self.fixed_w = 70
        self.fixed_h = 226 
        self.setFixedSize(self.fixed_w, self.fixed_h)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 🚀 2. 核心层级控制：确保按钮永远在最上层
        self.ui.btn_upload.raise_()
        
        # 3. 精准对齐 Y 轴
        # 按钮在 176，我们让菜单高度展开为 160
        self.full_menu_h = 130
        # 菜单 Y = 按钮顶部(176) - 菜单高度(160) + 15(重叠部分，让它钻进按钮后方)
        menu_y = 176 - self.full_menu_h + 15
        self.ui.menu_frame.move(self.ui.menu_frame.x(), menu_y)
        
        # 4. 初始状态
        self.ui.menu_frame.setMaximumHeight(0)
        self.ui.menu_frame.setVisible(False)
        
        # 5. 动画设置
        self.anim = QPropertyAnimation(self.ui.menu_frame, b"maximumHeight")
        self.anim.setDuration(300)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # 6. 安装事件过滤
        self.ui.btn_upload.installEventFilter(self)
        self.installEventFilter(self)
        if self.parentWidget():
            self.parentWidget().installEventFilter(self)
        
        self.auto_layout()

    def toggle_menu(self, show):
        self.anim.stop()
        if show:
            self.ui.menu_frame.setVisible(True)
            # 🚀 每次弹出前再次置顶按钮，确保盖住菜单底部
            self.ui.btn_upload.raise_() 
            self.anim.setEndValue(self.full_menu_h)
        else:
            self.anim.setEndValue(0)
        self.anim.start()

    def eventFilter(self, obj, event):
        # A. 鼠标进入按钮 -> 展开
        if obj == self.ui.btn_upload and event.type() == QEvent.Type.Enter:
            self.toggle_menu(True)
            
        # B. 鼠标离开整个 Manager 区域 -> 收回
        elif obj == self and event.type() == QEvent.Type.Leave:
            # 修复：使用 QCursor 获取全局位置并转为本地坐标
            local_pos = self.mapFromGlobal(QCursor.pos())
            if not self.rect().contains(local_pos):
                self.toggle_menu(False)
            
        # C. 父容器缩放重新定位
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