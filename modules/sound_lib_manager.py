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
from PySide6.QtGui import QPixmap, QColor, QPainter, QIcon


class SoundLibCardDelegate(QStyledItemDelegate):
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
            max_w = 150
            max_h = 110
            pix_w = thumb_data.width()
            pix_h = thumb_data.height()
            scale = min(max_w / pix_w, max_h / pix_h) if pix_w > 0 and pix_h > 0 else 1
            draw_w = int(pix_w * scale)
            draw_h = int(pix_h * scale)
            area_rect = QRect(card_rect.x(), card_rect.y(), card_w, card_h - 30)
            draw_x = area_rect.x() + (area_rect.width() - draw_w) // 2
            draw_y = area_rect.y() + (area_rect.height() - draw_h) // 2
            draw_rect = QRect(draw_x, draw_y, draw_w, draw_h)
            painter.drawPixmap(draw_rect, thumb_data, thumb_data.rect())

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


class SoundLibManager(QObject):
    sig_sound_imported = Signal(str)

    THUMB_ROLE = Qt.ItemDataRole.UserRole + 1
    PATH_ROLE = Qt.ItemDataRole.UserRole + 2
    CATEGORY_ROLE = Qt.ItemDataRole.UserRole + 3

    CATEGORIES = {
        "sound_lib_btn1": None,
        "sound_lib_btn2": "effects",
        "sound_lib_btn3": "loop",
    }

    SOUND_EXTENSIONS = (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".wma")

    def __init__(self, ui, app_controller):
        super().__init__()
        self.ui = ui
        self.app_controller = app_controller
        self._pixmap_cache = {}
        self._current_category = None
        self._setup_list_widget()
        self._connect_signals()

    def _setup_list_widget(self):
        lw = self.ui.listWidget_2
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
        lw.setItemDelegate(SoundLibCardDelegate())
        lw.itemClicked.connect(self._on_card_clicked)

    def _connect_signals(self):
        self.ui.sound_lib_return.clicked.connect(self._on_return)
        self.ui.sound_lib_search.textChanged.connect(self._on_search)
        for btn_name in self.CATEGORIES:
            btn = getattr(self.ui, btn_name, None)
            if btn:
                btn.clicked.connect(self._on_category_clicked)

    def load_sound_lib(self):
        self.ui.listWidget_2.clear()
        self.ui.sound_lib_search.clear()
        self._current_category = None

        app_dir = self._get_app_dir()
        if not app_dir:
            return

        sound_lib_dir = os.path.join(app_dir, "assets", "sound_lib")
        if not os.path.exists(sound_lib_dir):
            return

        for entry in sorted(os.listdir(sound_lib_dir)):
            if entry.startswith("."):
                continue
            full_path = os.path.join(sound_lib_dir, entry)
            if os.path.isfile(full_path) and entry.lower().endswith(self.SOUND_EXTENSIONS):
                self._add_sound_card(full_path, None)

        for cat_dir_name in ("effects", "loop"):
            cat_dir = os.path.join(sound_lib_dir, cat_dir_name)
            if os.path.isdir(cat_dir):
                self._load_sounds_from_dir(cat_dir, cat_dir_name)

    def _load_sounds_from_dir(self, directory, category):
        try:
            entries = sorted(os.listdir(directory))
        except Exception:
            return

        for entry in entries:
            if entry.startswith("."):
                continue
            full_path = os.path.join(directory, entry)
            if os.path.isfile(full_path) and entry.lower().endswith(self.SOUND_EXTENSIONS):
                self._add_sound_card(full_path, category)

    def _add_sound_card(self, sound_path, category):
        name = os.path.splitext(os.path.basename(sound_path))[0]
        thumb_pix = self._load_thumbnail()

        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.DisplayRole, name)
        item.setData(self.THUMB_ROLE, thumb_pix)
        item.setData(self.PATH_ROLE, sound_path)
        item.setData(self.CATEGORY_ROLE, category)
        item.setSizeHint(QSize(170, 170))

        if self._current_category is not None and category != self._current_category:
            item.setHidden(True)

        self.ui.listWidget_2.addItem(item)

    def _load_thumbnail(self):
        cache_key = "sound_lib_default_thumb"
        if cache_key in self._pixmap_cache:
            return self._pixmap_cache[cache_key]

        icon = QIcon(":/icons/sound_icon.svg")
        if not icon.isNull():
            pix = icon.pixmap(QSize(150, 110))
            if not pix.isNull():
                self._pixmap_cache[cache_key] = pix
                return pix

        placeholder = QPixmap(150, 110)
        placeholder.fill(QColor(61, 61, 61))
        self._pixmap_cache[cache_key] = placeholder
        return placeholder

    def _on_card_clicked(self, item):
        src_path = item.data(self.PATH_ROLE)
        if not src_path or not os.path.exists(src_path):
            return

        project_root = self.app_controller.project_manager.project_root
        if not project_root:
            return

        sounds_dir = os.path.join(project_root, "assets", "sounds")
        os.makedirs(sounds_dir, exist_ok=True)

        original_name = os.path.splitext(os.path.basename(src_path))[0]
        ext = os.path.splitext(src_path)[1]
        safe_name = self._get_safe_sound_name(sounds_dir, original_name, ext)
        target_path = os.path.join(sounds_dir, safe_name + ext)

        try:
            shutil.copy2(src_path, target_path)
        except Exception as e:
            QMessageBox.critical(None, "导入失败", f"导入声音时发生错误:\n{str(e)}")
            return

        self.ui.change_page.setCurrentIndex(0)
        self.sig_sound_imported.emit(target_path)

    def _on_return(self):
        self.ui.change_page.setCurrentIndex(0)

    def _on_search(self, text):
        keyword = text.strip().lower()
        lw = self.ui.listWidget_2
        for i in range(lw.count()):
            item = lw.item(i)
            name = item.data(Qt.ItemDataRole.DisplayRole) or ""
            cat_match = (
                self._current_category is None
                or item.data(self.CATEGORY_ROLE) == self._current_category
            )
            item.setHidden(keyword not in name.lower() or not cat_match)

    def _on_category_clicked(self):
        sender = self.sender()
        if not sender:
            return
        btn_name = sender.objectName()
        self._current_category = self.CATEGORIES.get(btn_name, None)

        lw = self.ui.listWidget_2
        keyword = self.ui.sound_lib_search.text().strip().lower()
        for i in range(lw.count()):
            item = lw.item(i)
            name = item.data(Qt.ItemDataRole.DisplayRole) or ""
            cat_match = (
                self._current_category is None
                or item.data(self.CATEGORY_ROLE) == self._current_category
            )
            item.setHidden(keyword not in name.lower() or not cat_match)

    def _get_safe_sound_name(self, sounds_dir, base_name, ext):
        target = os.path.join(sounds_dir, base_name + ext)
        if not os.path.exists(target):
            return base_name
        counter = 1
        while True:
            new_name = f"{base_name}_{counter}"
            target = os.path.join(sounds_dir, new_name + ext)
            if not os.path.exists(target):
                return new_name
            counter += 1

    def _get_app_dir(self):
        try:
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        except Exception:
            return None
