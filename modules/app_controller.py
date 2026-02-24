import os
from PySide6.QtCore import Qt, QStandardPaths, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QFileDialog, QMessageBox, QTabBar, QSizePolicy, QApplication, QVBoxLayout)

from ui.main_window_ui import Ui_Form
from modules.mune_manager import MenuManager
from modules.console_manager import ConsoleManager
from modules.editor_manager import EditorManager



# 整合好的模组
from modules.render_manager import RenderManager
from modules.screen_manager import ScreenManager
from modules.tabbar_manager import TabbarManager
from modules.file_manager import FileManager
from modules.script_runner import ScriptRunner

class AppController:
    def __init__(self, main_window: Ui_Form):
        self.window = main_window
        self.ui: Ui_Form = main_window.ui
        self.last_active_index = -1
        self._is_adjusting = False
        
        # 🚀 1. 核心分辨率：统一使用 640x480 (自研引擎黄金比例)
        self.stage_width = 640   
        self.stage_height = 480  

        # 首先实例化文件管理器 后续其他管理器需要用到root_path
        self.file_manager = FileManager(self.window)
        
        # 带整理的模块
        self.console_manager = ConsoleManager(self.ui.splitter, self.ui.console_output)        
        self.menu_manager = MenuManager(main_window)

        # 整理过的模块
        self.render_manager = RenderManager(self.ui.game_view)
        self.screen_manager = ScreenManager(self)
        self.tabbar_manager = TabbarManager(self.ui.tab_frame)
        self.editor_manager = EditorManager(self.ui.code_stacked, self.tabbar_manager, self.file_manager.root_path)
        self.script_runner = ScriptRunner(self)

        # 4. 绑定信号 (保持原有业务连接)
        self.setup_connections()


        
     
    def setup_connections(self):
        """绑定业务信号，完全保留文件和编辑器逻辑"""
        # 主页全局按钮-
        self.ui.btn_file.clicked.connect(lambda: self.menu_manager.show_popup_menu(self.ui.btn_file))
        self.ui.btn_save.clicked.connect(lambda: self.file_manager.save_file(self.editor_manager))

    
        # 菜单栏按钮_>文件管理 
        self.menu_manager.new_file_signal.connect(self.editor_manager.create_untitled_file)
        self.menu_manager.open_file_signal.connect(lambda: self.file_manager.open_file_dialog(self.editor_manager))        
        self.menu_manager.save_file_signal.connect(lambda: self.file_manager.save_file(self.editor_manager))
        self.menu_manager.save_as_signal.connect(lambda: self.file_manager.save_as_file(self.editor_manager))


        # 运行程序按钮
        self.ui.btn_run.clicked.connect(self.script_runner.run_current_script)
        if hasattr(self.ui, 'btn_stop'):
            self.ui.btn_stop.clicked.connect(self.script_runner.stop_script)

        
        # 运行console控制台
        self.console_manager.process_started.connect(lambda: self.script_runner.set_run_btn_visual(True))
        self.console_manager.process_finished.connect(lambda: self.script_runner.set_run_btn_visual(False))


        # 切换全屏和编辑模式
        self.ui.btn_full_screen.clicked.connect(self.screen_manager.enter_fullscreen)
        self.ui.fullscreen_btn_unfull.clicked.connect(self.screen_manager.exit_fullscreen)


        # 代码编辑标签页功能
        self.tabbar_manager.tab_changed.connect(self.editor_manager.switch_to_page)
        self.ui.btn_add_tab.clicked.connect(self.editor_manager.create_untitled_file)


        # 将捕获的JSON指令喂给render_manager
        # self.console_manager.draw_signal.connect(self.render_manager.handle_instruction)
        self.console_manager.instruction_received.connect(self.render_manager.handle_instruction)


