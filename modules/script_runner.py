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
        self.console_mgr = controller.console

    def run_current_script(self):
        """执行脚本流程：保存 -> 重置舞台 -> 运行"""
        # 1. 调用文件经理保存当前编辑器内容
        self.file_mgr.save_file(self.editor_mgr)
        
        # 2. 获取当前编辑器
        editor = self.editor_mgr.get_current_editor()
        if not editor:
            return
            
        file_path = editor.file_path
        if file_path and os.path.exists(file_path):
            # 3. 重置渲染引擎画布
            self.render_mgr.reset_session()
            # 4. 驱动控制台执行 Python 进程
            self.console_mgr.run_script(file_path)
        else:
            QMessageBox.warning(self.window, "提示", "请先保存文件再运行")

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