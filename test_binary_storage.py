#!/usr/bin/env python3
"""测试二进制分层存储架构"""

import os
import sys
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from models.map_model import MapDataModel

def test_binary_storage():
    """测试二进制分层存储功能"""
    print("🎮 测试二进制分层存储架构")
    
    # 创建测试地图模型
    model = MapDataModel()
    
    # 设置一些测试数据
    model.set_tile(0, 10, 10, 1001)  # 资源索引0，图块索引0
    model.set_tile(0, 11, 10, 1002)  # 资源索引0，图块索引1
    model.set_tile(0, 10, 11, 1003)  # 资源索引0，图块索引2
    
    # 测试保存（应该保存为二进制文件）
    test_file = "/Volumes/WorkStation/MyWork/CodeStation/MyIDE/test_map.map"
    
    print(f"\n📝 保存地图到: {test_file}")
    save_result = model.save(test_file)
    
    if save_result:
        print("✅ 地图保存成功！")
        
        # 检查生成的文件
        base_name = os.path.splitext(test_file)[0]
        files = [
            base_name + ".info",
            base_name + ".tiles",
            base_name + ".collision",
            base_name + ".resources"
        ]
        
        print("\n📁 生成的文件:")
        for file_path in files:
            if os.path.exists(file_path):
                size = os.path.getsize(file_path)
                print(f"  ✅ {os.path.basename(file_path)} ({size} bytes)")
            else:
                print(f"  ❌ {os.path.basename(file_path)} (不存在)")
        
        # 测试加载
        print("\n🔄 测试加载二进制地图")
        model2 = MapDataModel()
        load_result = model2.load(test_file)
        
        if load_result:
            print("✅ 地图加载成功！")
            print(f"   - 地图尺寸: {model2.map_data['width']}x{model2.map_data['height']}")
            print(f"   - 图层数量: {len(model2.map_data['layers'])}")
            
            # 检查图块数据
            tile1 = model2.get_tile(0, 10, 10)
            tile2 = model2.get_tile(0, 11, 10)
            tile3 = model2.get_tile(0, 10, 11)
            
            print(f"\n🔍 图块数据检查:")
            print(f"   - (10,10): {tile1}")
            print(f"   - (11,10): {tile2}")
            print(f"   - (10,11): {tile3}")
            
            # 验证数据一致性
            if tile1 == 1001 and tile2 == 1002 and tile3 == 1003:
                print("✅ 数据一致性验证通过！")
            else:
                print("❌ 数据一致性验证失败！")
        else:
            print("❌ 地图加载失败！")
            
        # 清理测试文件
        for file_path in files:
            if os.path.exists(file_path):
                os.remove(file_path)
        if os.path.exists(test_file):
            os.remove(test_file)
            
    else:
        print("❌ 地图保存失败！")

if __name__ == "__main__":
    test_binary_storage()
