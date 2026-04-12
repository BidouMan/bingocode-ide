import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from models.map_model import MapDataModel

def test_collision_reset():
    """测试碰撞锚点的重置和保存功能"""
    print("=== 测试碰撞锚点重置和保存功能 ===")
    
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
    
    # 2. 重置碰撞锚点为默认状态（全高度）
    print("\n2. 重置碰撞锚点为默认状态...")
    # 找到 'map_1' 瓦片集
    map1_index = -1
    tile_sets = map_model.get_tile_sets()
    for i, tile_set in enumerate(tile_sets):
        if tile_set.get('name') == 'map_1.png':
            map1_index = i
            break
    
    if map1_index != -1:
        # 重置为全高度
        default_shape = {
            "points": [[0, 0], [32, 0], [32, 32], [0, 32]]  # 全高度
        }
        print(f"重置 'map_1.png' 的碰撞锚点为: {default_shape}")
        map_model.set_tile_collision_shape(map1_index, 0, default_shape)
        print("✅ 重置碰撞锚点成功")
    else:
        print("❌ 未找到 'map_1.png' 瓦片集")
        return
    
    # 3. 保存重置后的数据
    print("\n3. 保存重置后的数据...")
    save_success = map_model.save(map_path)
    if save_success:
        print("✅ 保存成功")
    else:
        print("❌ 保存失败")
        return
    
    # 4. 重新加载地图并记录初始数据
    print("\n4. 重新加载地图并记录初始数据...")
    map_model2 = MapDataModel()
    reload_success = map_model2.load(map_path)
    
    if not reload_success:
        print("❌ 重新加载失败")
        return
    
    print("✅ 重新加载成功")
    
    # 记录初始碰撞数据
    initial_data = {}
    tile_sets2 = map_model2.get_tile_sets()
    for i, tile_set in enumerate(tile_sets2):
        tile_set_name = tile_set.get('name')
        initial_data[tile_set_name] = {}
        tiles = tile_set.get('tiles', [])
        for j, tile in enumerate(tiles):
            collision_shape = tile.get('collision_shape')
            initial_data[tile_set_name][j] = collision_shape
            print(f"  瓦片集 {i} ({tile_set_name}) 瓦片 {j}: {collision_shape}")
    
    # 5. 模拟鼠标操作修改碰撞锚点为1/4高度
    print("\n5. 模拟鼠标操作修改碰撞锚点...")
    if map1_index != -1:
        # 模拟鼠标拖拽修改碰撞锚点为1/4高度
        new_shape = {
            "points": [[0, 0], [32, 0], [32, 8], [0, 8]]  # 1/4高度
        }
        print(f"修改 'map_1.png' 的碰撞锚点为: {new_shape}")
        map_model2.set_tile_collision_shape(map1_index, 0, new_shape)
        print("✅ 修改碰撞锚点成功")
    
    # 6. 检查修改后的数据
    print("\n6. 检查修改后的数据...")
    modified_data = {}
    tile_sets_modified = map_model2.get_tile_sets()
    for i, tile_set in enumerate(tile_sets_modified):
        tile_set_name = tile_set.get('name')
        modified_data[tile_set_name] = {}
        tiles = tile_set.get('tiles', [])
        for j, tile in enumerate(tiles):
            collision_shape = tile.get('collision_shape')
            modified_data[tile_set_name][j] = collision_shape
            print(f"  瓦片集 {i} ({tile_set_name}) 瓦片 {j}: {collision_shape}")
    
    # 7. 保存地图
    print("\n7. 保存地图...")
    save_success2 = map_model2.save(map_path)
    if save_success2:
        print("✅ 保存成功")
    else:
        print("❌ 保存失败")
        return
    
    # 8. 重新加载地图
    print("\n8. 重新加载地图...")
    map_model3 = MapDataModel()
    reload_success2 = map_model3.load(map_path)
    
    if not reload_success2:
        print("❌ 重新加载失败")
        return
    
    print("✅ 重新加载成功")
    
    # 9. 检查重新加载的数据
    print("\n9. 检查重新加载的数据...")
    reloaded_data = {}
    tile_sets_reloaded = map_model3.get_tile_sets()
    for i, tile_set in enumerate(tile_sets_reloaded):
        tile_set_name = tile_set.get('name')
        reloaded_data[tile_set_name] = {}
        tiles = tile_set.get('tiles', [])
        for j, tile in enumerate(tiles):
            collision_shape = tile.get('collision_shape')
            reloaded_data[tile_set_name][j] = collision_shape
            print(f"  瓦片集 {i} ({tile_set_name}) 瓦片 {j}: {collision_shape}")
    
    # 10. 验证数据变化
    print("\n10. 验证数据变化...")
    map1_initial = initial_data.get('map_1.png', {}).get(0)
    map1_modified = modified_data.get('map_1.png', {}).get(0)
    map1_reloaded = reloaded_data.get('map_1.png', {}).get(0)
    
    print(f"初始 'map_1.png' 碰撞锚点: {map1_initial}")
    print(f"修改后 'map_1.png' 碰撞锚点: {map1_modified}")
    print(f"重新加载 'map_1.png' 碰撞锚点: {map1_reloaded}")
    
    # 检查数据是否真正保存
    if map1_initial != map1_modified:
        print("✅ 修改成功：碰撞锚点已发生变化")
    else:
        print("❌ 修改失败：碰撞锚点未发生变化")
    
    if map1_modified == map1_reloaded:
        print("✅ 保存成功：重新加载的数据与修改后的数据一致")
    else:
        print("❌ 保存失败：重新加载的数据与修改后的数据不一致")
    
    # 11. 最终验证
    print("\n11. 最终验证...")
    if map1_initial != map1_reloaded:
        print("✅ 测试通过：碰撞锚点确实被修改并保存")
    else:
        print("❌ 测试失败：碰撞锚点未被保存")
    
    print("\n" + "=" * 80)
    print("✅ 测试完成！")

if __name__ == "__main__":
    test_collision_reset()
