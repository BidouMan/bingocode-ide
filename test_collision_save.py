import os
import sys
import struct

# 添加项目根目录到路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from models.map_model import MapDataModel

def read_resources_file(file_path):
    """读取 .resources 文件的内容"""
    try:
        with open(file_path, 'rb') as f:
            # 读取文件头
            magic = f.read(4).decode('utf-8')
            version = struct.unpack('I', f.read(4))[0]
            print(f"文件头: magic={magic}, version={version}")
            
            # 读取瓦片集数量
            tile_set_count = struct.unpack('I', f.read(4))[0]
            print(f"瓦片集数量: {tile_set_count}")
            
            for i in range(tile_set_count):
                # 读取瓦片集名称长度和名称
                name_length = struct.unpack('I', f.read(4))[0]
                name = f.read(name_length).decode('utf-8')
                
                # 读取图像路径长度和路径
                path_length = struct.unpack('I', f.read(4))[0]
                path = f.read(path_length).decode('utf-8')
                
                # 读取瓦片集信息
                tile_width = struct.unpack('I', f.read(4))[0]
                tile_height = struct.unpack('I', f.read(4))[0]
                tile_count = struct.unpack('I', f.read(4))[0]
                
                print(f"\n瓦片集 {i}: {name}")
                print(f"  路径: {path}")
                print(f"  瓦片尺寸: {tile_width}x{tile_height}")
                print(f"  瓦片数量: {tile_count}")
                
                # 读取每个瓦片的碰撞形状
                for j in range(tile_count):
                    # 读取碰撞形状类型
                    shape_type = struct.unpack('I', f.read(4))[0]
                    
                    if shape_type == 1:  # 自定义多边形
                        # 读取顶点数量
                        point_count = struct.unpack('I', f.read(4))[0]
                        # 读取顶点坐标
                        points = []
                        for _ in range(point_count):
                            x = struct.unpack('f', f.read(4))[0]
                            y = struct.unpack('f', f.read(4))[0]
                            points.append([x, y])
                        print(f"  瓦片 {j} 碰撞形状: {points}")
                    else:
                        print(f"  瓦片 {j} 无碰撞形状")
        return True
    except Exception as e:
        print(f"读取文件错误: {e}")
        return False

def test_collision_save():
    """测试碰撞信息的保存和读取"""
    print("=== 测试碰撞信息保存和读取 ===")
    
    # 测试地图路径
    map_path = "/Users/amixc/Desktop/IDEtest/Test/assets/maps/地图1/地图1.info"
    resources_path = "/Users/amixc/Desktop/IDEtest/Test/assets/maps/地图1/地图1.resources"
    
    print(f"测试地图路径: {map_path}")
    print(f"资源文件路径: {resources_path}")
    print("=" * 80)
    
    # 1. 初始读取文件内容
    print("\n1. 初始读取资源文件内容...")
    read_resources_file(resources_path)
    
    # 2. 加载地图
    print("\n2. 加载地图...")
    map_model = MapDataModel()
    success = map_model.load(map_path)
    
    if not success:
        print("❌ 加载地图失败")
        return
    
    print("✅ 加载地图成功")
    
    # 3. 检查初始碰撞信息
    print("\n3. 检查初始碰撞信息...")
    tile_sets = map_model.get_tile_sets()
    for i, tile_set in enumerate(tile_sets):
        print(f"瓦片集 {i}: {tile_set.get('name')}")
        tiles = tile_set.get('tiles', [])
        for j, tile in enumerate(tiles):
            collision_shape = tile.get('collision_shape')
            if collision_shape:
                print(f"  瓦片 {j} 碰撞形状: {collision_shape}")
            else:
                print(f"  瓦片 {j} 无碰撞形状")
    
    # 4. 编辑碰撞形状（模拟用户操作）
    print("\n4. 编辑碰撞形状...")
    # 找到 'map_1' 瓦片集
    map1_index = -1
    for i, tile_set in enumerate(tile_sets):
        if tile_set.get('name') == 'map_1.png':
            map1_index = i
            break
    
    if map1_index != -1:
        # 编辑碰撞形状为1/4高度
        new_shape = {
            "points": [[0, 0], [32, 0], [32, 8], [0, 8]]  # 1/4高度
        }
        print(f"编辑 'map_1' 瓦片集的碰撞形状为: {new_shape}")
        map_model.set_tile_collision_shape(map1_index, 0, new_shape)
        print("✅ 编辑碰撞形状成功")
    else:
        print("❌ 未找到 'map_1' 瓦片集")
        return
    
    # 5. 保存地图
    print("\n5. 保存地图...")
    save_success = map_model.save(map_path)
    if save_success:
        print("✅ 保存成功")
    else:
        print("❌ 保存失败")
        return
    
    # 6. 重新读取文件内容
    print("\n6. 保存后读取资源文件内容...")
    read_resources_file(resources_path)
    
    # 7. 重新加载地图
    print("\n7. 重新加载地图...")
    map_model2 = MapDataModel()
    reload_success = map_model2.load(map_path)
    
    if not reload_success:
        print("❌ 重新加载失败")
        return
    
    print("✅ 重新加载成功")
    
    # 8. 检查重新加载的碰撞信息
    print("\n8. 检查重新加载的碰撞信息...")
    tile_sets2 = map_model2.get_tile_sets()
    for i, tile_set in enumerate(tile_sets2):
        print(f"瓦片集 {i}: {tile_set.get('name')}")
        tiles = tile_set.get('tiles', [])
        for j, tile in enumerate(tiles):
            collision_shape = tile.get('collision_shape')
            if collision_shape:
                print(f"  瓦片 {j} 碰撞形状: {collision_shape}")
            else:
                print(f"  瓦片 {j} 无碰撞形状")
    
    # 9. 验证数据一致性
    print("\n9. 验证数据一致性...")
    if map1_index != -1:
        reloaded_shape = map_model2.get_tile_collision_shape(map1_index, 0)
        if reloaded_shape == new_shape:
            print("✅ 数据一致！保存和加载成功")
        else:
            print("❌ 数据不一致！")
            print(f"期望: {new_shape}")
            print(f"实际: {reloaded_shape}")
    
    print("\n" + "=" * 80)
    print("✅ 测试完成！")

if __name__ == "__main__":
    test_collision_save()
