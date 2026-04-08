#!/usr/bin/env python3
"""测试标签碰撞检测功能"""

import os
import sys
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from models.map_model import MapDataModel

def test_tag_collision():
    """测试标签碰撞检测功能"""
    print("🎮 测试标签碰撞检测功能")
    
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
    while len(model.map_data["tile_sets"][0]["tiles"]) < 2:
        model.map_data["tile_sets"][0]["tiles"].append({"collision": True})
    
    # 设置标签
    model.set_tile_tag(0, 0, "地面")
    model.set_tile_tag(0, 1, "墙壁")
    
    # 设置一些测试数据
    model.set_tile(0, 10, 10, 1001)  # 资源索引0，图块索引0
    model.set_tile(0, 11, 10, 1002)  # 资源索引0，图块索引1
    
    # 测试保存（应该保存为二进制文件）
    test_file = "/Volumes/WorkStation/MyWork/CodeStation/MyIDE/test_tag_map.map"
    
    print(f"\n📝 保存带标签的地图到: {test_file}")
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
            
            print(f"\n🔍 标签数据检查:")
            print(f"   - 图块索引0标签: '{tag1}'")
            print(f"   - 图块索引1标签: '{tag2}'")
            
            # 验证标签一致性
            if tag1 == "地面" and tag2 == "墙壁":
                print("✅ 标签一致性验证通过！")
            else:
                print("❌ 标签一致性验证失败！")
                
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
        else:
            print("❌ 地图加载失败！")
    else:
        print("❌ 地图保存失败！")

if __name__ == "__main__":
    test_tag_collision()
