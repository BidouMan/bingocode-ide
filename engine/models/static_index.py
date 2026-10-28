# -*- coding: utf-8 -*-
"""静态几何空间索引：地图加载时烘焙一次，运行时只查询。

为什么需要：
  - 地图里的形状层 / 图像碰撞 / 图块碰撞都是静态的，每帧全表扫描既慢又会限制后续能力。
  - P3 先做「行为不变」的宽相：碰撞解算仍走原有逻辑，但先用索引剔除不可能相交的候选。
  - 后续 P4/P5/P6 的 Contact、move_and_slide、is_blocked、raycast 直接复用这里的索引。

索引结构：静态 AABB 树（BVH）。
  - 每个 StaticEntry 持有 shape_kernel 的 Shape，构建时一次性算好包围盒。
  - 查询按 AABB 剪枝，返回候选条目；调用方再做精确几何判定。
  - 叶子节点容量小，重建只在 load_map 时发生，运行时不增删。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from models.shape_kernel import AABB, Shape, inflate

# 叶子节点最多容纳的条目数
_LEAF_SIZE = 8

# 感应区判定外扩（像素）：让「刚好贴着边界」也算进入。
# 只用于感应判定/进出事件，实心形状保持原样，物理推挤不受影响。
SENSOR_EPS = 0.5


@dataclass
class StaticEntry:
    """一个静态碰撞/感应单元。

    source:
      - "shape": 形状层里的一个判定形状（origin 为引擎内部 poly 字典）
      - "image": 图像碰撞体的一个凸块
      - "tile":  一个实心图块
    kind:
      - "solid" / "sensor" / "both"（图像与图块固定 solid）
    """
    shape: Shape
    source: str
    kind: str = "solid"
    tag: str = ""
    collision_type: str = "墙体"
    layer_index: int = -1
    ref: Any = None
    origin: Any = None
    bbox: AABB = field(init=False)
    _sensor_shape: Optional[Shape] = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.bbox = self.shape.bbox

    @property
    def is_sensor(self) -> bool:
        return self.kind in ("sensor", "both")

    @property
    def is_solid(self) -> bool:
        return self.kind in ("solid", "both")

    @property
    def sensor_shape(self) -> Shape:
        """感应判定形状：感应类形状外扩 SENSOR_EPS，实心形状原样返回。

        「阻挡 + 感应」同时命中时，物理仍用未外扩的 shape，只有感应检测走这里。
        首次访问才计算并缓存。
        """
        if self._sensor_shape is None:
            self._sensor_shape = (
                inflate(self.shape, SENSOR_EPS) if self.is_sensor else self.shape
            )
        return self._sensor_shape


class _BVHNode:
    __slots__ = ("bbox", "left", "right", "entries")

    def __init__(self) -> None:
        self.bbox: AABB = AABB(0.0, 0.0, 0.0, 0.0)
        self.left: Optional["_BVHNode"] = None
        self.right: Optional["_BVHNode"] = None
        self.entries: Optional[List[StaticEntry]] = None


def _union(a: AABB, b: AABB) -> AABB:
    return AABB(
        min(a.left, b.left), min(a.top, b.top),
        max(a.right, b.right), max(a.bottom, b.bottom),
    )


def _build_node(entries: List[StaticEntry], depth: int = 0) -> Optional[_BVHNode]:
    if not entries:
        return None
    node = _BVHNode()
    total = entries[0].bbox
    for e in entries[1:]:
        total = _union(total, e.bbox)
    node.bbox = total

    if len(entries) <= _LEAF_SIZE:
        node.entries = entries
        return node

    # 按最长轴切分，取中位数；避免极端长条导致树退化
    w = total.right - total.left
    h = total.bottom - total.top
    axis = 0 if w >= h else 1

    def center(e: StaticEntry) -> float:
        b = e.bbox
        return (b.left + b.right) * 0.5 if axis == 0 else (b.top + b.bottom) * 0.5

    entries.sort(key=center)
    mid = len(entries) // 2
    node.left = _build_node(entries[:mid], depth + 1)
    node.right = _build_node(entries[mid:], depth + 1)
    return node


class StaticIndex:
    """静态 AABB 树。构建后结构不再变化。"""

    def __init__(self, entries: Sequence[StaticEntry]):
        self.entries: Tuple[StaticEntry, ...] = tuple(entries)
        self._root = _build_node(list(self.entries))

    def __len__(self) -> int:
        return len(self.entries)

    def query(self, box: AABB) -> List[StaticEntry]:
        """返回包围盒与 box 相交的所有条目（宽相候选，可能包含误报）。"""
        if self._root is None:
            return []
        result: List[StaticEntry] = []
        stack: List[_BVHNode] = [self._root]
        while stack:
            node = stack.pop()
            if not node.bbox.intersects(box):
                continue
            if node.entries is not None:
                for e in node.entries:
                    if e.bbox.intersects(box):
                        result.append(e)
                continue
            if node.left is not None:
                stack.append(node.left)
            if node.right is not None:
                stack.append(node.right)
        return result

    def query_rect(self, left: float, top: float, right: float, bottom: float) -> List[StaticEntry]:
        """矩形查询（引擎碰撞盒是 [left, top, right, bottom]，避免反复构造 AABB）。"""
        box = AABB(min(left, right), min(top, bottom), max(left, right), max(top, bottom))
        return self.query(box)

    def query_point(self, x: float, y: float) -> List[StaticEntry]:
        return self.query(AABB(x, y, x, y))

    def raycast_candidates(self, left: float, top: float, right: float, bottom: float) -> List[StaticEntry]:
        """射线查询的宽相：先查射线 AABB 覆盖的条目（P6 可升级为 BVH 遍历）。"""
        return self.query_rect(left, top, right, bottom)


class StaticWorld:
    """地图静态几何的运行时容器：阻挡索引 + 感应索引 + tag 查找表。"""

    __slots__ = ("solid", "sensors", "tags", "entries")

    def __init__(self, entries: Sequence[StaticEntry]):
        self.entries = tuple(entries)
        solid = [e for e in entries if e.is_solid]
        sensors = [e for e in entries if e.is_sensor]
        self.solid = StaticIndex(solid)
        self.sensors = StaticIndex(sensors)
        tags: Dict[str, List[StaticEntry]] = {}
        for e in entries:
            if e.tag:
                tags.setdefault(e.tag, []).append(e)
        self.tags: Dict[str, Tuple[StaticEntry, ...]] = {
            k: tuple(v) for k, v in tags.items()
        }

    def __len__(self) -> int:
        return len(self.entries)

    def tag_entries(self, tag: str) -> Tuple[StaticEntry, ...]:
        return self.tags.get(tag, ())

    def stats(self) -> Dict[str, int]:
        return {
            "entries": len(self.entries),
            "solid": len(self.solid),
            "sensors": len(self.sensors),
            "tags": len(self.tags),
        }


def build_world(entries: Iterable[StaticEntry]) -> StaticWorld:
    return StaticWorld(tuple(entries))
