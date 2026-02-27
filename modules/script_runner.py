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

    def run_project(self):
        print('run')
        editor_manager = self.controller.editor_manager
        project_manager = self.controller.project_manager
        console_manager = self.controller.console_manager

        editor = editor_manager.get_current_editor()
        if not editor: return

        # 🚀 重点：这里需要像 run_current_script 那样做代码处理
        raw_code = editor.toPlainText()
        
        # 如果你的引擎需要自动 import，就在这里加上
        if "from bingo_engine import" not in raw_code:
            final_code = "from bingo_engine import *\n\n" + raw_code
        else:
            final_code = raw_code

        # 同步写入临时 main.py
        try:
            with open(project_manager.main_script_path, "w", encoding="utf-8") as f:
                f.write(final_code)
        except Exception as e:
            print(f"❌ 同步失败: {e}")
            return

        # 启动运行
        console_manager.run_file(project_manager.main_script_path)

    # def run_current_script(self):
    #     print(f"子进程 PID: {os.getpid()}")
    #     print(f"stdin 是否可读: {not sys.stdin.closed}")
    #     editor = self.editor_mgr.get_current_editor()
    #     if not editor: return
        
    #     raw_code = editor.toPlainText()
        
    #     # 🚀 1. 修正注入逻辑：确保 import 在最顶层
    #     if "from bingo_engine import" not in raw_code:
    #         final_code = "from bingo_engine import *\n\n" + raw_code
    #     else:
    #         final_code = raw_code

    #     # 🚀 2. 写入物理文件 (解决 stdin disconnected 报错)
    #     tmp_file = os.path.join(os.getcwd(), ".bin_run.py")
    #     with open(tmp_file, "w", encoding="utf-8") as f:
    #         f.write(final_code)

    #     # 🚀 3. 先重置渲染器，再启动
    #     self.render_mgr.reset_session()
    #     self.console_mgr.run_file(tmp_file) 
        
    #     # 🚀 4. 聚焦确保按键生效
    #     QTimer.singleShot(150, lambda: self.ui.game_view.setFocus())



    def stop_script(self):
        """强制停止并收回控制台"""
        print("🛑 正在尝试强制停止进程...")
        
        # 1. 停止数据拉取
        if self.console_mgr.pull_timer.isActive():
            self.console_mgr.pull_timer.stop()

        # 2. 强杀进程
        if self.console_mgr.process and self.console_mgr.process.state() != QProcess.NotRunning:
            self.console_mgr.process.kill() 
            self.console_mgr.process.waitForFinished(300)
            
        # 3. 🚀 【新增】命令控制台执行收回动画
        # 这样点击 stop 后，控制台会自动滑回去
        self.console_mgr.anim_console(show=False)
        
        # 4. 🚀 【新增】清空控制台内容 (如果你希望停止后立即清空的话)
        self.console_mgr.output.clear()

        # 5. 恢复按钮状态
        self.set_run_btn_visual(False)
        print("✅ 进程已强行终止并收回 UI")

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
    

    
