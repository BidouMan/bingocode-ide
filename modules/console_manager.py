import sys,os
from PySide6.QtCore import QObject, QProcess, QPropertyAnimation, QEasingCurve, QTimer, Signal,QProcessEnvironment
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication

class ConsoleManager(QObject):
    # 定义状态信号，供 AppController 监听以改变按钮样式
    process_started = Signal()
    process_finished = Signal()
    # 新增：定义绘图信号，传递指令字符串
    draw_signal = Signal(str)

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


    def _start_process(self, file_path, screen_width=480, screen_height=360):
        # ... 前面清理进程的代码 ...
        env = QProcessEnvironment.systemEnvironment()
        
        # 获取 internal_lib 的绝对路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        lib_path = os.path.join(current_dir, "internal_lib")
        
        # 🚀 调试打印：核对这个路径在不在你的访达(Finder)里真实存在
        print(f"DEBUG [主进程]: 正在尝试注入的目录是: {lib_path}")
        if not os.path.exists(os.path.join(lib_path, "arcade_shell.py")):
            print(f"❌ 严重警告: 在 {lib_path} 下没找到 arcade_shell.py!")

        # 强制注入
        old_pp = env.value("PYTHONPATH", "")
        env.insert("PYTHONPATH", f"{lib_path}{os.pathsep}{old_pp}" if old_pp else lib_path)
        
        # 🚀 绝招：告诉 Python 不要从当前脚本目录先找，确保先走 PYTHONPATH
        env.insert("PYTHON_PATH_FORCE", "1") 

        self.process.setProcessEnvironment(env)
        self.process.start(sys.executable, ["-u", file_path])



    def handle_stdout(self):
        # 1. 读取原始字节数据并解码
        raw_data = self.process.readAllStandardOutput().data().decode("utf-8")
        
        # 2. 按行拆分处理，因为指令是以行为单位的
        lines = raw_data.splitlines()
        normal_output = []

        for line in lines:
            if line.startswith("|DRAW|"):
                # 触发绘图信号
                self.draw_signal.emit(line)
            else:
                normal_output.append(line)

        # 3. 将非指令的普通输出显示到控制台
        if normal_output:
            self.output.appendPlainText("\n".join(normal_output))
            self.output.moveCursor(QTextCursor.End)

    def anim_console(self, show=True, duration=250):
        """带 Splitter 同步的动画"""
        if self.anim:
            self.anim.stop()
            
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

    def run_script(self, file_path, w=480, h=360): # 🚀 修改：接收 w, h 参数
        if not file_path: 
            return
            
        # 1. 清理控制台输出
        self.output.clear()
        
        # 2. 🚀 关键改进：无论如何，启动前先彻底杀掉旧进程
        # 这能保证资源释放，并给 UI 留出切换背景的时间
        # self.stop_script()
        
        # 3. 🚀 核心黑科技：强制刷新 UI 事件循环
        # 这行代码会告诉 Qt：“先别管后面的代码，把刚才 handle_run_python 里的 show_status_text 给我画出来！”
        QApplication.processEvents()

        # 环境准备
        env = QProcessEnvironment.systemEnvironment()
        if sys.platform == "darwin":
            env.insert("ApplePersistenceIgnoreState", "YES")
        self.process.setProcessEnvironment(env)

        # 判断高度，决定是否播动画
        current_h = self.console_container.height()
        
        if current_h > 200:
            # 🚀 即使不播动画，也加一个极其微小的延迟 (10ms) 
            # 这样能让用户看到背景切换的瞬间，体验更稳
            QTimer.singleShot(10, lambda: self._start_process(file_path, w, h))
        else:
            self.anim_console(show=True, duration=250)
            QTimer.singleShot(100, lambda: self._start_process(file_path, w, h))




    def stop_script(self):
        """立即强杀进程，并清理系统资源"""
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill() 
            self.process.waitForFinished(100)

        
        # 🚀 补充：主动触发一次清理脚本
        # 确保在停止时，系统级的共享内存句柄被真正释放
        cleanup_script = (
            "from multiprocessing import shared_memory; "
            "try: "
            "shm = shared_memory.SharedMemory(name='arcade_frame'); "
            "shm.close(); shm.unlink(); "
            "except: pass"
            "os._exit(0)"
        )
        cleanup_proc = QProcess()
        cleanup_proc.start(sys.executable, ["-c", cleanup_script])
        cleanup_proc.waitForFinished(500)

        self.anim_console(show=False)

    def handle_stderr(self):
        data = self.process.readAllStandardError().data().decode("utf-8")
        self.output.appendPlainText(f"\n❌ Error:\n{data}")
        self.output.moveCursor(QTextCursor.End)

    # 在处理 stdout 的函数里增加判断
    def handle_output(self, text):
        if text.startswith("|DRAW|"):
            # 提取指令并发送给 ScreenManager
            # 例如: "|DRAW|MOVE|100" -> 发送信号 ("MOVE", 100)
            self.draw_signal.emit(text)
        else:
            # 正常的 print 输出显示到控制台
            self.append_to_console(text)