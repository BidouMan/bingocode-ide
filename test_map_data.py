import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from models.map_model import MapDataModel

def test_map_data_consistency():
    """测试地图数据的一致性：加载、修改、保存、重新加载"""
    print("=== 开始测试地图数据一致性 ===")
    
    # 测试地图路径
    map_path = "/Users/amixc/Desktop/IDEtest/Test/assets/maps/地图1/地图1.info"
    
    # 1. 第一次加载地图
    print("\n1. 第一次加载地图...")
    map_model = MapDataModel()
    success = map_model.load(map_path)
    
    if not success:
        print("❌ 加载地图失败")
        return
    
    print("✅ 加载地图成功")
    print(f"地图名称: {map_model.get_map_name()}")
    print(f"地图尺寸: {map_model.get_map_size()}")
    print(f"瓦片大小: {map_model.get_tile_size()}")
    print(f"瓦片集数量: {len(map_model.get_tile_sets())}")
    
    # 检查碰撞形状数据
    tile_sets = map_model.get_tile_sets()
    for i, tile_set in enumerate(tile_sets):
        print(f"\n瓦片集 {i}: {tile_set.get('name')}")
        print(f"  图片路径: {tile_set.get('image_path')}")
        print(f"  瓦片数量: {len(tile_set.get('tiles', []))}")
        
        # 检查每个瓦片的碰撞形状
        tiles = tile_set.get('tiles', [])
        for j, tile in enumerate(tiles):
            collision_shape = tile.get('collision_shape')
            if collision_shape:
                print(f"  瓦片 {j} 碰撞形状: {collision_shape}")
            else:
                print(f"  瓦片 {j} 无碰撞形状")
    
    # 2. 修改碰撞形状数据
    print("\n2. 修改碰撞形状数据...")
    if tile_sets:
        # 选择第一个瓦片集的第一个瓦片
        tile_set_index = 0
        tile_index = 0
        
        # 创建一个新的碰撞形状
        new_shape = {
            "points": [[0, 0], [16, 0], [16, 16], [0, 16]]  # 矩形
        }
        
        print(f"修改瓦片集 {tile_set_index} 瓦片 {tile_index} 的碰撞形状为: {new_shape}")
        success = map_model.set_tile_collision_shape(tile_set_index, tile_index, new_shape)
        if success:
            print("✅ 修改成功")
        else:
            print("❌ 修改失败")
    
    # 3. 保存地图
    print("\n3. 保存地图...")
    save_success = map_model.save(map_path)
    if save_success:
        print("✅ 保存成功")
    else:
        print("❌ 保存失败")
    
    # 4. 重新加载地图
    print("\n4. 重新加载地图...")
    map_model2 = MapDataModel()
    reload_success = map_model2.load(map_path)
    
    if not reload_success:
        print("❌ 重新加载地图失败")
        return
    
    print("✅ 重新加载地图成功")
    
    # 5. 比较数据
    print("\n5. 比较修改前后的数据...")
    tile_sets2 = map_model2.get_tile_sets()
    
    if tile_sets and tile_sets2:
        tile_set_index = 0
        tile_index = 0
        
        # 获取修改后的数据
        if tile_set_index < len(tile_sets2):
            tile_set2 = tile_sets2[tile_set_index]
            tiles2 = tile_set2.get('tiles', [])
            
            if tile_index < len(tiles2):
                tile2 = tiles2[tile_index]
                loaded_shape = tile2.get('collision_shape')
                print(f"加载后的碰撞形状: {loaded_shape}")
                
                # 比较
                if loaded_shape == new_shape:
                    print("✅ 数据一致！保存和加载成功")
                else:
                    print("❌ 数据不一致！保存和加载失败")
                    print(f"期望: {new_shape}")
                    print(f"实际: {loaded_shape}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_map_data_consistency()
