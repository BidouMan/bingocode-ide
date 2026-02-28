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

        # 🚀 规则 1：判定当前文件是否有 run()。 strip() 确保不受末尾空格影响
        has_run = "run()" in current_code

        if has_run:
            # 仅保留核心业务提示
            print(f"🎮 游戏模式：正在启动项目...")
            final_code = self._merge_project_files(file_path, current_code)
        else:
            print(f"📝 练习模式：正在运行 {os.path.basename(file_path)}")
            final_code = current_code

        # 🚀 规则 2：自动注入引擎（如果学生没写 import）
        if "from bingo_engine import" not in final_code:
            final_code = "from bingo_engine import * \n" + final_code

        # 3. 写入临时文件并交给 ConsoleManager 运行
        temp_run_path = os.path.join(os.path.dirname(file_path), ".temp_run.py")
        try:
            with open(temp_run_path, "w", encoding="utf-8") as f:
                f.write(final_code)
            self.console_mgr.run_file(temp_run_path)
        except Exception as e:
            QMessageBox.critical(self.window, "运行错误", f"无法创建临时运行文件: {e}")



    def stop_script(self,is_exiting=False):
        """强制停止并收回控制台"""
       
        # 1. 停止数据拉取
        if self.console_mgr.pull_timer.isActive():
            self.console_mgr.pull_timer.stop()

        # 2. 强杀进程
        if self.console_mgr.process and self.console_mgr.process.state() != QProcess.NotRunning:
            self.console_mgr.process.kill() 
            self.console_mgr.process.waitForFinished(300)
        # 🚀 如果是正在退出程序，跳过所有 UI 动画和属性设置
        if is_exiting:
            return
            
        # 3. 🚀 【新增】命令控制台执行收回动画
        # 这样点击 stop 后，控制台会自动滑回去
        self.console_mgr.anim_console(show=False)
        
        # 4. 🚀 【新增】清空控制台内容 (如果你希望停止后立即清空的话)
        self.console_mgr.output.clear()

        # 5. 恢复按钮状态
        self.set_run_btn_visual(False)

    def cleanup_temp_files(self):
        """
        彻底删除产生的隐藏临时文件
        """
        if not self.controller.project_manager.project_root:
            return
            
        temp_run_file = os.path.join(self.controller.project_manager.project_root, ".temp_run.py")
        
        if os.path.exists(temp_run_file):
            try:
                os.remove(temp_run_file)
            except Exception as e:
                print(f"⚠️ 清理临时文件失败: {e}")


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
        """汇总同目录下所有符合条件的 .py 文件"""
        root = os.path.dirname(active_path)
        # 过滤掉隐藏文件和临时文件
        all_py = [f for f in os.listdir(root) if f.endswith('.py') and not f.startswith('.')]
        
        merged_parts = []
        for f_name in all_py:
            full_path = os.path.join(root, f_name)
            # 跳过主运行文件（因为它已经作为 active_code 传入了）
            if full_path == active_path:
                continue
                
            try:
                # 明确指定编码，防止 Windows 下读取失败
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                    # 🚀 核心判定：如果邻居文件完全没有游戏特征，不合并
                    if not self._is_game_project(content):
                        continue
                    
                    # 屏蔽非主文件里的 run()，防止多重循环启动
                    clean_content = content.replace("run()", "# [已屏蔽非主文件 run()]")
                    # 移除重复导入，保持代码整洁
                    clean_content = clean_content.replace("from bingo_engine import *", "")
                    
                    merged_parts.append(f"### File: {f_name} ###\n" + clean_content)
            except:
                # 读取失败的文件（如权限问题）直接跳过
                continue
        
        # 将主文件放在最后，确保主逻辑最后加载
        merged_parts.append(f"### Main: {os.path.basename(active_path)} ###\n" + active_code)
        return "\n\n".join(merged_parts)

    def _is_game_project(self, code):
        """判断代码是否属于 bingo 引擎项目的一部分"""
        # 优化：简单的字符串查找比正则快得多
        game_keywords = ["Sprite(", "run()", "set_background(", "mouse.", "key_down("]
        return any(key in code for key in game_keywords)
