import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from models.map_model import MapDataModel

def test_map_switch_scenario():
    """测试用户编辑碰撞形状后切换页面再重新进入的场景"""
    print("=== 测试地图切换场景 ===")
    
    # 测试地图路径
    map_path = "/Users/amixc/Desktop/IDEtest/Test/assets/maps/地图1/地图1.info"
    
    # 1. 第一次加载地图（模拟用户双击进入）
    print("\n1. 第一次加载地图（模拟用户双击进入）...")
    map_model1 = MapDataModel()
    success = map_model1.load(map_path)
    
    if not success:
        print("❌ 加载地图失败")
        return
    
    print("✅ 加载地图成功")
    
    # 2. 检查初始碰撞形状
    print("\n2. 检查初始碰撞形状...")
    tile_sets = map_model1.get_tile_sets()
    for i, tile_set in enumerate(tile_sets):
        print(f"瓦片集 {i}: {tile_set.get('name')}")
        tiles = tile_set.get('tiles', [])
        for j, tile in enumerate(tiles):
            collision_shape = tile.get('collision_shape')
            if collision_shape:
                print(f"  瓦片 {j} 碰撞形状: {collision_shape}")
            else:
                print(f"  瓦片 {j} 无碰撞形状")
    
    # 3. 模拟用户编辑碰撞形状
    print("\n3. 模拟用户编辑碰撞形状...")
    # 编辑第一个图块
    resource_index1 = 0
    tile_index1 = 0
    new_shape1 = {
        "points": [[0, 0], [32, 0], [32, 32], [0, 32]]  # 矩形
    }
    print(f"编辑瓦片集 {resource_index1} 瓦片 {tile_index1} 的碰撞形状为: {new_shape1}")
    map_model1.set_tile_collision_shape(resource_index1, tile_index1, new_shape1)
    
    # 编辑第二个图块
    resource_index2 = 1
    tile_index2 = 0
    new_shape2 = {
        "points": [[8, 8], [24, 8], [24, 24], [8, 24]]  # 中心矩形
    }
    print(f"编辑瓦片集 {resource_index2} 瓦片 {tile_index2} 的碰撞形状为: {new_shape2}")
    map_model1.set_tile_collision_shape(resource_index2, tile_index2, new_shape2)
    
    # 4. 模拟用户保存并切换到代码编辑页面
    print("\n4. 模拟用户保存并切换页面...")
    save_success = map_model1.save(map_path)
    if save_success:
        print("✅ 保存成功")
    else:
        print("❌ 保存失败")
        return
    
    # 5. 模拟用户再次双击地图卡片进入编辑器
    print("\n5. 模拟用户再次双击地图卡片进入编辑器...")
    map_model2 = MapDataModel()
    reload_success = map_model2.load(map_path)
    
    if not reload_success:
        print("❌ 重新加载地图失败")
        return
    
    print("✅ 重新加载地图成功")
    
    # 6. 检查重新加载的碰撞形状
    print("\n6. 检查重新加载的碰撞形状...")
    tile_sets2 = map_model2.get_tile_sets()
    all_match = True
    
    for i, tile_set in enumerate(tile_sets2):
        print(f"瓦片集 {i}: {tile_set.get('name')}")
        tiles = tile_set.get('tiles', [])
        for j, tile in enumerate(tiles):
            collision_shape = tile.get('collision_shape')
            if collision_shape:
                print(f"  瓦片 {j} 碰撞形状: {collision_shape}")
                
                # 验证数据
                if i == resource_index1 and j == tile_index1:
                    if collision_shape != new_shape1:
                        print(f"❌ 瓦片集 {i} 瓦片 {j} 数据不一致！")
                        print(f"期望: {new_shape1}")
                        print(f"实际: {collision_shape}")
                        all_match = False
                elif i == resource_index2 and j == tile_index2:
                    if collision_shape != new_shape2:
                        print(f"❌ 瓦片集 {i} 瓦片 {j} 数据不一致！")
                        print(f"期望: {new_shape2}")
                        print(f"实际: {collision_shape}")
                        all_match = False
            else:
                print(f"  瓦片 {j} 无碰撞形状")
    
    if all_match:
        print("\n✅ 所有数据一致！保存和加载成功")
    else:
        print("\n❌ 数据不一致！保存和加载失败")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_map_switch_scenario()
