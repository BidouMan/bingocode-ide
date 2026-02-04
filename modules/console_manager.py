import sys
import os
import json
from PySide6.QtCore import QObject, QProcess, QPropertyAnimation, QEasingCurve, QTimer, Signal, QProcessEnvironment
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication

class ConsoleManager(QObject):
    # 状态信号：供 AppController 监听以改变按钮样式
    process_started = Signal()
    process_finished = Signal()
    # 指令信号：传递 BINGO: 开头的 JSON 字符串
    draw_signal = Signal(str)

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

        # 初始化进程
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self._on_process_finished)

    def _on_process_finished(self):
        """进程自然结束或被杀死后的回调"""
        self.process_finished.emit()

    def run_script(self, file_path):
        """主入口：启动脚本并显示控制台"""
        if not file_path: return
            
        self.output.clear()
        # 强制刷新 UI，确保“启动中”等提示能立刻显示
        QApplication.processEvents()

        # 如果控制台没打开，先播动画打开它
        current_h = self.console_container.height()
        if current_h < 10:
            self.anim_console(show=True)
            QTimer.singleShot(200, lambda: self._start_process(file_path))
        else:
            self._start_process(file_path)

    def _start_process(self, file_path):
        """真正的进程启动逻辑"""
        env = QProcessEnvironment.systemEnvironment()
        
        # 🚀 注入你的 internal_lib 路径，确保学生代码能 import bingo
        # 假设你的库放在项目根目录下的 modules/internal_lib
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        lib_path = os.path.join(base_dir, "modules", "internal_lib")
        
        old_pp = env.value("PYTHONPATH", "")
        new_pp = f"{lib_path}{os.pathsep}{old_pp}" if old_pp else lib_path
        env.insert("PYTHONPATH", new_pp)
        
        # 解决 macOS 上的某些 UI 警告
        if sys.platform == "darwin":
            env.insert("ApplePersistenceIgnoreState", "YES")

        self.process.setProcessEnvironment(env)
        # 直接使用系统 Python 解释器运行
        self.process.start(sys.executable, [file_path])
        self.process_started.emit()

    def handle_stdout(self):
        """核心：分拣输出信息"""
        raw_data = self.process.readAllStandardOutput().data().decode("utf-8")
        lines = raw_data.splitlines()
        
        for line in lines:
            # 🚀 识别指令：不再用旧的 |DRAW|，统一使用 BINGO: 开头的 JSON
            if line.startswith("BINGO:"):
                # 去掉前缀，发送纯 JSON 字符串
                self.draw_signal.emit(line[6:].strip())
            else:
                # 普通 print 输出到控制台
                self.output.appendPlainText(line)
                self.output.moveCursor(QTextCursor.End)

    def stop_script(self):
        """强杀进程，不再需要清理共享内存"""
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill() 
            self.process.waitForFinished(300)
        
        # 关闭控制台面板
        self.anim_console(show=False)

    def handle_stderr(self):
        data = self.process.readAllStandardError().data().decode("utf-8")
        if data.strip():
            self.output.appendPlainText(f"❌ Error:\n{data}")
            self.output.moveCursor(QTextCursor.End)

    # --- 动画逻辑 (保持不变，用于抽屉式控制台) ---
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
        self.splitter.setSizes([max(0, total_h - h), h])