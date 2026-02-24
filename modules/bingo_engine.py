import json
import sys
import time
import os
import random
import math
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
        self._rotation_style = "all"

        # 发送创建指令
        self._send_command("CREATE", {
            "image": self.image,
            "x": self._x,
            "y": self._y,
            "angle": self._angle,
            "scale_x": 1.0, # 初始镜像
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

    def move(self, distance):
        """朝着当前 angle 方向移动 distance 像素"""
        # 将角度转为弧度
        radians = math.radians(self._angle)
        
        # 计算增量 (注意：y轴向下，所以sin的结果通常直接加)
        dx = distance * math.cos(radians)
        dy = distance * math.sin(radians)
        
        # 利用我们写好的 setter 自动同步到渲染器
        self.x += dx
        self.y += dy

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
    def set_rotation_mode(self, style):
        """
        style: 
        'all': 任意旋转 (默认)
        'left_right': 左右翻转 (角度不改变图片旋转，只决定水平镜像)
        'none': 不可旋转 (图片始终正向)
        """
        self._rotation_style = style
        # 立即触发一次更新以应用新样式
        self._update_transform()
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
        # self._send_command('UPDATE',{'angle':self._angle})
        self._update_transform()

    def _update_transform(self):
        """统一处理旋转和镜像逻辑并发送给渲染器"""
        display_angle = self._angle
        scale_x = 1.0
        
        if self._rotation_style == 'none':
            display_angle = 0
        elif self._rotation_style == 'left_right':
            # 🚀 核心逻辑：
            # 规范化角度到 0-360 之间
            norm_angle = self._angle % 360
            # 如果朝向左边（90~270度），水平镜像
            if 90 < norm_angle <= 270:
                scale_x = -1.0
            else:
                scale_x = 1.0
            # 🚀 重点：在左右翻转模式下，图片本身永远不倾斜（角度保持0）
            display_angle = 0
            
        self._send_command("UPDATE", {
            "x": self._x,
            "y": self._y,
            "angle": display_angle,
            "scale_x": scale_x
        })

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