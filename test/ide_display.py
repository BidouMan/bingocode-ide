import sys
import json
import os
from PySide6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsRectItem
from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QBrush, QColor, QPainter

class MiniIDE(QGraphicsView):
    def __init__(self):
        super().__init__()
        
        # 1. 窗口基本设置
        self.win_w, self.win_h = 400, 400
        self.setWindowTitle("Bingo IDE - 引擎分离渲染测试")
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 2. 场景初始化
        self.scene = QGraphicsScene(0, 0, self.win_w, self.win_h)
        self.setScene(self.scene)
        
        # 3. 创建 UI 元素
        self.ball = QGraphicsEllipseItem(0, 0, 30, 30)
        self.ball.setBrush(QBrush(QColor("#3498db")))
        self.ball.setPen(Qt.NoPen)
        self.scene.addItem(self.ball)
        
        self.ground = QGraphicsRectItem(0, 340, 400, 20)
        self.ground.setBrush(QBrush(QColor("#27ae60")))
        self.ground.setPen(Qt.NoPen)
        self.scene.addItem(self.ground)

        # 4. 🚀 核心：先定义 process 对象，再执行启动逻辑
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.handle_output)
        self.process.readyReadStandardError.connect(self.handle_error)

        # 5. 路径处理：自动定位 physics_worker.py
        current_dir = os.path.dirname(os.path.abspath(__file__))
        worker_path = os.path.join(current_dir, "physics_worker.py")

        if os.path.exists(worker_path):
            print(f"💡 启动物理子进程: {worker_path}")
            self.process.start(sys.executable, [worker_path])
        else:
            print(f"❌ 找不到文件: {worker_path}")

    def handle_output(self):
        """处理子进程的坐标数据"""
        while self.process.canReadLine():
            line = self.process.readLine().data().decode().strip()
            if line.startswith("DATA:"):
                try:
                    data = json.loads(line[5:])
                    # Arcade 坐标 (左下) -> Qt 坐标 (左上)
                    # Arcade 的 center_x 是圆心，Qt 的 setPos 是左上角
                    qt_x = data['x'] - 15
                    qt_y = self.win_h - data['y'] - 15
                    self.ball.setPos(qt_x, qt_y)
                except:
                    pass

    def handle_error(self):
        """处理子进程报错"""
        err = self.process.readAllStandardError().data().decode()
        print(f"⚠️ 子进程报错: {err}")

    def closeEvent(self, event):
        """窗口关闭时强制结束子进程"""
        if self.process.state() == QProcess.ProcessState.Running:
            self.process.kill()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    view = MiniIDE()
    view.setFixedSize(420, 420)
    view.show()
    sys.exit(app.exec())