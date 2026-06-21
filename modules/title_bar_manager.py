import sys
from PySide6.QtWidgets import (
    QPushButton, QFrame, QHBoxLayout, QLabel, QWidget, QVBoxLayout,
)
from PySide6.QtCore import Qt, QEvent, QObject
from PySide6.QtGui import QPainter, QColor, QRadialGradient

_IS_MAC = sys.platform == "darwin"


class TitleBarManager(QObject):
    def __init__(self, window, ui, menu_manager):
        super().__init__()
        self.window = window
        self.ui = ui
        self.menu_manager = menu_manager
        self._drag_pos = None
        self._radius = 10

        self._create_title_bar()
        self._apply_rounded_corners()
        self._apply_shape()
        self.title_bar_frame.installEventFilter(self)

    def _apply_rounded_corners(self):
        r = f"{self._radius}px"

        self.title_bar_frame.setStyleSheet(
            f"#title_bar_frame{{background:rgb(26,28,33);border:none;"
            f"border-top-left-radius:{r};border-top-right-radius:{r};}}"
        )

        self.ui.menu_frame.setStyleSheet(
            f"#menu_frame{{margin:0px;padding:0px;border:none;"
            f"border-bottom:1px solid rgb(12,12,12);"
            f"background-color:rgb(34,37,43);}}"
            f"#menu_frame QPushButton{{background-color:transparent;border:none;}}"
            f"#menu_frame QPushButton:pressed,"
            f"#menu_frame QPushButton:hover,"
            f"#menu_frame QPushButton[menuOpen=\"true\"]{{"
            f"background-color:rgb(61,64,72);border:none;}}"
            f"#menu_frame QPushButton#btn_help:pressed,"
            f"#menu_frame QPushButton#btn_help:hover{{"
            f"background-color:transparent;border:none;}}"
        )

        self.ui.editor_stacked.setStyleSheet(
            f"QStackedWidget{{background:rgb(34,37,43);border:none;"
            f"border-bottom-left-radius:{r};border-bottom-right-radius:{r};}}"
        )
        self.ui.editor_stacked.setContentsMargins(0, 0, 0, self._radius)

        self.window.setStyleSheet(
            self.window.styleSheet() + f"#Form{{background:transparent;}}"
        )

    def _apply_shape(self):
        w = self.window
        w.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        w.setWindowFlags(
            w.windowFlags() | Qt.WindowType.FramelessWindowHint
        )
        if _IS_MAC:
            self._enable_native_shadow()

        orig_paint = w.paintEvent
        orig_resize = w.resizeEvent

        def paint(event):
            painter = QPainter(w)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            if not _IS_MAC:
                margin = 8
                for i in range(margin, 0, -1):
                    alpha = max(8, int(30 * (1 - i / margin)))
                    painter.setBrush(QColor(0, 0, 0, alpha))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRoundedRect(
                        w.rect().adjusted(-i, -i, i, i),
                        self._radius + i, self._radius + i,
                    )

            painter.setBrush(QColor(34, 37, 43))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(w.rect(), self._radius, self._radius)
            painter.end()
            orig_paint(event)

        def on_resize(event):
            orig_resize(event)

        w.paintEvent = paint
        w.resizeEvent = on_resize

    def _enable_native_shadow(self):
        try:
            from AppKit import NSWindow
            import objc
            qwindow = self.window.windowHandle()
            if qwindow is None:
                return
            qwindow.create()
            ns_ptr = qwindow.winId()
            ns_view = objc.objc_object(c_void_p=int(ns_ptr))
            ns_window = ns_view.window()
            if ns_window:
                ns_window.setHasShadow_(True)
                ns_window.setMovableByWindowBackground_(True)
        except Exception:
            pass

    def _create_title_bar(self):
        frame = QFrame()
        frame.setObjectName("title_bar_frame")
        frame.setFixedHeight(28)

        layout = QHBoxLayout(frame)
        layout.setContentsMargins(14, 0, 14, 0)
        layout.setSpacing(0)

        self.btn_close = QPushButton(frame)
        self.btn_close.setFixedSize(12, 12)
        self.btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_close.setStyleSheet(
            "QPushButton{background:#ff5f57;border:none;border-radius:6px;"
            "color:rgba(0,0,0,0);font-size:8px;font-weight:bold;}"
            "QPushButton:hover{background:#ff4040;color:rgba(0,0,0,200);}"
            "QPushButton:pressed{background:#cc3a35;}"
        )
        self.btn_close.setText("\u00d7")
        self.btn_close.clicked.connect(self.window.close)
        layout.addWidget(self.btn_close)

        layout.addSpacing(8)

        self.btn_minimize = QPushButton(frame)
        self.btn_minimize.setFixedSize(12, 12)
        self.btn_minimize.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_minimize.setStyleSheet(
            "QPushButton{background:#febc2e;border:none;border-radius:6px;"
            "color:rgba(0,0,0,0);font-size:8px;font-weight:bold;}"
            "QPushButton:hover{background:#ffa500;color:rgba(0,0,0,200);}"
            "QPushButton:pressed{background:#cc9520;}"
        )
        self.btn_minimize.setText("\u2212")
        self.btn_minimize.clicked.connect(self.window.showMinimized)
        layout.addWidget(self.btn_minimize)

        layout.addSpacing(8)

        self.btn_maximize = QPushButton(frame)
        self.btn_maximize.setFixedSize(12, 12)
        self.btn_maximize.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_maximize.setStyleSheet(
            "QPushButton{background:#28c840;border:none;border-radius:6px;"
            "color:rgba(0,0,0,0);font-size:8px;font-weight:bold;}"
            "QPushButton:hover{background:#20a030;color:rgba(0,0,0,200);}"
            "QPushButton:pressed{background:#1d8a2a;}"
        )
        self.btn_maximize.setText("+")
        self.btn_maximize.clicked.connect(self._toggle_maximize)
        layout.addWidget(self.btn_maximize)

        layout.addStretch(1)

        self.title_label = QLabel("BingoCode", frame)
        self.title_label.setStyleSheet(
            "color:rgb(160,160,160);font-size:13px;border:none;background:transparent;"
        )
        self.title_label.setFixedHeight(28)
        self.title_label.setParent(frame)
        self.title_label.show()

        self.ui.verticalLayout_19.insertWidget(0, frame)
        self.title_bar_frame = frame

    def _center_title(self):
        w = self.title_bar_frame.width()
        fw = self.title_label.fontMetrics().horizontalAdvance(self.title_label.text())
        self.title_label.move((w - fw) // 2, 0)

    def set_title(self, text):
        self.title_label.setText(text)
        self._center_title()

    def _toggle_maximize(self):
        if self.window.isMaximized():
            self.window.showNormal()
        else:
            self.window.showMaximized()

    def eventFilter(self, obj, event):
        if obj is not self.title_bar_frame:
            return False

        if event.type() == QEvent.Type.MouseButtonDblClick:
            if event.button() == Qt.MouseButton.LeftButton:
                self._toggle_maximize()
                return True

        if event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                if self.menu_manager.isVisible():
                    return False
                self._drag_pos = (
                    event.globalPosition().toPoint()
                    - self.window.frameGeometry().topLeft()
                )
                return False

        if event.type() == QEvent.Type.MouseButtonRelease:
            self._drag_pos = None
            return False

        if event.type() == QEvent.Type.MouseMove:
            if self._drag_pos is not None:
                self.window.move(event.globalPosition().toPoint() - self._drag_pos)
                return True

        if event.type() == QEvent.Type.Resize:
            self._center_title()

        return False
