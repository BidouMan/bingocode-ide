"""音效播放：play_sound / stop_sound / 音效路径解析。

什么时候来这里改：音效找不到、音效格式、循环播放、停止音效。"""
import json
import os
import engine_state as st


def _resolve_sound_path(sound_name):
    """在项目 assets/sounds 下查找音效，返回绝对路径；找不到返回 None"""
    if not sound_name:
        return None
    # 允许直接传绝对路径或带路径的文件名
    if os.path.exists(sound_name):
        return os.path.abspath(sound_name)

    sounds_dir = os.path.join("assets", "sounds")
    sound_path = None
    if os.path.exists(os.path.join(sounds_dir, sound_name)):
        sound_path = os.path.join(sounds_dir, sound_name)
    else:
        for ext in (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".aac", ".wma"):
            candidate = os.path.join(sounds_dir, sound_name + ext)
            if os.path.exists(candidate):
                sound_path = candidate
                break
    # 递归搜索子目录（如 effects/、loop/）
    if not sound_path:
        for root, dirs, files in os.walk(sounds_dir):
            for f in files:
                if f == sound_name or f.rsplit(".", 1)[0] == sound_name:
                    sound_path = os.path.join(root, f)
                    break
            if sound_path:
                break
    return os.path.abspath(sound_path) if sound_path else None


def stop_sound(sound_name=None):
    """停止音效。不传参数则停止所有音效。"""
    sound = _resolve_sound_path(sound_name) or sound_name
    packet = {
        "type": "STOP_SOUND",
        "data": {"sound": sound} if sound else {},
    }
    print(json.dumps(packet))


def play_sound(sound_name, loop=False):
    sound_path = _resolve_sound_path(sound_name)
    if not sound_path:
        # 只提示一次，避免循环里每帧刷屏
        if sound_name not in st._SOUND_WARNED:
            st._SOUND_WARNED.add(sound_name)
            print(f"[提示] 找不到音效 '{sound_name}'，请先在资源管理器中导入音效")
        return
    packet = {
        "type": "PLAY_SOUND",
        "data": {
            # 前端 convertFileSrc 需要绝对路径
            "sound": sound_path,
            "loop": loop,
        },
    }
    print(json.dumps(packet))
