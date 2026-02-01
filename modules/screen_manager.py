# modules/screen_manager.py

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QImage, QColor, QPen, QResizeEvent, QPainterPath
from PySide6.QtCore import Qt, QPointF, QTimer, Property
import math
from multiprocessing import shared_memory

class ScreenManager(QWidget):
    def __init__(self, parent_frame):
        super().__init__(parent_frame)
        self.shm = None
        
        # 1. 核心属性
        self.logic_w = 480
        self.logic_h = 360

        # 🚀 修正：必须初始化私有变量，否则 QSS 属性接口会报错
        self.ARCADE_BG = QColor("#1E1E1E") # 深色
        self.TURTLE_BG = QColor("#F5F5F5") # 浅灰色/白色

        self._border_radius = 6
        self._bg_color = self.ARCADE_BG

        # 2. 渲染时钟
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        
        # 3. 画布初始化 (统一使用 logic 尺寸)
        self.canvas = QImage(self.logic_w, self.logic_h, QImage.Format_ARGB32)
        self.canvas.fill(self._bg_color)
        
        self.current_pos = QPointF(self.logic_w/2, self.logic_h/2)
        self.current_angle = 0  
        self.pen_is_down = True
        self.current_color = QColor("black")
        self.pen_width = 2
        
        self.setObjectName("game_screen")

    def set_logic_size(self, w, h):
        self.logic_w = w
        self.logic_h = h
        if not self.shm:
            self.clear_canvas()

    def update_frame(self):
        try:
            if not self.shm:
                try:
                    self.shm = shared_memory.SharedMemory(name="arcade_frame")
                except FileNotFoundError:
                    return 

            w, h = self.logic_w, self.logic_h
            if self.shm.size < w * h * 4:
                return

            # 🚀 修正：arcade 模式下建议创建一个临时 image，
            # 只有当数据有效时再更新 self.canvas，防止闪烁
            raw_image = QImage(self.shm.buf, w, h, QImage.Format_RGBA8888)
            if not raw_image.isNull():
                # 使用 .copy() 确保从共享内存中脱离出来，防止内存访问冲突
                self.canvas = raw_image.mirrored(False, True).copy()
                self.update()
        except Exception:
            self.shm = None

    def paintEvent(self, event):
        if not hasattr(self, 'canvas') or self.canvas.isNull():
            return
        
        try:
            painter = QPainter(self)
            if not painter.isActive():
                return
                
            painter.setRenderHint(QPainter.Antialiasing)
            # 🚀 关键：如果物理缩放了，开启平滑缩放
            painter.setRenderHint(QPainter.SmoothPixmapTransform)

            path = QPainterPath()
            rect = self.rect()
            if rect.width() <= 0 or rect.height() <= 0:
                painter.end()
                return

            path.addRoundedRect(rect, self._border_radius, self._border_radius)
            
            # # 1. 绘制背景
            # painter.fillPath(path, self._bg_color)

            # 2. 裁切并绘制
            painter.setClipPath(path)
            # 🚀 关键点：将 logic 尺寸的 canvas 自动拉伸填充到当前 QWidget 的物理 rect 中
            painter.drawImage(rect, self.canvas)
            
            painter.end()
        except Exception as e:
            print(f"⚠️ Render Error: {e}")

    # ==========================
    # 🐢 Turtle 模式专属逻辑
    # ==========================
    def draw_instruction(self, instruction):
        try:
            parts = instruction.strip().split('|')
            if len(parts) < 4: return
            
            cmd = parts[2]
            val = parts[3]

            # 🚀 优化：如果正在 Arcade 模式运行，可以选择忽略 Turtle 指令
            if self.shm: return 

            painter = QPainter(self.canvas)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(self.current_color, self.pen_width, Qt.SolidLine, Qt.RoundCap))

            if cmd == "MOVE":
                dist = float(val)
                rad = math.radians(self.current_angle)
                new_x = self.current_pos.x() + dist * math.cos(rad)
                new_y = self.current_pos.y() - dist * math.sin(rad)
                new_pos = QPointF(new_x, new_y)
                if self.pen_is_down:
                    painter.drawLine(self.current_pos, new_pos)
                self.current_pos = new_pos
            elif cmd == "LEFT":
                self.current_angle += float(val)
            elif cmd == "RIGHT":
                self.current_angle -= float(val)
            elif cmd == "COLOR":
                c = QColor(val)
                if c.isValid(): self.current_color = c
            elif cmd == "PEN":
                self.pen_is_down = (val == "DOWN")

            painter.end()
            self.update() 
            
        except Exception as e:
            print(f"🎨 Turtle 指令失败: {e}")

    def clear_canvas(self):
        self.canvas = QImage(self.logic_w, self.logic_h, QImage.Format_ARGB32)
        self.canvas.fill(self._bg_color)
        self.current_pos = QPointF(self.logic_w / 2, self.logic_h / 2)
        self.current_angle = 0
        self.update()

    def reset_session(self):
        self.timer.stop()
        if self.shm:
            try: self.shm.close()
            except: pass
        self.shm = None

    # 🚀 优化建议：resizeEvent 其实不需要重新创建 self.canvas
    # 因为 self.canvas 是 logic 尺寸，它是固定的（如 320x240）。
    # QWidget 的缩放通过 paintEvent 里的 drawImage(rect, canvas) 自动完成。
    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)

    # ---------- QSS属性 ----------
    @Property(int)
    def borderRadius(self): return self._border_radius

    @borderRadius.setter
    def borderRadius(self, r):
        self._border_radius = r
        self.update()

    @Property(QColor)
    def bg(self): return self._bg_color

    @bg.setter
    def bg(self, color):
        if self._bg_color != color:
            self._bg_color = color
            # 🚀 核心逻辑：直接同步填充给 canvas
            if hasattr(self, 'canvas') and not self.canvas.isNull():
                self.canvas.fill(self._bg_color)
            self.update()