import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from models.map_model import MapDataModel

def test_page_switch():
    """测试页面切换时的数据状态和碰撞信息读取"""
    print("=== 测试页面切换和碰撞信息读取 ===")
    
    # 测试地图路径
    map_path = "/Users/amixc/Desktop/IDEtest/Test/assets/maps/地图1/地图1.info"
    
    # 1. 第一次加载地图（模拟进入地图编辑器）
    print("\n1. 模拟进入地图编辑器...")
    map_model = MapDataModel()
    success = map_model.load(map_path)
    
    if not success:
        print("❌ 加载地图失败")
        return
    
    print("✅ 加载地图成功")
    
    # 2. 检查初始碰撞信息
    print("\n2. 检查初始碰撞信息...")
    tile_sets = map_model.get_tile_sets()
    initial_collisions = {}
    
    for i, tile_set in enumerate(tile_sets):
        print(f"瓦片集 {i}: {tile_set.get('name')}")
        tiles = tile_set.get('tiles', [])
        for j, tile in enumerate(tiles):
            collision_shape = tile.get('collision_shape')
            if collision_shape:
                print(f"  瓦片 {j} 碰撞形状: {collision_shape}")
                initial_collisions[(i, j)] = collision_shape
            else:
                print(f"  瓦片 {j} 无碰撞形状")
    
    # 3. 模拟用户编辑碰撞形状
    print("\n3. 模拟用户编辑碰撞形状...")
    resource_index = 0
    tile_index = 0
    new_shape = {
        "points": [[2, 2], [30, 2], [30, 30], [2, 30]]  # 新的矩形
    }
    
    print(f"编辑瓦片集 {resource_index} 瓦片 {tile_index} 的碰撞形状为: {new_shape}")
    map_model.set_tile_collision_shape(resource_index, tile_index, new_shape)
    print("✅ 更新碰撞形状成功")
    
    # 4. 模拟用户保存
    print("\n4. 模拟用户保存...")
    save_success = map_model.save(map_path)
    if save_success:
        print("✅ 保存成功")
    else:
        print("❌ 保存失败")
        return
    
    # 5. 模拟切换到精灵编辑器页面
    print("\n5. 模拟切换到精灵编辑器页面...")
    print("用户点击 btn_sprite_editor 按钮")
    
    # 6. 模拟切换回地图编辑器页面
    print("\n6. 模拟切换回地图编辑器页面...")
    print("用户点击 btn_map_editor 按钮")
    
    # 7. 模拟在 list_map 中选择地图1
    print("\n7. 模拟在 list_map 中选择地图1...")
    # 重新加载地图
    map_model2 = MapDataModel()
    reload_success = map_model2.load(map_path)
    
    if not reload_success:
        print("❌ 重新加载地图失败")
        return
    
    print("✅ 重新加载地图成功")
    
    # 8. 检查重新加载后的碰撞信息
    print("\n8. 检查重新加载后的碰撞信息...")
    tile_sets2 = map_model2.get_tile_sets()
    reload_collisions = {}
    
    for i, tile_set in enumerate(tile_sets2):
        print(f"瓦片集 {i}: {tile_set.get('name')}")
        tiles = tile_set.get('tiles', [])
        for j, tile in enumerate(tiles):
            collision_shape = tile.get('collision_shape')
            if collision_shape:
                print(f"  瓦片 {j} 碰撞形状: {collision_shape}")
                reload_collisions[(i, j)] = collision_shape
            else:
                print(f"  瓦片 {j} 无碰撞形状")
    
    # 9. 验证数据一致性
    print("\n9. 验证数据一致性...")
    # 检查修改的瓦片
    modified_key = (resource_index, tile_index)
    if modified_key in reload_collisions:
        if reload_collisions[modified_key] == new_shape:
            print("✅ 修改的瓦片碰撞形状正确")
        else:
            print("❌ 修改的瓦片碰撞形状不一致")
            print(f"期望: {new_shape}")
            print(f"实际: {reload_collisions[modified_key]}")
    else:
        print("❌ 修改的瓦片碰撞形状未找到")
    
    # 10. 模拟点击 res_view_list 中的图块
    print("\n10. 模拟点击 res_view_list 中的图块...")
    # 测试获取碰撞信息
    for i, tile_set in enumerate(tile_sets2):
        for j, tile in enumerate(tile_set.get('tiles', [])):
            # 模拟点击图块
            print(f"点击瓦片集 {i} 瓦片 {j}")
            # 获取碰撞形状
            collision_shape = map_model2.get_tile_collision_shape(i, j)
            if collision_shape:
                print(f"  读取到的碰撞形状: {collision_shape}")
            else:
                print(f"  无碰撞形状")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_page_switch()
