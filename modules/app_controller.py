import os
from PySide6.QtCore import Qt, QStandardPaths
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QFileDialog, QMessageBox, QTabBar, QSizePolicy)

from ui.main_window_ui import Ui_Form
from modules.file_menu import FileMenu
from modules.console_manager import ConsoleManager
from modules.editor_manager import EditorManager
from modules.console_manager import ConsoleManager

class AppController:
    def __init__(self, main_window: Ui_Form):
        self.window = main_window
        self.ui: Ui_Form= main_window.ui
        self.last_active_index = -1

        # 1. 初始化路径
        self._init_workspace()

        # 2. 关键：先创建 TabBar 实例
        self.setup_tab_bar()

        # 3. 初始化逻辑经理 (传入真正的 self.tab_bar)
        self.editor_logic = EditorManager(self.ui.code_stacked, self.tab_bar, self.root_path)
        self.console = ConsoleManager(self.ui.splitter, self.ui.console_output)

        self.file_menu = FileMenu(main_window)
        
        # 4. 绑定剩余的 UI 信号
        self.setup_connections()


    def _init_workspace(self):
        doc_path = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        self.root_path = os.path.join(doc_path, "BingoIDE_Projects")
        if not os.path.exists(self.root_path):
            os.makedirs(self.root_path, exist_ok=True)
        
    def setup_tab_bar(self):
        """将手动的 TabBar 插入 UI 容器"""
        self.tab_bar = QTabBar()
        self.tab_bar.setDocumentMode(True)
        self.tab_bar.setExpanding(True)
        self.tab_bar.setElideMode(Qt.TextElideMode.ElideRight)        
        self.tab_bar.setObjectName("mainTabBar") # 👈 给它一个身份证号
    
        # 修正：将 tab_bar 放入名为 tab_frame 的容器中
        tab_container = self.ui.tab_frame
        tab_container.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        layout = tab_container.layout()
        if layout:
            layout.setContentsMargins(0, 0, 0, 0)
            layout.insertWidget(0, self.tab_bar)
            layout.setStretchFactor(self.tab_bar, 1)

    def setup_connections(self):
        """只绑定 App 层的业务信号"""
        # 菜单信号
        self.file_menu.new_file_signal.connect(self.editor_logic.create_untitled_file)
        self.file_menu.open_file_signal.connect(self.handle_open_file)        
        self.file_menu.save_file_signal.connect(self.handle_save_file)
        self.file_menu.save_as_signal.connect(self.handle_save_as)

        self.console.process_started.connect(lambda: self._set_run_btn_state(True))
        self.console.process_finished.connect(lambda: self._set_run_btn_state(False))

        # UI 按钮
        self.ui.btn_file.clicked.connect(lambda: self.file_menu.show_popup_menu(self.ui.btn_file))
        self.ui.btn_add_tab.clicked.connect(self.editor_logic.create_untitled_file)
        self.ui.btn_save.clicked.connect(self.handle_save_file)
        self.ui.btn_run.clicked.connect(self.handle_run_python)
        if hasattr(self.ui, 'btn_stop'):
            self.ui.btn_stop.clicked.connect(self.handle_stop_python)

        # 视觉效果：保留 TabBar 的高亮更新
        self.tab_bar.currentChanged.connect(self.update_tab_buttons)

    def handle_open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self.window, "选择文件", "", "Python Files (*.py);;All Files (*)")
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.editor_logic.create_new_tab(file_path, content)

    def handle_save_file(self):
        # 委托经理人处理保存逻辑（包含 untitled 判断）
        self.editor_logic.request_save_file(self.window)

    def handle_save_as(self):
        self.editor_logic.request_save_as(self.window)


    def handle_run_python(self):
        """点击运行按钮时的调度逻辑"""
        self.handle_save_file() # 先保存
        
        editor = self.editor_logic.get_current_editor()
        if not editor: return
            
        editor.format_code() # 自动格式化
        
        if editor.file_path and os.path.exists(editor.file_path):
            # 调度核心：现在这个方法内部会先弹窗，后跑代码
            self.console.run_script(editor.file_path) 
        else:
            print("请先保存文件再运行")

    def handle_stop_python(self):
        """点击停止按钮或需要强制收回控制台时的调度"""
        # 1. 直接指挥控制台逻辑执行停止任务
        # console_manager 会处理：停止 QProcess + 执行收回动画
        self.console.stop_script() 
        
    def update_tab_buttons(self, current_index):
        if self.last_active_index != -1 and self.last_active_index != current_index:
            self._refresh_button_style(self.last_active_index, is_active=False)
        self._refresh_button_style(current_index, is_active=True)
        self.last_active_index = current_index

    def _refresh_button_style(self, index, is_active):
        if 0 <= index < self.tab_bar.count():
            btn = self.tab_bar.tabButton(index, QTabBar.ButtonPosition.RightSide)
            if btn:
                btn.setProperty("active", "true" if is_active else "false")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
    
    def _set_run_btn_state(self, active):
        """更新按钮视觉状态"""
        btn = self.ui.btn_run
        # 假设你使用 QSS 属性来控制高亮
        btn.setProperty("active", "true" if active else "false")
        btn.style().unpolish(btn)
        btn.style().polish(btn)
        # 如果是 Checkable 按钮
        btn.setChecked(active)
    
    