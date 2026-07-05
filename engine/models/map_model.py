"""地图模型：提供瓦片碰撞查询接口"""


class MapModel:
    """地图碰撞数据模型"""

    def __init__(self, tile_sets):
        self._tile_sets = tile_sets or []

    def _get_tile(self, ts_index, tile_index):
        """获取瓦片数据，越界返回 None"""
        if ts_index < 0 or ts_index >= len(self._tile_sets):
            return None, None
        ts = self._tile_sets[ts_index]
        tiles = ts.get("tiles", [])
        if 0 <= tile_index < len(tiles):
            return ts, tiles[tile_index]
        return ts, None

    def get_tile_collision(self, resource_index, tile_index):
        """查询指定瓦片是否启用碰撞。优先读取单瓦片数据，其次回退到 tileset 级"""
        ts, tile = self._get_tile(resource_index, tile_index)
        if ts is None:
            return False
        if tile is not None and isinstance(tile, dict):
            return tile.get("collision", "none") == "solid"
        # 回退到 tileset 级碰撞开关
        return ts.get("collisionEnabled", False) and ts.get("collisionType", "图像") != "图像"

    def get_tile_collision_type(self, resource_index, tile_index):
        """查询指定瓦片的碰撞类型"""
        ts, tile = self._get_tile(resource_index, tile_index)
        if ts is None:
            return "图像"
        if tile is not None and isinstance(tile, dict):
            ct = tile.get("collisionType")
            if ct:
                return ct
        # 回退到 tileset 级碰撞类型
        return ts.get("collisionType", "图像")

    def get_tile_collision_shape(self, resource_index, tile_index):
        """查询指定瓦片的自定义碰撞形状"""
        ts, tile = self._get_tile(resource_index, tile_index)
        if ts is None:
            return None
        if tile is not None and isinstance(tile, dict):
            return tile.get("collisionShape")
        return None

    def get_tile_tag(self, resource_index, tile_index):
        """查询指定瓦片的标签"""
        ts, tile = self._get_tile(resource_index, tile_index)
        if ts is None:
            return ""
        if tile is not None and isinstance(tile, dict):
            return tile.get("tag", "")
        return ""
