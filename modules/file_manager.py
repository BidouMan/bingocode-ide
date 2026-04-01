'''
负责所有与磁盘交互的逻辑，并作为 EditorManager 和 FileMenu 之间的桥梁
'''

import os
from PySide6.QtCore import QObject, QStandardPaths
from PySide6.QtWidgets import QFileDialog

class FileManager(QObject):
    def __init__(self, parent_window):
        super().__init__()
        self.window = parent_window
        self.root_path = self._init_workspace()

    def _init_workspace(self):
        """初始化工作空间路径"""
        doc_path = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        root = os.path.join(doc_path, "BingoIDE_Projects")
        if not os.path.exists(root):
            os.makedirs(root, exist_ok=True)
        return root

    def open_file_dialog(self, editor_manager):
        """打开文件对话框并加载到编辑器"""
        file_path, _ = QFileDialog.getOpenFileName(
            self.window, "选择文件", "", "Python Files (*.py);;All Files (*)"
        )
        
        # 🚀 修复焦点丢失问题：强制主窗口重新获取焦点
        self.window.activateWindow()
        self.window.raise_()
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                editor_manager.create_new_tab(file_path, content)
            except Exception as e:
                print(f"读取文件失败: {e}")

    def save_file(self, editor_manager):
        """保存当前文件"""
        editor_manager.request_save_file(self.window)

    def save_as_file(self, editor_manager):
        """另存为文件"""
        editor_manager.request_save_as(self.window)