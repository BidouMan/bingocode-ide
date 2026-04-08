
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modules.bingo_engine import Sprite, follow, load_map

# 加载地图
load_map('地图1')

# 创建精灵
player = Sprite('洛克人')

# 设置摄像机跟随精灵
follow(player)

# 移动精灵，测试摄像机跟随
positions = [
    (400, 300),
    (500, 200),
    (200, 400),
    (320, 240)
]

for i, (x, y) in enumerate(positions):
    print(f"移动到位置 {i+1}: ({x}, {y})")
    player._x = x
    player._y = y
    player._update_transform()
    time.sleep(1)

print("摄像机跟随测试完成！")
