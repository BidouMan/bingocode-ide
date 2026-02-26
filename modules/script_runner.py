import os,sys
from PySide6.QtWidgets import QMessageBox
from PySide6.QtCore import QProcess,QTimer

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
        print(f"子进程 PID: {os.getpid()}")
        print(f"stdin 是否可读: {not sys.stdin.closed}")
        editor = self.editor_mgr.get_current_editor()
        if not editor: return
        
        raw_code = editor.toPlainText()
        
        # 🚀 1. 修正注入逻辑：确保 import 在最顶层
        if "from bingo_engine import" not in raw_code:
            final_code = "from bingo_engine import *\n\n" + raw_code
        else:
            final_code = raw_code

        # 🚀 2. 写入物理文件 (解决 stdin disconnected 报错)
        tmp_file = os.path.join(os.getcwd(), ".bin_run.py")
        with open(tmp_file, "w", encoding="utf-8") as f:
            f.write(final_code)

        # 🚀 3. 先重置渲染器，再启动
        self.render_mgr.reset_session()
        self.console_mgr.run_file(tmp_file) 
        
        # 🚀 4. 聚焦确保按键生效
        QTimer.singleShot(150, lambda: self.ui.game_view.setFocus())

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
    

    
