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

        # 1. 强杀进程
        if self.console_mgr.process and self.console_mgr.process.state() != QProcess.NotRunning:
            self.console_mgr.process.kill()
            self.console_mgr.process.waitForFinished(300)
        if is_exiting:
            return

        # 2. 命令控制台执行收回动画
        self.console_mgr.anim_console(show=False)

        # 3. 清空控制台内容
        self.console_mgr.output.clear()

        # 4. 恢复按钮状态
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
        """
        深度汇总：解决多文件变量引用顺序问题。
        策略：将所有文件的变量定义、函数、类提取到前面，确保 run() 在最后执行。
        """
        import os
        root = os.path.dirname(active_path)
        all_py = [f for f in os.listdir(root) if f.endswith('.py') and not f.startswith('.')]
        
        # 建立代码池，存储 (文件名, 内容)
        code_pool = []
        for f_name in all_py:
            full_path = os.path.join(root, f_name)
            if full_path == active_path:
                content = active_code
            else:
                try:
                    with open(full_path, "r", encoding="utf-8") as f:
                        content = f.read()
                except: continue
            
            # 过滤：只处理有游戏特征的代码
            if self._is_game_project(content):
                code_pool.append((f_name, content))

        # 准备合并的三大板块
        imports_section = []    # 存放 import 语句
        definitions_section = [] # 存放变量定义、函数、类
        
        for f_name, content in code_pool:
            lines = content.splitlines()
            file_body = []
            
            for line in lines:
                stripped = line.strip()
                
                # 1. 提取并去重 import
                if stripped.startswith("import ") or stripped.startswith("from "):
                    # 排除掉我们稍后会自动统一注入的引擎导入
                    if "bingo_engine" not in stripped and line not in imports_section:
                        imports_section.append(line)
                    continue
                
                # 2. 屏蔽所有文件中的 run() 调用
                # 我们要在最后手动添加一个唯一的 run()
                if "run()" in stripped and not stripped.startswith("#"):
                    line = line.replace("run()", "# [已在合并时移至末尾]")
                
                file_body.append(line)
            
            # 包装每个文件的内容，增加注释方便学生调试查看
            definitions_section.append(f"### --- File: {f_name} --- ###")
            definitions_section.extend(file_body)
            definitions_section.append("\n")

        # 🚀 最终组装顺序：
        # Layer 1: 引擎导入（确保最优先）
        # Layer 2: 其他库导入 (math, random 等)
        # Layer 3: 所有文件的全部代码（变量 a=..., b=..., def loop()...）
        # Layer 4: 唯一的启动指令 run()
        
        final_code_lines = [
            "from bingo_engine import *",
            "\n".join(imports_section),
            "\n".join(definitions_section),
            "run()"  # 确保整个项目只有一个 run() 在最后
        ]
        
        return "\n\n".join(final_code_lines)

    def _is_game_project(self, code):
        """判断代码是否属于 bingo 引擎项目的一部分"""
        # 优化：简单的字符串查找比正则快得多
        game_keywords = ["Sprite(", "run()", "set_background(", "mouse.", "key_down("]
        return any(key in code for key in game_keywords)
