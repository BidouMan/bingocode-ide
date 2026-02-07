import os
from PySide6.QtWidgets import QMessageBox

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
        """执行脚本流程：物理注入 -> 运行"""
        editor = self.editor_mgr.get_current_editor()
        if not editor: return
        
        # 1. 获取代码内容
        raw_code = editor.toPlainText()
        
        # 2. 🚀 物理注入逻辑：如果没写 import，自动补上一行
        if "from bingo_engine" not in raw_code and "import bingo_engine" not in raw_code:
            final_code = "from bingo_engine import *\n" + raw_code
        else:
            final_code = raw_code

        # 3. 将注入后的代码写入一个临时文件或覆盖原文件运行
        # 建议保存到一个隐藏的运行缓存文件，避免破坏用户正在编辑的代码
        run_file_path = editor.file_path.replace(".py", "_run.py")
        with open(run_file_path, "w", encoding="utf-8") as f:
            f.write(final_code)

        if os.path.exists(run_file_path):
            self.render_mgr.reset_session()
            # 🚀 关键：运行的是注入后的文件
            self.console_mgr.run_script(run_file_path)
            
            # 运行完后可以考虑删掉这个 _run.py 文件（或者在 stop 时删）
        else:
            QMessageBox.warning(self.window, "提示", "运行准备失败")

    def stop_script(self):
        """停止逻辑：杀掉进程并清理画布"""
        self.render_mgr.reset_session()
        self.console_mgr.stop_script()
        self.set_run_btn_visual(False)

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
    
