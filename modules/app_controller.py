import os
from PySide6.QtCore import Qt, QStandardPaths, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QFileDialog, QMessageBox, QTabBar, QSizePolicy, QApplication, QVBoxLayout)

from ui.main_window_ui import Ui_Form
from modules.file_menu import FileMenu
from modules.console_manager import ConsoleManager
from modules.editor_manager import EditorManager



# 整合好的模组
from modules.render_manager import RenderManager
from modules.screen_manager import ScreenManager
from modules.tabbar_manager import TabbarManager

class AppController:
    def __init__(self, main_window: Ui_Form):
        self.window = main_window
        self.ui: Ui_Form = main_window.ui
        self.last_active_index = -1
        self._is_adjusting = False
        
        # 🚀 1. 核心分辨率：统一使用 640x480 (自研引擎黄金比例)
        self.stage_width = 640   
        self.stage_height = 480  

        # 2. 初始化基础环境与布局
        self._init_workspace()
        

        self.console = ConsoleManager(self.ui.splitter, self.ui.console_output)
        
        self.file_menu = FileMenu(main_window)

        # 整理过的模块
        self.render_manager = RenderManager(self.ui.game_view)
        self.screen_manager = ScreenManager(self)
        self.tabbar_manager = TabbarManager(self.ui.tab_frame)
        self.editor_manager = EditorManager(self.ui.code_stacked, self.tabbar_manager, self.root_path)


        # 4. 绑定信号 (保持原有业务连接)
        self.setup_connections()

    def _init_workspace(self):
        doc_path = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        self.root_path = os.path.join(doc_path, "BingoIDE_Projects")
        if not os.path.exists(self.root_path):
            os.makedirs(self.root_path, exist_ok=True)
        
    # def setup_tab_bar(self):
    #     """将手动的 TabBar 插入 UI 容器，保留原有的 ID 以匹配 QSS"""
    #     self.tab_bar = QTabBar()
    #     self.tab_bar.setDocumentMode(True)
    #     self.tab_bar.setExpanding(True)
    #     self.tab_bar.setElideMode(Qt.TextElideMode.ElideRight)        
    #     self.tab_bar.setObjectName("mainTabBar") # 👈 身份证号绝对不能改，否则样式会乱
    
    #     tab_container = self.ui.tab_frame
    #     tab_container.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    #     layout = tab_container.layout()
    #     if layout:
    #         layout.setContentsMargins(0, 0, 0, 0)
    #         layout.insertWidget(0, self.tab_bar)
    #         layout.setStretchFactor(self.tab_bar, 1)

    def setup_connections(self):
        """绑定业务信号，完全保留文件和编辑器逻辑"""
        # 菜单信号
        self.file_menu.new_file_signal.connect(self.editor_manager.create_untitled_file)
        self.file_menu.open_file_signal.connect(self.handle_open_file)        
        self.file_menu.save_file_signal.connect(self.handle_save_file)
        self.file_menu.save_as_signal.connect(self.handle_save_as)

        # 进程状态监控
        self.console.process_started.connect(lambda: self._set_run_btn_state(True))
        self.console.process_finished.connect(lambda: self._set_run_btn_state(False))

        # UI 按钮响应
        self.ui.btn_file.clicked.connect(lambda: self.file_menu.show_popup_menu(self.ui.btn_file))

        self.ui.btn_save.clicked.connect(self.handle_save_file)
        self.ui.btn_run.clicked.connect(self.handle_run_python)
        if hasattr(self.ui, 'btn_stop'):
            self.ui.btn_stop.clicked.connect(self.handle_stop_python)
        
        # 切换全屏和编辑模式
        self.ui.btn_full_screen.clicked.connect(self.screen_manager.enter_fullscreen)
        self.ui.fullscreen_btn_unfull.clicked.connect(self.screen_manager.exit_fullscreen)

        # 视觉效果：TabBar 高亮更新
        self.tabbar_manager.tab_changed.connect(self.editor_manager.switch_to_page)
        self.ui.btn_add_tab.clicked.connect(self.editor_manager.create_untitled_file)


        # 🚀 核心指令对接：将控制台捕获的 JSON 指令喂给舞台
        self.console.draw_signal.connect(self.render_manager.handle_instruction)


    def handle_open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self.window, "选择文件", "", "Python Files (*.py);;All Files (*)")
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.editor_manager.create_new_tab(file_path, content)

    def handle_save_file(self):
        self.editor_manager.request_save_file(self.window)

    def handle_save_as(self):
        self.editor_manager.request_save_as(self.window)

    def handle_run_python(self):
        self.handle_save_file() 
        editor = self.editor_manager.get_current_editor()
        if not editor: return
            
        file_path = editor.file_path
        if file_path and os.path.exists(file_path):
            # 1. 重置舞台
            if hasattr(self, 'stage'):
                self.stage.reset_session()
                QApplication.processEvents() 

            # 🚀 修复这里：只传 file_path 即可，去掉后面的 width 和 height
            self.console.run_script(file_path) 
        else:
            QMessageBox.warning(self.window, "提示", "请先保存文件再运行")

    def handle_stop_python(self):
        """停止运行：重置舞台并杀掉进程"""
        if hasattr(self, 'stage'):
            self.stage.reset_session()
                
        if hasattr(self, 'console'):
            self.console.stop_script() 
        
        self._set_run_btn_state(False)
        
    def update_tab_buttons(self, current_index):
        if self.last_active_index != -1 and self.last_active_index != current_index:
            self._refresh_button_style(self.last_active_index, is_active=False)
        self._refresh_button_style(current_index, is_active=True)
        self.last_active_index = current_index

    def _refresh_button_style(self, index, is_active):
        """精准控制 Tab 按钮样式，保持原有 QSS 效果"""
        if 0 <= index < self.tab_bar.count():
            btn = self.tab_bar.tabButton(index, QTabBar.ButtonPosition.RightSide)
            if btn:
                btn.setProperty("active", "true" if is_active else "false")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
    
    def _set_run_btn_state(self, active):
        """同步运行按钮的视觉状态"""
        btn = self.ui.btn_run
        btn.setProperty("active", "true" if active else "false")
        btn.style().unpolish(btn)
        btn.style().polish(btn)
        btn.setChecked(active)

    def cleanup_before_exit(self):
        """退出前的清理"""
        if hasattr(self, 'console'):
            self.console.stop_script()
        if hasattr(self, 'stage'):
            self.stage.reset_session()
    
