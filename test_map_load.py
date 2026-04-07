#!/usr/bin/env python3
"""测试地图加载功能"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from modules.bingo_engine import load_map


def test_map_load():
    """测试地图加载功能"""
    print("开始测试地图加载功能...")
    
    # 测试加载不存在的地图
    print("测试1 - 加载不存在的地图")
    result = load_map("不存在的地图")
    print(f"结果: {result}")
    assert result == False, "测试1失败：加载不存在的地图应该返回False"
    
    # 创建测试地图文件
    test_map_data = {
        "width": 20,
        "height": 15,
        "tile_size": 16,
        "layers": [
            {
                "name": "ground",
                "visible": True,
                "tiles": [
                    [0, 0, 1],
                    [1, 0, 2],
                    [2, 0, 3],
                    [0, 1, 4],
                    [1, 1, 5],
                    [2, 1, 6],
                    [0, 2, 7],
                    [1, 2, 8],
                    [2, 2, 9]
                ],
                "objects": []
            }
        ],
        "tile_sets": [
            {
                "name": "test_tileset",
                "image_path": "test_tiles.png",
                "tile_width": 16,
                "tile_height": 16,
                "tile_count": 10,
                "tiles": [{"collision": True} for _ in range(10)]
            }
        ]
    }
    
    # 创建测试地图文件
    maps_dir = os.path.join("assets", "maps")
    os.makedirs(maps_dir, exist_ok=True)
    test_map_file = os.path.join(maps_dir, "测试地图.json")
    
    import json
    with open(test_map_file, 'w', encoding='utf-8') as f:
        json.dump(test_map_data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 创建测试地图文件: {test_map_file}")
    
    # 测试加载存在的地图
    print("测试2 - 加载存在的地图")
    result = load_map("测试地图")
    print(f"结果: {result}")
    assert result == True, "测试2失败：加载存在的地图应该返回True"
    
    # 测试再次加载同一地图（应该清理旧地图）
    print("测试3 - 再次加载同一地图")
    result = load_map("测试地图")
    print(f"结果: {result}")
    assert result == True, "测试3失败：再次加载地图应该成功"
    
    # 清理测试文件
    os.remove(test_map_file)
    print(f"✅ 清理测试文件: {test_map_file}")
    
    print("🎉 所有地图加载测试通过！")


if __name__ == "__main__":
    test_map_load()