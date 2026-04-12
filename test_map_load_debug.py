import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from models.map_model import MapDataModel

def test_map_load_debug():
    """测试双击地图卡片进入编辑器时的读取debug信息"""
    print("=== 测试地图加载debug信息 ===")
    
    # 测试地图路径
    map_path = "/Users/amixc/Desktop/IDEtest/Test/assets/maps/地图1/地图1.info"
    
    print(f"\n加载地图: {map_path}")
    print("=" * 60)
    
    # 加载地图
    map_model = MapDataModel()
    success = map_model.load(map_path)
    
    print("=" * 60)
    if success:
        print("✅ 地图加载成功")
    else:
        print("❌ 地图加载失败")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_map_load_debug()
