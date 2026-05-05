import os
import shutil
from PySide6.QtCore import QObject, Qt, QSize, Signal, QRect
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
    QMessageBox,
)
from PySide6.QtGui import QPixmap, QColor, QPainter


class MapResLibCardDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = option.rect
        card_w, card_h = 160, 160
        card_rect = self._center_rect(rect, card_w, card_h)

        if option.state & QStyle.StateFlag.State_Selected:
            painter.setBrush(QColor(60, 60, 60))
            painter.setPen(Qt.PenStyle.NoPen)
        else:
            painter.setBrush(QColor(45, 45, 45))
            painter.setPen(Qt.PenStyle.NoPen)

        painter.drawRoundedRect(card_rect, 8, 8)

        thumb_data = index.data(Qt.ItemDataRole.UserRole + 1)
        if thumb_data and isinstance(thumb_data, QPixmap) and not thumb_data.isNull():
            thumb_w = 150
            thumb_h = 110
            thumb_rect = self._center_rect(
                QRect(card_rect.x(), card_rect.y(), card_w, card_h - 30),
                thumb_w, thumb_h,
            )
            painter.drawPixmap(thumb_rect, thumb_data, thumb_data.rect())

        name = index.data(Qt.ItemDataRole.DisplayRole)
        if name:
            painter.setPen(QColor(230, 230, 230))
            font = painter.font()
            font.setPointSize(10)
            painter.setFont(font)
            text_rect = QRect(card_rect.x(), card_rect.bottom() - 28, card_w, 24)
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, name)

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(170, 170)

    @staticmethod
    def _center_rect(outer, w, h):
        return QRect(
            int(outer.x() + (outer.width() - w) / 2),
            int(outer.y() + (outer.height() - h) / 2),
            w, h,
        )


class MapResLibManager(QObject):
    sig_resource_imported = Signal(str)

    THUMB_ROLE = Qt.ItemDataRole.UserRole + 1
    PATH_ROLE = Qt.ItemDataRole.UserRole + 2

    CATEGORIES = {
        "map_res_lib_btn1": "images",
        "map_res_lib_btn2": "tiles",
        "map_res_lib_btn3": "tilesets",
    }

    def __init__(self, ui, app_controller):
        super().__init__()
        self.ui = ui
        self.app_controller = app_controller
        self._pixmap_cache = {}
        self._current_category = "images"
        self._setup_list_widget()
        self._connect_signals()

    def _setup_list_widget(self):
        lw = self.ui.map_res_lib_list
        lw.setViewMode(QListWidget.ViewMode.IconMode)
        lw.setIconSize(QSize(160, 160))
        lw.setGridSize(QSize(170, 170))
        lw.setResizeMode(QListWidget.ResizeMode.Adjust)
        lw.setMovement(QListWidget.Movement.Static)
        lw.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        lw.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        lw.setFrameShape(QListWidget.Shape.NoFrame)
        lw.setStyleSheet("""
            QListWidget {
                background-color: #1E1E1E;
                border: none;
                outline: none;
            }
            QListWidget::item {
                background: transparent;
                border-radius: 8px;
                margin: 2px;
            }
            QListWidget::item:selected {
                background-color: #3D3D3D;
            }
        """)
        lw.setItemDelegate(MapResLibCardDelegate())
        lw.itemClicked.connect(self._on_card_clicked)

    def _connect_signals(self):
        self.ui.map_res_lib_return.clicked.connect(self._on_return)
        self.ui.map_res_lib_search.textChanged.connect(self._on_search)
        self.ui.map_res_lib_btn1.clicked.connect(lambda: self._switch_category("map_res_lib_btn1"))
        self.ui.map_res_lib_btn2.clicked.connect(lambda: self._switch_category("map_res_lib_btn2"))
        self.ui.map_res_lib_btn3.clicked.connect(lambda: self._switch_category("map_res_lib_btn3"))

    def _switch_category(self, btn_name):
        self._current_category = self.CATEGORIES.get(btn_name, "images")
        self._load_category(self._current_category)

    def load_map_res_lib(self):
        self.ui.map_res_lib_search.clear()
        self.ui.map_res_lib_btn1.setChecked(True)
        self._current_category = "images"
        self._load_category("images")

    def _load_category(self, category):
        self.ui.map_res_lib_list.clear()

        app_dir = self._get_app_dir()
        if not app_dir:
            return

        res_dir = os.path.join(app_dir, "assets", "map_res_lib", category)
        if not os.path.exists(res_dir):
            return

        image_exts = (".png", ".jpg", ".jpeg", ".bmp", ".gif")
        files = sorted([
            f for f in os.listdir(res_dir)
            if not f.startswith(".") and f.lower().endswith(image_exts)
        ])

        for f in files:
            file_path = os.path.join(res_dir, f)
            self._add_res_card(file_path, f)

    def _add_res_card(self, file_path, display_name):
        name = os.path.splitext(display_name)[0]
        thumb_pix = self._load_thumbnail(file_path)

        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.DisplayRole, name)
        item.setData(self.THUMB_ROLE, thumb_pix)
        item.setData(self.PATH_ROLE, file_path)
        item.setSizeHint(QSize(170, 170))
        self.ui.map_res_lib_list.addItem(item)

    def _on_card_clicked(self, item):
        src_path = item.data(self.PATH_ROLE)
        if not src_path or not os.path.exists(src_path):
            return

        me = getattr(self.app_controller, "map_editor", None)
        if not me or not hasattr(me, "current_map_path") or not me.current_map_path:
            QMessageBox.information(None, "提示", "请先打开一个地图再导入资源")
            return

        me.add_resource_from_path(src_path)

        self.ui.change_page.setCurrentIndex(0)

    def _on_return(self):
        self.ui.change_page.setCurrentIndex(0)

    def _on_search(self, text):
        keyword = text.strip().lower()
        lw = self.ui.map_res_lib_list
        for i in range(lw.count()):
            item = lw.item(i)
            name = item.data(Qt.ItemDataRole.DisplayRole) or ""
            item.setHidden(keyword not in name.lower())

    def _load_thumbnail(self, file_path):
        cache_key = f"map_res_thumb:{file_path}"
        if cache_key in self._pixmap_cache:
            return self._pixmap_cache[cache_key]

        pix = QPixmap(file_path)
        if not pix.isNull():
            scaled = pix.scaled(
                150, 110,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            self._pixmap_cache[cache_key] = scaled
            return scaled

        placeholder = QPixmap(150, 110)
        placeholder.fill(QColor(61, 61, 61))
        self._pixmap_cache[cache_key] = placeholder
        return placeholder

    def _get_app_dir(self):
        try:
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        except Exception:
            return None
