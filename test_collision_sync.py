import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from models.map_model import MapDataModel

def test_collision_data_sync():
    """测试碰撞形状数据同步"""
    print("=== 测试碰撞形状数据同步 ===")
    
    # 测试地图路径
    map_path = "/Users/amixc/Desktop/IDEtest/Test/assets/maps/地图1/地图1.info"
    
    # 1. 加载地图
    print("\n1. 加载地图...")
    map_model = MapDataModel()
    success = map_model.load(map_path)
    
    if not success:
        print("❌ 加载地图失败")
        return
    
    print("✅ 加载地图成功")
    
    # 2. 模拟 MapEditorManager 初始化
    print("\n2. 初始化 MapEditorManager 模拟环境...")
    uploaded_resources = []
    tile_sets = map_model.get_tile_sets()
    map_dir = os.path.dirname(map_path)
    
    for i, tile_set in enumerate(tile_sets):
        resource_name = tile_set.get("name")
        image_path = tile_set.get("image_path")
        tile_width = tile_set.get("tile_width", 32)
        tile_height = tile_set.get("tile_height", 32)
        
        # 初始化资源信息
        resource_info = {
            "name": resource_name,
            "path": "",
            "resource_type": "tileset",
            "tile_width": tile_width,
            "tile_height": tile_height,
            "tile_size": tile_width,
            "width": tile_width,
            "height": tile_height,
            "frames": 1,
            "collisions": []
        }
        
        # 从 tile_set 中获取碰撞形状数据
        tiles_data = tile_set.get("tiles", [])
        for j, tile_data in enumerate(tiles_data):
            # 确保 collisions 数组足够大
            while len(resource_info["collisions"]) <= j:
                resource_info["collisions"].append({})
            # 保存碰撞形状数据
            if "collision_shape" in tile_data and tile_data["collision_shape"]:
                resource_info["collisions"][j]["points"] = tile_data["collision_shape"].get("points", [])
        
        # 处理图片路径
        if image_path:
            if not os.path.isabs(image_path):
                image_path = os.path.join(map_dir, image_path)
            if os.path.exists(image_path):
                resource_info["path"] = os.path.relpath(image_path, map_dir)
        
        uploaded_resources.append(resource_info)
    
    # 3. 模拟选择图块（触发同步）
    print("\n3. 模拟选择图块...")
    resource_index = 0
    tile_index = 0
    
    # 模拟 select_tile 方法的同步逻辑
    resource_info = uploaded_resources[resource_index]
    
    # 确保资源的碰撞数据结构存在
    if 'collisions' not in resource_info:
        resource_info['collisions'] = []
    # 确保collisions数组足够大
    while len(resource_info['collisions']) <= tile_index:
        resource_info['collisions'].append({})
    
    # 从地图模型获取最新的碰撞形状数据
    collision_shape = map_model.get_tile_collision_shape(resource_index, tile_index)
    if collision_shape and 'points' in collision_shape:
        resource_info['collisions'][tile_index]['points'] = collision_shape['points']
        print(f"✅ 从地图模型同步碰撞形状数据: {collision_shape}")
    
    # 4. 模拟修改碰撞形状
    print("\n4. 模拟修改碰撞形状...")
    new_shape = {
        "points": [[0, 0], [32, 0], [32, 32], [0, 32]]
    }
    
    # 更新 map_model
    map_model.set_tile_collision_shape(resource_index, tile_index, new_shape)
    print(f"✅ 更新 map_model 中的碰撞形状: {new_shape}")
    
    # 模拟碰撞编辑器中的同步逻辑
    if 'collisions' not in resource_info:
        resource_info['collisions'] = []
    while len(resource_info['collisions']) <= tile_index:
        resource_info['collisions'].append({})
    resource_info['collisions'][tile_index]['points'] = new_shape['points']
    print(f"✅ 同步更新 uploaded_resources 中的碰撞形状: {new_shape['points']}")
    
    # 5. 验证数据一致性
    print("\n5. 验证数据一致性...")
    # 从 map_model 获取数据
    model_shape = map_model.get_tile_collision_shape(resource_index, tile_index)
    # 从 uploaded_resources 获取数据
    uploaded_shape = resource_info['collisions'][tile_index].get('points', [])
    
    print(f"map_model 中的碰撞形状: {model_shape}")
    print(f"uploaded_resources 中的碰撞形状: {uploaded_shape}")
    
    if model_shape['points'] == uploaded_shape:
        print("✅ 数据一致！同步成功")
    else:
        print("❌ 数据不一致！同步失败")
    
    # 6. 模拟保存和重新加载
    print("\n6. 模拟保存和重新加载...")
    # 保存地图
    save_success = map_model.save(map_path)
    if save_success:
        print("✅ 保存成功")
    else:
        print("❌ 保存失败")
    
    # 重新加载
    map_model2 = MapDataModel()
    reload_success = map_model2.load(map_path)
    if reload_success:
        print("✅ 重新加载成功")
        # 验证重新加载的数据
        reloaded_shape = map_model2.get_tile_collision_shape(resource_index, tile_index)
        print(f"重新加载的碰撞形状: {reloaded_shape}")
        
        if reloaded_shape == new_shape:
            print("✅ 重新加载的数据正确！")
        else:
            print("❌ 重新加载的数据错误！")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_collision_data_sync()
