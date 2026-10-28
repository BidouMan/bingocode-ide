"""游戏控制与事件广播：暂停/继续/停止、FPS 显示、broadcast/receive/on_receive。

什么时候来这里改：pause/resume/stop/is_paused、事件广播时序、GameStop 异常、用户回调调用。
GameStop 定义在这里，被主循环与事件广播共同使用。"""
import inspect
import json
import engine_state as st


class GameStop(Exception):
    """游戏停止异常"""
    pass


def stop_game():
    """停止游戏（抛出异常中断 generator）"""
    raise GameStop()


def pause():
    """暂停游戏（loop 仍运行，但精灵停止移动）"""
    st._PAUSED = True


def resume():
    """继续游戏"""
    st._PAUSED = False


def is_paused():
    """检查是否暂停"""
    return st._PAUSED


def stop():
    """停止游戏（退出 run 循环）"""
    st._STOPPED = True


def show_fps(visible=True):
    """学生调用的接口"""
    st._SHOW_FPS = visible
    packet = {"type": "UI_COMMAND", "data": {"visible": visible}}
    print(json.dumps(packet))


def _promote_event_frame():
    """物理步开始：把上一步发出的广播提升为本步可见"""
    st._EVENT_ACTIVE.clear()
    st._EVENT_ACTIVE.update(st._EVENT_PENDING)
    st._EVENT_PENDING.clear()


def broadcast(event_name):
    """发送全局广播（单个回调出错不会中断游戏主循环）"""
    # 登记给 receive() 轮询：下一物理步可见，持续一帧
    st._EVENT_PENDING.add(event_name)
    for callback in list(st._EVENT_LISTENERS.get(event_name, [])):
        try:
            callback()
        except GameStop:
            raise
        except Exception as e:
            print(f"[错误] 广播「{event_name}」的处理函数出错: {e}")


def receive(event_name):
    """这一帧有没有收到指定广播（广播发出后的下一帧返回一次 True）"""
    return event_name in st._EVENT_ACTIVE


def on_receive(event_name, callback):
    """当收到指定的广播时，执行 callback（Scratch「当接收到」帽子积木同款）"""
    if event_name not in st._EVENT_LISTENERS:
        st._EVENT_LISTENERS[event_name] = []
    st._EVENT_LISTENERS[event_name].append(callback)


# ---------- 物理步共用实现 ----------
# 旧式 run()（def loop()）与 while True generator 模式过去各写了一份物理步，
# 任何碰撞/感应功能都要改两处，极易漏改。现在统一走这两个函数：
#   _begin_physics_step：推进时间、更新动画、记录步初位置
#   学生代码（loop() / generator）
#   _end_physics_step：气泡计时、自动移动、触碰回调、地形碰撞、感应事件

def _supported_args(callback, args):
    """按回调函数声明的参数个数裁剪要传的位置参数。

    规则：函数能接几个就传几个（第一个参数永远是「角色自己」）。
      - def f():             → 不传
      - def f(who):          → 传 (角色,)
      - def f(who, tag):     → 传 (角色, 标签) 或 (角色, 对方)
      - def f(*args):        → 全部传
    取不到签名（少数内置函数）时按原样全部传，不猜。
    """
    try:
        positional = 0
        varargs = False
        for p in inspect.signature(callback).parameters.values():
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD):
                positional += 1
            elif p.kind == p.VAR_POSITIONAL:
                varargs = True
        take = len(args) if varargs else min(positional, len(args))
    except (TypeError, ValueError):
        take = len(args)
    return args[:take]


def _safe_call(callback, *args):
    """执行用户回调；回调内出错只打印错误，不中断游戏（与 broadcast 行为一致）。

    回调参数按函数声明的个数自动裁剪（见 _supported_args），
    学生写 def f()、def f(who)、def f(who, tag) 都能正常使用。
    GameStop 必须继续向上抛：学生代码里调用 stop() 时依赖它结束 generator。
    """
    try:
        callback(*_supported_args(callback, args))
    except GameStop:
        raise
    except Exception as e:
        print(f"[错误] 回调出错: {e}")
