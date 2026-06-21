from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtCore import Qt, QPoint, QEvent, QTimer, QObject


class PopupManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.NoDropShadowWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._anchor_btn = None
        self._parent_filter = None

    def _cleanup(self):
        if self._anchor_btn:
            self._anchor_btn.setProperty("menuOpen", False)
            self._anchor_btn.style().unpolish(self._anchor_btn)
            self._anchor_btn.style().polish(self._anchor_btn)
            self._anchor_btn = None

    def show_popup_menu(self, target_widget):
        self._anchor_btn = target_widget
        global_pos = target_widget.mapToGlobal(target_widget.rect().bottomLeft())
        self.move(global_pos + QPoint(0, 2))
        self.show()
        self.raise_()
        self.activateWindow()

        if self._anchor_btn:
            self._anchor_btn.setProperty("menuOpen", True)
            self._anchor_btn.style().unpolish(self._anchor_btn)
            self._anchor_btn.style().polish(self._anchor_btn)

        QApplication.instance().installEventFilter(self)
        parent = self.parent()
        if parent and self._parent_filter is None:
            self._parent_filter = _ParentFilter(self)
            parent.installEventFilter(self._parent_filter)

    def hide_popup_menu(self):
        if self._parent_filter:
            parent = self.parent()
            if parent:
                parent.removeEventFilter(self._parent_filter)
            self._parent_filter = None

        QApplication.instance().removeEventFilter(self)
        self.hide()
        QTimer.singleShot(0, self._cleanup)

    def close(self):
        self.hide_popup_menu()
        super().close()

    def eventFilter(self, obj, event):
        if not self.isVisible():
            return False
        if event.type() == QEvent.Type.MouseButtonPress:
            pos = event.globalPosition().toPoint()
            if not self.geometry().contains(pos):
                self.hide_popup_menu()
                return False
        return False


class _ParentFilter(QObject):
    def __init__(self, popup):
        super().__init__()
        self._popup = popup

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Move and self._popup.isVisible():
            self._popup.hide()
            QTimer.singleShot(0, self._popup._cleanup)
        return False
