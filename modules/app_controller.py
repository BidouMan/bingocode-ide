import os
import json
from PySide6.QtCore import Qt, QStandardPaths, QTimer
from PySide6.QtWidgets import (QFileDialog, QMessageBox, QTabBar, QSizePolicy, QApplication, QVBoxLayout)

from modules.file_menu import FileMenu
from modules.console_manager import ConsoleManager
from modules.editor_manager import EditorManager
from modules.stage_manager import StageManager # 👈 引用新引擎

class AppController:
    def __init__(self, main_window):
        self.window = main_window
        self.ui = main_window.ui
        self.last_active_index = -1
        
        # 1. 核心分辨率
        self.logic_w = 640
        self.logic_h = 480

        # 2. 基础环境与组件初始化
        self._init_workspace()
        self.setup_tab_bar()

        # 3. 模块实例化 (按依赖顺序排列)
        self.editor_logic = EditorManager(self.ui.code_stacked, self.tab_bar, self.root_path)
        self.console = ConsoleManager(self.ui.splitter, self.ui.console_output)
        
        # 🚀 直接注入 Designer 里的 game_view
        self.stage = StageManager(self.ui.game_view)
        
        # 🚀 必须确保 file_menu 实例化时传入的是 self.window (BingoIDE 实例)
        self.file_menu = FileMenu(self.window) 

        # 4. 绑定信号 (这一步如果不执行，点击就没反应)
        self.setup_connections()



    def setup_connections(self):
        # 菜单与文件操作
        self.file_menu.new_file_signal.connect(self.editor_logic.create_untitled_file)
        self.file_menu.open_file_signal.connect(self.handle_open_file)        
        self.file_menu.save_file_signal.connect(self.handle_save_file)
        
        # 进程状态监控
        self.console.process_started.connect(lambda: self._set_run_btn_state(True))
        self.console.process_finished.connect(lambda: self._set_run_btn_state(False))

        # 🚀 指令对接：将控制台捕获到的指令，直接喂给舞台引擎
        self.console.draw_signal.connect(self.stage.handle_instruction)

        # UI 交互
        self.ui.btn_run.clicked.connect(self.handle_run_python)
        if hasattr(self.ui, 'btn_stop'):
            self.ui.btn_stop.clicked.connect(self.handle_stop_python)
        
        self.tab_bar.currentChanged.connect(self.update_tab_buttons)

    def handle_run_python(self):
        """点击运行：清空旧舞台，启动新进程"""
        self.handle_save_file() 
        editor = self.editor_logic.get_current_editor()
        if not editor: return
            
        file_path = editor.file_path
        if file_path and os.path.exists(file_path):
            # 1. 重置舞台引擎
            self.stage.reset_session()
            QApplication.processEvents() # 强制 UI 刷新，确保重置效果立刻可见

            # 2. 启动脚本（不再需要传复杂的 w, h 参数给环境变量）
            self.console.run_script(file_path)
        else:
            QMessageBox.warning(self.window, "提示", "请先保存文件再运行")

    def handle_stop_python(self):
        """停止运行：重置舞台并强杀进程"""
        self.stage.reset_session()
        self.console.stop_script() 
        self._set_run_btn_state(False)

    # --- 基础 UI 维护函数 (保持不变) ---
    def _init_workspace(self):
        doc_path = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        self.root_path = os.path.join(doc_path, "BingoIDE_Projects")
        os.makedirs(self.root_path, exist_ok=True)

    def setup_tab_bar(self):
        self.tab_bar = QTabBar()
        self.tab_bar.setDocumentMode(True)
        self.tab_bar.setExpanding(True)
        self.ui.tab_frame.layout().insertWidget(0, self.tab_bar)

    def handle_open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self.window, "选择文件", "", "Python Files (*.py)")
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.editor_logic.create_new_tab(file_path, content)

    def handle_save_file(self):
        self.editor_logic.request_save_file(self.window)

    def update_tab_buttons(self, index):
        if self.last_active_index != -1:
            self._refresh_button_style(self.last_active_index, False)
        self._refresh_button_style(index, True)
        self.last_active_index = index

    def _refresh_button_style(self, index, is_active):
        if 0 <= index < self.tab_bar.count():
            btn = self.tab_bar.tabButton(index, QTabBar.ButtonPosition.RightSide)
            if btn:
                btn.setProperty("active", "true" if is_active else "false")
                btn.style().unpolish(btn); btn.style().polish(btn)
    
    def _set_run_btn_state(self, active):
        btn = self.ui.btn_run
        btn.setProperty("active", "true" if active else "false")
        btn.style().unpolish(btn); btn.style().polish(btn)

    def cleanup_before_exit(self):
        self.console.stop_script()
        self.stage.reset_session()