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
        self.console.process_finished.connect(self.on_run_finished)

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
        if not editor: return
            
        file_path = editor.file_path
        if file_path and os.path.exists(file_path):
            content = editor.toPlainText()
            # 1. 识别模式
            self.is_turtle = "import turtle" in content or "from turtle" in content
            self.is_arcade = "import arcade" in content or "from arcade" in content
            
            # 2. 确定逻辑尺寸 (Turtle 默认 480x360 体验更好，若需统一 320 则手动改回)
            # curr_w, curr_h = (480, 360) if self.is_turtle else (self.stage_width, self.stage_height)
            curr_w, curr_h = self.stage_width, self.stage_height

            if hasattr(self, 'screen'):
                self.screen.timer.stop()
                self.screen.reset_session()
                
                # 2. 🚀 先定尺寸 (这一步会创建新的空白 canvas)
                self.screen.set_logic_size(curr_w, curr_h)

                # 3. 再定背景 (触发 bg.setter，填充纯色)
                mode = 'turtle' if self.is_turtle else 'arcade'
                self.screen.set_render_mode(mode)

                # 4. 🚀 最后写字 (覆盖掉 setter 涂的纯色)
                if not self.is_turtle:
                    txt = "🚀 游戏加载中..." if self.is_arcade else "⚙️ 程序运行中..."
                    self.screen.show_status_text(txt)
                    # 必须放在所有画布操作的最后
                    self.screen.repaint()

                # if self.is_turtle:
                #     self.screen.set_render_mode('turtle')
                #     self.screen.clear_to_empty()
                # elif self.is_arcade:
                #     self.screen.set_render_mode('arcade')
                #     # 🚀 使用 repaint 确保文字在进程启动前强制渲染
                #     self.screen.show_status_text("🚀 游戏加载中...")
                #     self.screen.repaint() 
                # else:
                #     self.screen.set_render_mode('arcade')
                #     self.screen.show_status_text("⚙️ 程序运行中...")
                #     self.screen.repaint()

            # 3. 启动进程：传入正确的 w, h
            self.console.run_script(file_path, curr_w, curr_h)
            
            if self.is_arcade:
                self.screen.timer.start(16)
        else:
            QMessageBox.warning(self.window, "提示", "请先保存文件再运行")

    def on_run_finished(self):
        """当程序运行结束时触发"""
        if hasattr(self, 'screen'):
            self.screen.timer.stop()
            
            # 🚀 关键逻辑：Turtle 模式直接跳过清理，保留画作
            if getattr(self, 'is_turtle', False):
                print("🐢 Turtle 绘图结束，保留画面")
                return

            # 非 Turtle 模式下，如果没有 Arcade 画面输出，则清空提示文字
            has_arcade_frame = hasattr(self.screen, 'shm') and self.screen.shm is not None
            if not has_arcade_frame:
                self.screen.clear_to_empty()
            
            print("✨ 运行结束，屏幕状态已更新")

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
    
    