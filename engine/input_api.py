"""键鼠输入：mouse 对象、key_down/pressed/up、mouse_down/pressed/up、input() 桥接。

什么时候来这里改：按键抖动/漏帧、鼠标坐标、输入监听线程、用户 input() 卡住。
注意：导入本模块会启动输入监听线程（daemon），这是原有行为。"""
import json
import queue
import sys
import threading
import time
from models.coords import screen_to_user_y, to_user_x
import engine_state as st


class _MouseType:
    @property
    def x(self):
        return to_user_x(st._MOUSE_STATE["x"])

    @property
    def y(self):
        # 鼠标是屏幕坐标：固定在屏幕左下角，不随地图高度变化
        return screen_to_user_y(st._MOUSE_STATE["y"])

    @property
    def pos(self):
        """一次性获取鼠标坐标 (x, y)，可直接拆包：x, y = mouse.pos"""
        return self.x, self.y

    def __repr__(self):
        return "mouse"


mouse = _MouseType()  # 🚀 定义全局变量 mouse


def _input_sync_listener():
    while True:
        try:
            # 🚀 确保是阻塞式读取
            line = sys.stdin.readline()
            if not line:
                time.sleep(0.01)
                continue

            clean_line = line.strip()

            if clean_line.startswith("K_DOWN:"):
                key = clean_line.split(":", 1)[1]
                st._PRESSED_KEYS.add(key)
            elif clean_line.startswith("K_UP:"):
                key = clean_line.split(":", 1)[1]
                # 只有确实按下过的键才算松开，避免启动前的多余松开事件触发 key_up
                if key in st._PRESSED_KEYS:
                    st._RELEASED_KEYS.add(key)
                st._PRESSED_KEYS.discard(key)

                # 🚀 新增鼠标事件处理
            elif clean_line.startswith("M_DOWN:"):
                old_value = st._MOUSE_STATE["down"]
                st._MOUSE_STATE["down"] = True

            elif clean_line.startswith("M_UP:"):
                old_value = st._MOUSE_STATE["down"]
                st._MOUSE_STATE["down"] = False
                # 只有确实按下过的才算松开，避免启动前的多余松开事件触发 mouse_up
                if old_value:
                    st._MOUSE_STATE["released"] = True

            elif clean_line.startswith("M_MOVE:"):
                # 解析 M_MOVE:320.5,240.0
                pos_str = clean_line.split(":", 1)[1]
                mx_s, my_s = pos_str.split(",")
                st._MOUSE_STATE["x"] = float(mx_s)
                st._MOUSE_STATE["y"] = float(my_s)

            # ─── 调试命令 ───
            elif clean_line == "PAUSE:":
                st._PAUSED = True
                st._PENDING_RESPONSES.append(json.dumps({"type": "PAUSE_STATE", "data": {"paused": True}}))
            elif clean_line == "RESUME:":
                st._PAUSED = False
                st._PENDING_RESPONSES.append(json.dumps({"type": "PAUSE_STATE", "data": {"paused": False}}))
            elif clean_line == "SHOW_FPS:1":
                st._SHOW_FPS = True
                st._PENDING_RESPONSES.append(json.dumps({"type": "FPS_UPDATE", "data": {"fps": round(st._PERF_STATS.get("last_fps", 0), 1)}}))
            elif clean_line == "SHOW_FPS:0":
                st._SHOW_FPS = False
                st._PENDING_RESPONSES.append(json.dumps({"type": "FPS_UPDATE", "data": {"fps": 0}}))
            elif clean_line == "SHOW_COLLISION:1":
                st._SHOW_ALL_COLLISION = True
                for sprite in st._SPRITES.values():
                    sprite._show_hitbox = True
                    sprite._last_update_key = None
            elif clean_line == "SHOW_COLLISION:0":
                st._SHOW_ALL_COLLISION = False
                for sprite in st._SPRITES.values():
                    sprite._show_hitbox = False
                    sprite._last_update_key = None
            else:
                # 不是控制命令 → 投喂给用户代码的 input()
                st._USER_INPUT_QUEUE.put(clean_line)
        except:
            time.sleep(0.01)


# 确保线程启动 (代码末尾)
threading.Thread(target=_input_sync_listener, daemon=True).start()


def _custom_input(prompt=""):
    """替代内置 input()，从 _USER_INPUT_QUEUE 读取，不跟 stdin 监听线程抢数据。"""
    import sys
    try:
        # 提示文字不加换行，光标停在同一行（与代码模式一致）
        sys.stdout.write(prompt + "__BINGO_WAITING_INPUT__\n")
        sys.stdout.flush()
        return st._USER_INPUT_QUEUE.get(timeout=300)
    except EOFError:
        # Windows 上 taskkill /F 强制终止进程时，stdin 管道关闭会触发 EOFError
        return ""
    except queue.Empty:
        return ""


def mouse_down():
    """判断鼠标是否按下"""
    # 🚀 不需要 global 声明，因为只读取不赋值
    return st._MOUSE_STATE["down"]


def mouse_pressed():
    """单次检测：只有在按下的那一帧返回 True"""
    # 如果当前按下，且上一帧没按，说明是刚刚按下的
    return st._MOUSE_STATE["down"] and not st._MOUSE_STATE["last_down"]


def mouse_up():
    """单次检测：只有在松开鼠标左键的那一帧返回 True"""
    return st._MOUSE_STATE["released_frame"]


def key_down(key):
    """供用户调用：if key_down('a')"""
    return str(key).lower() in st._PRESSED_KEYS_FRAME


def key_pressed(key):
    """只有按下的那一帧返回 True"""
    k = str(key).lower()
    return k in st._PRESSED_KEYS_FRAME and k not in st._PRESSED_KEYS_PREV


def key_up(key):
    """只有松开的那一帧返回 True"""
    return str(key).lower() in st._RELEASED_FRAME


def _sync_input_frame():
    """物理步开始前同步输入状态快照

    输入线程是异步改 _PRESSED_KEYS / _RELEASED_KEYS 的，这里统一快照一份给本步的
    学生代码，保证 key_down / key_pressed / key_up 三个 API 看到的是同一时刻的状态
    """
    st._PRESSED_KEYS_PREV.clear()
    st._PRESSED_KEYS_PREV.update(st._PRESSED_KEYS_FRAME)
    st._PRESSED_KEYS_FRAME.clear()
    st._PRESSED_KEYS_FRAME.update(st._PRESSED_KEYS)
    st._RELEASED_FRAME.clear()
    st._RELEASED_FRAME.update(st._RELEASED_KEYS)
    st._RELEASED_KEYS.clear()

    # 鼠标松开同样用「事件累积 + 本步快照」，避免异步事件落在两步之间被漏掉
    st._MOUSE_STATE["released_frame"] = st._MOUSE_STATE["released"]
    st._MOUSE_STATE["released"] = False
