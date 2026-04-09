from PySide6.QtCore import QObject, Signal


class PropertyManager(QObject):
    """属性管理器，负责处理属性面板相关的功能"""

    # 信号定义
    property_changed = Signal(int, int, str, object)  # 属性变化信号

    def __init__(self, map_model, parent=None):
        super().__init__(parent)
        self.map_model = map_model
        self.current_tile = None

    def __del__(self):
        """清理资源，避免程序退出时崩溃"""
        try:
            self.current_tile = None
        except Exception:
            pass

    def set_current_tile(self, resource_index, tile_index):
        """设置当前选中的瓦片"""
        self.current_tile = (resource_index, tile_index)

    def update_properties(self, tile_id=None, coordinates=None):
        """更新属性面板显示"""
        # 这里需要根据瓦片ID或坐标更新属性面板
        # 实际使用时需要与UI进行交互
        pass

    def set_tile_tag(self, tag):
        """设置瓦片标签"""
        if self.current_tile:
            resource_index, tile_index = self.current_tile
            if self.map_model:
                self.map_model.set_tile_tag(resource_index, tile_index, tag)
                self.property_changed.emit(resource_index, tile_index, "tag", tag)

    def get_tile_tag(self):
        """获取瓦片标签"""
        if self.current_tile:
            resource_index, tile_index = self.current_tile
            if self.map_model:
                return self.map_model.get_tile_tag(resource_index, tile_index)
        return ""

    def get_tile_collision(self):
        """获取瓦片碰撞状态"""
        if self.current_tile:
            resource_index, tile_index = self.current_tile
            if self.map_model:
                return self.map_model.get_tile_collision(resource_index, tile_index)
        return False
