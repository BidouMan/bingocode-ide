# modules/screen_manager.py

from PySide6.QtWidgets import QWidget
       
from PySide6.QtGui import QPainter, QImage, QColor, QPen, QResizeEvent, QPainterPath,QFont
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
        self._turtle_bg = QColor("#FFFFFF")
        self._arcade_bg = QColor("#1E1E1E")
        self._normal_bg = QColor("#1E1E1E")
        self._bg_color = self._arcade_bg
        self._border_radius = 6
       
        self.frame_ready = False
        # 2. 渲染时钟
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        
        # 3. 画布初始化 (统一使用 logic 尺寸)
        self.canvas = QImage(self.logic_w, self.logic_h, QImage.Format_ARGB32)
        # self.canvas.fill(self._bg_color)
        
        self.current_pos = QPointF(self.logic_w/2, self.logic_h/2)
        self.current_angle = 0  
        self.pen_is_down = True
        self.current_color = QColor("black")
        self.pen_width = 2
        self.first_instruction = True # 🚀 新增：标记是否为第一条指令
        
        self.setObjectName("game_screen")

    def set_render_mode(self, mode="arcade"):
        # 根据模式选择目标颜色
        if mode == "turtle":
            target_color = self._turtle_bg
        elif mode == "arcade":
            target_color = self._arcade_bg
        else:
            target_color = self._normal_bg
        
        # 1. 更新内部颜色变量 (直接赋值，避开 setter 的 fill 逻辑或重复判断)
        self._bg_color = QColor(target_color)
        
        # 2. 🚀 关键：既然模式切换了，必须立刻把当前画布刷成对应的底色
        if hasattr(self, 'canvas') and not self.canvas.isNull():
            self.canvas.fill(self._bg_color)
            self.update()
            # print(f"DEBUG: 模式切换为 {mode}，画布已刷色: {self._bg_color.name()}")

    def set_logic_size(self, w, h):
        if self.logic_w == w and self.logic_h == h:
            return
        self.logic_w = w
        self.logic_h = h
        
        # 🚀 重新创建画布时，确保填充的是当前的模式背景色
        self.canvas = QImage(self.logic_w, self.logic_h, QImage.Format_ARGB32)
        self.canvas.fill(self._bg_color) 
        self.update()

    def update_frame(self):
        # 🚀 新增：如果进程还没启动完，绝对不准碰画布
        if getattr(self, 'is_locked', False):
            return
        try:
            if not self.shm:
                try:
                    # 尝试连接共享内存
                    self.shm = shared_memory.SharedMemory(name="arcade_frame")
                    # 🚀 关键：连接上的瞬间，先不准画，等下一轮
                    self.frame_ready = False 
                    return 
                except FileNotFoundError:
                    return 

            # 🚀 只有第二次进入且 shm 已存在时，才认为新进程的数据可能到了
            if not self.frame_ready:
                self.frame_ready = True
                return

            w, h = self.logic_w, self.logic_h
            raw_image = QImage(self.shm.buf, w, h, QImage.Format_RGBA8888)
            
            if not raw_image.isNull():
                # 只有拿到有效图像才覆盖
                self.canvas = raw_image.mirrored(False, True) 
                self.update()
        except Exception:
            self.shm = None
            self.frame_ready = False

    def paintEvent(self, event):
        print("DEBUG: 正在执行 paintEvent 重绘屏幕")
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
        # 1. 前置性能检查：如果是 Arcade 模式，直接无视 Turtle 信号
        if self.shm: 
            return 

        try:
            # 2. 快速拆分
            parts = instruction.strip().split('|')
            if len(parts) < 4: 
                return
            
            cmd = parts[2]
            val = parts[3]

            # 3. 绘图逻辑
            painter = QPainter(self.canvas)
            painter.setRenderHint(QPainter.Antialiasing)
            # 使用预设好的笔刷属性
            painter.setPen(QPen(self.current_color, self.pen_width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))

            if cmd == "MOVE":
                dist = float(val)
                if dist != 0: # 性能优化：位移为0时不处理
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
                # 统一为加法处理，角度逻辑由子进程计算好
                self.current_angle -= float(val)
                
            elif cmd == "COLOR":
                c = QColor(val)
                if c.isValid(): 
                    self.current_color = c
                    
            elif cmd == "PEN":
                self.pen_is_down = (val == "DOWN")

            painter.end()
            self.update() 
            
        except Exception as e:
            # 这里的 print 建议只在 debug 模式开启，避免阻塞渲染
            pass

    def clear_canvas(self):
        """清空画布并显示启动反馈"""
        self.canvas = QImage(self.logic_w, self.logic_h, QImage.Format_ARGB32)
        self.canvas.fill(self._bg_color)
        
        # 🚀 在画布上绘制 Loading 文字
        painter = QPainter(self.canvas)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 自动适配文字颜色：深色背景用灰色，浅色用深灰
        text_color = QColor("#888888") if self._bg_color.lightness() > 128 else QColor("#AAAAAA")
        painter.setPen(text_color)
        
        font = painter.font()
        font.setFamily("Microsoft YaHei") # 确保中文字体显示
        font.setPointSize(12)
        painter.setFont(font)
        
        # 在画布中心绘制
        painter.drawText(self.canvas.rect(), Qt.AlignCenter, "🚀 程序启动中...")
        painter.end()

        # 重置 Turtle 状态坐标
        self.current_pos = QPointF(self.logic_w / 2, self.logic_h / 2)
        self.current_angle = 0
        self.update()

    def clear_to_empty(self):
        """还原为纯净背景，不带任何文字"""
        if hasattr(self, 'canvas') and not self.canvas.isNull():
            self.canvas.fill(self._bg_color)
            self.update()

    def show_status_text(self, text):
        print(f"DEBUG: show_status_text 开始画字: {text}") # 👈 加这行
        self.canvas.fill(self._bg_color)
        painter = QPainter(self.canvas)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 稍微淡一点的灰色，看起来不刺眼
        painter.setPen(QColor("#666666"))
        
        font = painter.font()
        font.setFamily("HarmonyOS Sans SC")
        font.setPointSize(14) # 稍微小一点，显得精致
        font.setWeight(QFont.Medium)
        painter.setFont(font)
        
        painter.drawText(self.canvas.rect(), Qt.AlignCenter, text)
        painter.end()
        self.update()

    def reset_session(self):
        self.timer.stop()
        if self.shm:
            try: 
                self.shm.close()
                # self.shm.unlink()
            except: pass
            self.shm = None
        self.first_instruction = True


    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)

    # ---------- QSS 属性接口 ----------
    @Property(int)
    def borderRadius(self): return self._border_radius
    @borderRadius.setter
    def borderRadius(self, r): self._border_radius = r

    @Property(QColor)
    def turtle_bg(self): return self._turtle_bg
    @turtle_bg.setter
    def turtle_bg(self, color): 
        self._turtle_bg = QColor(color)

    @Property(QColor)
    def arcade_bg(self): return self._arcade_bg
    @arcade_bg.setter
    def arcade_bg(self, color): 
        self._arcade_bg = QColor(color)

    @Property(QColor)
    def normal_bg(self): return self._normal_bg
    @normal_bg.setter
    def normal_bg(self, color): self._normal_bg = QColor(color)

    @Property(QColor)
    def bg(self): return self._bg_color
    
    @bg.setter
    @bg.setter
    def bg(self, color):
        new_color = QColor(color)
        if self._bg_color != new_color:  # 👈 问题出在这里
            self._bg_color = new_color
            if hasattr(self, 'canvas') and not self.canvas.isNull():
                self.canvas.fill(self._bg_color) 
            self.update()