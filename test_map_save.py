import sys
sys.path.insert(0, '.')

from models.map_model import MapDataModel, ChunkedMapData

# 测试保存逻辑
model = MapDataModel()
model.set_tile(0, 2, 2, 1001)
model.set_tile(0, 3, 3, 1002)

# 添加瓦片集
model.add_tile_set('test.png', 'tilesets/test.png', 16, 16)

# 保存测试
import tempfile
import os
import json

with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
    temp_path = f.name

try:
    success = model.save(temp_path)
    print(f'保存测试: {success}')
    
    # 读取验证
    with open(temp_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        print(f'读取测试成功，瓦片数量: {len(data["layers"][0]["tiles"])}')
        print(f'瓦片集数量: {len(data["tile_sets"])}')
        
        # 打印保存的数据
        print('\n保存的数据:')
        print(json.dumps(data, indent=2))
        
finally:
    os.unlink(temp_path)
