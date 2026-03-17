# models/sprite_model.py
import json
import os
from PySide6.QtCore import QObject, Signal

class SpriteDataModel(QObject):
    """
    角色数据模型：负责 config.json 的内存映射与逻辑运算
    """
    # 信号：type="COSTUME" (造型变动), "ANIMATION" (动作变动), "ALL" (加载)
    data_changed = Signal(str, dict)

    def __init__(self, project_path):
        super().__init__()
        self.project_path = project_path
        self.config_path = os.path.join(project_path, "config.json")
        self.name = os.path.basename(project_path)
        self.costumes = []
        self.animations = {}
        self.load()

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # 🚀 兼容性修复：适配你的 .bgs JSON 格式
                    # 1. 处理造型 (你的 JSON 里叫 frames)
                    self.costumes = data.get("frames", data.get("costumes", []))
                    
                    # 2. 处理动作 (你的 JSON 里叫 segments)
                    raw_segments = data.get("segments", [])
                    if raw_segments:
                        # 将列表格式的 segments 转为模型需要的字典格式
                        self.animations = {}
                        for seg in raw_segments:
                            name = seg.get("name", "未命名")
                            self.animations[name] = {
                                "start": seg.get("start", 1),
                                "end": seg.get("end", 1),
                                "fps": seg.get("fps", 10), # 默认补全
                                "loop": seg.get("loop", True)
                            }
                    else:
                        self.animations = data.get("animations", {})

                print(f"✅ [Model] 加载完成: 造型={len(self.costumes)}, 动作={len(self.animations)}")
            except Exception as e:
                print(f"❌ [Model] 解析 JSON 失败: {e}")
        
        self.data_changed.emit("ALL", {})

    def get_costume_path(self, display_index):
        """1-Base 映射获取路径"""
        real_idx = display_index - 1
        if 0 <= real_idx < len(self.costumes):
            # 获取文件名
            filename = self.costumes[real_idx]
            # 如果 filename 是字典（某些格式会包含 file 字段），兼容处理
            if isinstance(filename, dict):
                filename = filename.get("file", "")
            return os.path.join(self.project_path, filename)
        return None

    def save(self):
        data = {"name": self.name, "costumes": self.costumes, "animations": self.animations}
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    

    def remove_costume(self, display_index):
        """核心：删除保护算法"""
        if not (1 <= display_index <= len(self.costumes)): return
        self.costumes.pop(display_index - 1)
        
        # 自动修正所有动画索引
        deleted_idx = display_index
        to_del = []
        for name, cfg in self.animations.items():
            if cfg["start"] > deleted_idx: cfg["start"] -= 1
            if cfg["end"] >= deleted_idx: cfg["end"] -= 1
            if cfg["start"] > cfg["end"] or not self.costumes:
                to_del.append(name)
        for name in to_del: del self.animations[name]
        
        self.data_changed.emit("COSTUME", {"deleted": deleted_idx})