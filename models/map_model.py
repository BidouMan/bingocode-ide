import os
import json
import struct
import numpy as np
from PySide6.QtCore import QObject, Signal, QTimer


class MapDataModel(QObject):
    """地图数据模型，管理地图的瓦片数据和文件操作"""

    data_changed = Signal()  # 数据变化信号

    def __init__(self, project_path=""):
        super().__init__()
        self.project_path = project_path
        self.map_data = {}
        self._changed_area = set()  # 变化区域跟踪
        self._initialize_default_data()
        # 防抖定时器，避免频繁触发信号
        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(16)  # 约60fps
        self._debounce_timer.timeout.connect(self._emit_data_changed)

    def _initialize_default_data(self):
        """初始化默认地图数据"""
        self.map_data = {
            "name": "未命名地图",  # 地图名称
            "width": 40,  # 地图宽度（瓦片数量）- 640/16=40
            "height": 30,  # 地图高度（瓦片数量）- 480/16=30
            "tile_size": 16,  # 瓦片大小（像素）
            "offset_x": 0,  # 坐标偏移量
            "offset_y": 0,  # 坐标偏移量
            "layers": [  # 地图图层
                {
                    "name": "ground",
                    "visible": True,
                    "tiles": {},  # 使用字典存储：(x, y): tile_id
                    "objects": [],  # 用于存放不规则的大图或背景
                }
            ],
            "tile_sets": [],  # 瓦片集配置
        }

    def get_tile(self, layer_index, x, y):
        """获取指定位置的瓦片ID"""
        if 0 <= layer_index < len(self.map_data["layers"]):
            layer = self.map_data["layers"][layer_index]
            return layer["tiles"].get((int(x), int(y)), 0)
        return 0

    def set_tile(self, layer_index, x, y, tile_id):
        """设置指定位置的瓦片ID，直接操作字典"""
        if 0 <= layer_index < len(self.map_data["layers"]):
            layer = self.map_data["layers"][layer_index]
            key = (int(x), int(y))

            # 添加到变化区域跟踪
            self._changed_area.add(key)

            if tile_id == 0:
                # 如果tile_id为0，删除该坐标点以节省内存
                if key in layer["tiles"]:
                    del layer["tiles"][key]
            else:
                # 否则设置瓦片ID
                layer["tiles"][key] = int(tile_id)

                # 检查新绘制的图块是否超出当前地图尺寸
                current_width = self.map_data["width"]
                current_height = self.map_data["height"]
                offset_x = self.map_data.get("offset_x", 0)
                offset_y = self.map_data.get("offset_y", 0)

                # 计算图块相对于地图原点的位置
                rel_x = x - offset_x
                rel_y = y - offset_y

                # 如果超出当前尺寸，更新地图尺寸
                if rel_x >= current_width or rel_y >= current_height:
                    new_width = max(current_width, rel_x + 1)
                    new_height = max(current_height, rel_y + 1)

                    # 添加最小尺寸限制：最小宽度40，最小高度30（基于16像素瓦片，640x480像素）
                    tile_size = self.map_data["tile_size"]
                    min_width_tiles = 640 // tile_size
                    min_height_tiles = 480 // tile_size
                    new_width = max(new_width, min_width_tiles)
                    new_height = max(new_height, min_height_tiles)

                    # 更新地图尺寸
                    if new_width != current_width or new_height != current_height:
                        self.map_data["width"] = new_width
                        self.map_data["height"] = new_height
                        print(
                            f"DEBUG: 地图尺寸更新: {current_width}x{current_height} -> {new_width}x{new_height}"
                        )

            # 使用防抖机制，避免频繁触发信号
            self._debounce_timer.start()
            return True
        return False

    def get_map_size(self):
        """获取地图尺寸"""
        return self.map_data["width"], self.map_data["height"]

    def get_tile_size(self):
        """获取瓦片大小"""
        return self.map_data["tile_size"]

    def get_changed_area(self):
        """获取变化区域"""
        return self._changed_area.copy()

    def clear_changed_area(self):
        """清除变化区域"""
        self._changed_area.clear()

    def _emit_data_changed(self):
        """防抖处理：在定时器触发时发出数据变化信号"""
        if self._changed_area:
            self.data_changed.emit()

    def get_layer_count(self):
        """获取图层数量"""
        return len(self.map_data["layers"])

    def get_layer(self, index):
        """获取指定图层"""
        if 0 <= index < len(self.map_data["layers"]):
            return self.map_data["layers"][index]
        return None

    def add_layer(self, name="new_layer"):
        """添加新图层"""
        new_layer = {"name": name, "visible": True, "tiles": {}, "objects": []}
        self.map_data["layers"].append(new_layer)
        self.data_changed.emit()
        return len(self.map_data["layers"]) - 1

    def remove_layer(self, index):
        """删除图层"""
        if 0 <= index < len(self.map_data["layers"]):
            del self.map_data["layers"][index]
            self.data_changed.emit()
            return True
        return False

    def set_map_size(self, width, height):
        """设置地图尺寸"""
        self.map_data["width"] = width
        self.map_data["height"] = height
        self.data_changed.emit()

    def set_tile_size(self, tile_size):
        """设置瓦片大小"""
        self.map_data["tile_size"] = tile_size
        self.data_changed.emit()

    def get_map_name(self):
        """获取地图名称"""
        return self.map_data.get("name", "未命名地图")

    def set_map_name(self, name):
        """设置地图名称"""
        self.map_data["name"] = name
        self.data_changed.emit()

    def save(self, file_path=None):
        """保存地图数据到文件（使用二进制分层存储架构）"""
        if file_path is None:
            file_path = self._get_default_save_path()

        try:
            print(f"=== 开始保存地图数据 ===")
            print(f"DEBUG: 保存路径: {file_path}")
            print(f"DEBUG: 当前地图数据 - 图层数: {len(self.map_data['layers'])}")
            print(f"DEBUG: 当前地图数据 - tile_size: {self.map_data['tile_size']}")

            # 统计每个图层的瓦片数量
            total_tiles = 0
            for i, layer in enumerate(self.map_data["layers"]):
                tile_count = len(layer.get("tiles", {}))
                total_tiles += tile_count
                print(
                    f"DEBUG: 图层 {i} ({layer.get('name', 'unnamed')}) 瓦片数: {tile_count}"
                )
                # 打印前3个瓦片的详细信息
                tiles = layer.get("tiles", {})
                for j, ((x, y), tile_id) in enumerate(list(tiles.items())[:3]):
                    print(f"DEBUG:   瓦片 {j}: [{x}, {y}] -> ID: {tile_id}")
                if len(tiles) > 3:
                    print(f"DEBUG:   ... 还有 {len(tiles) - 3} 个瓦片")
            print(f"DEBUG: 总瓦片数: {total_tiles}")
            # 动态计算地图尺寸：根据所有图层中实际绘制的图块位置
            min_x = float("inf")
            max_x = -float("inf")
            min_y = float("inf")
            max_y = -float("inf")

            for layer in self.map_data["layers"]:
                for (x, y), tile_id in layer["tiles"].items():
                    if tile_id != 0:
                        min_x = min(min_x, x)
                        max_x = max(max_x, x)
                        min_y = min(min_y, y)
                        max_y = max(max_y, y)

            # 如果没有绘制任何图块，使用默认尺寸
            if min_x == float("inf"):
                map_width = self.map_data["width"]
                map_height = self.map_data["height"]
                offset_x = 0
                offset_y = 0
                print(f"DEBUG: 没有图块，使用默认尺寸: {map_width}x{map_height}")
            else:
                # 地图尺寸 = 最大坐标 - 最小坐标 + 1（确保包含所有图块）
                map_width = max_x - min_x + 1
                map_height = max_y - min_y + 1
                offset_x = min_x
                offset_y = min_y
                print(
                    f"DEBUG: 根据图块坐标计算尺寸: {map_width}x{map_height}, 偏移量: ({offset_x}, {offset_y})"
                )

            # 更新map_data中的偏移量和尺寸
            self.map_data["offset_x"] = offset_x
            self.map_data["offset_y"] = offset_y
            self.map_data["width"] = map_width
            self.map_data["height"] = map_height

            # 添加最小尺寸限制：最小宽度640，最小高度480（像素）
            # 转换为瓦片数：640/16=40, 480/16=30
            tile_size = self.map_data["tile_size"]
            min_width_tiles = 640 // tile_size
            min_height_tiles = 480 // tile_size

            map_width = max(map_width, min_width_tiles)
            map_height = max(map_height, min_height_tiles)
            print(f"DEBUG: 应用最小尺寸限制后: {map_width}x{map_height}")

            # 创建二进制分层存储文件
            base_name = os.path.splitext(file_path)[0]
            print(f"DEBUG: 基础文件名: {base_name}")

            # 1. 保存地图元数据 (.info)
            print(f"DEBUG: 保存元数据到: {base_name}.info")
            self._save_map_info(
                base_name + ".info", map_width, map_height, offset_x, offset_y
            )

            # 2. 保存图块数据 (.tiles)
            print(f"DEBUG: 保存图块数据到: {base_name}.tiles")
            self._save_map_tiles(
                base_name + ".tiles", map_width, map_height, offset_x, offset_y
            )

            # 3. 保存碰撞数据 (.collision)
            print(f"DEBUG: 保存碰撞数据到: {base_name}.collision")
            self._save_map_collision(
                base_name + ".collision", map_width, map_height, offset_x, offset_y
            )

            # 4. 保存资源引用 (.resources)
            print(f"DEBUG: 保存资源引用到: {base_name}.resources")
            print(f"DEBUG: 瓦片集数量: {len(self.map_data['tile_sets'])}")
            for i, tile_set in enumerate(self.map_data["tile_sets"]):
                print(
                    f"DEBUG: 瓦片集 {i}: {tile_set.get('name', 'unnamed')}, 路径: {tile_set.get('image_path', 'unknown')}"
                )
            self._save_map_resources(base_name + ".resources")

            # 记录保存的所有瓦片坐标
            try:
                import datetime

                record_dir = (
                    "/Volumes/WorkStation/MyWork/CodeStation/MyIDE/MyWorkspace/备份"
                )
                os.makedirs(record_dir, exist_ok=True)
                record_file = os.path.join(record_dir, "coordinate_log.md")

                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                with open(record_file, "a", encoding="utf-8") as f_record:
                    f_record.write(f"## {timestamp} - Save Map (Binary)\n\n")
                    f_record.write(f"**File Path:** {file_path}\n\n")
                    f_record.write("**Tiles Saved:**\n\n")

                    for layer_idx, layer in enumerate(self.map_data["layers"]):
                        f_record.write(f"### Layer {layer_idx}: {layer['name']}\n\n")
                        for (x, y), tile_id in layer["tiles"].items():
                            if tile_id != 0:
                                f_record.write(f"- [x={x}, y={y}] -> ID: {tile_id}\n")
                        f_record.write("\n")

            except Exception as e:
                print(f"记录保存坐标错误: {e}")

            print(f"✅ 地图保存成功")
            return True
        except Exception as e:
            print(f"❌ 保存地图失败: {e}")
            import traceback

            traceback.print_exc()
            return False

    def _save_map_info(self, file_path, width, height, offset_x=0, offset_y=0):
        """保存地图元数据"""
        with open(file_path, "wb") as f:
            # 写入文件头（4字节）
            f.write(struct.pack("<I", 0x4D415050))  # "MAP_"

            # 写入版本号（4字节）
            f.write(struct.pack("<I", 3))  # 更新版本号以支持地图名称

            # 写入地图名称
            map_name = self.map_data.get("name", "")
            name_bytes = map_name.encode("utf-8")
            f.write(struct.pack("<I", len(name_bytes)))
            f.write(name_bytes)

            # 写入地图尺寸（8字节）
            f.write(struct.pack("<II", width, height))

            # 写入瓦片大小（4字节）
            f.write(struct.pack("<I", self.map_data["tile_size"]))

            # 写入偏移量（8字节，使用有符号整数）
            f.write(struct.pack("<ii", offset_x, offset_y))

            # 写入图层数量（4字节）
            f.write(struct.pack("<I", len(self.map_data["layers"])))

            # 写入瓦片集数量（4字节）
            f.write(struct.pack("<I", len(self.map_data["tile_sets"])))

    def _save_map_tiles(self, file_path, width, height, offset_x=0, offset_y=0):
        """保存图块数据（使用numpy批量写入）"""
        with open(file_path, "wb") as f:
            # 写入文件头（4字节）
            f.write(struct.pack("<I", 0x54494C45))  # "TILE"

            # 写入图层数量（4字节）
            f.write(struct.pack("<I", len(self.map_data["layers"])))

            # 为每个图层保存图块数据
            for layer_idx, layer in enumerate(self.map_data["layers"]):
                # 写入图层名称长度（4字节）
                name_bytes = layer["name"].encode("utf-8")
                f.write(struct.pack("<I", len(name_bytes)))
                f.write(name_bytes)

                # 写入图层可见性（1字节）
                f.write(struct.pack("<B", 1 if layer["visible"] else 0))

                # 创建numpy数组存储图块数据
                tile_array = np.zeros((height, width), dtype=np.uint16)

                # 填充图块数据（使用偏移后的坐标）
                for (x, y), tile_id in layer["tiles"].items():
                    # 计算相对坐标
                    rel_x = x - offset_x
                    rel_y = y - offset_y
                    if 0 <= rel_x < width and 0 <= rel_y < height:
                        tile_array[rel_y][rel_x] = tile_id

                # 一次性写入所有数据
                tile_array.tofile(f)

    def _save_map_collision(self, file_path, width, height, offset_x=0, offset_y=0):
        """保存碰撞数据（使用相对坐标）"""
        with open(file_path, "wb") as f:
            # 写入文件头（4字节）
            f.write(struct.pack("<I", 0x434F4C4C))  # "COLL"

            # 写入图层数量（4字节）
            f.write(struct.pack("<I", len(self.map_data["layers"])))

            # 为每个图层保存碰撞数据
            for layer_idx, layer in enumerate(self.map_data["layers"]):
                # 创建numpy数组存储碰撞数据（每个图块4字节）
                collision_array = np.zeros((height, width), dtype=np.uint32)

                # 填充碰撞数据（目前使用默认矩形碰撞）
                for (x, y), tile_id in layer["tiles"].items():
                    if tile_id > 0:
                        # 计算相对坐标
                        rel_x = x - offset_x
                        rel_y = y - offset_y
                        if 0 <= rel_x < width and 0 <= rel_y < height:
                            # 解析tile_id获取资源索引和图块索引
                            resource_index = (tile_id // 1000) - 1
                            tile_index = (tile_id % 1000) - 1

                            # 获取图块碰撞状态
                            collision_enabled = self.get_tile_collision(
                                resource_index, tile_index
                            )

                            # 获取图块标签
                            tile_tag = self.get_tile_tag(resource_index, tile_index)

                            # 编码碰撞数据（简化版：使用整数表示）
                            # 最高位表示碰撞是否启用，其余位保留
                            collision_value = 0
                            if collision_enabled:
                                collision_value = 1 << 31

                            collision_array[rel_y][rel_x] = collision_value

                # 一次性写入所有数据
                collision_array.tofile(f)

    def _save_map_resources(self, file_path):
        """保存资源引用"""
        with open(file_path, "wb") as f:
            # 写入文件头（4字节）
            f.write(struct.pack("<I", 0x52455352))  # "RESR"

            # 写入瓦片集数量（4字节）
            f.write(struct.pack("<I", len(self.map_data["tile_sets"])))

            # 获取地图文件所在目录（用于计算相对路径）
            map_dir = os.path.dirname(file_path)
            maps_dir = os.path.dirname(map_dir)

            # 保存每个瓦片集
            for tile_set in self.map_data["tile_sets"]:
                # 写入瓦片集名称长度（4字节）
                name_bytes = tile_set.get("name", "").encode("utf-8")
                f.write(struct.pack("<I", len(name_bytes)))
                f.write(name_bytes)

                # 写入图片路径长度（4字节）
                image_path = tile_set.get("image_path", "")
                # 将绝对路径转换为相对于maps目录的相对路径
                if os.path.isabs(image_path):
                    try:
                        # 计算相对于maps目录的相对路径
                        rel_path = os.path.relpath(image_path, maps_dir)
                        image_path = rel_path
                    except ValueError:
                        # 如果无法计算相对路径（不同驱动器），保留绝对路径
                        pass
                path_bytes = image_path.encode("utf-8")
                f.write(struct.pack("<I", len(path_bytes)))
                f.write(path_bytes)

                # 写入瓦片宽度和高度（每个4字节）
                tile_width = tile_set.get("tile_width", 16)
                tile_height = tile_set.get("tile_height", 16)
                f.write(struct.pack("<II", tile_width, tile_height))

                # 写入瓦片数量（4字节）
                tiles = tile_set.get("tiles", [])
                f.write(struct.pack("<I", len(tiles)))

                # 保存每个瓦片的属性（碰撞状态和标签）
                for tile in tiles:
                    # 写入碰撞状态（1字节）
                    collision = tile.get("collision", True)
                    f.write(struct.pack("<B", 1 if collision else 0))

                    # 写入标签长度（4字节）和标签内容
                    tag = tile.get("tag", "")
                    tag_bytes = tag.encode("utf-8")
                    f.write(struct.pack("<I", len(tag_bytes)))
                    f.write(tag_bytes)

    def load(self, file_path):
        """从二进制分层文件加载地图数据"""
        try:
            # 只支持二进制分层文件格式
            return self._load_from_binary(file_path)
        except Exception as e:
            print(f"加载地图失败: {e}")
            return False

    def _load_from_binary(self, file_path):
        """从二进制分层文件加载地图数据"""
        try:
            base_name = os.path.splitext(file_path)[0]

            # 1. 加载地图元数据 (.info)
            (
                width,
                height,
                tile_size,
                layer_count,
                tile_set_count,
                offset_x,
                offset_y,
                map_name,
            ) = self._load_map_info(base_name + ".info")

            # 2. 加载图块数据 (.tiles)
            layers = self._load_map_tiles(
                base_name + ".tiles", width, height, layer_count, offset_x, offset_y
            )

            # 3. 加载碰撞数据 (.collision)
            # 碰撞数据暂时不直接加载到内存，按需使用

            # 4. 加载资源引用 (.resources)
            tile_sets = self._load_map_resources(
                base_name + ".resources", tile_set_count
            )

            # 更新地图数据
            # 如果地图名称为空（旧版本文件），使用文件基本名称作为地图名称
            if not map_name:
                map_name = os.path.basename(base_name)

            self.map_data = {
                "name": map_name,
                "width": width,
                "height": height,
                "tile_size": tile_size,
                "offset_x": offset_x,
                "offset_y": offset_y,
                "layers": layers,
                "tile_sets": tile_sets,
            }

            # 打印加载后的地图数据信息
            print(
                f"DEBUG: 二进制地图加载完成 - width: {width}, height: {height}, tile_size: {tile_size}"
            )
            print(
                f"DEBUG: 二进制地图加载完成 - offset_x: {offset_x}, offset_y: {offset_y}"
            )
            print(
                f"DEBUG: 二进制地图加载完成 - 图层数: {len(layers)}, 瓦片集数: {len(tile_sets)}"
            )

            # 打印图层信息
            for i, layer in enumerate(layers):
                tile_count = len(layer.get("tiles", {}))
                print(
                    f"DEBUG: 图层 {i} ({layer.get('name', 'unnamed')}) 瓦片数: {tile_count}"
                )
                # 打印前3个瓦片的详细信息
                tiles = layer.get("tiles", {})
                for j, ((x, y), tile_id) in enumerate(list(tiles.items())[:3]):
                    print(f"DEBUG:   瓦片 {j}: [{x}, {y}] -> ID: {tile_id}")

            self.data_changed.emit()
            return True
        except Exception as e:
            print(f"从二进制加载地图失败: {e}")
            return False

    def _load_map_info(self, file_path):
        """加载地图元数据"""
        with open(file_path, "rb") as f:
            # 读取文件头（4字节）
            magic = struct.unpack("<I", f.read(4))[0]
            if magic != 0x4D415050:  # "MAP_"
                raise ValueError("Invalid map info file")

            # 读取版本号（4字节）
            version = struct.unpack("<I", f.read(4))[0]

            # 读取地图名称（版本3及以上）
            map_name = ""
            if version >= 3:
                name_length = struct.unpack("<I", f.read(4))[0]
                map_name = f.read(name_length).decode("utf-8")

            # 读取地图尺寸（8字节）
            width, height = struct.unpack("<II", f.read(8))

            # 读取瓦片大小（4字节）
            tile_size = struct.unpack("<I", f.read(4))[0]

            # 读取偏移量（版本2及以上，使用有符号整数）
            offset_x = 0
            offset_y = 0
            if version >= 2:
                offset_x, offset_y = struct.unpack("<ii", f.read(8))

            # 读取图层数量（4字节）
            layer_count = struct.unpack("<I", f.read(4))[0]

            # 读取瓦片集数量（4字节）
            tile_set_count = struct.unpack("<I", f.read(4))[0]

            return (
                width,
                height,
                tile_size,
                layer_count,
                tile_set_count,
                offset_x,
                offset_y,
                map_name,
            )

    def _load_map_tiles(
        self, file_path, width, height, layer_count, offset_x=0, offset_y=0
    ):
        """加载图块数据（使用numpy批量读取）"""
        layers = []

        with open(file_path, "rb") as f:
            # 读取文件头（4字节）
            magic = struct.unpack("<I", f.read(4))[0]
            if magic != 0x54494C45:  # "TILE"
                raise ValueError("Invalid map tiles file")

            # 读取图层数量（4字节）
            actual_layer_count = struct.unpack("<I", f.read(4))[0]

            # 加载每个图层的数据
            for _ in range(actual_layer_count):
                # 读取图层名称
                name_length = struct.unpack("<I", f.read(4))[0]
                name = f.read(name_length).decode("utf-8")

                # 读取图层可见性
                visible = struct.unpack("<B", f.read(1))[0] == 1

                # 使用numpy一次性加载图块数据
                tile_data = np.fromfile(f, dtype=np.uint16, count=width * height)
                tile_grid = tile_data.reshape((height, width))

                # 转换为字典格式（只保存非零图块，应用偏移量）
                tiles_dict = {}
                for y in range(height):
                    for x in range(width):
                        tile_id = tile_grid[y][x]
                        if tile_id != 0:
                            # 应用偏移量恢复原始坐标
                            original_x = x + offset_x
                            original_y = y + offset_y
                            tiles_dict[(original_x, original_y)] = tile_id

                layer = {
                    "name": name,
                    "visible": visible,
                    "tiles": tiles_dict,
                    "objects": [],
                }
                layers.append(layer)

        return layers

    def _load_map_resources(self, file_path, tile_set_count):
        """加载资源引用"""
        tile_sets = []

        with open(file_path, "rb") as f:
            # 读取文件头（4字节）
            magic = struct.unpack("<I", f.read(4))[0]
            if magic != 0x52455352:  # "RESR"
                raise ValueError("Invalid map resources file")

            # 读取瓦片集数量（4字节）
            actual_tile_set_count = struct.unpack("<I", f.read(4))[0]

            # 获取地图文件所在目录（用于解析相对路径）
            map_dir = os.path.dirname(file_path)
            maps_dir = os.path.dirname(map_dir)

            # 加载每个瓦片集
            for _ in range(actual_tile_set_count):
                # 读取瓦片集名称
                name_length = struct.unpack("<I", f.read(4))[0]
                name = f.read(name_length).decode("utf-8")

                # 读取图片路径
                path_length = struct.unpack("<I", f.read(4))[0]
                image_path = f.read(path_length).decode("utf-8")

                # 如果是相对路径，转换为绝对路径
                if not os.path.isabs(image_path):
                    # 相对于maps目录的相对路径
                    image_path = os.path.join(maps_dir, image_path)

                # 读取瓦片宽度和高度
                tile_width, tile_height = struct.unpack("<II", f.read(8))

                # 读取瓦片数量
                tile_count = struct.unpack("<I", f.read(4))[0]

                # 加载每个瓦片的属性
                tiles = []
                for _ in range(tile_count):
                    # 读取碰撞状态
                    collision = struct.unpack("<B", f.read(1))[0] == 1

                    # 读取标签
                    tag_length = struct.unpack("<I", f.read(4))[0]
                    tag = f.read(tag_length).decode("utf-8")

                    tile = {"collision": collision, "tag": tag}
                    tiles.append(tile)

                tile_set = {
                    "name": name,
                    "image_path": image_path,
                    "tile_width": tile_width,
                    "tile_height": tile_height,
                    "tiles": tiles,
                }
                tile_sets.append(tile_set)

        return tile_sets

    def _get_default_save_path(self):
        """获取默认保存路径"""
        if self.project_path:
            maps_dir = os.path.join(self.project_path, "assets", "maps")
            os.makedirs(maps_dir, exist_ok=True)
            return os.path.join(maps_dir, "map.json")
        return "map.json"

    def add_tile_set(self, name, image_path, tile_width, tile_height):
        """添加瓦片集"""
        tile_set = {
            "name": name,
            "image_path": image_path,
            "tile_width": tile_width,
            "tile_height": tile_height,
            "tile_count": 0,  # 将在加载图片后计算
            "tiles": [],  # 每个图块单独的碰撞设置
        }
        self.map_data["tile_sets"].append(tile_set)
        self.data_changed.emit()
        return len(self.map_data["tile_sets"]) - 1

    def get_tile_sets(self):
        """获取所有瓦片集"""
        return self.map_data["tile_sets"]

    def get_tile_set(self, index):
        """获取指定瓦片集"""
        if 0 <= index < len(self.map_data["tile_sets"]):
            return self.map_data["tile_sets"][index]
        return None

    def set_tile_collision(self, tile_set_index, tile_index, collision):
        """设置单个图块的碰撞状态"""
        if 0 <= tile_set_index < len(self.map_data["tile_sets"]):
            tile_set = self.map_data["tile_sets"][tile_set_index]
            # 确保tiles数组足够大
            while len(tile_set["tiles"]) <= tile_index:
                tile_set["tiles"].append({"collision": True})  # 默认开启碰撞
            tile_set["tiles"][tile_index]["collision"] = collision
            self.data_changed.emit()
            return True
        return False

    def get_tile_collision(self, tile_set_index, tile_index):
        """获取单个图块的碰撞状态"""
        if 0 <= tile_set_index < len(self.map_data["tile_sets"]):
            tile_set = self.map_data["tile_sets"][tile_set_index]
            if 0 <= tile_index < len(tile_set["tiles"]):
                return tile_set["tiles"][tile_index].get("collision", True)
        return True

    def set_tile_tag(self, tile_set_index, tile_index, tag):
        """设置单个图块的标签"""
        if 0 <= tile_set_index < len(self.map_data["tile_sets"]):
            tile_set = self.map_data["tile_sets"][tile_set_index]
            # 确保tiles数组足够大
            while len(tile_set["tiles"]) <= tile_index:
                tile_set["tiles"].append({"collision": True})
            tile_set["tiles"][tile_index]["tag"] = tag
            self.data_changed.emit()
            return True
        return False

    def get_tile_tag(self, tile_set_index, tile_index):
        """获取单个图块的标签"""
        if 0 <= tile_set_index < len(self.map_data["tile_sets"]):
            tile_set = self.map_data["tile_sets"][tile_set_index]
            if 0 <= tile_index < len(tile_set["tiles"]):
                return tile_set["tiles"][tile_index].get("tag", "")
        return ""

    def set_tile_set_collision(self, index, collision):
        """设置整个瓦片集的碰撞状态（兼容旧方法）"""
        if 0 <= index < len(self.map_data["tile_sets"]):
            tile_set = self.map_data["tile_sets"][index]
            # 为所有图块设置相同的碰撞状态
            for i in range(len(tile_set["tiles"])):
                tile_set["tiles"][i]["collision"] = collision
            self.data_changed.emit()
            return True
        return False

    def get_tile_set_collision(self, index):
        """获取瓦片集的碰撞状态（兼容旧方法，返回第一个图块的状态）"""
        if 0 <= index < len(self.map_data["tile_sets"]):
            tile_set = self.map_data["tile_sets"][index]
            if tile_set["tiles"]:
                return tile_set["tiles"][0].get("collision", True)
        return True
