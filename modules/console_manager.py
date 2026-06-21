import sys
import os
from PySide6.QtCore import QObject, QProcess, Qt, QTimer, Signal, QProcessEnvironment
from PySide6.QtGui import QTextCursor, QFont
from PySide6.QtWidgets import QPlainTextEdit


class TerminalWidget(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self._input_mode = False
        self._input_callback = None

        font = QFont("JetBrains Mono", 12)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)

    def set_input_mode(self, enabled, callback=None):
        self._input_mode = enabled
        self._input_callback = callback
        self.setReadOnly(not enabled)
        if enabled:
            self.moveCursor(QTextCursor.End)
            self.setFocus()

    def keyPressEvent(self, event):
        if not self._input_mode:
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.setTextCursor(cursor)
            line = self.toPlainText().split("\n")[-1]
            self.appendPlainText("")
            self.setReadOnly(True)
            self._input_mode = False
            if self._input_callback:
                self._input_callback(line)
            return
        if event.key() == Qt.Key.Key_Backspace:
            cursor = self.textCursor()
            if cursor.positionInBlock() > 0:
                super().keyPressEvent(event)
            return
        if event.text() and event.key() not in (
            Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Shift, Qt.Key.Key_Meta
        ):
            super().keyPressEvent(event)


class ConsoleManager(QObject):
    process_started = Signal()
    process_finished = Signal()
    instruction_received = Signal(str)

    MAX_LINES = 5000
    FLUSH_INTERVAL_MS = 30

    def __init__(self, splitter, console_output, container=None):
        super().__init__()
        self.splitter = splitter
        self.output = console_output
        self.console_container = container if container else self.output
        self.target_height = 240

        self.console_container.setMaximumHeight(0)
        self.console_container.setMinimumHeight(0)

        self.process = QProcess(self)
        self.process.readyReadStandardError.connect(self._handle_stderr)
        self.process.readyReadStandardOutput.connect(self._on_stdout_ready)
        self.process.finished.connect(self._on_process_finished)

        self._pending_text = ""
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(self.FLUSH_INTERVAL_MS)
        self._flush_timer.timeout.connect(self._flush)

    def run_file(self, file_path):
        if self.process and self.process.state() != QProcess.NotRunning:
            try:
                self.process.kill()
                self.process.waitForFinished(100)
            except:
                pass

        self.anim_console(show=True)
        self.output.clear()
        self.output.set_input_mode(False)
        self._pending_text = ""
        self.process_started.emit()

        current_file_dir = os.path.dirname(os.path.abspath(__file__))
        ide_root = os.path.dirname(current_file_dir)
        modules_dir = os.path.join(ide_root, "modules")
        file_dir = os.path.dirname(file_path)

        env = QProcessEnvironment.systemEnvironment()
        old_path = env.value("PYTHONPATH", "")
        new_path = modules_dir + os.pathsep + old_path if old_path else modules_dir
        env.insert("PYTHONPATH", new_path)

        self.process.setWorkingDirectory(file_dir)
        self.process.setProcessEnvironment(env)

        with open(file_path, "r", encoding="utf-8") as f:
            user_code = f.read()
        injected = (
            "import sys, builtins\n"
            "def _bingo_input(prompt=''):\n"
            "    if prompt:\n"
            "        sys.stdout.write(str(prompt))\n"
            "        sys.stdout.flush()\n"
            "    sys.stdout.write('__BINGO_WAITING_INPUT__')\n"
            "    sys.stdout.flush()\n"
            "    line = sys.stdin.readline()\n"
            "    return line.rstrip(chr(10)) if line else ''\n"
            "builtins.input = _bingo_input\n"
            + user_code
        )
        temp_path = os.path.join(file_dir, ".bingo_run.py")
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except:
            pass
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(injected)
        except Exception as e:
            self._raw_append(f"❌ 无法创建临时文件: {e}\n")
            return
        self.process.start(sys.executable, ["-u", temp_path])

    def _on_stdout_ready(self):
        if not self.process:
            return
        data = self.process.readAllStandardOutput().data()
        if not data:
            return
        self._pending_text += data.decode("utf-8", errors="replace")
        if not self._flush_timer.isActive():
            self._flush_timer.start()

    def _flush(self):
        if not self._pending_text:
            self._flush_timer.stop()
            return

        text = self._pending_text
        self._pending_text = ""

        waiting = "__BINGO_WAITING_INPUT__" in text
        text = text.replace("__BINGO_WAITING_INPUT__", "")

        lines = []
        for line in text.split("\n"):
            if not line:
                continue
            stripped = line.strip()
            if stripped.startswith('{"type":') and stripped.endswith("}"):
                self.instruction_received.emit(stripped)
            else:
                lines.append(line)

        if lines:
            self._raw_append("\n".join(lines) + "\n")

        if waiting:
            self.output.set_input_mode(True, callback=self._on_user_input)

    def _raw_append(self, text):
        if not text:
            return
        self.output.setUpdatesEnabled(False)
        cursor = self.output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.output.setTextCursor(cursor)
        self.output.setUpdatesEnabled(True)
        self._trim_lines()

    def _trim_lines(self):
        count = self.output.document().blockCount()
        if count > self.MAX_LINES:
            cursor = self.output.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.movePosition(
                QTextCursor.MoveOperation.Down,
                QTextCursor.MoveMode.KeepAnchor,
                count - self.MAX_LINES,
            )
            cursor.removeSelectedText()

    def _handle_stderr(self):
        data = self.process.readAllStandardError().data()
        if data:
            self._raw_append("❌ " + data.decode("utf-8", errors="replace"))

    def _on_process_finished(self):
        try:
            data = self.process.readAllStandardOutput().data()
            if data:
                self._pending_text += data.decode("utf-8", errors="replace")
        except:
            pass
        self._flush()
        try:
            temp_path = os.path.join(self.process.workingDirectory(), ".bingo_run.py")
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except:
            pass
        self.output.set_input_mode(False)
        self.process_finished.emit()

    def _on_user_input(self, text):
        if self.process and self.process.state() == QProcess.Running:
            self.process.write((text + "\n").encode("utf-8"))

    def anim_console(self, show=True):
        if show:
            self.console_container.setMaximumHeight(16777215)
            self.console_container.setMinimumHeight(0)
            sizes = self.splitter.sizes()
            total = sum(sizes)
            console_h = min(self.target_height, total // 2)
            code_h = total - console_h
            self.splitter.setSizes([code_h, console_h])
        else:
            sizes = self.splitter.sizes()
            self.splitter.setSizes([sizes[0] + sizes[1], 0])
            self.console_container.setMaximumHeight(0)
