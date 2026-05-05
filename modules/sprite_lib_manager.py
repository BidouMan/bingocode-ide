import os
import json
import zipfile
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


class SpriteLibCardDelegate(QStyledItemDelegate):
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


class SpriteLibManager(QObject):
    sig_sprite_imported = Signal(str)

    THUMB_ROLE = Qt.ItemDataRole.UserRole + 1
    PATH_ROLE = Qt.ItemDataRole.UserRole + 2

    def __init__(self, ui, app_controller):
        super().__init__()
        self.ui = ui
        self.app_controller = app_controller
        self._pixmap_cache = {}
        self._setup_list_widget()
        self._connect_signals()

    def _setup_list_widget(self):
        lw = self.ui.sprite_lib_list
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
        lw.setItemDelegate(SpriteLibCardDelegate())
        lw.itemClicked.connect(self._on_card_clicked)

    def _connect_signals(self):
        self.ui.sprite_lib_return.clicked.connect(self._on_return)
        self.ui.sprite_lib_search.textChanged.connect(self._on_search)

    def load_sprite_lib(self):
        self.ui.sprite_lib_list.clear()
        self.ui.sprite_lib_search.clear()

        app_dir = self._get_app_dir()
        if not app_dir:
            return

        sprite_lib_dir = os.path.join(app_dir, "assets", "sprite_lib")
        if not os.path.exists(sprite_lib_dir):
            return

        bgs_files = sorted([
            f for f in os.listdir(sprite_lib_dir)
            if f.endswith(".bgs")
        ])

        for bgs_file in bgs_files:
            bgs_path = os.path.join(sprite_lib_dir, bgs_file)
            self._add_bgs_card(bgs_path)

    def _add_bgs_card(self, bgs_path):
        sprite_name = self._read_sprite_name_from_bgs(bgs_path)
        if not sprite_name:
            sprite_name = os.path.splitext(os.path.basename(bgs_path))[0]

        thumb_pix = self._load_thumbnail_from_bgs(bgs_path)

        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.DisplayRole, sprite_name)
        item.setData(self.THUMB_ROLE, thumb_pix)
        item.setData(self.PATH_ROLE, bgs_path)
        item.setSizeHint(QSize(170, 170))
        self.ui.sprite_lib_list.addItem(item)

    def _on_card_clicked(self, item):
        bgs_path = item.data(self.PATH_ROLE)
        if not bgs_path or not os.path.exists(bgs_path):
            return

        project_root = self.app_controller.project_manager.project_root
        if not project_root:
            return

        sprites_dir = os.path.join(project_root, "assets", "sprites")
        os.makedirs(sprites_dir, exist_ok=True)

        original_name = self._read_sprite_name_from_bgs(bgs_path)
        if not original_name:
            original_name = os.path.splitext(os.path.basename(bgs_path))[0]

        sprite_name = original_name
        target_dir = os.path.join(sprites_dir, sprite_name)
        if os.path.exists(target_dir):
            sprite_name = self._get_safe_sprite_name(sprites_dir, sprite_name)
            target_dir = os.path.join(sprites_dir, sprite_name)

        os.makedirs(target_dir, exist_ok=True)

        try:
            with zipfile.ZipFile(bgs_path, "r") as zf:
                zf.extractall(target_dir)
        except Exception as e:
            QMessageBox.critical(None, "导入失败", f"导入角色时发生错误:\n{str(e)}")
            return

        if sprite_name != original_name:
            self._update_config_name(target_dir, sprite_name)

        self.ui.change_page.setCurrentIndex(0)
        self.sig_sprite_imported.emit(target_dir)

    def _on_return(self):
        self.ui.change_page.setCurrentIndex(0)

    def _on_search(self, text):
        keyword = text.strip().lower()
        lw = self.ui.sprite_lib_list
        for i in range(lw.count()):
            item = lw.item(i)
            name = item.data(Qt.ItemDataRole.DisplayRole) or ""
            item.setHidden(keyword not in name.lower())

    def _get_safe_sprite_name(self, sprites_dir, base_name):
        target = os.path.join(sprites_dir, base_name)
        if not os.path.exists(target):
            return base_name
        counter = 1
        while True:
            new_name = f"{base_name}_{counter}"
            target = os.path.join(sprites_dir, new_name)
            if not os.path.exists(target):
                return new_name
            counter += 1

    def _update_config_name(self, target_dir, new_name):
        config_path = os.path.join(target_dir, "config.json")
        if not os.path.exists(config_path):
            return
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            config["name"] = new_name
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_thumbnail_from_bgs(self, bgs_path):
        cache_key = f"sprite_lib_thumb:{bgs_path}"
        if cache_key in self._pixmap_cache:
            return self._pixmap_cache[cache_key]

        try:
            with zipfile.ZipFile(bgs_path, "r") as zf:
                config = json.load(zf.open("config.json"))
                frames = config.get("frames", config.get("costumes", []))
                if not frames:
                    raise ValueError("no frames")
                first_frame = frames[0]
                if isinstance(first_frame, dict):
                    first_frame = first_frame.get("file", "")
                if not first_frame:
                    raise ValueError("empty frame name")
                png_data = zf.read(first_frame)
                pix = QPixmap()
                pix.loadFromData(png_data)
                if not pix.isNull():
                    scaled = pix.scaled(
                        150, 110,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.FastTransformation,
                    )
                    self._pixmap_cache[cache_key] = scaled
                    return scaled
        except Exception:
            pass

        placeholder = QPixmap(150, 110)
        placeholder.fill(QColor(61, 61, 61))
        self._pixmap_cache[cache_key] = placeholder
        return placeholder

    def _read_sprite_name_from_bgs(self, bgs_path):
        try:
            with zipfile.ZipFile(bgs_path, "r") as zf:
                config = json.load(zf.open("config.json"))
                return config.get("name", None)
        except Exception:
            pass
        return None

    def _get_app_dir(self):
        try:
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        except Exception:
            return None
