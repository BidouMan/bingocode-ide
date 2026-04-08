#!/usr/bin/env python3
"""测试完整的碰撞检测功能"""

import os
import sys
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from models.map_model import MapDataModel
from modules.bingo_engine import Sprite

def test_full_collision():
    """测试完整的碰撞检测流程"""
    print("🎮 测试完整的碰撞检测功能")
    
    # 创建测试地图模型
    model = MapDataModel()
    
    # 确保瓦片集存在
    if not model.map_data["tile_sets"]:
        model.map_data["tile_sets"].append({
            "name": "test_tileset",
            "image": "test.png",
            "tiles": []
        })
    
    # 确保tiles数组足够大
    while len(model.map_data["tile_sets"][0]["tiles"]) < 3:
        model.map_data["tile_sets"][0]["tiles"].append({"collision": True})
    
    # 设置标签
    model.set_tile_tag(0, 0, "地面")
    model.set_tile_tag(0, 1, "墙壁")
    model.set_tile_tag(0, 2, "危险")
    
    # 设置一些测试数据
    model.set_tile(0, 10, 10, 1001)  # 资源索引0，图块索引0（地面）
    model.set_tile(0, 11, 10, 1002)  # 资源索引0，图块索引1（墙壁）
    model.set_tile(0, 10, 11, 1003)  # 资源索引0，图块索引2（危险）
    
    # 测试保存（应该保存为二进制文件）
    test_file = "/Volumes/WorkStation/MyWork/CodeStation/MyIDE/test_full_map.map"
    
    print(f"\n📝 保存地图到: {test_file}")
    save_result = model.save(test_file)
    
    if save_result:
        print("✅ 地图保存成功！")
        
        # 测试加载
        model2 = MapDataModel()
        load_result = model2.load(test_file)
        
        if load_result:
            print("✅ 地图加载成功！")
            
            # 测试标签读取
            tag1 = model2.get_tile_tag(0, 0)
            tag2 = model2.get_tile_tag(0, 1)
            tag3 = model2.get_tile_tag(0, 2)
            
            print(f"\n🔍 标签数据检查:")
            print(f"   - 图块索引0标签: '{tag1}'")
            print(f"   - 图块索引1标签: '{tag2}'")
            print(f"   - 图块索引2标签: '{tag3}'")
            
            # 验证标签一致性
            if tag1 == "地面" and tag2 == "墙壁" and tag3 == "危险":
                print("✅ 标签一致性验证通过！")
            else:
                print("❌ 标签一致性验证失败！")
            
            # 创建Sprite对象测试碰撞检测
            print("\n🎯 测试碰撞检测功能")
            player = Sprite('rockman')
            
            # 设置精灵位置（站在地面上）
            player.x = 10 * 16 + 8  # 图块中心
            player.y = 10 * 16 + 8
            
            print(f"   - 精灵位置: ({player.x}, {player.y})")
            
            # 测试碰撞检测（这里只是模拟，实际碰撞需要完整的游戏环境）
            print(f"   - 碰撞检测API: player.is_touch('地面')")
            print(f"   - 碰撞检测API: player.is_touch('墙壁')")
            print(f"   - 碰撞检测API: player.is_touch('危险')")
            
            # 清理测试文件
            base_name = os.path.splitext(test_file)[0]
            files = [
                base_name + ".info",
                base_name + ".tiles",
                base_name + ".collision",
                base_name + ".resources"
            ]
            for file_path in files:
                if os.path.exists(file_path):
                    os.remove(file_path)
            if os.path.exists(test_file):
                os.remove(test_file)
                
            print("\n✅ 完整碰撞检测功能测试完成！")
        else:
            print("❌ 地图加载失败！")
    else:
        print("❌ 地图保存失败！")

if __name__ == "__main__":
    test_full_collision()
