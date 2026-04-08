import os
from PySide6.QtWidgets import QDialog, QFileDialog
from PySide6.QtCore import Qt
from ui.map_resource_import_ui import Ui_Form


class MapResourceImportDialog(QDialog):
    """地图资源导入对话框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Form()
        self.ui.setupUi(self)

        # 设置窗口标题
        self.setWindowTitle("导入地图资源")

        # 初始化数据
        self.selected_files = []
        self.resource_type = "image"  # image 或 tileset
        self.tile_size = 32

        # 连接信号槽
        self._connect_signals()

        # 设置初始状态
        self._update_ui_state()

    def _connect_signals(self):
        """连接信号槽"""
        # 浏览按钮
        self.ui.btn_browse.clicked.connect(self._on_browse_clicked)

        # 单选按钮
        self.ui.radioButton_image.toggled.connect(self._on_resource_type_changed)
        self.ui.radioButton_tileset.toggled.connect(self._on_resource_type_changed)

        # 确定/取消按钮
        self.ui.btn_ok.clicked.connect(self._on_ok_clicked)
        self.ui.btn_no.clicked.connect(self.reject)

    def _on_browse_clicked(self):
        """处理浏览按钮点击"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "选择资源文件",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp);;所有文件 (*)",
        )

        if files:
            self.selected_files = files
            # 显示第一个文件路径作为预览
            self.ui.import_res_path.setText(files[0])
            # 如果有多个文件，显示数量
            if len(files) > 1:
                self.ui.import_res_path.setText(f"{files[0]} 等{len(files)}个文件")

    def _on_resource_type_changed(self):
        """处理资源类型变化"""
        if self.ui.radioButton_image.isChecked():
            self.resource_type = "image"
        else:
            self.resource_type = "tileset"

        self._update_ui_state()

    def _update_ui_state(self):
        """更新UI状态"""
        # 始终启用尺寸选择，不再与资源类型绑定
        self.ui.label_2.setEnabled(True)
        self.ui.comboBox_size.setEnabled(True)

    def _on_ok_clicked(self):
        """处理确定按钮点击"""
        # 验证是否选择了文件
        if not self.selected_files:
            return

        # 始终获取尺寸设置，无论是image还是tileset
        size_text = self.ui.comboBox_size.currentText()
        self.tile_size = int(size_text.split("x")[0])

        # 接受对话框
        self.accept()

    def get_import_data(self):
        """获取导入数据"""
        return {
            "files": self.selected_files,
            "resource_type": self.resource_type,
            "tile_size": self.tile_size,
        }
