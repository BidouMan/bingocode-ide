import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from modules.bingo_engine import load_map

print("测试地图加载功能...")

# 调用load_map函数
result = load_map('地图1')

print(f"地图加载结果: {result}")
