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

        # 🚀 防火墙定时器：每 16ms 铲一次缓冲区数据 (60 FPS 刷新率)
        self.pull_timer = QTimer(self)
        self.pull_timer.setInterval(16)
        self.pull_timer.timeout.connect(self._pull_output)


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
            p = self.process
            try:
                # readyReadStandardOutput 没连过，所以不需要 disconnect 它
                self.process.readyReadStandardError.disconnect()
                self.process.finished.disconnect()
                p.closeWriteChannel()
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
    

    # modules/console_manager.py 里的启动逻辑

    # modules/console_manager.py

    # modules/console_manager.py

    def run_file(self, file_path):
        """统一后的文件运行入口"""
        # 🚀 1. 彻底杀掉旧进程，解决 "already running" 报错
        if self.process and self.process.state() != QProcess.NotRunning:
            self.process.kill()  # 强杀
            self.process.waitForFinished(100) # 等待 100ms 确保资源释放

        # 🚀 2. 弹出控制台 UI (这行是你漏掉的)
        self.anim_console(show=True)

        self.output.clear()
        self.process_started.emit()

        # --- 路径注入逻辑 (保持你之前的代码) ---
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_file_dir)
        modules_dir = os.path.join(project_root, "modules")

        env = QProcessEnvironment.systemEnvironment()
        old_path = env.value("PYTHONPATH", "")
        new_path = modules_dir + os.pathsep + old_path if old_path else modules_dir
        env.insert("PYTHONPATH", new_path)
        
        self.process.setWorkingDirectory(project_root)
        self.process.setProcessEnvironment(env)

        # 🚀 3. 启动新进程
        python_path = sys.executable
        self.process.start(python_path, ["-u", file_path])
        
        # 🚀 4. 开启数据拉取定时器
        if hasattr(self, 'pull_timer'):
            self.pull_timer.start()
