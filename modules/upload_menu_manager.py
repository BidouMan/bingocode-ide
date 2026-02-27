from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QEvent
from ui.upload_menu_ui import Ui_upload_menu 

class UploadMenuManager(QWidget):
    def __init__(self, parent_frame):
        # parent_frame 传入的是 self.ui.sprite_frame
        super().__init__(parent_frame)
        self.ui = Ui_upload_menu()
        self.ui.setupUi(self)
        
        # 1. 初始状态：让 menu_frame 不可见且高度为 0
        self.ui.menu_frame.setVisible(False)
        self.ui.menu_frame.setMaximumHeight(0)
        
        # 2. 这里的 QWidget 载体设为透明，避免遮挡底部其他元素
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 3. 核心：监听父容器的 Resize 事件实现自动定位 (无需在 main.py 手写)
        if self.parentWidget():
            self.parentWidget().installEventFilter(self)
        
        # 4. 监听触碰弹出逻辑
        self.ui.btn_upload.installEventFilter(self)
        self.installEventFilter(self)
        
        # 初始定位
        self.auto_layout()

    def eventFilter(self, obj, event):
        # A. 自动处理父级缩放导致的位移
        if obj == self.parentWidget() and event.type() == QEvent.Resize:
            self.auto_layout()
            
        # B. 鼠标进入主按钮 -> 展开子菜单
        elif obj == self.ui.btn_upload and event.type() == QEvent.Enter:
            self.toggle_menu(True)
            
        # C. 鼠标离开整个组件区域 -> 收回子菜单
        elif obj == self and event.type() == QEvent.Leave:
            self.toggle_menu(False)
            
        return super().eventFilter(obj, event)

    def auto_layout(self):
        parent = self.parentWidget()
        if not parent:
            return
        
        # 🚀 关键修正 1：强制刷新父容器布局，确保获取真实宽高
        parent.layout().activate() 
        
        # 获取组件建议的大小（按钮+菜单的总尺寸）
        # 如果 sizeHint 不准，可以尝试 self.frameGeometry().size()
        self.adjustSize() 
        mysize = self.size()
        
        # 边界距离
        margin = 15
        
        # 计算坐标
        # pw - sw = 右对齐； ph - sh = 下对齐
        pw = parent.width()
        ph = parent.height()
        
        # 🚀 调试：打印一下，看看父容器是不是太小了
        # print(f"Parent Size: {pw}x{ph}, My Size: {mysize.width()}x{mysize.height()}")
        
        new_x = pw - mysize.width() - margin
        new_y = ph - mysize.height() - margin
        
        self.move(new_x, new_y)

    def toggle_menu(self, show):
        """执行向上弹出的高度动画"""
        if show:
            self.ui.menu_frame.setVisible(True)
        
        self.anim = QPropertyAnimation(self.ui.menu_frame, b"maximumHeight")
        self.anim.setDuration(300)
        self.anim.setStartValue(self.ui.menu_frame.height())
        
        # 根据你三个按钮的大致高度，设置展开值 (120-150左右)
        target_h = 120 if show else 0
        self.anim.setEndValue(target_h)
        
        # 弹出用 OutBack 有弹性感，收回用 InCubic 较快
        self.anim.setEasingCurve(QEasingCurve.OutBack if show else QEasingCurve.InCubic)
        
        # 🚀 重点：动画过程中不断重新计算位置，防止菜单向上伸缩时底部按钮位置抖动
        self.anim.valueChanged.connect(self.auto_layout)
        
        if not show:
            self.anim.finished.connect(lambda: self.ui.menu_frame.setVisible(False))
            
        self.anim.start()