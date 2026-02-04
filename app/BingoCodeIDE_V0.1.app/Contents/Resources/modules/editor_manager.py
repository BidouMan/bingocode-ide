import os
from PySide6.QtWidgets import QWidget, QLineEdit, QFileDialog, QPushButton, QTabBar
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor
# 导入专业的编辑器类
from modules.code_editor_pro import QCodeEditor

class EditorManager(QObject):
    file_created_on_disk = Signal()
    file_renamed_on_disk = Signal()

    def __init__(self, stacked_widget, tab_bar, root_path: str):
        super().__init__()
        self.stacked = stacked_widget
        self.tabs = tab_bar
        self.root_path = root_path
        
        # 1. 深度清理：确保容器初始状态为空
        if hasattr(self.tabs, 'count'):
            while self.tabs.count() > 0:
                self.tabs.removeTab(0)
        
        while self.stacked.count() > 0:
            w = self.stacked.widget(0)
            self.stacked.removeWidget(w)
            w.deleteLater()
            
        # 2. 配置标签栏基础属性
        self.tabs.setTabsClosable(False) 
        self.tabs.setMovable(True)
        
        # 3. 内部信号绑定
        self.tabs.currentChanged.connect(self.stacked.setCurrentIndex)
        self.tabs.tabBarDoubleClicked.connect(self.on_tab_double_clicked)

        # 4. 自动执行启动逻辑
        self.initialize_startup()

    def initialize_startup(self):
        """启动逻辑：不写磁盘，只创建虚拟 Tab"""
        file_path = self._generate_unique_name(self.root_path)
        # 初始 content 为空，触发延迟创建逻辑
        self.create_new_tab(file_path, "")

    def create_untitled_file(self):
        """外部调用：手动新建一个未命名标签"""
        file_path = self._generate_unique_name(self.root_path)
        self.create_new_tab(file_path, "")

    def create_new_tab(self, file_path, content):
        """核心方法：创建编辑器。支持延迟物理创建，不破坏原有 UI 功能"""
        editor = QCodeEditor()
        editor.file_path = file_path
        editor.setPlainText(content)
        
        # --- 🚀 延迟创建逻辑标记 ---
        # 如果 content 为空，标记为临时状态，先不写磁盘
        editor.is_temp = not bool(content.strip()) 
        
        file_name = os.path.basename(file_path)
        display_name = os.path.splitext(file_name)[0]
        
        # UI 添加
        new_index = self.tabs.addTab(display_name)
        self.stacked.addWidget(editor)
        
        # --- 🚀 增强 UI：添加自定义关闭/状态按钮 ---
        close_btn = QPushButton("")
        close_btn.setObjectName("tabCloseBtn")
        close_btn.setProperty("modified", "false") 
        close_btn.setFixedSize(16, 16)
        self.tabs.setTabButton(new_index, QTabBar.ButtonPosition.RightSide, close_btn)
        
        # 绑定点击关闭：使用 lambda 实时获取当前编辑器在 stacked 中的索引
        close_btn.clicked.connect(lambda: self.close_tab(self.stacked.indexOf(editor)))

        # 监听内容变化：合并小圆点逻辑与延迟创建逻辑
        editor.textChanged.connect(lambda: self._handle_text_changed(editor))

        # 激活当前页
        self.tabs.setCurrentIndex(new_index)
        self.stacked.setCurrentIndex(new_index)
        return editor

    def _handle_text_changed(self, editor):
        """处理文本改变：处理小圆点 + 延迟创建物理文件"""
        # 1. 触发原有的未保存状态小圆点
        self._set_tab_modified(editor, True)   

    def _do_physical_save(self, editor):
        """执行实际的磁盘写入操作"""
        try:
            with open(editor.file_path, 'w', encoding='utf-8') as f:
                f.write(editor.toPlainText())
            return True
        except Exception as e:
            print(f"磁盘写入失败: {e}")
            return False

    def close_tab(self, index):
        """关闭标签：如果是未动过的 untitled 文件，由于没创建，自然不需要清理"""
        if index < 0 or index >= self.tabs.count():
            return
        
        editor = self.stacked.widget(index)
        if not editor: return

        # 获取文件路径和内容状态
        file_path = getattr(editor, 'file_path', None)
        is_temp = getattr(editor, 'is_temp', False)

        # 如果它是 untitled 且已经写了磁盘（不是 temp 了），但内容又被删空了，则清理
        if not is_temp and file_path and "untitled" in os.path.basename(file_path):
            if not editor.toPlainText().strip():
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        self.file_created_on_disk.emit()
                except Exception as e:
                    print(f"清理空白文件失败: {e}")

        # UI 移除
        self.stacked.removeWidget(editor)
        editor.deleteLater()
        self.tabs.removeTab(index)
        
        # 自动选中下一个
        if self.tabs.count() > 0:
            new_idx = min(index, self.tabs.count() - 1)
            self.tabs.setCurrentIndex(new_idx)
        else:
            # 如果全关了，可以考虑自动开一个新的虚拟 Tab
            # self.create_untitled_file()
            pass

    def request_save_file(self, parent_window):
        """保存当前文件：修正保存后状态不更新的问题"""
        editor = self.get_current_editor()
        if not editor: return

        path = editor.file_path
        file_name = os.path.basename(path).lower()
        
        # 判定：如果是临时文件，或者磁盘上不存在，或者文件名叫 untitled
        if getattr(editor, 'is_temp', False) or not os.path.exists(path) or "untitled" in file_name:
            new_path, _ = QFileDialog.getSaveFileName(
                parent_window, 
                "保存文件", 
                path, 
                "Python Files (*.py);;All Files (*)"
            )
            
            if new_path:
                # 如果用户选了新路径，且原本后台有残留文件，则清理
                if path and os.path.exists(path) and path != new_path:
                    try: os.remove(path)
                    except: pass
                
                # 更新编辑器路径
                editor.file_path = new_path
                if self._do_physical_save(editor):
                    # 🚀 【关键修正】：一旦手动保存成功，必须取消 temp 标记
                    editor.is_temp = False 
                    
                    self._set_tab_modified(editor, False)
                    
                    # 更新界面文字
                    idx = self.tabs.currentIndex()
                    self.tabs.setTabText(idx, os.path.splitext(os.path.basename(new_path))[0])
                    self.file_created_on_disk.emit()
        else:
            # 对于已经不是 temp 的文件，直接执行静默覆盖
            if self._do_physical_save(editor):
                self._set_tab_modified(editor, False)

    def request_save_as(self, parent_window):
            """另存为：跳过任何状态判断，强制弹出文件选择框"""
            editor = self.get_current_editor()
            if not editor: return

            # 强制弹出另存为对话框
            new_path, _ = QFileDialog.getSaveFileName(
                parent_window, 
                "另存为", 
                editor.file_path, # 初始路径建议为当前文件路径
                "Python Files (*.py);;All Files (*)"
            )
            
            if new_path:
                # 执行物理保存并更新编辑器状态
                editor.file_path = new_path
                if self._do_physical_save(editor):
                    editor.is_temp = False  # 落地后标记为正式文件
                    self._set_tab_modified(editor, False) # 重置圆点
                    
                    # 更新 Tab 标签文字
                    idx = self.tabs.currentIndex()
                    self.tabs.setTabText(idx, os.path.splitext(os.path.basename(new_path))[0])
                    self.file_created_on_disk.emit() # 通知文件树刷新

    def on_tab_double_clicked(self, index):
        """双击重命名"""
        if index < 0 or index >= self.tabs.count():
            return

        rect = self.tabs.tabRect(index)
        original_text = self.tabs.tabText(index)
        editor = self.stacked.widget(index)

        edit = QLineEdit(self.tabs)
        edit.setObjectName("tabRenameEdit")
        edit.setText(original_text)
        edit.setGeometry(rect) 
        
        self.tabs.setTabTextColor(index, Qt.GlobalColor.transparent)
        edit.show()
        edit.setFocus()
        edit.selectAll()

        def finish_edit():
            if not edit.isVisible(): return
            new_name = edit.text().strip()
            self.tabs.setTabTextColor(index, QColor()) 
            if new_name and new_name != original_text:
                self.tabs.setTabText(index, new_name)
                # 只有正式文件才需要物理重命名
                if not getattr(editor, 'is_temp', False):
                    self._sync_file_rename(editor, new_name)
                else:
                    # 如果是 temp 文件，只更新它预期的路径名
                    directory = os.path.dirname(editor.file_path)
                    editor.file_path = os.path.join(directory, f"{new_name}.py")
            edit.deleteLater()

        edit.returnPressed.connect(finish_edit)
        edit.editingFinished.connect(finish_edit)

    def _sync_file_rename(self, editor, new_name):
        """物理重命名"""
        old_path = getattr(editor, 'file_path', None)
        if not old_path or not os.path.exists(old_path): return
        directory = os.path.dirname(old_path)
        new_path = os.path.join(directory, f"{new_name}.py")
        if old_path == new_path: return
        try:
            os.rename(old_path, new_path)
            editor.file_path = new_path
            self.file_renamed_on_disk.emit()
        except Exception as e: print(f"重命名失败: {e}")

    def _set_tab_modified(self, editor, is_modified):
        idx = self.stacked.indexOf(editor)
        if idx == -1: return
        btn = self.tabs.tabButton(idx, QTabBar.ButtonPosition.RightSide)
        if btn:
            status = "true" if is_modified else "false"
            if btn.property("modified") != status:
                btn.setProperty("modified", status)
                btn.style().unpolish(btn)
                btn.style().polish(btn)

    def get_current_editor(self):
        idx = self.tabs.currentIndex()
        return self.stacked.widget(idx) if idx != -1 else None

    def _generate_unique_name(self, directory):
        i = 1
        while True:
            name = f"untitled_{i}.py"
            path = os.path.join(directory, name)
            if not os.path.exists(path): return path
            i += 1