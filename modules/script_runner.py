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

    def run_script(self, file_path):
        """主运行逻辑：判定模式 -> 合并/注入 -> 启动"""
        editor = self.editor_mgr.get_current_editor()
        if not editor: return
        current_code = editor.toPlainText()

        # 🚀 规则 1：判定当前文件是否有 run()
        has_run = "run()" in current_code

        if has_run:
            print(f"🎮 游戏模式：正在汇总项目文件并启动...")
            # 汇总全量代码
            final_code = self._merge_project_files(file_path, current_code)
        else:
            print(f"📝 练习模式：仅运行当前文件 {os.path.basename(file_path)}")
            final_code = current_code

        # 🚀 规则 2：自动注入引擎（如果学生没写 import）
        if "from bingo_engine import" not in final_code:
            final_code = "from bingo_engine import *\n\n" + final_code

        # 3. 写入隐藏的临时运行文件，避免改动学生的原始文件
        temp_run_file = os.path.join(self.controller.project_manager.project_root, ".temp_run.py")
        try:
            with open(temp_run_file, "w", encoding="utf-8") as f:
                f.write(final_code)
        except Exception as e:
            print(f"❌ 准备运行文件失败: {e}")
            return

        # 4. 启动引擎
        self.render_mgr.reset_session()
        self.console_mgr.run_file(temp_run_file)
        
        # 5. 如果是游戏，自动聚焦
        if has_run:
            QTimer.singleShot(150, lambda: self.ui.game_view.setFocus())

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
    
    def _merge_project_files(self, active_path, active_code):
        """汇总逻辑：仅合并含有游戏特征的邻居文件，并屏蔽它们的 run()"""
        root = self.controller.project_manager.project_root
        all_py = [f for f in os.listdir(root) if f.endswith('.py') and not f.startswith('.')]
        
        merged_parts = []
        
        for f_name in all_py:
            full_path = os.path.join(root, f_name)
            # 1. 跳过当前正在运行的文件
            if full_path == active_path:
                continue
                
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                    # 🚀 【核心修复】：如果这个邻居文件既没有 run() 也没有 Sprite(
                    # 说明它是一个普通练习文件，不应该被合并到游戏项目中
                    if not self._is_game_project(content):
                        continue
                    
                    # 2. 屏蔽非活动文件里的 run()
                    clean_content = content.replace("run()", "# [已在汇总时屏蔽非主文件的 run()]")
                    # 3. 移除重复的 import
                    clean_content = clean_content.replace("from bingo_engine import *", "")
                    
                    merged_parts.append(f"### 来自文件: {f_name} ###\n" + clean_content)
            except:
                continue
        
        # 4. 最后加上当前主文件
        merged_parts.append(f"### 主运行文件: {os.path.basename(active_path)} ###\n" + active_code)
        
        return "\n\n".join(merged_parts)

    def _is_game_project(self, code):
        """判定是否为游戏项目：通过核心函数 run() 识别"""
        # 匹配 run() 调用。注意：这里可以检查是否独立成行或在行尾
        # 甚至可以更严谨点，检查是否包含 Sprite( 或 run()
        return "run()" in code or "Sprite(" in code
