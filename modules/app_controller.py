import os
from PySide6.QtCore import Qt, QStandardPaths,QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QFileDialog, QMessageBox, QTabBar, QSizePolicy,QVBoxLayout)

from ui.main_window_ui import Ui_Form
from modules.file_menu import FileMenu
from modules.console_manager import ConsoleManager
from modules.editor_manager import EditorManager
from modules.console_manager import ConsoleManager
from modules.screen_manager import ScreenManager

class AppController:
    def __init__(self, main_window: Ui_Form):
        self.window = main_window
        self.ui: Ui_Form = main_window.ui
        self.last_active_index = -1
        
        # 🚀 1. 定义核心状态：逻辑分辨率（在这里修改，全局生效）
        self.stage_width = 320   # 基准宽度
        self.stage_height = 240  # 基准高度

        # 2. 初始化基础环境与布局
        self._init_workspace()
        self.setup_tab_bar()
        self._setup_screen_layout() # 将复杂的布局逻辑抽离

        # 3. 初始化各模块逻辑（确保 ScreenManager 只创建一次）
        self.editor_logic = EditorManager(self.ui.code_stacked, self.tab_bar, self.root_path)
        self.console = ConsoleManager(self.ui.splitter, self.ui.console_output)
        
        # 传入 container，内部会自动根据 stage_width/height 准备画布
        self.screen = ScreenManager(self.ui.screen_frame)
        self.screen.setObjectName("game_screen")
        self.ui.screen_frame.layout().addWidget(self.screen)
        
        self.file_menu = FileMenu(main_window)

        # 4. 绑定信号
        self.setup_connections()

    def _setup_screen_layout(self):
        """专门处理舞台容器的布局初始化"""
        container = self.ui.screen_frame
        if not container.layout():
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            container.setLayout(layout)


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

        self.console.draw_signal.connect(self.screen.draw_instruction)

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


    # modules/app_controller.py

    def handle_run_python(self):
        """点击运行按钮的核心逻辑：智能识别模式"""
        self.handle_save_file() 
        editor = self.editor_logic.get_current_editor()
        if not editor: 
            return
            
        file_path = editor.file_path
        if file_path and os.path.exists(file_path):
            # --- 🚀 新增：智能模式检测 ---
            content = editor.toPlainText() # 直接从编辑器获取内容
            is_turtle = "import turtle" in content or "from turtle" in content
            
            # --- 第一步：资源彻底清理与重置 ---
            if hasattr(self, 'screen'):
                self.screen.timer.stop()
                self.screen.reset_session()
                
                # --- 🚀 核心改进：根据模式动态配置 ---
                if is_turtle:
                    print("🐢 检测到 Turtle 模式")
                    # 1. 切换为淡色背景 (这会触发 ScreenManager 的 canvas.fill)
                    self.screen.bg = QColor("#F5F5F5") 
                    # 2. Turtle 强制使用 480x360 逻辑尺寸
                    current_w, current_h = 480, 360
                else:
                    print("🕹️ 检测到 Arcade 模式")
                    # 1. 切换为深色背景
                    self.screen.bg = QColor("#1E1E1E")
                    # 2. Arcade 使用预设尺寸 (如 320x240)
                    current_w, current_h = self.stage_width, self.stage_height
                
                # 同步尺寸给 ScreenManager
                self.screen.set_logic_size(current_w, current_h)
                self.screen.clear_canvas()

            # --- 第二步：强杀可能残留的旧进程 ---
            self.console.stop_script()

            # --- 第三步：启动新进程 ---
            # 传入检测后的尺寸，确保环境变量注入正确
            self.console.run_script(file_path, current_w, current_h)
            
            # --- 第四步：根据模式开启采样 ---
            if is_turtle:
                # Turtle 模式不需要读取共享内存，不需要开启 timer 采样
                # 指令会通过 draw_signal 实时传回
                pass 
            else:
                # Arcade 模式延迟开启画面采样
                QTimer.singleShot(300, lambda: self.screen.timer.start(16))
                
        else:
            QMessageBox.warning(self.window, "提示", "请先保存文件再运行")



    def handle_stop_python(self):
        """点击停止按钮后的处理逻辑"""
        # 1. 停止 ScreenManager 的渲染并断开连接
        if hasattr(self, 'screen'):
            # 🚀 建议调用封装好的 reset_session
            # 它会停止 timer 并安全地关闭 shm 句柄
            self.screen.reset_session()
            print("🛑 已断开图形渲染连接并停止时钟")
                
        # 2. 强杀子进程并清理系统级共享内存
        if hasattr(self, 'console'):
            # 🚀 调用增强后的 stop_script
            # 确保不仅杀了进程，还通过 Python 脚本 unlink 了共享内存
            self.console.stop_script() 
            print("🛑 子进程已强制结束，系统资源已回收")
        
        # 3. 视觉反馈：恢复运行按钮状态
        self._set_run_btn_state(False)
        
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
    
    