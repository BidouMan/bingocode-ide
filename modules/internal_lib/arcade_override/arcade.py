# modules/internal_lib/arcade_override/arcade.py
import sys
import os
import importlib

# 🚀 1. 核心黑科技：防止递归导入，确保加载的是真正的原生 arcade
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir in sys.path:
    sys.path.remove(current_dir)

temp_arcade = sys.modules.pop('arcade', None)
real_arcade = importlib.import_module('arcade')

# 恢复 sys.modules 确保环境一致性
if temp_arcade:
    sys.modules['arcade'] = temp_arcade
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import numpy as np
from multiprocessing import shared_memory
import pyglet.gl as gl

# 🚀 2. 拦截 Window 类实现底层像素共享
class Window(real_arcade.Window):
    def __init__(self, width=None, height=None, title="Arcade", **kwargs):
        # 💡 优先读取 IDE 注入的环境变量，确保两端尺寸像素级对齐
        # 默认 480x360 (Scratch 比例)
        self.ide_w = int(os.environ.get("IDE_SCREEN_WIDTH", 480))
        self.ide_h = int(os.environ.get("IDE_SCREEN_HEIGHT", 360))
        
        # 强制覆盖学生代码中的尺寸设定，实现 IDE 舞台接管
        final_w = self.ide_w
        final_h = self.ide_h

        # 💡 强制隐藏原生窗口，对学生完全透明
        kwargs['visible'] = False
        super().__init__(final_w, final_h, title, **kwargs)
        
        # 💡 共享内存安全初始化
        self._shm_name = os.environ.get("IDE_SHM_NAME", "arcade_frame")
        shm_size = self.width * self.height * 4
        
        try:
            # 尝试接管已存在的内存（防止 ConsoleManager 清理延迟）
            self._shm = shared_memory.SharedMemory(name=self._shm_name)
        except FileNotFoundError:
            # 如果不存在则创建
            self._shm = shared_memory.SharedMemory(name=self._shm_name, create=True, size=shm_size)
        
        # 将共享内存包装为 NumPy 数组，方便像素填充
        self._shm_buffer = np.ndarray((self.height, self.width, 4), dtype=np.uint8, buffer=self._shm.buf)

    def on_draw(self):
        """每帧渲染逻辑：先由原生 Arcade 绘图，再同步至共享内存"""
        super().on_draw() # 执行学生写的绘图逻辑
        
        # ⚡️ 高效抓取像素：直接从 GPU 帧缓冲区读取 RGBA 数据
        # 使用 GLubyte 数组作为中转，避免频繁创建内存对象
        raw_data = (gl.GLubyte * (self.width * self.height * 4))()
        gl.glReadPixels(0, 0, self.width, self.height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, raw_data)
        
        # 将像素数据快速同步到共享内存
        # 注意：此处未加锁是为了追求 60FPS 的极致性能，轻微撕裂不影响教学使用
        self._shm_buffer[:] = np.frombuffer(raw_data, dtype=np.uint8).reshape(self.height, self.width, 4)

    def close(self):
        """重写关闭方法，确保子进程退出时资源被释放"""
        if hasattr(self, '_shm'):
            self._shm.close()
            # 注意：unlink 由 IDE 的 ConsoleManager 统一负责，此处仅 close
        super().close()

# 🚀 3. 动态导出原生库的所有属性（如 arcade.color, arcade.Sprite 等）
# 确保学生调用 `import arcade` 后依然能正常使用所有 API
globals().update({k: v for k, v in real_arcade.__dict__.items() if k not in ['Window']})