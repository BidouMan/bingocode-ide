import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from models.map_model import MapDataModel

def test_autosave():
    """测试碰撞形状的自动保存功能"""
    print("=== 测试碰撞形状自动保存功能 ===")
    
    # 测试地图路径
    map_path = "/Users/amixc/Desktop/IDEtest/Test/assets/maps/地图1/地图1.info"
    
    print(f"测试地图路径: {map_path}")
    print("=" * 80)
    
    # 1. 加载地图
    print("\n1. 加载地图...")
    map_model = MapDataModel()
    success = map_model.load(map_path)
    
    if not success:
        print("❌ 加载地图失败")
        return
    
    print("✅ 加载地图成功")
    
    # 2. 记录初始碰撞数据
    print("\n2. 记录初始碰撞数据...")
    initial_shape = map_model.get_tile_collision_shape(1, 0)
    print(f"初始碰撞形状: {initial_shape}")
    
    # 3. 修改碰撞形状
    print("\n3. 修改碰撞形状...")
    new_shape = {
        "points": [[0, 0], [32, 0], [32, 16], [0, 16]]  # 1/2高度
    }
    print(f"新碰撞形状: {new_shape}")
    
    # 保存修改
    save_success = map_model.set_tile_collision_shape(1, 0, new_shape)
    if save_success:
        print("✅ 碰撞形状修改成功")
    else:
        print("❌ 碰撞形状修改失败")
        return
    
    # 4. 保存地图
    print("\n4. 保存地图...")
    map_save_success = map_model.save(map_path)
    if map_save_success:
        print("✅ 地图保存成功")
    else:
        print("❌ 地图保存失败")
        return
    
    # 5. 重新加载地图
    print("\n5. 重新加载地图...")
    map_model2 = MapDataModel()
    reload_success = map_model2.load(map_path)
    
    if not reload_success:
        print("❌ 重新加载失败")
        return
    
    print("✅ 重新加载成功")
    
    # 6. 检查重新加载的数据
    print("\n6. 检查重新加载的数据...")
    reloaded_shape = map_model2.get_tile_collision_shape(1, 0)
    print(f"重新加载的碰撞形状: {reloaded_shape}")
    
    # 7. 验证数据一致性
    print("\n7. 验证数据一致性...")
    if new_shape == reloaded_shape:
        print("✅ 测试通过：碰撞形状修改后保存成功")
    else:
        print("❌ 测试失败：碰撞形状未正确保存")
    
    print("\n" + "=" * 80)
    print("✅ 测试完成！")

if __name__ == "__main__":
    test_autosave()
