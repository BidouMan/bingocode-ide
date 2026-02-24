import json
import sys
import time
import os
import random
__all__ = ['Sprite', 'run']

class Sprite:
    def __init__(self, image_name):        
        # 使用内存地址作为唯一ID
        self.id = str(id(self))
        # 🚀 修正路径：确保与你 assets 文件夹名称一致
        self.image = os.path.join("assets", "images", image_name)
        self._x = 320  
        self._y = 240
        self._angle = 0

        # 发送创建指令
        self._send_command("CREATE", {
            "image": self.image,
            "x": self._x,
            "y": self._y,
            "angle": self._angle,
            "type": "image"
        })

    # ---------- 运动模块 ----------
    def set_xy(self, x, y):
        """设置坐标"""
        self._x = x
        self._y = y
        self._send_command("UPDATE", {
            "x": self._x,
            "y": self._y
        })
    
    def set_x(self,x):
        self._x = x
        self._send_command("UPDATE", {
            "x": self._x,
            "y": self._y
        })

    def set_y(self,y):
        self._y = y
        self._send_command("UPDATE", {
            "x": self._x,
            "y": self._y
        })
    def add_x(self, delta_x):
        """将 x 坐标增加（或减少）一定数值"""
        self._x += delta_x
        self._send_command("UPDATE", {
            "x": self._x,
            "y": self._y
        })

    def add_y(self, delta_y):
        """将 y 坐标增加（或减少）一定数值"""
        self._y += delta_y
        self._send_command("UPDATE", {
            "x": self._x,
            "y": self._y
        })

    def goto_rand(self):
        '''移到随机位置'''
        self._x = random.randint(0,640)
        self._y = random.randint(0,480)
        self._send_command('UPDATE',{'x':self._x,'y':self._y})

    def set_angle(self, angle):
        """设置旋转角度"""
        self._angle = angle
        self._send_command("UPDATE", {
            "angle": self._angle
        })

    # ----------- 属性赋值 ----------
    @property
    def x(self):
        return self._x
    @x.setter
    def x(self,value):
        self._x = value
        self._send_command("UPDATE", {"x": self._x,'y':self._y})
    
    @property
    def y(self):
        return self._y
    @y.setter
    def y(self, value):
        self._y = value
        self._send_command("UPDATE", {"x": self._x, "y": self._y})

    @property
    def angle(self):
        return self._angle
    @angle.setter
    def angle(self,value):
        self._angle = value
        self._send_command('UPDATE',{'angle':self._angle})

    # ----------- 超级核心 -----------
    def _send_command(self, cmd_type, data_dict):
        """核心:所有指令都是通过它发送出去并执行的"""
        packet = {
            "type": cmd_type,
            "id": self.id,
            "data": data_dict 
        }
        # 🚀 必须取消注释，且必须 flush=True 保证实时性
        print(json.dumps(packet), flush=True)

def run():
    """驱动游戏循环"""
    # 查找运行脚本中的 loop 函数
    main_module = sys.modules['__main__']
        
    while True:
        if hasattr(main_module, 'loop'):
            try:
                main_module.loop()
            except Exception as e:
                print(f"Loop Error: {e}", file=sys.stderr)
                break
        # 保持约 60FPS
        time.sleep(0.016)