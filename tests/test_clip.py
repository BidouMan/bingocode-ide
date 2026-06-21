import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "modules"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ui"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "assets"))

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QPainterPath, QPen


class ClipWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._radius = 10
        print(f"[ClipWidget] created, size={self.size()}")

    def paintEvent(self, event):
        print(f"[ClipWidget] paintEvent called, size={self.size()}")
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(),
                            self._radius, self._radius)
        painter.setClipPath(path)
        painter.setBrush(QColor(34, 37, 43))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())
        painter.end()
        super().paintEvent(event)


class TestWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(800, 600)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)

        clip = ClipWidget(self)
        clip_layout = QVBoxLayout(clip)
        clip_layout.setContentsMargins(0, 0, 0, 0)
        clip_layout.setSpacing(0)

        title_bar = QFrame(clip)
        title_bar.setFixedHeight(28)
        title_bar.setStyleSheet(
            "background:rgb(26,28,33);border:none;"
        )
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(14, 0, 14, 0)
        close_btn = QPushButton("x", title_bar)
        close_btn.setFixedSize(12, 12)
        close_btn.setStyleSheet(
            "QPushButton{background:#ff5f57;border:none;border-radius:6px;color:white;font-size:8px;}"
        )
        close_btn.clicked.connect(self.close)
        tb_layout.addWidget(close_btn)
        tb_layout.addStretch()
        title_label = QLabel("Test Window", title_bar)
        title_label.setStyleSheet("color:rgb(160,160,160);font-size:13px;background:transparent;")
        tb_layout.addWidget(title_label)

        content = QFrame(clip)
        content.setStyleSheet("background:rgb(41,44,52);border:none;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        label = QLabel("This content should be clipped to rounded corners")
        label.setStyleSheet("color:white;font-size:16px;background:transparent;")
        content_layout.addWidget(label)

        btn = QPushButton("Button inside clipped area")
        btn.setStyleSheet("background:rgb(61,64,72);color:white;border:none;padding:10px;")
        content_layout.addWidget(btn)

        clip_layout.addWidget(title_bar)
        clip_layout.addWidget(content, 1)

        outer.addWidget(clip)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = 10
        s = 12
        content = self.rect().adjusted(s, s, -s, -s)

        for i in range(s):
            alpha = int(100 * (1 - i / s) ** 2)
            painter.setBrush(QColor(0, 0, 0, alpha))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(
                content.adjusted(-i, -i, i, i), r + i, r + i
            )

        painter.setBrush(QColor(34, 37, 43))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(content, r, r)

        pen_top = QPen(QColor(80, 80, 80))
        pen_top.setWidthF(1.0)
        painter.setPen(pen_top)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawLine(content.x() + r, content.y(),
                         content.x() + content.width() - r, content.y())

        pen_side = QPen(QColor(50, 50, 50))
        pen_side.setWidthF(1.0)
        painter.setPen(pen_side)

        path = QPainterPath()
        path.moveTo(content.x(), content.y() + r)
        path.arcTo(content.x(), content.y(), r * 2, r * 2, 180, 90)
        path.lineTo(content.x(), content.y() + content.height() - r)
        path.arcTo(content.x(), content.y() + content.height() - r * 2,
                   r * 2, r * 2, 90, 90)
        painter.drawPath(path)

        cx = content.x() + content.width()
        path2 = QPainterPath()
        path2.moveTo(cx, content.y() + r)
        path2.arcTo(cx - r * 2, content.y(), r * 2, r * 2, 0, -90)
        path2.lineTo(cx, content.y() + content.height() - r)
        path2.arcTo(cx - r * 2, content.y() + content.height() - r * 2,
                    r * 2, r * 2, 270, -90)
        painter.drawPath(path2)

        painter.end()
        super().paintEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = TestWindow()
    w.show()
    sys.exit(app.exec())
