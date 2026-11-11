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
from sprite import Sprite, _resolve_click_target
from timing import Timer, time_passed, wait
from user_error import report_code_errors, report_error, report_user_error
import engine_state as st


# ---------- 内部函数 ----------

_READY_SENT = False


def _flush_updates_maybe():
    """帧末合并发送精灵更新。

    性能模式下隔帧发送（30 次/秒）：更新里存的是绝对坐标，少发一半包只是画面刷新
    变疏，不会影响游戏速度；逻辑步进始终保持 60Hz。
    """
    st._FRAME_SEQ += 1
    if st._PERF_MODE and (st._FRAME_SEQ & 1):
        return
    _flush_frame_updates()


def _notify_ready():
    """用户代码的初始化（建角色、载地图等）全部完成后，通知 IDE 结束启动加载页。
    旧 run() 与新 start_game() 两条入口都会调用，保证每次运行只发一次。"""
    global _READY_SENT
    if _READY_SENT:
        return
    _READY_SENT = True
    print(json.dumps({"type": "GAME_READY", "data": {}}))


# 前端异常时不要永远卡住：最多等这么久就自己开始。
# 旧机器上贴图解码 + 首帧渲染可能明显超过 5 秒，超时太短会在加载页还盖着时
# 就悄悄开跑，撤掉加载页的瞬间角色已经移动了一段（看起来像闪了一下旧画面）。
_START_GATE_TIMEOUT = 15.0


def _wait_for_start():
    """等前端把启动加载页收起后再开始跑主循环。
    等待期间主循环尚未进入，角色位置、动画、generator 都不会动，
    避免加载页还盖着时角色已经走出一段距离。"""
    st._GAME_START_GATE.wait(timeout=_START_GATE_TIMEOUT)


def _send_fps_to_ide(fps):
    """内部统计并发送 FPS 数值"""
    packet = {"type": "FPS_UPDATE", "data": {"fps": round(fps, 1)}}
    print(json.dumps(packet))


def _reset_perf_window():
    """重置 FPS / 逻辑耗时的统计窗口（每次运行开始时调用）"""
    st._PERF_STATS["last_time"] = time.time()
    st._PERF_STATS["frame_count"] = 0
    st._PERF_STATS["logic_sum"] = 0.0
    st._PERF_STATS["logic_max"] = 0.0
    st._PERF_STATS["logic_frames"] = 0


def _record_logic_time(dt):
    """累计本帧逻辑耗时（秒）。窗口统计由 _send_perf_stats 汇总上报。"""
    stats = st._PERF_STATS
    stats["logic_sum"] = stats.get("logic_sum", 0.0) + dt
    stats["logic_frames"] = stats.get("logic_frames", 0) + 1
    if dt > stats.get("logic_max", 0.0):
        stats["logic_max"] = dt


def _send_perf_stats(fps):
    """随 FPS 刷新一并上报逻辑耗时统计（每 0.5 秒一条，开销可忽略）。

    IDE 性能面板用它区分「渲染慢」还是「游戏逻辑慢」：
    逻辑耗时 = 主循环一帧实际花掉的时间（物理步进 + 用户 generator + 更新序列化 + 输出），
    不含末尾的 time.sleep 等待。
    """
    stats = st._PERF_STATS
    frames = stats.get("logic_frames", 0)
    if frames <= 0:
        return
    packet = {
        "type": "PERF_STATS",
        "data": {
            "logic_avg_ms": round(stats.get("logic_sum", 0.0) / frames * 1000.0, 2),
            "logic_max_ms": round(stats.get("logic_max", 0.0) * 1000.0, 2),
        },
    }
    print(json.dumps(packet))
    stats["logic_sum"] = 0.0
    stats["logic_max"] = 0.0
    stats["logic_frames"] = 0


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
            # 禁止下滑功能据此区分主动移动与斜面推挤下滑；
            # _frame_start_y 供「移动平台跟随」算平台本帧走了多远
            sprite._frame_start_x = sprite._x
            sprite._frame_start_y = sprite._y


def _process_click_events():
    """把本物理步的鼠标点击派发给命中的角色（on_clicked 回调）。

    和 is_clicked 共用 _resolve_click_target 的解析结果，一次按下只触发一次；
    暂停中也照常派发，与 mouse_pressed() 的语义保持一致。
    """
    seq = st._CLICK_STATE["active_seq"]
    if seq < 0 or st._CLICK_STATE["dispatched_seq"] == seq:
        return
    st._CLICK_STATE["dispatched_seq"] = seq
    target_id = _resolve_click_target()
    if target_id is None:
        return
    sprite = st._SPRITES.get(target_id)
    if sprite is None or sprite._is_deleted or not sprite._visible:
        return
    callback = getattr(sprite, "_click_callback", None)
    if callback:
        _safe_call(callback, sprite)


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
    st._MOUSE_STATE["down_step_prev"] = False
    st._MOUSE_STATE["released"] = False
    st._MOUSE_STATE["released_frame"] = False
    st._CLICK_STATE.update(press_seq=0, active_seq=-1, resolved_seq=-1, target_id=None, dispatched_seq=-1)
    st._GAME_TIME = 0.0
    st._WAIT_TIMERS.clear()
    st._EVENT_PENDING.clear()
    st._EVENT_ACTIVE.clear()
    main_module = sys.modules["__main__"]
    if not hasattr(main_module, "loop"):
        return

    _reset_perf_window()

    _notify_ready()
    _wait_for_start()

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
            _process_click_events()

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
        _flush_updates_maybe()

        st._MOUSE_STATE["last_down"] = st._MOUSE_STATE["down"]

        st._PERF_STATS["frame_count"] += 1
        t = time.time()
        duration = t - st._PERF_STATS["last_time"]
        if duration >= 0.5:
            fps = st._PERF_STATS["frame_count"] / duration
            st._PERF_STATS["last_fps"] = round(fps, 1)
            if st._SHOW_FPS:
                _send_fps_to_ide(fps)
            _send_perf_stats(fps)
            st._PERF_STATS["frame_count"] = 0
            st._PERF_STATS["last_time"] = t

        # 刷出监听线程的待发响应
        while st._PENDING_RESPONSES:
            print(st._PENDING_RESPONSES.pop(0))

        # 帧率限制：纯 time.sleep()，不 busy-wait 自旋。
        # 自旋（while pass）会把一个 CPU 核心占满，低端机器直接过热降频、越跑越卡。
        # Scratch 用浏览器 requestAnimationFrame 调度，从不自旋——这是我们和 Scratch 的关键差异。
        # time.sleep 精度虽不如自旋，但省电优先；帧率偶尔波动远比 CPU 100% 好。
        target_frame_time = 1.0 / 60.0
        elapsed = time.perf_counter() - now
        _record_logic_time(elapsed)
        remaining = target_frame_time - elapsed
        if remaining > 0:
            time.sleep(remaining)


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
        from script_runner import CodeErrors, load_scripts
        try:
            scripts = load_scripts(project_dir, target_file)
        except CodeErrors as err:
            # 语法错误一次性全部列出（文件 + 编辑器里的真实行号）
            report_code_errors(err.errors)
            return
        if not scripts:
            report_error("没有找到 Python 文件")
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
        # 逐文件执行（共用同一个 globals，跨文件变量照常可见）。
        # 每个文件单独编译并带文件名/真实行号，出错时能直接定位到学生写的那一行。
        for _file_path, _code in scripts:
            try:
                exec(_code, exec_globals)
            except GameStop:
                return
            except Exception as e:
                report_user_error(e)
                return

    # 初始化阶段产生的变换（goto / scale / angle / 可见性等）都进了帧缓冲，
    # 必须在通知就绪前刷出去：否则性能模式隔帧发送会跳过第一次 flush，
    # 而「没有 generator、也没有活跃行为」时主循环第一步就正常退出，
    # 这些初始设置就永远发不出去——前端只看到 CREATE 里的默认位置/大小/角度。
    _flush_frame_updates()

    # 初始化完成：通知 IDE 结束启动加载页（旧 run() 模式已在 run() 内部发过，不会重复）
    _notify_ready()
    _wait_for_start()

    # 主循环
    _reset_perf_window()
    accumulator = 0.0
    prev_time = time.perf_counter()

    while True:
        # 用户可能用 `from bingo_engine import *` 拿到只设置 _STOPPED 的 stop()，
        # 与 exec_globals 里抛 GameStop 的版本并存，两种都要能真正结束游戏
        if st._STOPPED:
            _flush_frame_updates()  # 退出前补发最后一帧，性能模式可能刚跳过这次发送
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
            _process_click_events()

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
                    _flush_frame_updates()  # 退出前补发最后一帧
                    return
                except Exception as e:
                    # 报错带文件名和真实行号，中小学生在控制台能直接找到写错的那一行
                    report_user_error(e)
                    st._generators.remove(gen)

            if not st._PAUSED:
                # 所有 generator 结束且无活跃行为时自动退出主循环，
                # 让 Python 进程正常结束，IDE 才能收到 engine:finished 复位运行按钮
                if not st._generators and not st._SAY_TIMERS:
                    _has_active = any(
                        (s._speed > 0) or
                        (getattr(s, "animation_state", None) and s.animation_state.get("is_playing", False)) or
                        bool(s._on_hit_callbacks) or
                        bool(getattr(s, "_click_callback", None)) or
                        bool(s._sensor_enter_callbacks) or
                        bool(s._sensor_exit_callbacks) or
                        s._follow_ref is not None
                        for s in st._SPRITES.values() if not s._is_deleted
                    )
                    if not _has_active:
                        # 程序自然结束：补发最后一帧，性能模式隔帧发送不能吞掉最终画面
                        _flush_frame_updates()
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
        _flush_updates_maybe()

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
            _send_perf_stats(fps)
            st._PERF_STATS["frame_count"] = 0
            st._PERF_STATS["last_time"] = t

        # 刷出监听线程的待发响应
        while st._PENDING_RESPONSES:
            print(st._PENDING_RESPONSES.pop(0))

        # 帧率限制
        # 帧率限制：纯 time.sleep()，不 busy-wait 自旋（理由同 run()）
        target_frame_time = 1.0 / 60.0
        elapsed = time.perf_counter() - now
        _record_logic_time(elapsed)
        remaining = target_frame_time - elapsed
        if remaining > 0:
            time.sleep(remaining)


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
