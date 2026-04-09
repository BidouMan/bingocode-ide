"""测试重构后的地图编辑器功能"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 初始化Qt应用程序
from PySide6.QtWidgets import QApplication
app = QApplication(sys.argv)

from modules.map_editor.map_editor_manager import MapEditorManager
from PySide6.QtWidgets import QGraphicsView, QWidget, QVBoxLayout

# 创建地图编辑器管理器实例
map_editor = MapEditorManager()

# 创建模拟UI和视图
parent_widget = QWidget()
layout = QVBoxLayout(parent_widget)

# 创建资源列表视图
res_list_view = QGraphicsView()
layout.addWidget(res_list_view)

# 设置资源列表视图
map_editor.set_res_list_view(res_list_view)

# 初始化地图编辑器
map_editor.initialize(parent_widget)

# 设置当前地图路径
map_dir = os.path.join("assets", "maps", "测试地图")
os.makedirs(map_dir, exist_ok=True)
map_path = os.path.join(map_dir, "测试地图")
map_editor.current_map_path = map_path

# 模拟导入资源
test_image_path = 'assets/images/test_tileset.png'
import_data = {
    "files": [test_image_path],
    "resource_type": "tileset",
    "tile_size": 16
}

print("=== 测试资源导入 ===")
print(f"导入前资源数量: {len(map_editor.uploaded_resources)}")
map_editor._process_imported_resources(import_data)
print(f"导入后资源数量: {len(map_editor.uploaded_resources)}")
print(f"地图模型瓦片集数量: {len(map_editor.map_model.map_data['tile_sets'])}")

# 选择资源和瓦片
if len(map_editor.uploaded_resources) > 0:
    map_editor.select_resource(0)
    print(f"\n=== 测试资源选择 ===")
    print(f"选中的资源索引: {map_editor.selected_resource_index}")
    print(f"选中的图块索引: {map_editor.selected_tile_index}")

# 模拟绘制瓦片
from PySide6.QtCore import QPointF
scene_pos = QPointF(0, 0)
print(f"\n=== 测试绘制功能 ===")
map_editor._draw_tile(scene_pos)

# 检查地图数据
layer = map_editor.map_model.get_layer(0)
tiles = layer.get("tiles", {})
print(f"绘制后瓦片数据: {tiles}")

# 测试保存地图
print(f"\n=== 测试保存功能 ===")
save_result = map_editor.save_map(map_path)
print(f"保存结果: {save_result}")

# 测试重新加载地图
print(f"\n=== 测试加载功能 ===")
new_map_editor = MapEditorManager()
new_res_list_view = QGraphicsView()
new_map_editor.set_res_list_view(new_res_list_view)
new_map_editor.initialize(parent_widget)

load_result = new_map_editor.load_map(map_path)
print(f"加载结果: {load_result}")
print(f"加载后资源数量: {len(new_map_editor.uploaded_resources)}")
print(f"加载后瓦片集数量: {len(new_map_editor.map_model.map_data['tile_sets'])}")

# 检查加载后的瓦片数据
layer = new_map_editor.map_model.get_layer(0)
tiles = layer.get("tiles", {})
print(f"加载后瓦片数据: {tiles}")

print("\n=== 测试完成 ===")
