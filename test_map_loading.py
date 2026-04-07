import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from modules.bingo_engine import load_map

def main():
    print("测试地图加载功能...")
    
    # 测试地图加载
    result = load_map('地图1')
    
    print(f"地图加载结果: {result}")

if __name__ == "__main__":
    main()
