#!/usr/bin/env python3
"""
测试地图渲染脚本
"""

import sys
import os
import time

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入地图加载函数
from modules.bingo_engine import load_map

def test_map_render():
    """测试地图渲染"""
    print("=== 测试地图渲染 ===")
    
    # 加载地图
    map_name = "地图1"
    print(f"加载地图: {map_name}")
    load_map(map_name)
    
    # 等待一段时间，让渲染完成
    print("渲染中...")
    time.sleep(2)
    
    print("测试完成")

if __name__ == "__main__":
    test_map_render()
