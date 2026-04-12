import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from models.map_model import MapDataModel

def test_comprehensive():
    """综合测试地图数据处理"""
    print("=== 综合测试地图数据处理 ===")
    
    # 测试地图路径
    map_path = "/Users/amixc/Desktop/IDEtest/Test/assets/maps/地图1/地图1.info"
    
    print(f"测试地图路径: {map_path}")
    print("=" * 80)
    
    # 1. 初始加载测试
    print("\n1. 初始加载测试...")
    map_model1 = MapDataModel()
    success = map_model1.load(map_path)
    
    if not success:
        print("❌ 初始加载失败")
        return
    
    print("✅ 初始加载成功")
    
    # 2. 检查初始数据
    print("\n2. 检查初始数据...")
    tile_sets = map_model1.get_tile_sets()
    print(f"瓦片集数量: {len(tile_sets)}")
    
    for i, tile_set in enumerate(tile_sets):
        print(f"  瓦片集 {i}: {tile_set.get('name')}")
        tiles = tile_set.get('tiles', [])
        for j, tile in enumerate(tiles):
            collision_shape = tile.get('collision_shape')
            if collision_shape:
                print(f"    瓦片 {j} 碰撞形状: {collision_shape}")
            else:
                print(f"    瓦片 {j} 无碰撞形状")
    
    # 3. 编辑碰撞形状测试
    print("\n3. 编辑碰撞形状测试...")
    resource_index = 0
    tile_index = 0
    new_shape = {
        "points": [[1, 1], [31, 1], [31, 31], [1, 31]]  # 新的矩形
    }
    
    print(f"编辑瓦片集 {resource_index} 瓦片 {tile_index} 的碰撞形状为: {new_shape}")
    map_model1.set_tile_collision_shape(resource_index, tile_index, new_shape)
    print("✅ 编辑碰撞形状成功")
    
    # 4. 保存测试
    print("\n4. 保存测试...")
    save_success = map_model1.save(map_path)
    if save_success:
        print("✅ 保存成功")
    else:
        print("❌ 保存失败")
        return
    
    # 5. 页面切换模拟
    print("\n5. 页面切换模拟...")
    print("模拟切换到精灵编辑器页面")
    print("模拟切换回地图编辑器页面")
    
    # 6. 重新加载测试
    print("\n6. 重新加载测试...")
    map_model2 = MapDataModel()
    reload_success = map_model2.load(map_path)
    
    if not reload_success:
        print("❌ 重新加载失败")
        return
    
    print("✅ 重新加载成功")
    
    # 7. 验证重新加载的数据
    print("\n7. 验证重新加载的数据...")
    tile_sets2 = map_model2.get_tile_sets()
    reloaded_shape = None
    
    for i, tile_set in enumerate(tile_sets2):
        print(f"  瓦片集 {i}: {tile_set.get('name')}")
        tiles = tile_set.get('tiles', [])
        for j, tile in enumerate(tiles):
            collision_shape = tile.get('collision_shape')
            if collision_shape:
                print(f"    瓦片 {j} 碰撞形状: {collision_shape}")
                if i == resource_index and j == tile_index:
                    reloaded_shape = collision_shape
            else:
                print(f"    瓦片 {j} 无碰撞形状")
    
    # 8. 验证数据一致性
    print("\n8. 验证数据一致性...")
    if reloaded_shape == new_shape:
        print("✅ 数据一致！保存和加载成功")
    else:
        print("❌ 数据不一致！")
        print(f"期望: {new_shape}")
        print(f"实际: {reloaded_shape}")
    
    # 9. 测试获取碰撞形状方法
    print("\n9. 测试获取碰撞形状方法...")
    for i, tile_set in enumerate(tile_sets2):
        for j, tile in enumerate(tile_set.get('tiles', [])):
            shape = map_model2.get_tile_collision_shape(i, j)
            if shape:
                print(f"  瓦片集 {i} 瓦片 {j}: {shape}")
            else:
                print(f"  瓦片集 {i} 瓦片 {j}: 无碰撞形状")
    
    # 10. 测试第二个图块
    print("\n10. 测试第二个图块...")
    if len(tile_sets2) > 1:
        resource_index2 = 1
        tile_index2 = 0
        new_shape2 = {
            "points": [[4, 4], [28, 4], [28, 28], [4, 28]]  # 新的矩形
        }
        
        print(f"编辑瓦片集 {resource_index2} 瓦片 {tile_index2} 的碰撞形状为: {new_shape2}")
        map_model2.set_tile_collision_shape(resource_index2, tile_index2, new_shape2)
        print("✅ 编辑碰撞形状成功")
        
        # 保存
        save_success2 = map_model2.save(map_path)
        if save_success2:
            print("✅ 保存成功")
        else:
            print("❌ 保存失败")
            return
        
        # 重新加载
        map_model3 = MapDataModel()
        reload_success2 = map_model3.load(map_path)
        
        if reload_success2:
            print("✅ 重新加载成功")
            # 验证
            reloaded_shape2 = map_model3.get_tile_collision_shape(resource_index2, tile_index2)
            if reloaded_shape2 == new_shape2:
                print("✅ 第二个图块数据一致！")
            else:
                print("❌ 第二个图块数据不一致！")
                print(f"期望: {new_shape2}")
                print(f"实际: {reloaded_shape2}")
        else:
            print("❌ 重新加载失败")
            return
    
    print("\n" + "=" * 80)
    print("✅ 综合测试完成！")

if __name__ == "__main__":
    test_comprehensive()
