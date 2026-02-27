import sys
import os
import json
from PySide6.QtCore import QObject, QProcess, QPropertyAnimation, QEasingCurve, QTimer, Signal, QProcessEnvironment
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication

class ConsoleManager(QObject):
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
        
        self.console_container.setMaximumHeight(0)
        self.console_container.setMinimumHeight(0)

        self.process = QProcess(self) 
        # 🚀 增加标准错误捕获
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.finished.connect(self._on_process_finished)

        self.pull_timer = QTimer(self)
        self.pull_timer.setInterval(16)
        self.pull_timer.timeout.connect(self._pull_output)

    def run_file(self, file_path):
        """统一后的文件运行入口"""
        if self.process and self.process.state() != QProcess.NotRunning:
            try:
                self.process.kill()
                self.process.waitForFinished(100)
            except Exception as e:
                print(f"清理旧进程失败: {e}")

        self.anim_console(show=True)
        self.output.clear()
        self.process_started.emit()

        # 🚀 路径准备
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        ide_root = os.path.dirname(current_file_dir)
        modules_dir = os.path.join(ide_root, "modules")
        file_dir = os.path.dirname(file_path)

        env = QProcessEnvironment.systemEnvironment()
        old_path = env.value("PYTHONPATH", "")
        new_path = modules_dir + os.pathsep + old_path if old_path else modules_dir
        env.insert("PYTHONPATH", new_path)
        
        # 🚀 核心修复：工作目录设为文件所在目录
        self.process.setWorkingDirectory(file_dir) 
        self.process.setProcessEnvironment(env)
        
        python_path = sys.executable
        # 🚀 使用 -u 强制无缓冲输出
        self.process.start(python_path, ["-u", file_path])
        
        if hasattr(self, 'pull_timer'):
            self.pull_timer.start()
            # 🚀 增强：立刻尝试拉取，防止瞬间崩溃被遗漏
            QTimer.singleShot(10, self._pull_output)
            QTimer.singleShot(100, self._pull_output)

        print(f"🚀 Console: 正在运行 -> {file_path}")

    def _pull_output(self):
        """拉取缓冲区数据的核心逻辑"""
        if not self.process: return
        
        # 读取标准输出
        data_out = self.process.readAllStandardOutput().data()
        if data_out:
            text = data_out.decode('utf-8', errors='replace')
            self.append_text(text)

        # 读取标准错误
        data_err = self.process.readAllStandardError().data()
        if data_err:
            text = data_err.decode('utf-8', errors='replace')
            # 🚀 暂时去掉 HTML 标签，直接添加文本
            self.append_text(f"[ERROR] {text}")

    def append_text(self, text):
        """线程安全地将文本添加到 UI (兼容 QPlainTextEdit)"""
        if not text:
            return
            
        # 移动到末尾
        self.output.moveCursor(QTextCursor.End)
        
        # 🚀 兼容性修复：QPlainTextEdit 使用 appendPlainText
        # 如果你想保持简单的格式，直接用这个
        self.output.appendPlainText(text.strip('\r\n'))
        
        # 确保自动滚动
        self.output.moveCursor(QTextCursor.End)

    def handle_stderr(self):
        """处理实时错误输出"""
        self._pull_output()

    def _on_process_finished(self):
        if hasattr(self, 'pull_timer'):
            self.pull_timer.stop()
            
        # 🚀 检查一次是否有残留数据，但不要在死循环被杀后处理太多
        # 我们只做最后一次轻量拉取
        try:
            self._pull_output() 
        except:
            pass
            
        self.process_finished.emit()


    def anim_console(self, show=True):
        """控制台弹出/隐藏动画"""
        start_h = self.console_container.height()
        end_h = self.target_height if show else 0
        
        self.anim = QPropertyAnimation(self.console_container, b"maximumHeight")
        self.anim.setDuration(300)
        self.anim.setStartValue(start_h)
        self.anim.setEndValue(end_h)
        self.anim.setEasingCurve(QEasingCurve.InOutQuart)
        self.anim.valueChanged.connect(self._sync_splitter)
        self.anim.start()

    def _sync_splitter(self):
        h = self.console_container.maximumHeight()
        total_h = self.splitter.height()
        self.splitter.setSizes([max(0, total_h - h), h])