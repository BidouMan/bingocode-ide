import json
import numpy as np
import os

# 测试保存逻辑
class ChunkedMapData:
    def __init__(self, chunk_size=16):
        self.chunk_size = chunk_size
        self.chunks = {}
        self.empty_tile_id = 0

    def set_tile(self, world_x, world_y, tile_id):
        cx, cy = world_x // self.chunk_size, world_y // self.chunk_size
        lx, ly = world_x % self.chunk_size, world_y % self.chunk_size
        if (cx, cy) not in self.chunks:
            self.chunks[(cx, cy)] = np.full((self.chunk_size, self.chunk_size), self.empty_tile_id, dtype=np.int32)
        self.chunks[(cx, cy)][ly, lx] = tile_id

# 创建测试数据
map_data = {
    'width': 40,
    'height': 30,
    'tile_size': 16,
    'layers': [
        {
            'name': 'ground',
            'visible': True,
            'tiles': ChunkedMapData()
        }
    ],
    'tile_sets': [
        {'name': 'test.png', 'image_path': 'tilesets/test.png', 'tile_width': 16, 'tile_height': 16}
    ]
}

# 添加一些测试数据
map_data['layers'][0]['tiles'].set_tile(2, 2, 1001)
map_data['layers'][0]['tiles'].set_tile(3, 3, 1002)

# 模拟保存过程
try:
    save_data = {
        'width': map_data['width'],
        'height': map_data['height'],
        'tile_size': map_data['tile_size'],
        'layers': [],
        'tile_sets': map_data['tile_sets']
    }

    for layer in map_data['layers']:
        tiles_list = []
        # 遍历所有区块
        for (chunk_x, chunk_y), chunk in layer['tiles'].chunks.items():
            # 遍历区块内的所有瓦片
            for local_y in range(chunk.shape[0]):
                for local_x in range(chunk.shape[1]):
                    tile_id = chunk[local_y, local_x]
                    if tile_id != 0:
                        # 计算世界坐标
                        world_x = chunk_x * layer['tiles'].chunk_size + local_x
                        world_y = chunk_y * layer['tiles'].chunk_size + local_y
                        # 将NumPy类型转换为Python原生类型
                        tiles_list.append([int(world_x), int(world_y), int(tile_id)])
        
        layer_data = {
            'name': layer['name'],
            'visible': layer['visible'],
            'tiles': tiles_list
        }
        save_data['layers'].append(layer_data)

    print('保存的数据:')
    print(json.dumps(save_data, indent=2))
    print(f"瓦片数量: {len(save_data['layers'][0]['tiles'])}")
    print(f"瓦片集数量: {len(save_data['tile_sets'])}")
    
    # 保存到文件
    test_file = 'test_map.json'
    with open(test_file, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False)
    print(f'保存到文件: {test_file}')
    
    # 读取验证
    with open(test_file, 'r', encoding='utf-8') as f:
        loaded_data = json.load(f)
    print('读取的数据:')
    print(json.dumps(loaded_data, indent=2))
    
except Exception as e:
    print(f'保存过程中出现错误: {e}')
    import traceback
    traceback.print_exc()
