"""屏幕表现类 API：show_text、shake、random_int、random_float、show_collision。

什么时候来这里改：文字显示、屏幕震动、随机数、显示碰撞盒。"""
import json
import random
from sprite import Sprite


def random_int(min_val, max_val):
    """在 min_val 和 max_val 之间取随机整数（包含两端）"""
    return random.randint(int(min_val), int(max_val))


def random_float(min_val=0.0, max_val=1.0, decimals=2):
    """在 min_val 和 max_val 之间取随机浮点数

    Args:
        decimals: 保留小数位数，默认 2 位（对中小学生更友好）；传 None 返回完整精度
    """
    value = random.uniform(float(min_val), float(max_val))
    return value if decimals is None else round(value, decimals)


def shake(intensity=5, duration=0.3):
    """屏幕震动效果"""
    packet = {
        "type": "SCREEN_SHAKE",
        "data": {"intensity": intensity, "duration": duration},
    }
    print(json.dumps(packet))


def show_text(x, y, *args):
    """在屏幕指定位置显示文字，参数自动拼接为字符串
    show_text(100, 50, "分数:", score)
    """
    text = "".join(str(a) for a in args)
    packet = {
        "type": "DRAW_TEXT",
        "data": {"id": f"text_{x}_{y}", "text": text, "x": x, "y": y},
    }
    print(json.dumps(packet))


def show_collision(sprite):
    if isinstance(sprite, Sprite):
        sprite._show_hitbox = True
        # 重置脏缓存，强制下一帧发送包含 hitbox 的 UPDATE
        sprite._last_update_key = None
        # 通知前端开启碰撞盒渲染开关
        print(json.dumps({"type": "SHOW_COLLISION", "data": {"visible": True}}))
