import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from models.map_model import MapDataModel

def test_map_editor_manager_behavior():
    """模拟 MapEditorManager 的行为，测试数据同步问题"""
    print("=== 测试 MapEditorManager 行为 ===")
    
    # 测试地图路径
    map_path = "/Users/amixc/Desktop/IDEtest/Test/assets/maps/地图1/地图1.info"
    
    # 1. 模拟 MapEditorManager 加载地图
    print("\n1. 模拟 MapEditorManager 加载地图...")
    map_model = MapDataModel()
    success = map_model.load(map_path)
    
    if not success:
        print("❌ 加载地图失败")
        return
    
    print("✅ 加载地图成功")
    
    # 2. 模拟 MapEditorManager 初始化 uploaded_resources
    print("\n2. 模拟初始化 uploaded_resources...")
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
                print(f"DEBUG: 加载碰撞形状数据 - 资源索引: {i}, 图块索引: {j}, 形状: {tile_data['collision_shape']}")
        
        # 处理图片路径
        if image_path:
            if not os.path.isabs(image_path):
                image_path = os.path.join(map_dir, image_path)
            if os.path.exists(image_path):
                resource_info["path"] = os.path.relpath(image_path, map_dir)
                print(f"✅ 加载资源: {resource_name} | 路径: {resource_info['path']}")
        
        uploaded_resources.append(resource_info)
        print(f"DEBUG: 资源 {i} 加载完成: {resource_info['name']}, 索引: {i}")
    
    # 3. 检查 uploaded_resources 中的碰撞数据
    print("\n3. 检查 uploaded_resources 中的碰撞数据...")
    for i, resource in enumerate(uploaded_resources):
        print(f"资源 {i}: {resource['name']}")
        collisions = resource.get('collisions', [])
        for j, collision in enumerate(collisions):
            points = collision.get('points', [])
            print(f"  图块 {j} 碰撞点: {points}")
    
    # 4. 模拟用户在碰撞编辑器中修改碰撞形状
    print("\n4. 模拟修改碰撞形状...")
    # 假设用户修改了第一个资源的第一个图块
    if uploaded_resources:
        resource_index = 0
        tile_index = 0
        
        # 创建新的碰撞形状
        new_shape = {
            "points": [[0, 0], [32, 0], [32, 32], [0, 32]]  # 更大的矩形
        }
        
        # 1. 更新 map_model
        print(f"修改 map_model 中的碰撞形状: {new_shape}")
        map_model.set_tile_collision_shape(resource_index, tile_index, new_shape)
        
        # 2. 检查 map_model 是否更新
        updated_shape = map_model.get_tile_collision_shape(resource_index, tile_index)
        print(f"map_model 中的碰撞形状: {updated_shape}")
        
        # 3. 但是 uploaded_resources 没有更新！
        print(f"uploaded_resources 中的碰撞形状: {uploaded_resources[resource_index]['collisions'][tile_index].get('points', [])}")
    
    # 5. 模拟保存地图
    print("\n5. 模拟保存地图...")
    save_success = map_model.save(map_path)
    if save_success:
        print("✅ 保存成功")
    else:
        print("❌ 保存失败")
    
    # 6. 模拟重新加载地图
    print("\n6. 模拟重新加载地图...")
    map_model2 = MapDataModel()
    reload_success = map_model2.load(map_path)
    
    if reload_success:
        print("✅ 重新加载成功")
        # 检查重新加载的数据
        tile_sets2 = map_model2.get_tile_sets()
        if tile_sets2:
            resource_index = 0
            tile_index = 0
            loaded_shape = map_model2.get_tile_collision_shape(resource_index, tile_index)
            print(f"重新加载的碰撞形状: {loaded_shape}")
    
    # 7. 分析问题
    print("\n7. 问题分析...")
    print("❌ 发现问题：MapEditorManager 中的 uploaded_resources 与 map_model 不同步！")
    print("   - 当用户在碰撞编辑器中修改碰撞形状时，只会更新 map_model")
    print("   - 但 uploaded_resources 中的数据没有同步更新")
    print("   - 当用户保存地图时，数据是从 map_model 读取的，所以保存是正确的")
    print("   - 但当用户再次打开地图时，MapEditorManager 会重新从文件加载数据到 uploaded_resources")
    print("   - 这可能导致用户看到的是旧数据，因为 uploaded_resources 没有与 map_model 同步")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_map_editor_manager_behavior()
