from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QPoint, QEvent


class PopupManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._anchor_btn = None

    def show_popup_menu(self, target_widget):
        self._anchor_btn = target_widget
        global_pos = target_widget.mapToGlobal(target_widget.rect().bottomLeft())
        self.move(global_pos + QPoint(0, 2))
        self.show()

        if self._anchor_btn:
            self._anchor_btn.setProperty("menuOpen", True)
            self._anchor_btn.style().unpolish(self._anchor_btn)
            self._anchor_btn.style().polish(self._anchor_btn)

        QApplication.instance().installEventFilter(self)

    def hide_popup_menu(self):
        QApplication.instance().removeEventFilter(self)

        if self._anchor_btn:
            self._anchor_btn.setProperty("menuOpen", False)
            self._anchor_btn.style().unpolish(self._anchor_btn)
            self._anchor_btn.style().polish(self._anchor_btn)
            self._anchor_btn = None

        self.hide()

    def close(self):
        self.hide_popup_menu()
        super().close()

    def eventFilter(self, obj, event):
        if not self.isVisible():
            return False

        if event.type() == QEvent.Type.MouseButtonPress:
            press_pos = event.globalPosition().toPoint()
            if not self.rect().contains(self.mapFromGlobal(press_pos)):
                self.hide_popup_menu()
                return False

        elif event.type() == QEvent.Type.WindowDeactivate:
            if not self.isActiveWindow():
                self.hide_popup_menu()

        return False
