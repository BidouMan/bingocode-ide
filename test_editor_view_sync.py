import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from models.map_model import MapDataModel

def test_editor_view_sync():
    """测试编辑器视图数据同步"""
    print("=== 测试编辑器视图数据同步 ===")
    
    # 测试地图路径
    map_path = "/Users/amixc/Desktop/IDEtest/Test/assets/maps/地图1/地图1.info"
    
    # 1. 第一次加载地图（模拟用户双击进入）
    print("\n1. 第一次加载地图（模拟用户双击进入）...")
    map_model = MapDataModel()
    success = map_model.load(map_path)
    
    if not success:
        print("❌ 加载地图失败")
        return
    
    print("✅ 加载地图成功")
    
    # 2. 模拟编辑器视图初始化（col_editor_view）
    print("\n2. 模拟编辑器视图初始化...")
    # 模拟 uploaded_resources 数据（col_editor_view 显示的数据）
    uploaded_resources = []
    tile_sets = map_model.get_tile_sets()
    
    for i, tile_set in enumerate(tile_sets):
        resource_info = {
            "name": tile_set.get("name"),
            "resource_type": "tileset",
            "collisions": []
        }
        
        # 加载碰撞形状数据到 uploaded_resources
        tiles = tile_set.get('tiles', [])
        for j, tile in enumerate(tiles):
            # 确保 collisions 数组足够大
            while len(resource_info["collisions"]) <= j:
                resource_info["collisions"].append({})
            # 保存碰撞形状数据
            if "collision_shape" in tile and tile["collision_shape"]:
                resource_info["collisions"][j]["points"] = tile["collision_shape"].get("points", [])
        
        uploaded_resources.append(resource_info)
        print(f"编辑器视图 - 瓦片集 {i}: {resource_info['name']}")
        for j, collision in enumerate(resource_info['collisions']):
            points = collision.get('points', [])
            print(f"  瓦片 {j} 碰撞点: {points}")
    
    # 3. 模拟用户编辑碰撞形状
    print("\n3. 模拟用户编辑碰撞形状...")
    resource_index = 0
    tile_index = 0
    new_shape = {
        "points": [[0, 0], [32, 0], [32, 32], [0, 32]]
    }
    
    # 更新 map_model
    print(f"更新 map_model 中的碰撞形状: {new_shape}")
    map_model.set_tile_collision_shape(resource_index, tile_index, new_shape)
    
    # 4. 模拟用户未保存直接切换页面
    print("\n4. 模拟用户未保存直接切换页面...")
    print("⚠️  注意：用户未点击保存按钮")
    
    # 5. 模拟用户切回地图编辑器
    print("\n5. 模拟用户切回地图编辑器...")
    # 模拟编辑器视图重新初始化
    print("模拟编辑器视图重新初始化...")
    
    # 检查 uploaded_resources 中的数据（如果没有同步，这里会是旧数据）
    print("编辑器视图中的碰撞数据（未同步）:")
    resource_info = uploaded_resources[resource_index]
    old_points = resource_info['collisions'][tile_index].get('points', [])
    print(f"  瓦片 {tile_index} 碰撞点: {old_points}")
    
    # 模拟编辑器视图从 map_model 同步数据（正确的做法）
    print("\n模拟编辑器视图从 map_model 同步数据...")
    # 从 map_model 获取最新数据
    collision_shape = map_model.get_tile_collision_shape(resource_index, tile_index)
    if collision_shape and 'points' in collision_shape:
        # 更新 uploaded_resources
        while len(resource_info['collisions']) <= tile_index:
            resource_info['collisions'].append({})
        resource_info['collisions'][tile_index]['points'] = collision_shape['points']
        print(f"  同步后的碰撞点: {collision_shape['points']}")
    
    # 6. 模拟用户保存并切换页面
    print("\n6. 模拟用户保存并切换页面...")
    save_success = map_model.save(map_path)
    if save_success:
        print("✅ 保存成功")
    else:
        print("❌ 保存失败")
        return
    
    # 7. 模拟用户再次进入编辑器
    print("\n7. 模拟用户再次进入编辑器...")
    # 重新加载地图
    map_model2 = MapDataModel()
    reload_success = map_model2.load(map_path)
    
    if not reload_success:
        print("❌ 重新加载地图失败")
        return
    
    print("✅ 重新加载地图成功")
    
    # 模拟编辑器视图初始化
    print("模拟编辑器视图初始化...")
    uploaded_resources2 = []
    tile_sets2 = map_model2.get_tile_sets()
    
    for i, tile_set in enumerate(tile_sets2):
        resource_info2 = {
            "name": tile_set.get("name"),
            "resource_type": "tileset",
            "collisions": []
        }
        
        # 加载碰撞形状数据到 uploaded_resources
        tiles = tile_set.get('tiles', [])
        for j, tile in enumerate(tiles):
            # 确保 collisions 数组足够大
            while len(resource_info2["collisions"]) <= j:
                resource_info2["collisions"].append({})
            # 保存碰撞形状数据
            if "collision_shape" in tile and tile["collision_shape"]:
                resource_info2["collisions"][j]["points"] = tile["collision_shape"].get("points", [])
        
        uploaded_resources2.append(resource_info2)
        print(f"编辑器视图 - 瓦片集 {i}: {resource_info2['name']}")
        for j, collision in enumerate(resource_info2['collisions']):
            points = collision.get('points', [])
            print(f"  瓦片 {j} 碰撞点: {points}")
    
    # 8. 验证数据一致性
    print("\n8. 验证数据一致性...")
    # 从 map_model 获取数据
    model_shape = map_model2.get_tile_collision_shape(resource_index, tile_index)
    # 从 uploaded_resources 获取数据
    uploaded_shape = uploaded_resources2[resource_index]['collisions'][tile_index].get('points', [])
    
    print(f"map_model 中的碰撞形状: {model_shape}")
    print(f"编辑器视图中的碰撞形状: {uploaded_shape}")
    
    if model_shape['points'] == uploaded_shape:
        print("✅ 数据一致！编辑器视图显示正确")
    else:
        print("❌ 数据不一致！编辑器视图显示错误")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_editor_view_sync()
