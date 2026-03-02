from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QEvent,QEasingCurve,QPropertyAnimation,QSize,QPoint
from ui.upload_menu_ui import Ui_upload_menu 

# modules/upload_menu_manager.py

class UploadMenuManager(QWidget):
    def __init__(self, parent_frame):
        super().__init__(parent_frame)
        self.ui = Ui_upload_menu()
        self.ui.setupUi(self)
        
        # 1. 核心：给容器一个固定的高度（假设按钮50 + 菜单150 = 200）
        # 宽度也给够（例如60），确保不会被裁切
        self.fixed_w = 60
        self.fixed_h = 220 
        self.setFixedSize(self.fixed_w, self.fixed_h)
        
        # 2. 设置透明，这样 220 高度的透明盒子不会遮挡列表的点击
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 3. 初始隐藏菜单
        self.ui.menu_frame.setVisible(False)
        self.ui.menu_frame.setMaximumHeight(0)
        
        # 4. 安装事件过滤器
        if self.parentWidget():
            self.parentWidget().installEventFilter(self)
        self.ui.btn_upload.installEventFilter(self)
        self.installEventFilter(self)

        self.default_icon_size = 40  # 你之前设置的默认尺寸
        self.hover_icon_size = 44    # 悬停时变大的尺寸
        
        # 初始化图标大小
        self.ui.btn_upload.setIconSize(QSize(self.default_icon_size, self.default_icon_size))
        
        self.auto_layout()

     

    def toggle_icon_zoom(self, zoom_in):
        """控制图标缩放动画"""
        # 如果之前有动画在跑，先停止它
        if hasattr(self, 'icon_anim'):
            self.icon_anim.stop()
            
        self.icon_anim = QPropertyAnimation(self.ui.btn_upload, b"iconSize")
        self.icon_anim.setDuration(200) # 200毫秒的平滑过渡
        
        start_size = self.ui.btn_upload.iconSize()
        end_val = self.hover_icon_size if zoom_in else self.default_icon_size
        end_size = QSize(end_val, end_val)
        
        self.icon_anim.setStartValue(start_size)
        self.icon_anim.setEndValue(end_size)
        self.icon_anim.setEasingCurve(QEasingCurve.Type.OutCubic) # 出色减速曲线，更有质感
        self.icon_anim.start()

    def eventFilter(self, obj, event):
        if obj == self.ui.btn_upload:
            if event.type() == QEvent.Type.Enter:
                self.toggle_icon_zoom(True)  # 图标变大
                # self.toggle_menu(True)       # 弹出菜单
            elif event.type() == QEvent.Type.Leave:
                # 注意：这里通常不需要在 Leave 变小，
                # 因为用户可能会移入菜单，变小逻辑写在整个组件的 Leave 更合适
                pass
                
        # 鼠标离开整个盒子（包含菜单和按钮）时，全部复原
        elif obj == self and event.type() == QEvent.Type.Leave:
            self.toggle_icon_zoom(False) # 图标恢复
            # self.toggle_menu(False)      # 收起菜单
            
        # 别忘了保留 Resize 的 auto_layout
        if obj == self.parentWidget() and event.type() == QEvent.Resize:
            self.auto_layout()
            
        return super().eventFilter(obj, event)

    def auto_layout(self):
        parent = self.parentWidget()
        if not parent: return
        
        margin = 20
        # 🚀 关键：因为 self.fixed_h 是恒定的 220，
        # 所以 new_y 永远是 parent.height() - 220 - 20。
        # 坐标绝对不会动，按钮也就绝对不会跳！
        new_x = parent.width() - self.fixed_w - margin
        new_y = parent.height() - self.fixed_h - margin
        
        self.move(new_x, new_y)
        self.raise_()

    def toggle_menu(self, show):
        if show:
            self.ui.menu_frame.setVisible(True)
        
        # 目标高度：根据 Designer 里的按钮数量决定
        target_h = 150 if show else 0
        
        self.anim = QPropertyAnimation(self.ui.menu_frame, b"maximumHeight")
        self.anim.setDuration(250)
        self.anim.setEndValue(target_h)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # 🚀 重点：这里不需要连接 auto_layout！
        # 盒子不动，按钮不动，只有菜单在盒子内部长高。
        
        if not show:
            self.anim.finished.connect(lambda: self.ui.menu_frame.setVisible(False))
        self.anim.start() # 确保在列表上方