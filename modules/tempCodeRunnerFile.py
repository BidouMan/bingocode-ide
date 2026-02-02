# modules/screen_manager.py

from PySide6.QtWidgets import QWidget
       
from PySide6.QtGui import QPainter, QImage, QColor, QPen, QResizeEvent, QPainterPath,QFont
from PySide6.QtCore import Qt, QPointF, QTimer, Property
import math
from multiprocessing import shared_memory
import numpy as np

class ScreenManager(QWidget):
    def __init__(self, parent_frame):
        super().__init__(parent_frame)
        self.shm = None
        
        # 1. 核心属性
        self.logic_w = 480
        self.logic_h = 360
        self.expected_bytes = self.logic_w*self.logic_h*4 #RGBA站用字节

        # 🚀 修正：必须初始化私有变量，否则 QSS 属性接口会报错
        self._turtle_bg = QColor("#FFFFFF")
        self._arcade_bg = QColor("#1E1E1E")
        self._normal_bg = QColor("#1E1E1E")
        self._bg_color = self._arcade_bg
        self._border_radius = 6
       
        # self.frame_ready = False
        # 2. 渲染时钟
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        
        # 3. 画布初始化 (统一使用 logic 尺寸)
        self.canvas = QImage(self.logic_w, self.logic_h, QImage.Format_ARGB32)
        # self.canvas.fill(self._bg_color)
        

        # --- turtle用 ------
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
        if not self.shm:
            # 尝试静默连接
            try:
                self.shm = shared_memory.SharedMemory(name="arcade_frame")
                print(f"✅ ScreenManager 成功连接共享内存 (Size: {self.shm.size})")
            except:
                return # 还没启动子进程，继续等

        try:
            # 🚀 [核心修复] 容错式切片读取
            # 不管 shm.size 是 307200 还是 311296，我们只取前 expected_bytes 字节
            # buffer=self.shm.buf[:self.expected_bytes] 是解决高清屏崩溃的关键
            raw_frame = np.ndarray(
                (self.logic_h, self.logic_w, 4), 
                dtype=np.uint8, 
                buffer=self.shm.buf[:self.expected_bytes] 
            )

            # 将 NumPy 数据转换为 QImage
            # 注意：Format_RGBA8888 或 Format_ARGB32 取决于 Arcade 的 glReadPixels 顺序
            img = QImage(raw_frame.data, self.logic_w, self.logic_h, QImage.Format_RGBA8888)
            
            # 深度拷贝，防止异步读写导致闪烁
            self.canvas = img.copy()
            self.update() # 触发 paintEvent
            
        except Exception as e:
            # 如果出现严重错误（如子进程关闭），重置连接
            print(f"❌ 渲染解析失败: {e}")
            self.reset_session()

    def paintEvent(self, event):
        """将 logic 画布缩放到当前 widget 的实际大小"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform) # 开启平滑缩放，解决锯齿

        # 绘制背景
        painter.setBrush(self._bg_color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(self.rect(), self._border_radius, self._border_radius)

        # 计算等比例缩放后的区域
        target_rect = self.rect()
        # 将 logic_w/h 的内容画入当前窗口
        painter.drawImage(target_rect, self.canvas)
        painter.end()

    def reset_session(self):
        """重置状态，用于下一次运行"""
        self.timer.stop()
        if self.shm:
            try:
                self.shm.close()
            except: pass
            self.shm = None
        print("🔄 ScreenManager 会话已重置")



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

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)


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