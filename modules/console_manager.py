import sys
import os
import json
from PySide6.QtCore import QObject, QProcess, QPropertyAnimation, QEasingCurve, QTimer, Signal, QProcessEnvironment
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication

class ConsoleManager(QObject):
    # 信号定义
    process_started = Signal()
    process_finished = Signal()
    draw_signal = Signal(str)
    instruction_received = Signal(str)

    def __init__(self, splitter, console_output):
        super().__init__()
        self.splitter = splitter
        self.output = console_output
        self.console_container = self.output
        self.anim = None 
        self.target_height = 240 
        
        # 初始状态隐藏控制台
        self.console_container.setMaximumHeight(0)
        self.console_container.setMinimumHeight(0)

        # 🚀 实例化 QProcess
        self.process = QProcess(self) 
        
        # 🚀 核心改造：不再连接 readyReadStandardOutput 信号，防止被死循环淹没
        # 错误输出通常量级较小且重要，保留信号连接或改为统一处理
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self._on_process_finished)

        # 🚀 防火墙定时器：每 50ms 铲一次缓冲区数据 (20 FPS 刷新率)
        self.pull_timer = QTimer(self)
        self.pull_timer.setInterval(50)
        self.pull_timer.timeout.connect(self._pull_output)

    def run_code_string(self, code):
        """
        🚀 优雅启动主入口：
        通过“延迟加载”消除启动时的瞬间卡顿，确保动画丝滑。
        """
        self.output.clear()
        self.process_started.emit()

        # 1. 检查控制台高度
        current_h = self.console_container.height()
        
        if current_h < 10:
            # 🚀 情况 A：控制台尚未打开
            # 先执行展开动画
            self.anim_console(show=True)
            # 延迟 250ms（等动画基本完成）再启动进程和数据拉取
            # 这样 UI 线程就不会同时处理“高度计算”和“数据渲染”
            QTimer.singleShot(250, lambda: self._do_execute_python(code))
        else:
            # 🚀 情况 B：控制台已经是打开状态
            # 直接启动，但依然给一个极短的微秒级延迟，让 UI 响应点击反馈
            QTimer.singleShot(10, lambda: self._do_execute_python(code))

    def _do_execute_python(self, code):
        """核心修复：确保在内存模式下正确加载 bingo_engine"""
        
        # 1. 重新计算并确认模块路径
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_file_dir)
        # 确保这是 bingo_engine 文件夹所在的父级目录
        modules_dir = os.path.join(project_root, "modules")

        # 2. 深度注入环境变量
        env = QProcessEnvironment.systemEnvironment()
        old_path = env.value("PYTHONPATH", "")
        # 将 modules 目录放在最前面
        new_path = modules_dir + os.pathsep + old_path if old_path else modules_dir
        env.insert("PYTHONPATH", new_path)
        
        # 额外保险：设置当前运行目录为项目根目录
        self.process.setWorkingDirectory(project_root)
        self.process.setProcessEnvironment(env)

        # 3. 🚀 修正 wrapper_code 语法
        # 注意：在 exec 模式下，多行代码需要正确处理缩进或使用分号
        # 我们直接在代码最前端插入 import 语句，并确保 sys.path 包含 modules
        wrapper_code = (
            f"import sys; sys.path.insert(0, r'{modules_dir}'); "
            "import signal, os; "
            "signal.signal(signal.SIGTERM, lambda s, f: os._exit(0)); "
            "from bingo_engine import *; "
            f"\n{code}" # 换行确保用户代码不会跟在 import 后面导致语法错误
        )

        # 4. 启动并写入
        self.process.start(sys.executable, ["-u", "-"])
        self.process.write(wrapper_code.encode("utf-8"))
        self.process.closeWriteChannel()
        
        if hasattr(self, 'pull_timer'):
            self.pull_timer.start()

    def handle_stdout_logic(self, data):

        """
        🔥 修复版：确保绘图指令 100% 触发，不受限流影响
        """
        lines = data.splitlines()
        display_text = []

        for line in lines:
            line = line.strip()
            if not line: continue
            
            # 🚀 优先级 1：绘图指令（绝对不能被截断，必须实时发射）
            if line.startswith("BINGO:"):
                json_content = line.replace("BINGO:", "", 1)
                self.instruction_received.emit(json_content)
                self.draw_signal.emit(line)
                continue # 处理完指令直接跳过，不计入文本截断限制
                
            elif line.startswith('{') and line.endswith('}'):
                self.instruction_received.emit(line)
                continue

            # 🚀 优先级 2：普通文本（存入列表，稍后进行限流渲染）
            display_text.append(line)

        # 🚀 性能限流：只针对普通文本进行截断，保证 UI 不卡顿
        if len(display_text) > 100:
            display_text = display_text[-100:]
            display_text.insert(0, "--- (输出过快，已省略部分文字日志) ---")

        if display_text:
            self.output.appendPlainText("\n".join(display_text))
            self.output.moveCursor(QTextCursor.End)

    def _pull_output(self):
        """防火墙核心：主动拉取缓冲区数据"""
        if self.process.state() == QProcess.ProcessState.NotRunning:
            self.pull_timer.stop()
            return
            
        # 批量读取本次 50ms 内积压的所有字节
        out_data = self.process.readAllStandardOutput().data().decode("utf-8", "ignore")
        if out_data:
            self.handle_stdout_logic(out_data)

    

    def handle_stderr(self):
        """处理异常输出"""
        err_data = self.process.readAllStandardError().data().decode("utf-8", "ignore")
        if err_data:
            self.output.appendPlainText(f"❌ Error:\n{err_data}")
            self.output.moveCursor(QTextCursor.End)

    def stop_script(self):
        """优化后的停止逻辑：消除断连警告并确保静默退出"""
        # 1. 🚀 停止拉取定时器
        if hasattr(self, 'pull_timer'):
            self.pull_timer.stop()
        
        if self.process and self.process.state() != QProcess.ProcessState.NotRunning:
            # 2. 🚀 仅断开真正连接过的信号，避免 RuntimeWarning
            try:
                # readyReadStandardOutput 没连过，所以不需要 disconnect 它
                self.process.readyReadStandardError.disconnect()
                self.process.finished.disconnect()
            except (RuntimeError, TypeError):
                # 如果信号本身没连接，静默跳过
                pass
            
            # 3. 🚀 强杀并等待系统回收
            p = self.process
            p.kill()
            
            # 使用较短的等待时间 (100ms 足够系统清理句柄)
            p.waitForFinished(100)
            
            # 4. 🚀 立即刷新 UI 事件循环，确保按钮点击反馈（Hover/Click）不卡顿
            QApplication.processEvents()
            
            # 5. 🚀 彻底剥离旧对象
            p.setParent(None)
            p.deleteLater()
            
            # 6. 🚀 重建 QProcess 为下次运行准备
            self.process = QProcess(self)
            self.process.readyReadStandardError.connect(self.handle_stderr)
            self.process.finished.connect(self._on_process_finished)
        
        self.anim_console(show=False)
        self.process_finished.emit()

    def _on_process_finished(self):
        """进程自然结束的回调"""
        self.pull_timer.stop()
        self.process_finished.emit()

    # --- 动画逻辑：抽屉式控制台控制 ---
    def anim_console(self, show=True):
        if self.anim: self.anim.stop()
        if show: self.console_container.setMaximumHeight(16777215)

        end_height = self.target_height if show else 0
        self.anim = QPropertyAnimation(self.console_container, b"maximumHeight")
        self.anim.setDuration(250)
        self.anim.setStartValue(self.console_container.height())
        self.anim.setEndValue(end_height)
        self.anim.setEasingCurve(QEasingCurve.OutCubic if show else QEasingCurve.OutQuint)
        self.anim.valueChanged.connect(self._sync_splitter_sizes)
        if not show: self.anim.finished.connect(self._finalize_hide)
        self.anim.start()

    def _finalize_hide(self):
        self.console_container.setMaximumHeight(0)
        self.splitter.setSizes([self.splitter.height(), 0])

    def _sync_splitter_sizes(self):
        h = self.console_container.maximumHeight()
        total_h = self.splitter.height()
        # 确保 Splitter 的两个部分比例同步更新
        self.splitter.setSizes([max(0, total_h - h), h])