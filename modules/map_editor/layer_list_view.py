from PySide6.QtCore import Qt, QModelIndex, QPoint, QAbstractListModel
from PySide6.QtWidgets import (
    QListView, QWidget, QHBoxLayout, QVBoxLayout,
    QCheckBox, QLabel, QPushButton, QMenu, QLineEdit, QInputDialog
)
from PySide6.QtGui import QIcon, QColor, QPainter, QPen


class LayerItemWidget(QWidget):
    """图层项控件"""
    
    def __init__(self, layer, index, parent=None):
        super().__init__(parent)
        self.layer = layer
        self.index = index
        self._editing = False
        self.setFixedHeight(30)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(5)
        
        self.visible_checkbox = QCheckBox()
        self.visible_checkbox.setChecked(layer.visible)
        self.visible_checkbox.stateChanged.connect(self._on_visible_changed)
        layout.addWidget(self.visible_checkbox)
        
        self.lock_button = QPushButton()
        self.lock_button.setFixedSize(20, 20)
        self._update_lock_icon()
        self.lock_button.clicked.connect(self._on_lock_clicked)
        layout.addWidget(self.lock_button)
        
        self.name_label = QLabel(layer.name)
        self.name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.name_label.setMinimumWidth(100)
        self.name_label.setStyleSheet("QLabel { border: 1px solid transparent; padding: 2px; }")
        self.name_label.mouseDoubleClickEvent = self._on_name_double_clicked
        layout.addWidget(self.name_label)

        self.name_edit = QLineEdit(layer.name)
        self.name_edit.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.name_edit.setMinimumWidth(100)
        self.name_edit.setStyleSheet(
            "QLineEdit { background-color: #3D3D3D; color: white; border: 1px solid #5bc772; "
            "border-radius: 2px; padding: 2px; }"
        )
        self.name_edit.editingFinished.connect(self._finish_edit)
        self.name_edit.installEventFilter(self)
        self.name_edit.hide()
        layout.addWidget(self.name_edit)
        
        self.type_label = QLabel(layer.layer_type.capitalize())
        self.type_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.type_label.setStyleSheet("QLabel { font-size: 10px; color: #666; }")
        layout.addWidget(self.type_label)
        
        self.layer.visibility_changed.connect(self._on_layer_visibility_changed)
        self.layer.locked_changed.connect(self._on_layer_locked_changed)
        self.layer.layer_changed.connect(self._on_layer_changed)
    
    def _on_visible_changed(self, state):
        self.layer.set_visible(state == Qt.Checked)
    
    def _on_lock_clicked(self):
        self.layer.set_locked(not self.layer.locked)
    
    def _on_name_double_clicked(self, event):
        self._start_edit()
    
    def _start_edit(self):
        if self._editing:
            return
        self._editing = True
        self.name_edit.setText(self.layer.name)
        self.name_label.hide()
        self.name_edit.show()
        self.name_edit.setFocus()
        self.name_edit.selectAll()
    
    def _finish_edit(self):
        if not self._editing:
            return
        new_name = self.name_edit.text().strip()
        if new_name and new_name != self.layer.name:
            self.layer.set_name(new_name)
        self.name_edit.hide()
        self.name_label.show()
        self.name_label.setText(self.layer.name)
        self._editing = False
    
    def eventFilter(self, obj, event):
        if obj == self.name_edit and self._editing:
            if event.type() == event.Type.KeyPress:
                if event.key() == Qt.Key_Escape:
                    self.name_edit.hide()
                    self.name_label.show()
                    self._editing = False
                    return True
                elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
                    self._finish_edit()
                    return True
            elif event.type() == event.Type.FocusOut:
                self._finish_edit()
                return True
        return super().eventFilter(obj, event)
    
    def _update_lock_icon(self):
        if self.layer.locked:
            self.lock_button.setStyleSheet("QPushButton { background-color: #f0f0f0; border: 1px solid #ccc; border-radius: 2px; }")
            self.lock_button.setText("🔒")
        else:
            self.lock_button.setStyleSheet("QPushButton { background-color: transparent; border: 1px solid transparent; }")
            self.lock_button.setText("🔓")
    
    def _on_layer_visibility_changed(self, visible):
        self.visible_checkbox.setChecked(visible)
    
    def _on_layer_locked_changed(self, locked):
        self._update_lock_icon()
    
    def _on_layer_changed(self):
        if not self._editing:
            self.name_label.setText(self.layer.name)


class LayerListModel(QAbstractListModel):
    """图层列表模型"""
    
    def __init__(self, layer_manager, parent=None):
        super().__init__(parent)
        self.layer_manager = layer_manager
        self.layer_manager.layers_changed.connect(self._on_layers_changed)
    
    def rowCount(self, parent=QModelIndex()):
        return self.layer_manager.get_layer_count()
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        layer = self.layer_manager.get_layer(row)
        if role == Qt.DisplayRole:
            return layer.name
        elif role == Qt.UserRole:
            return layer
        return None
    
    def _on_layers_changed(self):
        self.beginResetModel()
        self.endResetModel()


class LayerListView(QListView):
    """图层列表视图"""
    
    def __init__(self, layer_manager=None, parent=None):
        super().__init__(parent)
        self.layer_manager = None
        if layer_manager:
            self.set_layer_manager(layer_manager)
        self.setSpacing(2)
        self.setStyleSheet("QListView { background-color: #f5f5f5; border: 1px solid #ddd; }")
    
    def set_layer_manager(self, layer_manager):
        self.layer_manager = layer_manager
        if layer_manager:
            self.setModel(LayerListModel(layer_manager, self))
            self.clicked.connect(self._on_item_clicked)
            self.layer_manager.current_layer_changed.connect(self._on_current_layer_changed)
    
    def _on_item_clicked(self, index):
        self.layer_manager.set_current_layer(index.row())
    
    def _on_current_layer_changed(self, index):
        if 0 <= index < self.model().rowCount():
            self.setCurrentIndex(self.model().index(index))
    
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        
        create_menu = menu.addMenu("创建图层")
        create_drawing_action = create_menu.addAction("绘制图层")
        create_image_action = create_menu.addAction("图像图层")
        
        delete_action = menu.addAction("删除图层")
        delete_action.setEnabled(self.layer_manager.get_layer_count() > 1)
        
        rename_action = menu.addAction("重命名图层")
        
        action = menu.exec(self.mapToGlobal(event.pos()))
        
        if action == create_drawing_action:
            self.layer_manager.create_layer("drawing")
        elif action == create_image_action:
            self.layer_manager.create_layer("image")
        elif action == delete_action:
            current_index = self.currentIndex().row()
            if 0 <= current_index < self.layer_manager.get_layer_count():
                self.layer_manager.delete_layer(current_index)
        elif action == rename_action:
            current_index = self.currentIndex().row()
            if 0 <= current_index < self.layer_manager.get_layer_count():
                layer = self.layer_manager.get_layer(current_index)
                new_name, ok = QInputDialog.getText(
                    self, "重命名图层", "输入新的图层名称:", text=layer.name
                )
                if ok and new_name:
                    layer.set_name(new_name)
    
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.model().rowCount() == 0:
            painter = QPainter(self.viewport())
            painter.setPen(QPen(QColor(128, 128, 128)))
            painter.drawText(self.rect(), Qt.AlignCenter, "没有图层，请右键创建")
    
    def update_layer_list(self):
        if self.model():
            self.model().beginResetModel()
            self.model().endResetModel()
