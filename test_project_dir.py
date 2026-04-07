import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from modules.bingo_engine import load_map

print("=== 测试项目目录地图加载 ===")
print(f"当前工作目录: {os.getcwd()}")

# 检查地图文件是否存在
map_file = os.path.join("assets", "maps", "地图1", "地图1.json")
print(f"\n检查地图文件: {map_file}")
print(f"文件存在: {os.path.exists(map_file)}")

# 检查瓦片集图片是否存在
tileset_file = os.path.join("assets", "maps", "地图1", "tilesets", "map_2.png")
print(f"\n检查瓦片集图片: {tileset_file}")
print(f"文件存在: {os.path.exists(tileset_file)}")

# 调用load_map函数
print("\n调用load_map函数...")
result = load_map('地图1')

print(f"\n地图加载结果: {result}")
