"""相机：camera_follow、跟随跟随目标、相机更新包、每帧 sprite 更新合并发送。

什么时候来这里改：镜头跟随抖动/偏移、相机边缘限制、跟随目标解析。
注意：这里会调用 map_runtime._render_map() 推动地图渲染。"""
import json
import sys
from map_runtime import _render_map
from markers import _MarkerRef
from sprite import Sprite, _resolve_target_xy
import engine_state as st


def get_main_player():
    """获取主玩家（第一个创建的精灵）"""
    for sprite in st._SPRITES.values():
        return sprite
    return None


def _send_camera_update(x, y, world_bounds=None):
    """发送摄像机更新指令到IDE"""
    data = {
        "x": x,
        "y": y,
    }
    if world_bounds:
        data["limit_left"] = world_bounds["left"]
        data["limit_right"] = world_bounds["right"]
        data["limit_top"] = world_bounds["top"]
        data["limit_bottom"] = world_bounds["bottom"]
    camera_packet = {
        "type": "CAMERA_UPDATE",
        "data": data,
    }
    print(json.dumps(camera_packet))


def _camera_config():
    """当前地图的相机设置（缺省为空字典 = 仅支持代码 camera_follow()）"""
    if not st._CURRENT_MAP:
        return {}
    cfg = st._CURRENT_MAP.get("camera") or {}
    return cfg if isinstance(cfg, dict) else {}


def _resolve_camera_target(name):
    """按角色变量名解析相机跟随目标。

    依次尝试：用户脚本里的同名变量 → 角色素材名（Sprite("角色1")）→ 1 号角色。
    找不到时回退主玩家，避免相机不跟随（课堂容错）。
    """
    name = str(name or "").strip()
    if name:
        main = sys.modules.get("__main__")
        obj = getattr(main, name, None) if main else None
        if isinstance(obj, Sprite) and not getattr(obj, "_is_deleted", False):
            return obj
        for sprite in st._SPRITES.values():
            if getattr(sprite, "sprite_name", "") == name and not getattr(sprite, "_is_deleted", False):
                return sprite
    return get_main_player()


def _update_camera_follow():
    """每帧更新相机。

    支持两种来源：
    - 地图属性里的相机设置（勾选「相机跟随」后自动跟随指定角色/1 号角色，可设偏移/平滑/边界限制）；
    - 代码调用 camera_follow() 手动跟随（优先级高于自动跟随）。
    """
    cfg = _camera_config()
    enabled = bool(cfg.get("enabled"))

    if enabled:
        # 只在没有目标时解析一次（代码 camera_follow() 或已解析的目标不会被覆盖）
        if st._FOLLOW_TARGET is None:
            target = _resolve_camera_target(cfg.get("target", ""))
            if target is not None:
                st._FOLLOW_TARGET = target
                st._AUTO_CAMERA_TARGET = target
    elif st._AUTO_CAMERA_TARGET is not None and st._FOLLOW_TARGET is st._AUTO_CAMERA_TARGET:
        # 关闭相机跟随：撤销自动目标，不影响代码 camera_follow()
        st._FOLLOW_TARGET = None
        st._AUTO_CAMERA_TARGET = None

    if st._FOLLOW_TARGET is None:
        return
    if getattr(st._FOLLOW_TARGET, "_is_deleted", False):
        # 目标被删除：停止跟随（地图开启自动跟随时下一帧会重新锁定主玩家）
        st._FOLLOW_TARGET = None
        st._AUTO_CAMERA_TARGET = None
        return

    offset_x = float(cfg.get("offsetX", 0) or 0)
    offset_y = float(cfg.get("offsetY", 0) or 0)
    smooth = max(0.0, min(0.95, float(cfg.get("smoothing", 0) or 0)))
    limit = bool(cfg.get("limitBounds", True))

    if st._CURRENT_MAP:
        # 相机活动范围 = 地图自身的像素矩形（不建议用 world_bounds：
        # 它包含图片出血/超出地图的素材，会把相机带到地图/游戏窗口之外）
        ts = st._CURRENT_MAP.get("tile_size", 16)
        bounds = {
            "left": 0,
            "top": 0,
            "right": st._CURRENT_MAP["width"] * ts,
            "bottom": st._CURRENT_MAP["height"] * ts,
        }
    else:
        bounds = {"left": 0, "top": 0, "right": 640, "bottom": 480}

    old_camera_x = st._CAMERA_X
    old_camera_y = st._CAMERA_Y

    # 摄像机是世界空间的量，必须读世界坐标；_FOLLOW_TARGET.x/y 是用户空间会翻转 y
    tx = st._FOLLOW_TARGET._x + offset_x
    ty = st._FOLLOW_TARGET._y + offset_y
    if limit:
        view_w, view_h = 640, 480
        tx = max(bounds["left"] + view_w / 2, min(tx, bounds["right"] - view_w / 2))
        ty = max(bounds["top"] + view_h / 2, min(ty, bounds["bottom"] - view_h / 2))

    if smooth > 0.001:
        factor = max(0.05, 1.0 - smooth)
        st._CAMERA_X += (tx - st._CAMERA_X) * factor
        st._CAMERA_Y += (ty - st._CAMERA_Y) * factor
    else:
        st._CAMERA_X = tx
        st._CAMERA_Y = ty

    _send_camera_update(st._CAMERA_X, st._CAMERA_Y, bounds if (st._CURRENT_MAP and limit) else None)

    if st._CURRENT_MAP:
        tile_size = st._CURRENT_MAP.get("tile_size", 16)
        if abs(st._CAMERA_X - old_camera_x) >= tile_size / 2 or abs(st._CAMERA_Y - old_camera_y) >= tile_size / 2:
            _render_map()


def _flush_frame_updates():
    """将帧缓冲中的精灵更新合并为一条 JSON 发送，大幅减少管道写入次数"""
    if not st._FRAME_UPDATES:
        return
    packet = {"type": "UPDATE_BATCH", "data": {"updates": st._FRAME_UPDATES}}
    print(json.dumps(packet))
    st._FRAME_UPDATES = []


def _update_follows():
    """每帧同步所有跟随者的位置与镜像继承（flush 前调用）。

    只写 x/y 与镜像（不碰 angle/scale）——朝向永远归用户控制；
    镜像继承目标的显示翻转（父翻面武器跟着翻，Godot 子节点观感，
    follow(target, flip=False) 可关）；目标被删除时自动停止跟随。
    """
    for sprite in list(st._SPRITES.values()):
        if sprite._is_deleted or sprite._follow_ref is None:
            continue
        ref = sprite._follow_ref
        pos = _resolve_target_xy(ref)
        if pos is None:
            # 目标已被删除：等同 unfollow，保留最后一次镜像继承的朝向
            sprite._follow_ref = None
            continue
        # 镜像继承：取目标的本帧显示翻转（链式跟随时含祖辈继承）
        flip = 1.0
        if sprite._follow_flip_on:
            parent = ref._sprite if isinstance(ref, _MarkerRef) else ref
            flip = getattr(parent, "_display_flip", 1.0)
        sprite._follow_flip = flip
        sprite._x, sprite._y = pos
        # 缓存比对在 _update_transform 内部，位置/镜像未变则不发包
        sprite._update_transform()


def camera_follow(sprite):
    """
    设置摄像机跟随指定精灵

    Args:
        sprite: 要跟随的精灵对象
    """
    st._FOLLOW_TARGET = sprite
    # 代码手动跟随优先于地图里的自动跟随
    st._AUTO_CAMERA_TARGET = None
