import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from models.map_model import MapDataModel

def test_page_switch_crash():
    """测试页面切换时的状态管理问题"""
    print("=== 测试页面切换时的状态管理 ===")
    
    # 测试地图路径
    map_path = "/Users/amixc/Desktop/IDEtest/Test/assets/maps/地图1/地图1.info"
    
    # 模拟 MapEditorManager 的状态
    class MockMapEditorManager:
        def __init__(self):
            self.map_model = None
            self.uploaded_resources = []
            self.selected_resource_index = -1
            self.selected_tile_index = -1
        
        def load_map(self, map_path):
            """加载地图"""
            self.map_model = MapDataModel()
            success = self.map_model.load(map_path)
            if success:
                # 初始化 uploaded_resources
                self._init_uploaded_resources()
            return success
        
        def _init_uploaded_resources(self):
            """初始化上传资源列表"""
            self.uploaded_resources = []
            tile_sets = self.map_model.get_tile_sets()
            
            for i, tile_set in enumerate(tile_sets):
                resource_info = {
                    "name": tile_set.get("name"),
                    "path": tile_set.get("image_path", ""),
                    "resource_type": "tileset",
                    "tile_width": tile_set.get("tile_width", 32),
                    "tile_height": tile_set.get("tile_height", 32),
                    "collisions": []
                }
                
                # 加载碰撞形状数据
                tiles = tile_set.get('tiles', [])
                for j, tile in enumerate(tiles):
                    while len(resource_info["collisions"]) <= j:
                        resource_info["collisions"].append({})
                    if "collision_shape" in tile and tile["collision_shape"]:
                        resource_info["collisions"][j]["points"] = tile["collision_shape"].get("points", [])
                
                self.uploaded_resources.append(resource_info)
        
        def select_tile(self, resource_info, tile_index):
            """选择图块"""
            try:
                # 查找资源索引
                resource_index = -1
                for i, res in enumerate(self.uploaded_resources):
                    if res == resource_info:
                        resource_index = i
                        break
                
                if resource_index != -1:
                    self.selected_resource_index = resource_index
                    self.selected_tile_index = tile_index
                    print(f"选中图块: 资源={resource_info['name']}, 图块索引={tile_index}")
                    
                    # 确保资源的碰撞数据结构存在
                    if 'collisions' not in resource_info:
                        resource_info['collisions'] = []
                    while len(resource_info['collisions']) <= tile_index:
                        resource_info['collisions'].append({})
                    
                    # 从地图模型获取最新的碰撞形状数据
                    if self.map_model:
                        collision_shape = self.map_model.get_tile_collision_shape(resource_index, tile_index)
                        if collision_shape and 'points' in collision_shape:
                            resource_info['collisions'][tile_index]['points'] = collision_shape['points']
                            print(f"从地图模型同步碰撞形状数据: {collision_shape}")
                    
                    # 打印当前内存中的碰撞形状
                    if 'collisions' in resource_info and tile_index < len(resource_info['collisions']):
                        collision_data = resource_info['collisions'][tile_index]
                        if 'points' in collision_data:
                            print(f"当前内存中的碰撞形状: {collision_data['points']}")
                        else:
                            print("当前内存中无碰撞形状")
                    
                    return True
                else:
                    print("资源未找到")
                    return False
            except Exception as e:
                print(f"选择图块错误: {e}")
                import traceback
                traceback.print_exc()
                return False
    
    # 1. 模拟进入地图编辑器
    print("\n1. 模拟进入地图编辑器...")
    manager = MockMapEditorManager()
    success = manager.load_map(map_path)
    
    if not success:
        print("❌ 加载地图失败")
        return
    
    print("✅ 加载地图成功")
    print(f"上传资源数量: {len(manager.uploaded_resources)}")
    for i, resource in enumerate(manager.uploaded_resources):
        print(f"  资源 {i}: {resource['name']}")
    
    # 2. 模拟用户选择图块
    print("\n2. 模拟用户选择图块...")
    if manager.uploaded_resources:
        resource_info = manager.uploaded_resources[0]
        success = manager.select_tile(resource_info, 0)
        if success:
            print("✅ 选择图块成功")
        else:
            print("❌ 选择图块失败")
    
    # 3. 模拟切换到精灵编辑器页面
    print("\n3. 模拟切换到精灵编辑器页面...")
    # 模拟页面切换时的清理
    manager.map_model = None
    manager.uploaded_resources = []
    manager.selected_resource_index = -1
    manager.selected_tile_index = -1
    print("已清理地图编辑器状态")
    
    # 4. 模拟切换回地图编辑器页面
    print("\n4. 模拟切换回地图编辑器页面...")
    # 重新加载地图
    success = manager.load_map(map_path)
    if success:
        print("✅ 重新加载地图成功")
        print(f"上传资源数量: {len(manager.uploaded_resources)}")
        for i, resource in enumerate(manager.uploaded_resources):
            print(f"  资源 {i}: {resource['name']}")
    else:
        print("❌ 重新加载地图失败")
        return
    
    # 5. 模拟用户再次选择图块（这里可能会闪退）
    print("\n5. 模拟用户再次选择图块...")
    if manager.uploaded_resources:
        # 注意：这里使用新的 resource_info，不是之前的
        resource_info = manager.uploaded_resources[0]
        success = manager.select_tile(resource_info, 0)
        if success:
            print("✅ 选择图块成功")
        else:
            print("❌ 选择图块失败")
    
    # 6. 模拟用户选择第二个图块
    print("\n6. 模拟用户选择第二个图块...")
    if len(manager.uploaded_resources) > 1:
        resource_info = manager.uploaded_resources[1]
        success = manager.select_tile(resource_info, 0)
        if success:
            print("✅ 选择图块成功")
        else:
            print("❌ 选择图块失败")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_page_switch_crash()
