# modules/internal_lib/arcade_shell.py
import sys
import os
import arcade as real_arcade
import numpy as np
from multiprocessing import shared_memory
import ctypes
import ctypes.util

# 🚀 强制设置环境变量，确保在 IDE 环境下行为一致
os.environ['PYGLET_SHADOW_WINDOW'] = '0'

def set_dock_silence(policy_id):
    if sys.platform == "darwin":
        try:
            objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library('objc'))
            objc.objc_msgSend.restype = ctypes.c_void_p
            objc.sel_registerName.restype = ctypes.c_void_p
            objc.objc_getClass.restype = ctypes.c_void_p
            NSApp = objc.objc_msgSend(objc.objc_getClass('NSApplication'), objc.sel_registerName('sharedApplication'))
            if NSApp:
                objc.objc_msgSend(NSApp, objc.sel_registerName('setActivationPolicy:'), policy_id)
        except: pass

# 🚀 立即执行禁言，抢在任何窗口初始化之前
set_dock_silence(2)

class MyWindow(real_arcade.Window):
    def __init__(self, width=640, height=480, title="Arcade", **kwargs):
        set_dock_silence(2)
        kwargs['visible'] = False
        super().__init__(width, height, title, **kwargs)
        set_dock_silence(2)
        
        self.phys_w, self.phys_h = self.get_framebuffer_size()
        self.pixel_bytes = self.phys_w * self.phys_h * 4
        
        try:
            self._shm = shared_memory.SharedMemory(name="arcade_frame", create=True, size=self.pixel_bytes + 8)
        except FileExistsError:
            self._shm = shared_memory.SharedMemory(name="arcade_frame")

        self.header = np.ndarray((2,), dtype=np.int32, buffer=self._shm.buf[:8])
        self.header[0], self.header[1] = self.phys_w, self.phys_h
        self._buf = np.ndarray((self.phys_h, self.phys_w, 4), dtype=np.uint8, buffer=self._shm.buf[8:])

    def flip(self):
        super().flip()
        try:
            from pyglet import gl as pgl
            pgl.glReadBuffer(pgl.GL_FRONT)
            raw_data = (pgl.GLubyte * self.pixel_bytes)()
            pgl.glReadPixels(0, 0, self.phys_w, self.phys_h, pgl.GL_RGBA, pgl.GL_UNSIGNED_BYTE, raw_data)
            pixel_array = np.frombuffer(raw_data, dtype=np.uint8).reshape(self.phys_h, self.phys_w, 4)
            self._buf[:] = np.flipud(pixel_array)
        except: pass

# --- 🚀 关键修复：完全补全模块属性 ---
# 1. 先劫持核心类
real_arcade.Window = MyWindow

# 2. 将此模块伪装成 arcade 注入系统
sys.modules['arcade'] = real_arcade

# 3. 🚀 必须手动导出 Window 属性到当前模块空间，防止 exec 时找不到
Window = MyWindow

# 4. 拷贝所有原始属性，确保像 arcade.color 这种也能正常访问
for attr in dir(real_arcade):
    if not attr.startswith('__'):
        globals()[attr] = getattr(real_arcade, attr)