import os
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QProcess

class ScriptRunner:
    def __init__(self, controller):
        self.controller = controller
        self.ui = controller.ui
        self.window = controller.window

        
        # 快捷引用其他经理，保持代码简洁
        self.file_mgr = controller.file_manager
        self.editor_mgr = controller.editor_manager
        self.render_mgr = controller.render_manager
        self.console_mgr = controller.console_manager

    # script_runner.py

    def run_current_script(self):
        """优雅版：直接内存注入运行，不再产生 _run.py"""
        editor = self.editor_mgr.get_current_editor()
        if not editor: return
        
        # 1. 直接获取编辑器里的文本
        raw_code = editor.toPlainText()
        
        # 2. 内存注入：自动补齐 import
        if "from bingo_engine" not in raw_code and "import bingo_engine" not in raw_code:
            final_code = "from bingo_engine import *\n" + raw_code
        else:
            final_code = raw_code

        # 🚀 关键改变：不再 open() 和 write() 文件
        # 直接把 final_code 传给 console_manager
        self.render_mgr.reset_session()
        self.console_mgr.run_code_string(final_code)


    def stop_script(self):
        # 1. 🚀 UI 层面立即宣布胜利：按钮变绿
        self.set_run_btn_visual(False)
        
        # 2. 🚀 切断 UI 连接：停止定时器，主线程立刻清静
        self.console_mgr.pull_timer.stop()
        
        # 3. 🚀 执行后台强杀（不阻塞）
        self.console_mgr.stop_script()

    def set_run_btn_visual(self, is_running):
        """控制运行按钮的高亮状态 (QSS 联动)"""
        btn = self.ui.btn_run
        # 确保通过 setProperty 触发 QSS 中的 [active="true"] 样式
        status = "true" if is_running else "false"
        if btn.property("active") != status:
            btn.setProperty("active", status)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.setChecked(is_running)
    

    
