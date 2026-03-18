import math
from PySide6.QtGui import QPixmap, QPainter, QColor, QBrush, QPalette
from PySide6.QtCore import Qt, QRectF

class CheckerboardManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CheckerboardManager, cls).__new__(cls)
            cls._instance._init_manager()
        return cls._instance

    def _init_manager(self):
        """初始化预设颜色和缓存"""
        self.themes = {
            "light": {"c1": QColor("#FFFFFF"), "c2": QColor("#DCDCDC")},
            "dark":  {"c1": QColor("#2B2B2B"), "c2": QColor("#333333")}
        }
        self.grid_size = 16  # 基准格子尺寸
        self._brush_cache = {}

    def get_brush(self, theme="light"):
        """获取用于普通 Widget 的静态平铺画刷"""
        if theme in self._brush_cache:
            return self._brush_cache[theme]

        colors = self.themes.get(theme, self.themes["light"])
        s = self.grid_size
        
        # 创建 2x2 的格点纹理
        pix = QPixmap(s * 2, s * 2)
        painter = QPainter(pix)
        painter.setPen(Qt.PenStyle.NoPen)
        
        painter.fillRect(0, 0, s, s, colors["c1"])
        painter.fillRect(s, s, s, s, colors["c1"])
        painter.fillRect(s, 0, s, s, colors["c2"])
        painter.fillRect(0, s, s, s, colors["c2"])
        painter.end()

        brush = QBrush(pix)
        self._brush_cache[theme] = brush
        return brush

    def apply_to_widget(self, widget, theme="light"):
        """快速将棋盘格应用到 QLabel 或 QWidget"""
        brush = self.get_brush(theme)
        palette = widget.palette()
        palette.setBrush(QPalette.ColorRole.Window, brush)
        widget.setPalette(palette)
        widget.setAutoFillBackground(True)
        # 清除 QSS 可能存在的背景颜色干扰
        widget.setStyleSheet("background: transparent; border: 1px solid #333;")

    def render_dynamic(self, painter, rect, transform, theme="light"):
        """
        核心算法：用于 QGraphicsView.drawBackground 的动态渲染
        rect: 当前视口在场景中的矩形区域 (Scene Rect)
        transform: 当前绘图设备的变换矩阵
        """
        scale = transform.m11() # 获取缩放倍率
        
        # 性能阈值：如果格子在屏幕上太小（小于4像素），绘制纯色背景以防摩尔纹
        if self.grid_size * scale < 4:
            painter.fillRect(rect, self.themes[theme]["c1"])
            return

        colors = self.themes.get(theme, self.themes["light"])
        if scale > 2.0:
            s = 8  # 高倍率下用小格子
        else:
            s = 16 # 低倍率下用大格子
        s = self.grid_size

        # 1. 计算对齐场景 (0,0) 的起始坐标 (Modulo Tiling)
        start_x = math.floor(rect.left() / s) * s
        start_y = math.floor(rect.top() / s) * s
        end_x = rect.right()
        end_y = rect.bottom()

        # 2. 局部渲染循环：只画眼睛看得见的区域
        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)

        curr_y = start_y
        while curr_y < end_y:
            curr_x = start_x
            while curr_x < end_x:
                # 使用位运算判断奇偶色块，极致性能
                is_color1 = (int(curr_x / s) + int(curr_y / s)) % 2 == 0
                color = colors["c1"] if is_color1 else colors["c2"]
                
                # 绘制单个格点
                painter.fillRect(QRectF(curr_x, curr_y, s, s), color)
                curr_x += s
            curr_y += s
            
        painter.restore()

# 全局单例对象
checker_manager = CheckerboardManager()