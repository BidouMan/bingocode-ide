import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from modules.bingo_engine import Sprite

print("测试精灵创建功能...")

# 创建一个精灵
sprite = Sprite('test_sprite')

print(f"精灵创建成功: {sprite.id}")
print(f"精灵位置: ({sprite.x}, {sprite.y})")
