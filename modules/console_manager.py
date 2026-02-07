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

        # 🚀 修正核心：先实例化对象，再连接信号
        self.process = QProcess(self) 
        
        # 🚀 关键：只保留这两个核心连接，删除所有其他的重复绑定
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
        """内部私有方法：负责配置环境并启动进程"""
        # 1. 动态计算项目根目录和 modules 目录
        # 假设 ConsoleManager.py 在项目根目录/modules/ 下
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_file_dir)
        modules_dir = os.path.join(project_root, "modules")

        # 2. 配置子进程环境变量
        env = QProcessEnvironment.systemEnvironment()
        
        # 获取现有的 PYTHONPATH
        old_pythonpath = env.value("PYTHONPATH", "")
        
        # 统一变量名为 new_pythonpath，确保包含 modules 目录
        if old_pythonpath:
            new_pythonpath = modules_dir + os.pathsep + old_pythonpath
        else:
            new_pythonpath = modules_dir
            
        # 将合成好的路径插入环境变量
        env.insert("PYTHONPATH", new_pythonpath)

        # 3. 启动进程
        # 注意：不要在这里重新 new QProcess，也不要在这里绑定 readAll 的 lambda 打印
        if hasattr(self, 'process') and self.process:
            self.process.setProcessEnvironment(env)
            
            # 🚀 核心修改：不直接运行 file_path，而是运行一段包装代码
            # 这段包装代码先执行 import，再执行用户的文件内容
            wrapper_code = (
                "import sys; "
                "from bingo_engine import *; "
                f"exec(open(r'{file_path}', encoding='utf-8').read(), globals())"
            )
            
            # 使用 -c 执行包装命令
            self.process.start(sys.executable, ["-u", "-c", wrapper_code])
                
        # 发送进程已启动信号，供 UI 改变按钮状态（如变红/禁用）
        if hasattr(self, 'process_started'):
            self.process_started.emit()

    def _internal_handle_output(self):
        """内部处理：负责清洗数据，不让脏数据流向外面"""
        raw_data = self.process.readAllStandardOutput().data().decode('utf-8')
        
        # 仍然可以保留原本打印到 UI 的功能
        # self.output.append(raw_data) 

        # 🚀 协议解析逻辑搬到这里
        for line in raw_data.strip().split('\n'):
            line = line.strip()
            if line.startswith("BINGO:"):
                self.instruction_received.emit(line.replace("BINGO:", "", 1))
            elif line.startswith('{'):
                self.instruction_received.emit(line)

    def handle_stdout(self):
        """🚀 全局唯一的读取入口：负责分发数据"""
        raw_data = self.process.readAllStandardOutput().data().decode("utf-8")
        if not raw_data: return

        lines = raw_data.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line: continue

            # 🚀 2. 识别并分发指令
            is_instruction = False
            json_content = ""

            if line.startswith("BINGO:"):
                json_content = line.replace("BINGO:", "", 1)
                is_instruction = True
            elif line.startswith('{') and line.endswith('}'):
                json_content = line
                is_instruction = True

            # 🚀 3. 根据类型分流
            if is_instruction:
                # 如果是指令，悄悄发给渲染器，不打印在 UI 上
                self.instruction_received.emit(json_content)
            else:
                # 如果是普通 print，才显示在 IDE 控制台 UI 上
                self.output.appendPlainText(line)
                self.output.moveCursor(QTextCursor.End)

    def stop_script(self):
        """强杀进程，不再需要清理共享内存"""
        if self.process.state() != QProcess.ProcessState.NotRunning:
            self.process.kill() 
            self.process.waitForFinished(300)
        
        # 关闭控制台面板
        self.anim_console(show=False)

        
    def run_code_string(self, code):
        """🚀 核心新方法：通过标准输入运行代码字符串"""
        self.output.clear()
        self.anim_console(show=True)
        self.process_started.emit()

        # 配置环境路径，确保能找到 bingo_engine
        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_file_dir)
        modules_dir = os.path.join(project_root, "modules")

        env = QProcessEnvironment.systemEnvironment()
        old_path = env.value("PYTHONPATH", "")
        env.insert("PYTHONPATH", modules_dir + os.pathsep + old_path if old_path else modules_dir)
        self.process.setProcessEnvironment(env)

        # 🚀 使用 "-" 告诉 Python 从 stdin 读取代码，不再需要文件路径
        # -u 保证输出是实时刷新的
        self.process.start(sys.executable, ["-u", "-"])
        
        # 🚀 将代码写入标准输入流
        self.process.write(code.encode("utf-8"))
        # 必须关闭写入通道，Python 才会开始执行接收到的代码
        self.process.closeWriteChannel()

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