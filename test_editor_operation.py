import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from models.map_model import MapDataModel

def test_editor_operation():
    """测试编辑器实际操作流程"""
    print("=== 测试编辑器实际操作流程 ===")
    
    # 测试地图路径
    map_path = "/Users/amixc/Desktop/IDEtest/Test/assets/maps/地图1/地图1.info"
    
    # 1. 模拟用户双击进入编辑器
    print("\n1. 模拟用户双击进入编辑器...")
    map_model = MapDataModel()
    success = map_model.load(map_path)
    
    if not success:
        print("❌ 加载地图失败")
        return
    
    print("✅ 加载地图成功")
    
    # 2. 模拟编辑器初始化
    print("\n2. 模拟编辑器初始化...")
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
        print(f"编辑器 - 瓦片集 {i}: {resource_info['name']}")
    
    # 3. 模拟用户选择图块（触发数据同步）
    print("\n3. 模拟用户选择图块...")
    resource_index = 0
    tile_index = 0
    
    # 模拟 collision_manager 中的选择逻辑
    print(f"选择瓦片集 {resource_index} 瓦片 {tile_index}")
    
    # 从 map_model 获取最新碰撞形状
    collision_shape = map_model.get_tile_collision_shape(resource_index, tile_index)
    print(f"从 map_model 获取碰撞形状: {collision_shape}")
    
    # 同步到 uploaded_resources
    if collision_shape and 'points' in collision_shape:
        resource_info = uploaded_resources[resource_index]
        while len(resource_info['collisions']) <= tile_index:
            resource_info['collisions'].append({})
        resource_info['collisions'][tile_index]['points'] = collision_shape['points']
        print(f"同步到 uploaded_resources: {collision_shape['points']}")
    
    # 4. 模拟用户编辑碰撞形状
    print("\n4. 模拟用户编辑碰撞形状...")
    new_shape = {
        "points": [[5, 5], [27, 5], [27, 27], [5, 27]]  # 缩小的矩形
    }
    
    # 模拟 collision_manager 中的编辑逻辑
    print(f"编辑碰撞形状为: {new_shape}")
    
    # 1. 更新 map_model
    map_model.set_tile_collision_shape(resource_index, tile_index, new_shape)
    print("✅ 更新 map_model 成功")
    
    # 2. 同步到 uploaded_resources
    resource_info = uploaded_resources[resource_index]
    while len(resource_info['collisions']) <= tile_index:
        resource_info['collisions'].append({})
    resource_info['collisions'][tile_index]['points'] = new_shape['points']
    print("✅ 同步到 uploaded_resources 成功")
    
    # 5. 模拟用户点击保存按钮
    print("\n5. 模拟用户点击保存按钮...")
    save_success = map_model.save(map_path)
    if save_success:
        print("✅ 保存成功")
    else:
        print("❌ 保存失败")
        return
    
    # 6. 模拟用户切换到代码编辑页面
    print("\n6. 模拟用户切换到代码编辑页面...")
    print("用户离开地图编辑器")
    
    # 7. 模拟用户再次双击进入编辑器
    print("\n7. 模拟用户再次双击进入编辑器...")
    map_model2 = MapDataModel()
    reload_success = map_model2.load(map_path)
    
    if not reload_success:
        print("❌ 重新加载地图失败")
        return
    
    print("✅ 重新加载地图成功")
    
    # 8. 模拟编辑器重新初始化
    print("\n8. 模拟编辑器重新初始化...")
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
        print(f"编辑器 - 瓦片集 {i}: {resource_info2['name']}")
    
    # 9. 模拟用户再次选择同一个图块
    print("\n9. 模拟用户再次选择同一个图块...")
    # 模拟 collision_manager 中的选择逻辑
    print(f"选择瓦片集 {resource_index} 瓦片 {tile_index}")
    
    # 从 map_model 获取最新碰撞形状
    collision_shape2 = map_model2.get_tile_collision_shape(resource_index, tile_index)
    print(f"从 map_model 获取碰撞形状: {collision_shape2}")
    
    # 同步到 uploaded_resources
    if collision_shape2 and 'points' in collision_shape2:
        resource_info2 = uploaded_resources2[resource_index]
        while len(resource_info2['collisions']) <= tile_index:
            resource_info2['collisions'].append({})
        resource_info2['collisions'][tile_index]['points'] = collision_shape2['points']
        print(f"同步到 uploaded_resources: {collision_shape2['points']}")
    
    # 10. 验证数据一致性
    print("\n10. 验证数据一致性...")
    # 从 map_model 获取数据
    model_shape = map_model2.get_tile_collision_shape(resource_index, tile_index)
    # 从 uploaded_resources 获取数据
    uploaded_shape = uploaded_resources2[resource_index]['collisions'][tile_index].get('points', [])
    
    print(f"map_model 中的碰撞形状: {model_shape}")
    print(f"编辑器视图中的碰撞形状: {uploaded_shape}")
    print(f"期望的碰撞形状: {new_shape}")
    
    if model_shape == new_shape and uploaded_shape == new_shape['points']:
        print("✅ 数据一致！编辑器视图显示正确")
    else:
        print("❌ 数据不一致！")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_editor_operation()
