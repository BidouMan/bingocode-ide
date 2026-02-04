import sys
import time

# 模拟原生的速度控制
_delay = 0.05  # 每次移动后的延迟时间（秒）

# 初始状态
_is_down = True

def forward(distance):
    print(f"|DRAW|MOVE|{distance}")
    sys.stdout.flush()
    # 🚀 只有延迟大于 0 时才 sleep
    if _delay > 0:
        time.sleep(_delay)

def left(angle):
    print(f"|DRAW|LEFT|{angle}")
    sys.stdout.flush()
    if _delay > 0:
        time.sleep(_delay)

def right(angle):
    # 兼容你的 ScreenManager LEFT 逻辑
    print(f"|DRAW|LEFT|-{angle}")
    sys.stdout.flush()
    if _delay > 0:
        time.sleep(_delay)

# 可以添加一个 speed 函数供学生调用
def speed(s):
    global _delay
    # 🚀 原生逻辑：0 是最快，完全不等待
    if s == 0:
        _delay = 0
    elif s >= 10:
        _delay = 0.002 # 极速
    elif s >= 6:
        _delay = 0.01  # 快速
    elif s >= 3:
        _delay = 0.05  # 中速
    else:
        _delay = 0.15  # 慢速

def pendown():
    global _is_down
    _is_down = True
    print("|DRAW|PEN|DOWN")
    sys.stdout.flush()

def penup():
    global _is_down
    _is_down = False
    print("|DRAW|PEN|UP")
    sys.stdout.flush()

# 必须提供这些空函数，防止学生代码报错
def setup(*args, **kwargs): pass
def done(*args, **kwargs): sys.stdout.flush()
# def speed(*args, **kwargs): pass