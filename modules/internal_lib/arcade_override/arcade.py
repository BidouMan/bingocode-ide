import sys
import os
import importlib
import numpy as np
from multiprocessing import shared_memory

# ==========================================
# 🚀 1. 环境屏蔽：彻底解决 Retina 缩放和多余窗口
# ==========================================
os.environ["ARCADE_DISABLE_GLEXT_DOT_RETAIN_WINDOW"] = "1"
os.environ["PYGLET_SHADOW_WINDOW"] = "0"
# 强制底层使用更稳定的渲染路径
os.environ["ARCADE_RESOURCES_WARN_MISSING"] = "0" 

# ==========================================
# 🚀 2. 递归拦截逻辑：获取原生 Arcade 3.3.3
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir in sys.path:
    sys.path.remove(current_dir)

temp_arcade = sys.modules.pop('arcade', None)
try:
    real_arcade = importlib.import_module('arcade')
    print("DEBUG [子进程]: 成功加载原生 Arcade 3.3.3")
except ImportError as e:
    print(f"❌ 错误：无法加载原生 arcade 库: {e}")
    sys.exit(1)

if temp_arcade:
    sys.modules['arcade'] = temp_arcade
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import pyglet.gl as gl

# ==========================================
# 🚀 3. 拦截 Window 类：实现跨进程像素共享
# ==========================================
class Window(real_arcade.Window):
    def __init__(self, width=None, height=None, title="Arcade", **kwargs):
        # 强制对齐主进程 ScreenManager 的 320x240
        self.ide_w = 320
        self.ide_h = 240
        self.expected_bytes = self.ide_w * self.ide_h * 4
        
        # 隐藏原生窗口，禁用抗锯齿以提升抓取性能
        kwargs['visible'] = False
        kwargs['antialiasing'] = False
        
        print(f"DEBUG [子进程]: 初始化 Window, 尺寸对齐: {self.ide_w}x{self.ide_h}")
        super().__init__(self.ide_w, self.ide_h, title, **kwargs)

        # 检查缩放屏蔽是否成功
        print(f"DEBUG [子进程]: 缓冲区尺寸: {self.width}x{self.height}")

        self._shm_name = "arcade_frame"
        try:
            self._shm = shared_memory.SharedMemory(name=self._shm_name)
            print(f"DEBUG [子进程]: 已连接共享内存, Size: {self._shm.size}")
        except FileNotFoundError:
            print("DEBUG [子进程]: 共享内存未就绪，正在自行初始化...")
            self._shm = shared_memory.SharedMemory(name=self._shm_name, create=True, size=self.expected_bytes)

        # 核心：使用切片映射，适配 macOS 4KB 内存对齐 (311296 -> 307200)
        self._shm_buffer = np.ndarray(
            (self.height, self.width, 4), 
            dtype=np.uint8, 
            buffer=self._shm.buf[:self.expected_bytes]
        )
        self.frame_count = 0

    def on_draw(self):
        """每帧渲染逻辑：适配 3.3.3 渲染管线"""
        try:
            super().on_draw() # 执行用户绘图代码
        except Exception as e:
            print(f"❌ [子进程] 用户绘图报错: {e}")
            return

        try:
            # 🚀 关键：3.3.3 使用了更复杂的 GPU 调度，必须用 glFinish 强制同步
            gl.glFinish()

            # 抓取像素
            raw_data = (gl.GLubyte * self.expected_bytes)()
            gl.glReadPixels(0, 0, self.width, self.height, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, raw_data)
            
            # 将数据填充到共享内存
            np_data = np.frombuffer(raw_data, dtype=np.uint8)
            self._shm_buffer[:] = np_data.reshape(self.height, self.width, 4)
            
            # 周期性监控
            self.frame_count += 1
            if self.frame_count % 60 == 0:
                print(f"DEBUG [子进程]: 帧推送中, 像素和: {np_data.sum()}")
                
        except Exception as e:
            print(f"❌ [子进程] 同步到主进程失败: {e}")

    def close(self):
        if hasattr(self, '_shm'):
            self._shm.close()
        super().close()

# ==========================================
# 🚀 4. 属性注入：适配 3.3.3 的新模块结构
# ==========================================

def inject_properties():
    # 1. 导出原生 arcade 的顶级属性
    for attr in dir(real_arcade):
        if not attr.startswith("__") and attr != "Window":
            globals()[attr] = getattr(real_arcade, attr)
    
    # 2. 核心：处理 3.3.3 的 draw 模块
    # 我们不要直接覆盖 globals()['draw']，而是确保它指向真正的模块
    import arcade.draw as arcade_draw_mod
    globals()['draw'] = arcade_draw_mod 
    
    # 3. 为了兼容旧教材（arcade.draw_circle_filled 这种写法）
    # 遍历 draw 模块下的所有新函数，手动补全到顶级命名空间
    for func_name in dir(arcade_draw_mod):
        if not func_name.startswith("__"):
            func_obj = getattr(arcade_draw_mod, func_name)
            # 补全 draw_circle 等
            globals()[f"draw_{func_name}"] = func_obj
            # 特别补全 circle_filled 等
            if func_name == "circle":
                globals()["circle_filled"] = func_obj
                globals()["draw_circle_filled"] = func_obj
            if func_name == "rect":
                globals()["draw_rectangle_filled"] = func_obj

inject_properties()
print("DEBUG [子进程]: 3.3.3 深度属性注入完成")