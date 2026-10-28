"""游戏时间与定时器：Timer、time_passed、wait。

什么时候来这里改：暂停时计时、帧率波动导致计时不准、循环计时器。
游戏时间 _GAME_TIME 只在物理步内累加，见 engine_state。"""
import sys
import engine_state as st


class Timer:
    def __init__(self, seconds, loop=True):
        self._interval = float(seconds)
        self._loop = loop
        self._running = False
        self._last_time = 0.0
        # 创建即自动开始（与文档、教程写法一致）；需要手动控制就先 stop() 再 start()
        self.start()

    def start(self):
        """开始/重新开始计时（会重置计时起点）"""
        self._running = True
        self._last_time = st._GAME_TIME

    def stop(self):
        """停止计时（再次 start() 后重新计时）"""
        self._running = False

    def is_timeout(self):
        """时间到了返回 True；循环计时器会自动重新计时"""
        if not self._running:
            return False
        if st._GAME_TIME - self._last_time >= self._interval:
            self._last_time = st._GAME_TIME
            if not self._loop:
                self._running = False
            return True
        return False


def _time_passed_impl(seconds, frame):
    key = (id(frame.f_code), frame.f_lineno)
    now = st._GAME_TIME
    last = st._WAIT_TIMERS.get(key)
    if last is None:
        st._WAIT_TIMERS[key] = now
        return False
    if now - last >= seconds:
        st._WAIT_TIMERS[key] = now
        return True
    return False


def time_passed(seconds):
    """每个调用位置独立计时：经过 N 秒后第一次返回 True，之后每隔 N 秒返回一次"""
    return _time_passed_impl(seconds, sys._getframe(1))


def wait(seconds):
    """旧名字，保留兼容；等价于 time_passed(seconds)"""
    return _time_passed_impl(seconds, sys._getframe(1))
