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
        """切换到全屏预览模式"""
        # 1. 切换到全屏页面 (Page 1)
        self.ui.change_page.setCurrentIndex(1)

        # 2. 搬运 game_view
        # 将游戏画面从编辑容器移动到全屏专用的 view_frame 中
        if self.ui.fullscreen_view_frame.layout():
            # 这一步会自动把 game_view 从旧容器中解绑并加入新容器
            self.ui.fullscreen_view_frame.layout().addWidget(self.ui.game_view)
            # 确保新容器内部没有边距，让画面能贴合边缘
            self.ui.fullscreen_view_frame.layout().setContentsMargins(0, 0, 0, 0)

        # 3. 彻底释放 game_view 的尺寸限制
        # 在 Page 0 可能设置了 320x240 的 FixedSize，这里必须清空，否则画面大不了
        self.ui.game_view.setMinimumSize(0, 0)
        self.ui.game_view.setMaximumSize(16777215, 16777215)
        # 设置为 Expanding 才能跟随父容器 (fullscreen_view_frame) 缩放
        self.ui.game_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 4. 触发一次初始比例校准
        self.adjust_fullscreen_layout()

    def exit_fullscreen(self):
        self.ui.change_page.setCurrentIndex(0)
    
        # 1. 搬回 Page0
        self.ui.edit_stage_container.layout().addWidget(self.ui.game_view)
        
        # 2. 🚀 恢复 Page0 的小尺寸约束
        self.ui.game_view.setFixedSize(320, 240)
        
        QTimer.singleShot(50, self.stage.apply_fit)
    
    def adjust_fullscreen_layout(self):
        # 1. 获取舞台容器目前的物理空间
        # 此时因为 Designer 设了 Stretch=1，wrapper 已经横向铺满了
        container_w = self.ui.central_stage_wrapper.width()
        container_h = self.ui.central_stage_wrapper.height()

        if container_h <= 100 or container_w <= 100:
            return

        # 2. 算 4:3 比例
        target_w = container_h * (4 / 3)
        target_h = container_h

        # 如果宽度超标，则以宽度为基准反算
        if target_w > container_w:
            target_w = container_w
            target_h = target_w * (3 / 4)

        # 3. 🚀 只改这一行：直接设置显示框的大小
        # 左右弹簧会自动处理剩余空间，完全不抖动
        self.ui.fullscreen_view_frame.setFixedSize(int(target_w), int(target_h))