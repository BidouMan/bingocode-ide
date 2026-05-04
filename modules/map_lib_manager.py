import os
import zipfile
import shutil
from PySide6.QtCore import QObject, Qt, QSize, Signal, QBuffer, QIODevice, QRect
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
    QWidget,
    QVBoxLayout,
    QLabel,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
    QMessageBox,
)
from PySide6.QtGui import QPixmap, QColor, QPainter, QFont


class MapLibCardDelegate(QStyledItemDelegate):
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


class MapLibManager(QObject):
    sig_map_imported = Signal(str)

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
        lw = self.ui.map_lib_list
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
        lw.setItemDelegate(MapLibCardDelegate())
        lw.itemClicked.connect(self._on_card_clicked)

    def _connect_signals(self):
        self.ui.mab_lib_return_btn.clicked.connect(self._on_return)
        self.ui.mab_lib_search.textChanged.connect(self._on_search)

    def load_map_lib(self):
        self.ui.map_lib_list.clear()
        self.ui.mab_lib_search.clear()

        app_dir = self._get_app_dir()
        if not app_dir:
            return

        map_lib_dir = os.path.join(app_dir, "assets", "map_lib")
        if not os.path.exists(map_lib_dir):
            return

        bgm_files = sorted([
            f for f in os.listdir(map_lib_dir)
            if f.endswith(".bgm")
        ])

        for bgm_file in bgm_files:
            bgm_path = os.path.join(map_lib_dir, bgm_file)
            self._add_bgm_card(bgm_path)

    def _add_bgm_card(self, bgm_path):
        map_name = self._read_map_name_from_bgm(bgm_path)
        if not map_name:
            map_name = os.path.splitext(os.path.basename(bgm_path))[0]

        thumb_pix = self._load_thumbnail_from_bgm(bgm_path)

        item = QListWidgetItem()
        item.setData(Qt.ItemDataRole.DisplayRole, map_name)
        item.setData(self.THUMB_ROLE, thumb_pix)
        item.setData(self.PATH_ROLE, bgm_path)
        item.setSizeHint(QSize(170, 170))
        self.ui.map_lib_list.addItem(item)

    def _on_card_clicked(self, item):
        bgm_path = item.data(self.PATH_ROLE)
        if not bgm_path or not os.path.exists(bgm_path):
            return

        self._save_current_map()

        original_name = self._read_map_name_from_bgm(bgm_path)
        if not original_name:
            original_name = os.path.splitext(os.path.basename(bgm_path))[0]

        project_root = self.app_controller.project_manager.project_root
        if not project_root:
            return

        maps_dir = os.path.join(project_root, "assets", "maps")
        os.makedirs(maps_dir, exist_ok=True)

        map_name = original_name
        target_dir = os.path.join(maps_dir, map_name)
        if os.path.exists(target_dir):
            map_name = self._get_safe_map_name(maps_dir, map_name)
            target_dir = os.path.join(maps_dir, map_name)

        os.makedirs(target_dir, exist_ok=True)

        try:
            self._extract_bgm(bgm_path, target_dir)
        except Exception as e:
            QMessageBox.critical(None, "导入失败", f"导入地图时发生错误:\n{str(e)}")
            return

        if map_name != original_name:
            self._rename_map_files(target_dir, original_name, map_name)

        info_path = os.path.join(target_dir, f"{map_name}.info")
        if not os.path.exists(info_path):
            for f in os.listdir(target_dir):
                if f.endswith(".info"):
                    info_path = os.path.join(target_dir, f)
                    break

        self.ui.change_page.setCurrentIndex(0)

        if os.path.exists(info_path):
            self.sig_map_imported.emit(info_path)
        else:
            self.sig_map_imported.emit("")

    def _save_current_map(self):
        try:
            me = getattr(self.app_controller, "map_editor", None)
            if me and hasattr(me, "current_map_path") and me.current_map_path:
                me.save_map()
        except Exception:
            pass

    def _on_return(self):
        self.ui.change_page.setCurrentIndex(0)

    def _on_search(self, text):
        keyword = text.strip().lower()
        lw = self.ui.map_lib_list
        for i in range(lw.count()):
            item = lw.item(i)
            name = item.data(Qt.ItemDataRole.DisplayRole) or ""
            item.setHidden(keyword not in name.lower())

    def _get_safe_map_name(self, maps_dir, base_name):
        target = os.path.join(maps_dir, base_name)
        if not os.path.exists(target):
            return base_name
        counter = 1
        while True:
            new_name = f"{base_name}_{counter}"
            target = os.path.join(maps_dir, new_name)
            if not os.path.exists(target):
                return new_name
            counter += 1

    def _rename_map_files(self, target_dir, old_name, new_name):
        for ext in (".info", ".tiles", ".collision", ".resources"):
            old_path = os.path.join(target_dir, f"{old_name}{ext}")
            if os.path.exists(old_path):
                new_path = os.path.join(target_dir, f"{new_name}{ext}")
                os.rename(old_path, new_path)

    def _load_thumbnail_from_bgm(self, bgm_path):
        cache_key = f"map_lib_thumb:{bgm_path}"
        if cache_key in self._pixmap_cache:
            return self._pixmap_cache[cache_key]

        try:
            with zipfile.ZipFile(bgm_path, "r") as zf:
                if "thumbnail.png" in zf.namelist():
                    png_data = zf.read("thumbnail.png")
                    pix = QPixmap()
                    pix.loadFromData(png_data, "PNG")
                    if not pix.isNull():
                        scaled = pix.scaled(
                            150, 110,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        self._pixmap_cache[cache_key] = scaled
                        return scaled
        except Exception:
            pass

        placeholder = QPixmap(150, 110)
        placeholder.fill(QColor(61, 61, 61))
        self._pixmap_cache[cache_key] = placeholder
        return placeholder

    def _read_map_name_from_bgm(self, bgm_path):
        try:
            with zipfile.ZipFile(bgm_path, "r") as zf:
                for member in zf.namelist():
                    if member.endswith(".info"):
                        return os.path.splitext(os.path.basename(member))[0]
        except Exception:
            pass
        return None

    def _extract_bgm(self, bgm_path, target_dir):
        with zipfile.ZipFile(bgm_path, "r") as zf:
            for member in zf.namelist():
                if member == "__bgm_magic__" or member == "thumbnail.png":
                    continue
                member_path = os.path.normpath(os.path.join(target_dir, member))
                if not member_path.startswith(os.path.normpath(target_dir)):
                    continue
                zf.extract(member, target_dir)

    def _get_app_dir(self):
        try:
            return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        except Exception:
            return None
