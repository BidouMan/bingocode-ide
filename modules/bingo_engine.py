import json
import sys
import time
import os

class Sprite:
    def __init__(self, image_name):
        # 使用内存地址作为唯一ID
        self.id = str(id(self))
        # 🚀 修正路径：确保与你 assets 文件夹名称一致
        self.image = os.path.join("assets", "images", image_name)
        self.x = 320  
        self.y = 240
        self.angle = 0

        # 发送创建指令
        self._send_command("CREATE", {
            "image": self.image,
            "x": self.x,
            "y": self.y,
            "angle": self.angle,
            "type": "image"
        })

    def set_xy(self, x, y):
        """设置坐标"""
        self.x = x
        self.y = y
        self._send_command("UPDATE", {
            "x": self.x,
            "y": self.y
        })

    def set_angle(self, angle):
        """设置旋转角度"""
        self.angle = angle
        self._send_command("UPDATE", {
            "angle": self.angle
        })

    def _send_command(self, cmd_type, data_dict):
        """底层发送逻辑：严格匹配 RenderManager 要求的 data 嵌套格式"""
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
    
    # 简单的启动提示
    # print("Bingo Engine Running...") 
    
    while True:
        if hasattr(main_module, 'loop'):
            try:
                main_module.loop()
            except Exception as e:
                print(f"Loop Error: {e}", file=sys.stderr)
                break
        # 保持约 60FPS
        time.sleep(0.016)