"""
while True 示例 - 多角色协作
"""
from bingo_engine import *

# 创建角色
hero = Sprite("洛克人")
enemy = Sprite("哥布林")

# 加载地图
load_map("地图1")

# 主循环 - 每个角色的行为
while True:
    # 玩家控制
    if key_down('a'):
        hero.move(-5)
    if key_down('d'):
        hero.move(5)
    if key_down('w'):
        hero.jump(10)
    
    # 敌人AI（简单追逐）
    enemy.look_at(hero)
    enemy.move(2)
    
    # 摄像机跟随玩家
    follow(hero)
