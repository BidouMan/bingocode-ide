#!/usr/bin/env python3
# """
# 测试图层资源隔离和保存功能
# """

# import os
# import sys
# import tempfile
# import shutil
# from PySide6.QtWidgets import QApplication

# 添加项目根目录到Python路径
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# from modules.map_editor.map_editor_manager import MapEditorManager
# from models.map_model import MapDataModel


# def test_layer_resources():
    # """测试图层资源隔离和保存功能"""
    # print("=== 开始测试图层资源隔离和保存功能 ===")
    
    # 创建临时目录用于测试
    # temp_dir = tempfile.mkdtemp()
    # print(f"创建临时测试目录: {temp_dir}")
    
    # try:
        # 创建应用实例
        # app = QApplication([])
        
        # 创建地图编辑器管理器
        # map_editor = MapEditorManager()
        
        # 创建新地图
        # map_editor.new_map()
        
        # 设置地图路径
        # map_path = os.path.join(temp_dir, "test_map.info")
        # map_editor.current_map_path = map_path
        
        # 模拟项目管理器
        # class MockProjectManager:
            # def __init__(self, project_root):
                # self.project_root = project_root
        
        # map_editor.project_manager = MockProjectManager(temp_dir)
        
        # 创建图层A（绘制模式）
        # print("\n1. 创建图层A（绘制模式）")
        # layer_a = map_editor.create_drawing_layer()
        # print(f"创建绘制图层: {layer_a}")
        
        # 模拟上传图块资源到图层A
        # print("\n2. 为图层A上传图块资源")
        # 这里需要模拟资源上传，暂时跳过实际文件操作
        # 直接添加资源到layer_resources
        # layer_id_a = map_editor.layer_manager.get_current_layer().layer_id
        # map_editor.layer_resources[layer_id_a] = [
            # {
                # "name": "grass_16.png",
                # "path": os.path.join(temp_dir, "tilesets", "grass_16.png"),
                # "resource_type": "tileset",
                # "tile_width": 16,
                # "tile_height": 16
            # }
        # ]
        # print(f"为图层A添加资源: grass_16.png")
        
        # 创建图层B（图像模式）
        # print("\n3. 创建图层B（图像模式）")
        # layer_b = map_editor.create_image_layer()
        # print(f"创建图像图层: {layer_b}")
        
        # 模拟上传图像资源到图层B
        # print("\n4. 为图层B上传图像资源")
        # layer_id_b = map_editor.layer_manager.get_current_layer().layer_id
        # map_editor.layer_resources[layer_id_b] = [
            # {
                # "name": "bg.png",
                # "path": os.path.join(temp_dir, "tilesets", "bg.png"),
                # "resource_type": "image",
                # "tile_width": 1,
                # "tile_height": 1
            # }
        # ]
        # print(f"为图层B添加资源: bg.png")
        
        # 保存地图
        # print("\n5. 保存地图")
        # save_result = map_editor.save_map()
        # print(f"保存结果: {save_result}")
        
        # 重新加载地图
        # print("\n6. 重新加载地图")
        # load_result = map_editor.load_map_from_path(map_path)
        # print(f"加载结果: {load_result}")
        
        # 验证图层数量
        # layer_count = map_editor.layer_manager.get_layer_count()
        # print(f"\n7. 验证图层数量: {layer_count}")
        # assert layer_count == 2, f"图层数量应为2，实际为{layer_count}"
        
        # 验证图层A的资源
        # print("\n8. 验证图层A的资源")
        # map_editor.layer_manager.set_current_layer(1)  # 图层A
        # current_layer = map_editor.layer_manager.get_current_layer()
        # layer_id_a = current_layer.layer_id
        # resources_a = map_editor.layer_resources.get(layer_id_a, [])
        # print(f"图层A资源数量: {len(resources_a)}")
        # assert len(resources_a) > 0, "图层A应该有资源"
        # assert resources_a[0]["name"] == "grass_16.png", f"图层A资源名称应为grass_16.png，实际为{resources_a[0].get('name', 'unknown')}"
        
        # 验证图层B的资源
        # print("\n9. 验证图层B的资源")
        # map_editor.layer_manager.set_current_layer(2)  # 图层B
        # current_layer = map_editor.layer_manager.get_current_layer()
        # layer_id_b = current_layer.layer_id
        # resources_b = map_editor.layer_resources.get(layer_id_b, [])
        # print(f"图层B资源数量: {len(resources_b)}")
        # assert len(resources_b) > 0, "图层B应该有资源"
        # assert resources_b[0]["name"] == "bg.png", f"图层B资源名称应为bg.png，实际为{resources_b[0].get('name', 'unknown')}"
        
        # print("\n✅ 测试通过！图层资源隔离和保存功能正常。")
        
    # finally:
        # 清理临时目录
        # shutil.rmtree(temp_dir)
        # print(f"\n清理临时测试目录: {temp_dir}")


# if __name__ == "__main__":
    # test_layer_resources()
