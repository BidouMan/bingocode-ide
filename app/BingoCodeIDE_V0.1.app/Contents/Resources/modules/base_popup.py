from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPoint

class BasePopup(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 核心设置：窗口置顶、弹出模式（点外部自动关闭）、无边框
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def show_popup_menu(self, target_widget):
        """将菜单显示在目标组件下方"""
        # target_widget就是绑定的按键 传递进来以后 就可以计算位置 确保下拉菜单在按钮下方
        # 计算目标组件左下角的全局坐标
        global_pos = target_widget.mapToGlobal(target_widget.rect().bottomLeft())
        # 稍微留 2 像素的间隙，更有高级感
        self.move(global_pos + QPoint(0, 2))
        self.show()