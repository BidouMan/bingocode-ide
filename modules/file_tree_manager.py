import os
from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QMenu, QInputDialog,
    QMessageBox, QAbstractItemView, QVBoxLayout, QWidget,
    QHBoxLayout, QPushButton, QLabel, QFrame,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon


class FileTreeManager(QWidget):
    file_opened = Signal(str)
    file_created = Signal(str)

    def __init__(self, project_manager=None, parent=None):
        super().__init__(parent)
        self.project_manager = project_manager
        self._root_path = ""
        self._collapsed = False

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QFrame()
        header.setFixedHeight(32)
        header.setStyleSheet(
            "QFrame{background:rgb(34,37,43);border:none;border-bottom:1px solid rgb(45,45,48);}"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 0, 4, 0)
        header_layout.setSpacing(4)

        self.btn_new_file = QPushButton("+")
        self.btn_new_file.setObjectName("btn_res_list_open")
        self.btn_new_file.setFixedSize(22, 22)
        self.btn_new_file.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new_file.setToolTip("新建文件")
        self.btn_new_file.setStyleSheet(
            "QPushButton{background:transparent;color:rgb(160,160,160);border:none;"
            "font-size:14px;font-weight:bold;border-radius:3px;}"
            "QPushButton:hover{background:rgb(61,64,72);}"
        )
        self.btn_new_file.clicked.connect(self._create_file)
        header_layout.addWidget(self.btn_new_file)

        self.btn_new_folder = QPushButton("+")
        self.btn_new_folder.setObjectName("btn_res_list_upload")
        self.btn_new_folder.setFixedSize(22, 22)
        self.btn_new_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new_folder.setToolTip("新建文件夹")
        self.btn_new_folder.setStyleSheet(
            "QPushButton{background:transparent;color:rgb(160,160,160);border:none;"
            "font-size:14px;font-weight:bold;border-radius:3px;}"
            "QPushButton:hover{background:rgb(61,64,72);}"
        )
        self.btn_new_folder.clicked.connect(self._create_folder)
        header_layout.addWidget(self.btn_new_folder)

        header_layout.addStretch()
        layout.addWidget(header)

        self.tree = QTreeWidget()
        self.tree.setObjectName("ide_file_tree")
        self.tree.setHeaderHidden(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(16)
        self.tree.setRootIsDecorated(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setStyleSheet(
            "QTreeWidget{background:rgb(34,37,43);color:rgb(200,200,200);border:none;"
            "font-size:12px;outline:none;}"
            "QTreeWidget::item{padding:3px 0;}"
            "QTreeWidget::item:selected{background:rgb(49,54,59);color:rgb(220,220,220);}"
            "QTreeWidget::item:hover{background:rgb(49,54,59);}"
            "QTreeWidget::branch{background:rgb(34,37,43);}"
        )
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.tree)

    def set_root(self, path):
        self._root_path = path
        self.refresh()

    def refresh(self):
        self.tree.clear()
        if not self._root_path or not os.path.isdir(self._root_path):
            return
        root_item = QTreeWidgetItem(self.tree)
        root_item.setText(0, os.path.basename(self._root_path))
        root_item.setData(0, Qt.ItemDataRole.UserRole, self._root_path)
        root_item.setExpanded(True)
        self._populate_tree(root_item, self._root_path)

    def _populate_tree(self, parent_item, path):
        try:
            entries = sorted(os.listdir(path), key=lambda e: (not os.path.isdir(os.path.join(path, e)), e.lower()))
        except PermissionError:
            return

        for name in entries:
            if name.startswith(".") or name == "__pycache__":
                continue
            full_path = os.path.join(path, name)
            item = QTreeWidgetItem(parent_item)
            item.setText(0, name)
            item.setData(0, Qt.ItemDataRole.UserRole, full_path)
            if os.path.isdir(full_path):
                item.setIcon(0, self.style().standardIcon(self.style().StandardPixmap.SP_DirIcon))
                self._populate_tree(item, full_path)
            else:
                item.setIcon(0, self.style().standardIcon(self.style().StandardPixmap.SP_FileIcon))

    def _on_double_click(self, item, col):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path and os.path.isfile(path):
            self.file_opened.emit(path)

    def _show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu{background:rgb(34,37,43);color:rgb(200,200,200);border:1px solid rgb(45,45,48);}"
            "QMenu::item{padding:4px 20px;}"
            "QMenu::item:selected{background:rgb(49,54,59);}"
        )

        if item:
            path = item.data(0, Qt.ItemDataRole.UserRole)
            is_dir = os.path.isdir(path) if path else False

            if is_dir:
                new_file_action = menu.addAction("新建文件")
                new_file_action.triggered.connect(lambda: self._create_file_in(item))
                new_folder_action = menu.addAction("新建文件夹")
                new_folder_action.triggered.connect(lambda: self._create_folder_in(item))
                menu.addSeparator()

            rename_action = menu.addAction("重命名")
            rename_action.triggered.connect(lambda: self._rename_item(item))
            delete_action = menu.addAction("删除")
            delete_action.triggered.connect(lambda: self._delete_item(item))
        else:
            new_file_action = menu.addAction("新建文件")
            new_file_action.triggered.connect(self._create_file)
            new_folder_action = menu.addAction("新建文件夹")
            new_folder_action.triggered.connect(self._create_folder)
            menu.addSeparator()
            refresh_action = menu.addAction("刷新")
            refresh_action.triggered.connect(self.refresh)

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _get_target_dir(self, parent_item=None):
        if parent_item:
            path = parent_item.data(0, Qt.ItemDataRole.UserRole)
            if path and os.path.isdir(path):
                return path
        return self._root_path

    def _create_file(self):
        self._create_file_in(None)

    def _create_file_in(self, parent_item):
        name, ok = QInputDialog.getText(self, "新建文件", "文件名:")
        if ok and name:
            target_dir = self._get_target_dir(parent_item)
            filepath = os.path.join(target_dir, name)
            if os.path.exists(filepath):
                QMessageBox.warning(self, "提示", "文件已存在")
                return
            with open(filepath, "w", encoding="utf-8") as f:
                pass
            self.refresh()
            self.file_created.emit(filepath)

    def _create_folder(self):
        self._create_folder_in(None)

    def _create_folder_in(self, parent_item):
        name, ok = QInputDialog.getText(self, "新建文件夹", "文件夹名:")
        if ok and name:
            target_dir = self._get_target_dir(parent_item)
            folder_path = os.path.join(target_dir, name)
            if os.path.exists(folder_path):
                QMessageBox.warning(self, "提示", "文件夹已存在")
                return
            os.makedirs(folder_path)
            self.refresh()

    def _rename_item(self, item):
        old_path = item.data(0, Qt.ItemDataRole.UserRole)
        if not old_path:
            return
        old_name = os.path.basename(old_path)
        new_name, ok = QInputDialog.getText(self, "重命名", "新名称:", text=old_name)
        if ok and new_name and new_name != old_name:
            new_path = os.path.join(os.path.dirname(old_path), new_name)
            if os.path.exists(new_path):
                QMessageBox.warning(self, "提示", "目标名称已存在")
                return
            os.rename(old_path, new_path)
            self.refresh()

    def _delete_item(self, item):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path:
            return
        name = os.path.basename(path)
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除 \"{name}\" 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):
                import shutil
                shutil.rmtree(path)
            self.refresh()

    def toggle_collapse(self):
        self._collapsed = not self._collapsed
        self.setVisible(not self._collapsed)
