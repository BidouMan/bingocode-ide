import os
import sys
import random

# 添加项目根目录到路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from models.map_model import MapDataModel

def generate_random_shape(tile_size=32):
    """生成随机碰撞形状"""
    # 生成4-8个随机点
    point_count = random.randint(4, 8)
    points = []
    
    for _ in range(point_count):
        x = random.uniform(0, tile_size)
        y = random.uniform(0, tile_size)
        points.append([x, y])
    
    return {"points": points}

def test_collision_stress():
    """压力测试：多次修改和保存碰撞形状"""
    print("=== 碰撞形状压力测试 ===")
    
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
    
    # 2. 压力测试参数
    test_count = 10  # 测试次数
    resource_index = 0
    tile_index = 0
    
    print(f"\n2. 开始压力测试，共 {test_count} 次修改和保存...")
    
    for i in range(test_count):
        print(f"\n=== 测试 {i+1}/{test_count} ===")
        
        # 3. 生成随机碰撞形状
        random_shape = generate_random_shape(32)
        print(f"生成随机碰撞形状: {random_shape}")
        
        # 4. 更新 map_model
        map_model.set_tile_collision_shape(resource_index, tile_index, random_shape)
        print("✅ 更新 map_model 成功")
        
        # 5. 保存地图
        save_success = map_model.save(map_path)
        if save_success:
            print("✅ 保存成功")
        else:
            print("❌ 保存失败")
            return
        
        # 6. 重新加载地图
        map_model2 = MapDataModel()
        reload_success = map_model2.load(map_path)
        if reload_success:
            print("✅ 重新加载成功")
        else:
            print("❌ 重新加载失败")
            return
        
        # 7. 验证数据
        reloaded_shape = map_model2.get_tile_collision_shape(resource_index, tile_index)
        print(f"重新加载的碰撞形状: {reloaded_shape}")
        
        # 比较数据（考虑浮点数精度）
        points1 = random_shape['points']
        points2 = reloaded_shape['points']
        
        if len(points1) == len(points2):
            match = True
            for p1, p2 in zip(points1, points2):
                if abs(p1[0] - p2[0]) > 0.001 or abs(p1[1] - p2[1]) > 0.001:
                    match = False
                    break
            
            if match:
                print("✅ 数据一致！")
            else:
                print("❌ 数据不一致！")
                print(f"期望: {points1}")
                print(f"实际: {points2}")
                return
        else:
            print("❌ 数据点数量不一致！")
            return
        
        # 8. 使用新加载的模型进行下一次测试
        map_model = map_model2
    
    print("\n=== 压力测试完成 ===")
    print("✅ 所有测试通过！碰撞形状数据保存和加载正常。")

if __name__ == "__main__":
    test_collision_stress()
