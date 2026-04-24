#!/usr/bin/env python3
"""
测试地图1加载功能
"""

import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入引擎模块
from modules.bingo_engine import load_map, run

# 测试函数
def test_map_load():
    print("=== 测试地图1加载功能 ===")
    
    # 尝试加载地图
    success = load_map('地图1')
    
    if success:
        print("✅ 地图加载成功！")
    else:
        print("❌ 地图加载失败！")
    
    # 简单的循环函数，用于保持程序运行
    def loop():
        pass
    
    # 设置loop函数
    sys.modules['__main__'].loop = loop
    
    # 运行引擎
    run()

if __name__ == "__main__":
    test_map_load()
