import sys
from PySide6.QtCore import QObject, QProcess, QPropertyAnimation, QEasingCurve, QTimer, Signal
from PySide6.QtGui import QTextCursor

class ConsoleManager(QObject):
    # 定义状态信号，供 AppController 监听以改变按钮样式
    process_started = Signal()
    process_finished = Signal()

    def __init__(self, splitter, console_output):
        super().__init__()
        self.splitter = splitter
        self.output = console_output
        self.console_container = self.output
        self.anim = None 
        self.target_height = 240 
        
        # 初始状态隐藏
        self.console_container.setMaximumHeight(0)
        self.console_container.setMinimumHeight(0)

        # 初始化进程
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.handle_stdout)
        self.process.readyReadStandardError.connect(self.handle_stderr)
        
        # 监听进程结束，用于重置按钮状态
        self.process.finished.connect(self._on_process_finished)

    def _on_process_finished(self):
        """进程自然结束或被杀死后的回调"""
        self.process_finished.emit()

    def _start_process(self, file_path):
        """内部启动逻辑"""
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill()
            self.process.waitForFinished(300)
            
        self.process.start(sys.executable, ["-u", file_path])
        self.process_started.emit() # 发送开始信号

    def handle_stdout(self):
        """
        优化后的输出处理：
        解决卡顿的关键：读取所有可用数据一次性插入，而不是每行插入一次。
        """
        # 读取当前缓冲区的所有数据
        data = self.process.readAllStandardOutput().data().decode("utf-8")
        
        # 限制文本框最大长度，防止死循环跑太久撑爆内存
        if self.output.blockCount() > 5000:
            self.output.clear()
            
        # 插入数据并滚动
        self.output.appendPlainText(data)
        self.output.moveCursor(QTextCursor.End)

    def anim_console(self, show=True, duration=250):
        """带 Splitter 同步的动画"""
        if self.anim:
            self.anim.stop()
            try: self.anim.valueChanged.disconnect()
            except: pass
            try: self.anim.finished.disconnect()
            except: pass

        if show:
            self.console_container.setMaximumHeight(16777215)

        end_height = self.target_height if show else 0
        current_h = self.console_container.height()

        if abs(current_h - end_height) < 2:
            if not show: self._finalize_hide()
            return

        self.anim = QPropertyAnimation(self.console_container, b"maximumHeight")
        self.anim.setDuration(duration)
        self.anim.setStartValue(current_h)
        self.anim.setEndValue(end_height)
        self.anim.setEasingCurve(QEasingCurve.OutCubic if show else QEasingCurve.OutQuint)

        self.anim.valueChanged.connect(self._sync_splitter_sizes)
        
        if show:
            self.anim.finished.connect(lambda: self.console_container.setMaximumHeight(16777215))
        else:
            self.anim.finished.connect(self._finalize_hide)

        self.anim.start()

    def _finalize_hide(self):
        self.console_container.setMaximumHeight(0)
        self.splitter.setSizes([self.splitter.height(), 0])

    def _sync_splitter_sizes(self):
        h = self.console_container.maximumHeight()
        total_h = self.splitter.height()
        self.splitter.setSizes([max(0, total_h - h), h])

    def run_script(self, file_path):
        if not file_path: return
        self.output.clear()
        
        if self.console_container.height() > 50:
            self._start_process(file_path)
        else:
            self.anim_console(show=True, duration=250)
            QTimer.singleShot(80, lambda: self._start_process(file_path))

    def stop_script(self):
        """点击停止时，进程结束会自动通过信号重置按钮"""
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.terminate()
            if not self.process.waitForFinished(500):
                self.process.kill()
        self.anim_console(show=False)

    def handle_stderr(self):
        data = self.process.readAllStandardError().data().decode("utf-8")
        self.output.appendPlainText(f"\n❌ Error:\n{data}")
        self.output.moveCursor(QTextCursor.End)