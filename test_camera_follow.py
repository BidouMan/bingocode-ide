import os
import sys

# 切换到用户项目目录
project_dir = "/Users/amixc/Desktop/IDEtest/Test"
if os.path.exists(project_dir):
    os.chdir(project_dir)
    print(f"切换到项目目录: {project_dir}")
else:
    print(f"项目目录不存在: {project_dir}")
    sys.exit(1)

# 添加IDE目录到Python路径
ide_dir = "/Volumes/WorkStation/MyWork/CodeStation/MyIDE"
if ide_dir not in sys.path:
    sys.path.insert(0, ide_dir)

from modules.bingo_engine import Sprite, run, load_map, follow

# 创建角色
player = Sprite("rockman")
player.x = 320
player.y = 240

# 加载地图
print("加载地图...")
success = load_map("地图3")
print(f"地图加载完成: {success}")

# 设置摄像机跟随玩家
print("设置摄像机跟随...")
follow(player)
print("摄像机跟随设置完成")

# 移动函数
def loop():
    # 让角色向右移动
    player.x += 1
    
    # 如果超出地图范围，重置位置
    if player.x > 640:
        player.x = 100
    
    # 打印调试信息
    if player.x % 50 == 0:
        print(f"玩家位置: x={player.x}, y={player.y}")

# 运行游戏
run()
