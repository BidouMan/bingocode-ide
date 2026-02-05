import os
from PySide6.QtCore import Qt, QStandardPaths, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QFileDialog, QMessageBox, QTabBar, QSizePolicy, QApplication, QVBoxLayout)

from ui.main_window_ui import Ui_Form
from modules.file_menu import FileMenu
from modules.console_manager import ConsoleManager
from modules.editor_manager import EditorManager
# 🚀 统一使用 StageManager 替代旧的 ScreenManager
from modules.stage_manager import StageManager

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
        self.setup_tab_bar()
        # 注意：由于 game_view 已在 Designer 中存在，不再需要动态创建布局

        # 3. 初始化各模块逻辑
        self.editor_logic = EditorManager(self.ui.code_stacked, self.tab_bar, self.root_path)
        self.console = ConsoleManager(self.ui.splitter, self.ui.console_output)
        
        # 🚀 关键：直接对接 Designer 中的 game_view (QGraphicsView)
        self.stage = StageManager(self.ui.game_view)
        
        self.file_menu = FileMenu(main_window)

        # 4. 绑定信号 (保持原有业务连接)
        self.setup_connections()

    def _init_workspace(self):
        doc_path = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        self.root_path = os.path.join(doc_path, "BingoIDE_Projects")
        if not os.path.exists(self.root_path):
            os.makedirs(self.root_path, exist_ok=True)
        
    def setup_tab_bar(self):
        """将手动的 TabBar 插入 UI 容器，保留原有的 ID 以匹配 QSS"""
        self.tab_bar = QTabBar()
        self.tab_bar.setDocumentMode(True)
        self.tab_bar.setExpanding(True)
        self.tab_bar.setElideMode(Qt.TextElideMode.ElideRight)        
        self.tab_bar.setObjectName("mainTabBar") # 👈 身份证号绝对不能改，否则样式会乱
    
        tab_container = self.ui.tab_frame
        tab_container.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        layout = tab_container.layout()
        if layout:
            layout.setContentsMargins(0, 0, 0, 0)
            layout.insertWidget(0, self.tab_bar)
            layout.setStretchFactor(self.tab_bar, 1)

    def setup_connections(self):
        """绑定业务信号，完全保留文件和编辑器逻辑"""
        # 菜单信号
        self.file_menu.new_file_signal.connect(self.editor_logic.create_untitled_file)
        self.file_menu.open_file_signal.connect(self.handle_open_file)        
        self.file_menu.save_file_signal.connect(self.handle_save_file)
        self.file_menu.save_as_signal.connect(self.handle_save_as)

        # 进程状态监控
        self.console.process_started.connect(lambda: self._set_run_btn_state(True))
        self.console.process_finished.connect(lambda: self._set_run_btn_state(False))

        # UI 按钮响应
        self.ui.btn_file.clicked.connect(lambda: self.file_menu.show_popup_menu(self.ui.btn_file))
        self.ui.btn_add_tab.clicked.connect(self.editor_logic.create_untitled_file)
        self.ui.btn_save.clicked.connect(self.handle_save_file)
        self.ui.btn_run.clicked.connect(self.handle_run_python)
        if hasattr(self.ui, 'btn_stop'):
            self.ui.btn_stop.clicked.connect(self.handle_stop_python)
        
        # page0 上的全屏按钮
        self.ui.btn_full_screen.clicked.connect(self.enter_fullscreen)
        # page1 上的退出全屏按钮 (名字请根据你 Designer 里的实际情况修改)
        self.ui.fullscreen_btn_unfull.clicked.connect(self.exit_fullscreen)

        # 视觉效果：TabBar 高亮更新
        self.tab_bar.currentChanged.connect(self.update_tab_buttons)

        # 🚀 核心指令对接：将控制台捕获的 JSON 指令喂给舞台
        self.console.draw_signal.connect(self.stage.handle_instruction)


    def handle_open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self.window, "选择文件", "", "Python Files (*.py);;All Files (*)")
        if file_path:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.editor_logic.create_new_tab(file_path, content)

    def handle_save_file(self):
        self.editor_logic.request_save_file(self.window)

    def handle_save_as(self):
        self.editor_logic.request_save_as(self.window)

    def handle_run_python(self):
        self.handle_save_file() 
        editor = self.editor_logic.get_current_editor()
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
    
    def enter_fullscreen(self):
        # 1. 切换页面
        self.ui.change_page.setCurrentIndex(1)

        # 2. 搬运 game_view
        if self.ui.fullscreen_view_frame.layout():
            self.ui.fullscreen_view_frame.layout().addWidget(self.ui.game_view)
            self.ui.fullscreen_view_frame.layout().setContentsMargins(0, 0, 0, 0)

        # 3. 彻底重置 game_view 的所有人工限制
        self.ui.game_view.setMinimumSize(0, 0)
        self.ui.game_view.setMaximumSize(16777215, 16777215)
        self.ui.game_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 4. 执行第一次对齐
        self.adjust_fullscreen_layout()

    def exit_fullscreen(self):
        self.ui.change_page.setCurrentIndex(0)
    
        # 1. 搬回 Page0
        self.ui.edit_stage_container.layout().addWidget(self.ui.game_view)
        
        # 2. 🚀 恢复 Page0 的小尺寸约束
        self.ui.game_view.setFixedSize(320, 240)
        
        QTimer.singleShot(50, self.stage.apply_fit)
    
    def adjust_fullscreen_layout(self):
        full_w = self.window.width()
        full_h = self.window.height()

        # 2. 减去工具栏固定的高度 (假设 30 或动态获取)
        # 这样 available_h 就变成了一个“死”的上限，不受内部控件影响
        tool_h = self.ui.fullscreen_tool_bar.height()
        if tool_h <= 0: tool_h = 30 # 防止初始化时高度为0
        
        available_w = full_w - 40 # 留出一点左右边距边差
        available_h = full_h - tool_h - 20 

        if available_w <= 100 or available_h <= 100:
            return

        # 3. 计算 4:3 比例
        # 算出在当前窗口高度下，最大的 4:3 宽度是多少
        target_h = available_h
        target_w = int(target_h * (4 / 3))

        # 如果算出来的宽度超过了窗口宽度，则反过来以宽度为准
        if target_w > available_w:
            target_w = available_w
            target_h = int(target_w * (3 / 4))

        # 4. 🚀 关键步骤：限制 Wrapper 的最大尺寸，防止它去推挤主窗口
        # 这一行是“灭火器”，它告诉布局系统：无论里面多大，你这个容器不准超过窗口大小
        # self.ui.central_stage_wrapper.setMaximumSize(full_w, full_h)
        self.ui.central_stage_wrapper.setMaximumSize(full_w, target_h + tool_h + 20)

        # 5. 执行缩放
        # 既然 target_w/h 是基于 win.width() 算出来的，它永远不会导致 win 变大
        if self.ui.fullscreen_view_frame.size() != (target_w, target_h):
            self.ui.fullscreen_view_frame.setFixedSize(target_w, target_h)
            print(f"[FIXED] Set Frame to {target_w}x{target_h} | Win was {full_w}")
        
        
    # 🚀 🚀 🚀 [断路器：关键测试] 🚀 🚀 🚀
    # 我已经把执行代码全部注释了。
    # pass 
    # self.ui.fullscreen_view_frame.setFixedSize(target_w, target_h)

    # 🚀 暂时注释掉下面这行执行代码，观察窗口是否还延伸！
    # self.ui.fullscreen_view_frame.setFixedSize(target_w, target_h)
        # # 1. 获取舞台容器目前的物理空间
        # # 此时因为 Designer 设了 Stretch=1，wrapper 已经横向铺满了
        # container_w = self.ui.central_stage_wrapper.width()
        # container_h = self.ui.central_stage_wrapper.height()

        # if container_h <= 100 or container_w <= 100:
        #     return

        # # 2. 算 4:3 比例
        # target_w = container_h * (4 / 3)
        # target_h = container_h

        # # 如果宽度超标，则以宽度为基准反算
        # if target_w > container_w:
        #     target_w = container_w
        #     target_h = target_w * (3 / 4)

        # # 3. 🚀 只改这一行：直接设置显示框的大小
        # # 左右弹簧会自动处理剩余空间，完全不抖动
        # self.ui.fullscreen_view_frame.setFixedSize(int(target_w), int(target_h))