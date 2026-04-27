import sys
import os
import json
from PySide6.QtCore import QObject, QProcess, QPropertyAnimation, QEasingCurve, QTimer, Signal, QProcessEnvironment
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication

class ConsoleManager(QObject):
    process_started = Signal()
    process_finished = Signal()
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
        self.process.readyReadStandardError.connect(self.handle_stderr)
        self.process.readyReadStandardOutput.connect(self._pull_output)
        self.process.finished.connect(self._on_process_finished)

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
        self.process.start(python_path, ["-u", file_path])

    def _pull_output(self):
        if not self.process: return
        
        # 只处理 Stdout 的分流逻辑
        while self.process.canReadLine():
            line_raw = self.process.readLine().data().decode('utf-8', errors='replace')
            line = line_raw.strip()
            if not line: continue

            if line.startswith('{"type":') and line.endswith('}'):
                # 🚀 删除了 DEBUG 打印，直接发送信号
                self.instruction_received.emit(line)
            else:
                self.append_text(line_raw)

    def append_text(self, text):
        """线程安全地将文本添加到 UI (兼容 QPlainTextEdit)"""
        if not text:
            return
            
        # 移动到末尾
        self.output.moveCursor(QTextCursor.End)
        
        # 🚀 兼容性修复：QPlainTextEdit 使用 appendPlainText
        self.output.appendPlainText(text.strip('\r\n'))
        
        # 确保自动滚动
        self.output.moveCursor(QTextCursor.End)

    def handle_stderr(self):
        """专门处理错误流，避免 Stdout 和 Stderr 混淆"""
        data_err = self.process.readAllStandardError().data()
        if data_err:
            text = data_err.decode('utf-8', errors='replace')
            # 🚀 保持错误信息在控制台的醒目显示
            self.append_text(f"❌ [ERROR] {text}")

    def _on_process_finished(self):
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