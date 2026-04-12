import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from models.map_model import MapDataModel

def test_verify_save():
    """验证碰撞形状是否正确保存到本地文件"""
    print("=== 验证碰撞形状保存到本地文件 ===")
    
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
    
    # 2. 检查碰撞形状数据
    print("\n2. 检查碰撞形状数据...")
    tile_sets = map_model.get_tile_sets()
    
    # 从debug信息中提取的碰撞形状数据
    debug_data = {
        'brick_32.png': {
            0: {'points': [[3.160487220650827, 12.741813826669734], [30.069744922661375, 12.334097800881695], [31.0, 31.0], [1.0, 31.0]}
        },
        'map_1.png': {
            0: {'points': [[0.0, 0.0], [32.0, 0.0], [32.51604107738961, 23.342430497158738], [0.30647504013455595, 18.449838187702277]}
        }
    }
    
    # 检查每个瓦片集的碰撞形状
    for i, tile_set in enumerate(tile_sets):
        tile_set_name = tile_set.get('name')
        print(f"瓦片集 {i}: {tile_set_name}")
        
        tiles = tile_set.get('tiles', [])
        for j, tile in enumerate(tiles):
            collision_shape = tile.get('collision_shape')
            print(f"  瓦片 {j} 碰撞形状: {collision_shape}")
            
            # 验证与debug数据是否一致
            if tile_set_name in debug_data and j in debug_data[tile_set_name]:
                debug_shape = debug_data[tile_set_name][j]
                if collision_shape == debug_shape:
                    print(f"  ✅ 碰撞形状与debug数据一致")
                else:
                    print(f"  ❌ 碰撞形状与debug数据不一致")
                    print(f"  期望: {debug_shape}")
                    print(f"  实际: {collision_shape}")
            else:
                print(f"  ⚠️  无对应debug数据")
    
    # 3. 验证文件修改时间
    print("\n3. 验证文件修改时间...")
    resources_path = "/Users/amixc/Desktop/IDEtest/Test/assets/maps/地图1/地图1.resources"
    if os.path.exists(resources_path):
        mtime = os.path.getmtime(resources_path)
        import datetime
        modified_time = datetime.datetime.fromtimestamp(mtime)
        print(f"  .resources 文件修改时间: {modified_time}")
        print(f"  当前时间: {datetime.datetime.now()}")
        
        # 检查是否是最近修改的
        time_diff = datetime.datetime.now() - modified_time
        if time_diff.total_seconds() < 3600:  # 1小时内
            print("  ✅ 文件最近被修改")
        else:
            print("  ⚠️  文件未最近修改")
    else:
        print("  ❌ .resources 文件不存在")
    
    print("\n" + "=" * 80)
    print("✅ 验证完成！")

if __name__ == "__main__":
    test_verify_save()
