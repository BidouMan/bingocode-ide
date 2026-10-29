"""主循环与游戏启动：run()（旧 while True 模式）、start_game()（generator 调度模式）、
每帧调度、generator 注册、FPS 上报、sprite 动画推进。

什么时候来这里改：帧率、物理步长、暂停语义、启动/重启、generator 不执行、动画不动。
这是入口层：只做调度，具体功能去对应模块改。"""
import json
import sys
import time
from audio import play_sound, stop_sound
from camera import _flush_frame_updates, _update_camera_follow, _update_follows, camera_follow
from effects import random_float, random_int, shake, show_collision, show_text
from game_control import GameStop, _promote_event_frame, _safe_call, broadcast, is_paused, on_receive, pause, receive, resume, show_fps, stop_game
from input_api import _custom_input, _sync_input_frame, key_down, key_pressed, key_up, mouse, mouse_down, mouse_pressed, mouse_up
from map_runtime import _handle_physics_collision, _process_sensor_events, load_map
from sprite import Sprite
from timing import Timer, time_passed, wait
import engine_state as st


# ---------- 内部函数 ----------


def _send_fps_to_ide(fps):
    """内部统计并发送 FPS 数值"""
    packet = {"type": "FPS_UPDATE", "data": {"fps": round(fps, 1)}}
    print(json.dumps(packet))


def _begin_physics_step():
    """物理步开始（未暂停时）：推进游戏时间、更新动画、记录本步初始 x。"""
    if st._PAUSED:
        return
    st._GAME_TIME += st._PHYSICS_DT
    for sprite in st._SPRITES.values():
        if getattr(sprite, "animation_state", None):
            _update_sprite_animation(sprite)
    if st._CURRENT_MAP is not None:
        for sprite in st._SPRITES.values():
            # 禁止下滑功能据此区分主动移动与斜面推挤下滑
            sprite._frame_start_x = sprite._x


def _end_physics_step():
    """物理步收尾（未暂停时）：气泡计时、自动移动、触碰回调、地形碰撞、感应事件。"""
    if st._PAUSED:
        return

    # say 计时器：到期自动隐藏气泡
    for sid in list(st._SAY_TIMERS.keys()):
        timer, hide_fn = st._SAY_TIMERS[sid]
        if timer.is_timeout():
            hide_fn()
            del st._SAY_TIMERS[sid]

    for sprite in list(st._SPRITES.values()):
        if sprite._is_deleted:
            continue
        # 持续速度自动移动
        if sprite._speed > 0:
            sprite.move(sprite._speed)
        # 自动销毁
        if sprite._auto_destroy and sprite.is_out_screen():
            sprite.delete()
        # 分组触碰回调
        if sprite._on_hit_callbacks:
            for group_name, callback in list(sprite._on_hit_callbacks):
                for other in list(st._GROUPS.get(group_name, [])):
                    if other is sprite or other._is_deleted:
                        continue
                    if sprite.is_touch(other):
                        if callback:
                            _safe_call(callback, sprite, other)
                        else:
                            # 不传回调：默认双方都删除
                            sprite.delete()
                            other.delete()
                        break

    if st._CURRENT_MAP:
        _handle_physics_collision()
        _process_sensor_events()


def run():
    st._MOUSE_STATE["down"] = False
    st._MOUSE_STATE["released"] = False
    st._MOUSE_STATE["released_frame"] = False
    st._GAME_TIME = 0.0
    st._WAIT_TIMERS.clear()
    st._EVENT_PENDING.clear()
    st._EVENT_ACTIVE.clear()
    main_module = sys.modules["__main__"]
    if not hasattr(main_module, "loop"):
        return

    st._PERF_STATS["last_time"] = time.time()
    accumulator = 0.0
    prev_time = time.perf_counter()

    while True:
        if st._STOPPED:
            break

        now = time.perf_counter()
        frame_time = min(now - prev_time, st._MAX_FRAME_TIME)
        prev_time = now
        accumulator += frame_time

        steps = 0
        while accumulator >= st._PHYSICS_DT and steps < st._MAX_PHYSICS_STEPS:
            # 暂停时也要同步输入快照：用户代码需要靠按键检测来调用 resume()
            _sync_input_frame()
            _promote_event_frame()

            _begin_physics_step()
            main_module.loop()
            _end_physics_step()

            accumulator -= st._PHYSICS_DT
            steps += 1

        if accumulator > st._PHYSICS_DT * st._MAX_PHYSICS_STEPS:
            accumulator = 0.0

        # 相机跟随（地图属性设置 / 代码 camera_follow()）
        _update_camera_follow()

        # 同步位置跟随（挂点/角色），再合并发送本帧所有精灵更新
        _update_follows()
        _flush_frame_updates()

        st._MOUSE_STATE["last_down"] = st._MOUSE_STATE["down"]

        st._PERF_STATS["frame_count"] += 1
        t = time.time()
        duration = t - st._PERF_STATS["last_time"]
        if duration >= 0.5:
            fps = st._PERF_STATS["frame_count"] / duration
            st._PERF_STATS["last_fps"] = round(fps, 1)
            if st._SHOW_FPS:
                _send_fps_to_ide(fps)
            st._PERF_STATS["frame_count"] = 0
            st._PERF_STATS["last_time"] = t

        # 刷出监听线程的待发响应
        while st._PENDING_RESPONSES:
            print(st._PENDING_RESPONSES.pop(0))

        # 帧率限制：混合等待策略。time.sleep() 睡大部分时间省电，
        # 末尾用精确自旋补齐 macOS time.sleep() 的精度不足
        target_frame_time = 1.0 / 60.0
        elapsed = time.perf_counter() - now
        remaining = target_frame_time - elapsed
        if remaining > 0.003:
            # 用 sleep 睡大部分时间（省电），留约 1.5ms 给自旋
            time.sleep(remaining - 0.0015)
            # 精确自旋补齐剩余时间
            while time.perf_counter() - now < target_frame_time:
                pass
        elif remaining > 0:
            # 剩余时间很少，直接自旋（避免 sleep 精度问题）
            while time.perf_counter() - now < target_frame_time:
                pass


def register_generator(gen):
    """注册一个 generator 到调度器"""
    st._generators.append(gen)


def unregister_generator(gen):
    """从调度器移除一个 generator"""
    if gen in st._generators:
        st._generators.remove(gen)


def start_game(project_dir=None, target_file=None):
    """
    新版游戏启动函数：使用 generator 调度模式

    Args:
        project_dir: 项目目录路径，用于自动发现 .py 文件
        target_file: 指定要运行的文件路径
    """

    st._STOPPED = False
    st._MOUSE_STATE["down"] = False
    st._MOUSE_STATE["released"] = False
    st._MOUSE_STATE["released_frame"] = False
    st._GAME_TIME = 0.0
    st._WAIT_TIMERS.clear()
    st._EVENT_PENDING.clear()
    st._EVENT_ACTIVE.clear()

    # 如果提供了项目目录，使用脚本发现模块
    if project_dir:
        from script_runner import discover_and_merge
        try:
            script_content = discover_and_merge(project_dir, target_file)
        except SyntaxError as e:
            print(f"[错误] {e}")
            return
        if not script_content:
            print("[错误] 没有找到 Python 文件")
            return

        # 执行脚本，注册 generator
        exec_globals = {
            "__name__": "__main__",
            "Sprite": Sprite,
            "Timer": Timer,
            "input": _custom_input,
            "key_down": key_down,
            "key_pressed": key_pressed,
            "key_up": key_up,
            "mouse": mouse,
            "mouse_down": mouse_down,
            "mouse_pressed": mouse_pressed,
            "mouse_up": mouse_up,
            "time_passed": time_passed,
            "wait": wait,  # 兼容旧项目
            "load_map": load_map,
            "play_sound": play_sound,
            "stop_sound": stop_sound,
            "show_text": show_text,
            "shake": shake,
            "camera_follow": camera_follow,
            "show_fps": show_fps,
            "show_collision": show_collision,
            "random_int": random_int,
            "random_float": random_float,
            "broadcast": broadcast,
            "receive": receive,
            "on_receive": on_receive,
            "pause": pause,
            "resume": resume,
            "is_paused": is_paused,
            "stop": stop_game,
            "register_generator": register_generator,
        }
        exec(script_content, exec_globals)

    # 主循环
    st._PERF_STATS["last_time"] = time.time()
    accumulator = 0.0
    prev_time = time.perf_counter()

    while True:
        # 用户可能用 `from bingo_engine import *` 拿到只设置 _STOPPED 的 stop()，
        # 与 exec_globals 里抛 GameStop 的版本并存，两种都要能真正结束游戏
        if st._STOPPED:
            return

        now = time.perf_counter()
        frame_time = min(now - prev_time, st._MAX_FRAME_TIME)
        prev_time = now
        accumulator += frame_time

        # 物理步进
        steps = 0
        while accumulator >= st._PHYSICS_DT and steps < st._MAX_PHYSICS_STEPS:
            # 暂停时也要同步输入快照：学生代码需要靠按键检测来调用 resume()
            _sync_input_frame()
            _promote_event_frame()

            _begin_physics_step()

            # 执行所有 generator（每帧一次迭代）
            # 暂停时照常执行：文档约定「程序还在跑」，否则 resume() 永远不会被调用
            for gen in list(st._generators):
                try:
                    next(gen)
                except StopIteration:
                    st._generators.remove(gen)
                except GameStop:
                    st._generators.clear()
                    return
                except Exception as e:
                    print(f"[错误] Generator 错误: {e}")
                    st._generators.remove(gen)

            if not st._PAUSED:
                # 所有 generator 结束且无活跃行为时自动退出主循环，
                # 让 Python 进程正常结束，IDE 才能收到 engine:finished 复位运行按钮
                if not st._generators and not st._SAY_TIMERS:
                    _has_active = any(
                        (s._speed > 0) or
                        (getattr(s, "animation_state", None) and s.animation_state.get("is_playing", False)) or
                        bool(s._on_hit_callbacks) or
                        bool(s._sensor_enter_callbacks) or
                        bool(s._sensor_exit_callbacks) or
                        s._follow_ref is not None
                        for s in st._SPRITES.values() if not s._is_deleted
                    )
                    if not _has_active:
                        return

            _end_physics_step()

            accumulator -= st._PHYSICS_DT
            steps += 1

        if accumulator > st._PHYSICS_DT * st._MAX_PHYSICS_STEPS:
            accumulator = 0.0

        # 相机跟随（地图属性设置 / 代码 camera_follow()）
        _update_camera_follow()

        # 同步位置跟随（挂点/角色），再帧合并发送
        _update_follows()
        _flush_frame_updates()

        # 状态更新
        st._MOUSE_STATE["last_down"] = st._MOUSE_STATE["down"]

        # FPS 统计
        st._PERF_STATS["frame_count"] += 1
        t = time.time()
        duration = t - st._PERF_STATS["last_time"]
        if duration >= 0.5:
            fps = st._PERF_STATS["frame_count"] / duration
            st._PERF_STATS["last_fps"] = round(fps, 1)
            if st._SHOW_FPS:
                _send_fps_to_ide(fps)
            st._PERF_STATS["frame_count"] = 0
            st._PERF_STATS["last_time"] = t

        # 刷出监听线程的待发响应
        while st._PENDING_RESPONSES:
            print(st._PENDING_RESPONSES.pop(0))

        # 帧率限制
        target_frame_time = 1.0 / 60.0
        elapsed = time.perf_counter() - now
        remaining = target_frame_time - elapsed
        if remaining > 0.003:
            time.sleep(remaining - 0.0015)
            while time.perf_counter() - now < target_frame_time:
                pass
        elif remaining > 0:
            while time.perf_counter() - now < target_frame_time:
                pass


def _update_sprite_animation(sprite):
    """更新精灵动画帧"""
    if not hasattr(sprite, "animation_state") or not sprite.animation_state:
        return

    sprite_state = sprite.animation_state
    if not sprite_state.get("is_playing", True):
        return

    t = time.time()
    if t - sprite_state["last_frame_time"] >= sprite_state["frame_duration"]:
        sprite_state["current_frame"] += 1
        if sprite_state["current_frame"] > sprite_state["end"]:
            if sprite_state.get("loop", True):
                sprite_state["current_frame"] = sprite_state["start"]
            else:
                sprite_state["current_frame"] = sprite_state["end"]
                sprite_state["is_playing"] = False
        sprite_state["last_frame_time"] = t
        sprite._update_animation_frame()
