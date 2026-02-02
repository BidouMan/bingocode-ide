import sys
import os
import arcade as real_arcade
import numpy as np
from multiprocessing import shared_memory
import ctypes

# 🚀 绕过所有 Python 层级的 gl 模块，直接从底层导入
from pyglet import gl as pgl 

class MyWindow(real_arcade.Window):
    def __init__(self, width=640, height=480, title="Arcade", **kwargs):
        kwargs['visible'] = True
        super().__init__(width, height, title, **kwargs)
        self.set_location(-2000, -2000)
        
        self.phys_w, self.phys_h = self.get_framebuffer_size()
        self.pixel_bytes = self.phys_w * self.phys_h * 4
        
        print(f"🚀 [Shell]: 窗口初始化成功, 物理尺寸: {self.phys_w}x{self.phys_h}")

        try:
            self._shm = shared_memory.SharedMemory(name="arcade_frame", create=True, size=self.pixel_bytes + 8)
        except FileExistsError:
            self._shm = shared_memory.SharedMemory(name="arcade_frame")

        self.header = np.ndarray((2,), dtype=np.int32, buffer=self._shm.buf[:8])
        self.header[0], self.header[1] = self.phys_w, self.phys_h
        self._buf = np.ndarray((self.phys_h, self.phys_w, 4), dtype=np.uint8, buffer=self._shm.buf[8:])

    def flip(self):
        super().flip()
        self.use()
        
        try:
            # 🚀 终极绝招：直接调用 pyglet 内部维护的底层 C 函数
            # 不再访问 pgl.glReadBuffer，而是访问底层的动态链接库接口
            pgl.glReadBuffer(pgl.GL_FRONT)
            
            raw_data = (pgl.GLubyte * self.pixel_bytes)()
            pgl.glReadPixels(0, 0, self.phys_w, self.phys_h, pgl.GL_RGBA, pgl.GL_UNSIGNED_BYTE, raw_data)
            
            pixel_array = np.frombuffer(raw_data, dtype=np.uint8).reshape(self.phys_h, self.phys_w, 4)
            self._buf[:] = np.flipud(pixel_array)
            
        except Exception as e:
            # 这里的打印会出现在 IDE 的控制台里
            print(f"❌ [Shell] 像素同步异常: {type(e).__name__} - {e}")

# 劫持 Window
real_arcade.Window = MyWindow

# 🚀 必须确保 arcade 模块被正确注入到 sys.modules
# 这样 a1.py 执行 import arcade 时，拿到的就是我们这个已经劫持了 Window 的模块
sys.modules['arcade'] = real_arcade

# 复制属性确保兼容性
for attr in dir(real_arcade):
    if not attr.startswith('__'):
        setattr(sys.modules[__name__], attr, getattr(real_arcade, attr))