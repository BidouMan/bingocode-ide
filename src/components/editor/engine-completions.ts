/** 引擎 API 补全项 — 所有 description 均为中文 */

/** Monaco CompletionItemKind 枚举值（避免动态导入的类型问题） */
const CompletionItemKind = {
  Class: 7,
  Function: 3,
  Method: 6,
  Property: 10,
  Variable: 12,
  Keyword: 14,
} as const

/** 补全项结构 */
interface EngineCompletionItem {
  label: string
  kind: number
  insertText: string
  documentation: string
  detail: string
}

// ─── Sprite 类方法 ───

const spriteMethods: EngineCompletionItem[] = [
  // 构造
  { label: 'Sprite', kind: CompletionItemKind.Class, insertText: 'Sprite', documentation: '创建一个精灵角色\n\n用法：sprite = Sprite("文件名")\n文件名对应 assets/sprites/ 下的精灵包或 PNG 文件', detail: 'class Sprite(filename)' },

  // 移动
  { label: 'goto', kind: CompletionItemKind.Method, insertText: 'goto', documentation: '移到指定坐标\n\ngoto(x, y)', detail: 'goto(x, y)' },
  { label: 'set_xy', kind: CompletionItemKind.Method, insertText: 'set_xy', documentation: '设置坐标（带碰撞检测）\n\nset_xy(x, y)', detail: 'set_xy(x, y)' },
  { label: 'set_x', kind: CompletionItemKind.Method, insertText: 'set_x', documentation: '设置水平位置\n\nset_x(x)', detail: 'set_x(x)' },
  { label: 'set_y', kind: CompletionItemKind.Method, insertText: 'set_y', documentation: '设置垂直位置\n\nset_y(y)', detail: 'set_y(y)' },
  { label: 'add_x', kind: CompletionItemKind.Method, insertText: 'add_x', documentation: '将 x 坐标增加（或减少）一定数值\n\nadd_x(delta_x)', detail: 'add_x(delta_x)' },
  { label: 'add_y', kind: CompletionItemKind.Method, insertText: 'add_y', documentation: '将 y 坐标增加（或减少）一定数值\n\nadd_y(delta_y)', detail: 'add_y(delta_y)' },
  { label: 'move', kind: CompletionItemKind.Method, insertText: 'move', documentation: '朝着当前 angle 方向移动 distance 像素\n\nmove(distance)', detail: 'move(distance)' },
  { label: 'goto_rand', kind: CompletionItemKind.Method, insertText: 'goto_rand', documentation: '移到随机位置（0-640, 0-480）', detail: 'goto_rand()' },
  { label: 'set_speed', kind: CompletionItemKind.Method, insertText: 'set_speed', documentation: '设置持续速度，引擎每帧自动沿当前方向移动\n\nset_speed(speed)', detail: 'set_speed(speed)' },

  // 物理 / 平台跳跃
  { label: 'jump', kind: CompletionItemKind.Method, insertText: 'jump', documentation: '角色跳跃\n\njump(power=10)\npower: 跳跃力度（默认10，越大跳得越高）', detail: 'jump(power=10)' },
  { label: 'cut_jump', kind: CompletionItemKind.Method, insertText: 'cut_jump', documentation: '截断跳跃（松开跳跃键时调用），使角色提前下落\n用于实现变高跳跃', detail: 'cut_jump()' },
  { label: 'drop_through', kind: CompletionItemKind.Method, insertText: 'drop_through', documentation: '从跳板下穿：角色站在跳板上时，按下键可穿过跳板下落', detail: 'drop_through()' },

  // 外观
  { label: 'set_scale', kind: CompletionItemKind.Method, insertText: 'set_scale', documentation: '设置缩放比例（5-1000）\n\nset_scale(value)', detail: 'set_scale(value)' },
  { label: 'add_scale', kind: CompletionItemKind.Method, insertText: 'add_scale', documentation: '在当前缩放比例的基础上增加 value（单位为百分比）\n例如：add_scale(10) 会让角色变大 10%', detail: 'add_scale(value)' },
  { label: 'set_rotation_mode', kind: CompletionItemKind.Method, insertText: 'set_rotation_mode', documentation: '设置旋转模式\n\nset_rotation_mode(style)\n- "all": 自由旋转（默认）\n- "left_right": 仅水平翻转\n- "none": 不旋转', detail: 'set_rotation_mode(style)' },
  { label: 'show', kind: CompletionItemKind.Method, insertText: 'show', documentation: '显示角色', detail: 'show()' },
  { label: 'hide', kind: CompletionItemKind.Method, insertText: 'hide', documentation: '隐藏角色（仅仅是看不见，物体还在内存里）', detail: 'hide()' },
  { label: 'say', kind: CompletionItemKind.Method, insertText: 'say', documentation: '让角色说话。新话会替换旧话\n\nsay("你好") → 永久显示\nsay("得分+1", 2) → 2秒后自动消失', detail: 'say(text, seconds=0)' },
  { label: 'play', kind: CompletionItemKind.Method, insertText: 'play', documentation: '播放指定名称的动画\n\nplay("idle")\nplay("walk", 0.2) → 0.2秒过渡', detail: 'play(animation_name, transition_time=0.1)' },
  { label: 'set_angle', kind: CompletionItemKind.Method, insertText: 'set_angle', documentation: '设置旋转角度\n\nset_angle(angle)', detail: 'set_angle(angle)' },

  // 朝向
  { label: 'look_at', kind: CompletionItemKind.Method, insertText: 'look_at', documentation: '让当前角色看向另一个角色或鼠标（自动旋转角度）\n\ntarget 可以是另一个 Sprite 或 mouse 对象', detail: 'look_at(target)' },

  // 边界
  { label: 'edge_bounce', kind: CompletionItemKind.Method, insertText: 'edge_bounce', documentation: '基于 Hitbox 的精准反弹，自动识别世界边界\n碰到边界时自动反转角度', detail: 'edge_bounce()' },

  // 感知 / 碰撞
  { label: 'is_touch_edge', kind: CompletionItemKind.Method, insertText: 'is_touch_edge', documentation: '精准边界检测：判定角色的实际视觉边缘是否越过了舞台', detail: 'is_touch_edge() -> bool' },
  { label: 'is_out_side', kind: CompletionItemKind.Method, insertText: 'is_out_side', documentation: '完全出界检测：只有当角色整体（所有像素）都离开舞台时才返回 True', detail: 'is_out_side() -> bool' },
  { label: 'is_touch', kind: CompletionItemKind.Method, insertText: 'is_touch', documentation: '判断是否碰到另一个 Sprite、鼠标或带有指定标签的图块\n\nis_touch(target)\ntarget 可以是 Sprite、mouse 或字符串（图块标签）', detail: 'is_touch(target) -> bool' },
  { label: 'touch_group', kind: CompletionItemKind.Method, insertText: 'touch_group', documentation: '判断是否撞到了某个组里的任意成员\n如果撞到了，返回那个成员；没撞到返回 None', detail: 'touch_group(group_name) -> Sprite or None' },
  { label: 'distance_to', kind: CompletionItemKind.Method, insertText: 'distance_to', documentation: '计算当前角色视觉中心点到目标（Sprite 或 mouse）的距离', detail: 'distance_to(target) -> float' },
  { label: 'is_on_floor', kind: CompletionItemKind.Method, insertText: 'is_on_floor', documentation: '检测角色脚底下方是否存在带有碰撞的图块', detail: 'is_on_floor() -> bool' },

  // 分组 / 事件
  { label: 'add_to_group', kind: CompletionItemKind.Method, insertText: 'add_to_group', documentation: '将角色归类，比如 "enemies", "bullets"\n\nadd_to_group(group_name)', detail: 'add_to_group(group_name)' },
  { label: 'on_hit', kind: CompletionItemKind.Method, insertText: 'on_hit', documentation: '注册碰撞回调\n\non_hit("bullets", callback)\ncallback(bullet, other)', detail: 'on_hit(group, callback=None)' },
  { label: 'broadcast', kind: CompletionItemKind.Method, insertText: 'broadcast', documentation: '发送广播（触发所有接收该事件的回调）\n\nbroadcast("事件名")', detail: 'broadcast(event_name)' },

  // 生命周期
  { label: 'delete', kind: CompletionItemKind.Method, insertText: 'delete', documentation: '彻底删除（视觉移除 + 物理移除 + 内存清理）', detail: 'delete()' },
]

/** Sprite 属性（通过 . 触发时显示） */
const spriteProperties: EngineCompletionItem[] = [
  { label: 'x', kind: CompletionItemKind.Property, insertText: 'x', documentation: '水平位置（默认 320）', detail: 'float' },
  { label: 'y', kind: CompletionItemKind.Property, insertText: 'y', documentation: '垂直位置（默认 240）', detail: 'float' },
  { label: 'angle', kind: CompletionItemKind.Property, insertText: 'angle', documentation: '旋转角度（度）', detail: 'float' },
  { label: 'scale', kind: CompletionItemKind.Property, insertText: 'scale', documentation: '缩放比例（百分比，默认 100）', detail: 'float' },
  { label: 'layer', kind: CompletionItemKind.Property, insertText: 'layer', documentation: '图层顺序（越大越靠前）', detail: 'int' },
  { label: 'on_ground', kind: CompletionItemKind.Property, insertText: 'on_ground', documentation: '是否在地面上', detail: 'bool' },
  { label: 'hitbox_scale', kind: CompletionItemKind.Property, insertText: 'hitbox_scale', documentation: '碰撞箱大小倍率（默认 1.0）', detail: 'float' },
]

/** Timer 类 */
const timerCompletions: EngineCompletionItem[] = [
  { label: 'Timer', kind: CompletionItemKind.Class, insertText: 'Timer', documentation: '创建一个定时器\n\nTimer(seconds, loop=True, autostart=False)\n- seconds: 间隔秒数\n- loop: 是否循环\n- autostart: 是否立即开始', detail: 'class Timer(seconds, loop, autostart)' },
]

/** Timer 方法（通过 . 触发时显示） */
const timerMethods: EngineCompletionItem[] = [
  { label: 'start', kind: CompletionItemKind.Method, insertText: 'start', documentation: '启动定时器', detail: 'start()' },
  { label: 'stop', kind: CompletionItemKind.Method, insertText: 'stop', documentation: '停止定时器', detail: 'stop()' },
  { label: 'is_timeout', kind: CompletionItemKind.Method, insertText: 'is_timeout', documentation: '检查定时器是否到期\n到期后自动重置，loop=False 时停止', detail: 'is_timeout() -> bool' },
]

/** 全局函数 */
const globalFunctions: EngineCompletionItem[] = [
  // 输入
  { label: 'key_down', kind: CompletionItemKind.Function, insertText: 'key_down', documentation: '判断某个键是否被按住（持续按住返回 True）\n\nkey_down("a")\nkey_down("space")\nkey_down("left")', detail: 'key_down(key) -> bool' },
  { label: 'key_pressed', kind: CompletionItemKind.Function, insertText: 'key_pressed', documentation: '只有按下的那一帧返回 True\n\nkey_pressed("a")', detail: 'key_pressed(key) -> bool' },
  { label: 'mouse_down', kind: CompletionItemKind.Function, insertText: 'mouse_down', documentation: '判断鼠标是否按下（持续按住返回 True）', detail: 'mouse_down() -> bool' },
  { label: 'mouse_pressed', kind: CompletionItemKind.Function, insertText: 'mouse_pressed', documentation: '单次检测：只有在按下的那一帧返回 True', detail: 'mouse_pressed() -> bool' },

  // 事件
  { label: 'wait', kind: CompletionItemKind.Function, insertText: 'wait', documentation: '每 N 秒返回一次 True\n\n用法：if wait(1): do_something()', detail: 'wait(seconds) -> bool' },
  { label: 'broadcast', kind: CompletionItemKind.Function, insertText: 'broadcast', documentation: '发送全局广播（触发所有接收该事件的回调）\n\nbroadcast("事件名")', detail: 'broadcast(event_name)' },
  { label: 'receive', kind: CompletionItemKind.Function, insertText: 'receive', documentation: '注册全局广播接收\n\nreceive("事件名", callback)', detail: 'receive(event_name, callback)' },

  // 游戏控制
  { label: 'pause', kind: CompletionItemKind.Function, insertText: 'pause', documentation: '暂停游戏（loop 仍运行，但精灵停止移动）', detail: 'pause()' },
  { label: 'resume', kind: CompletionItemKind.Function, insertText: 'resume', documentation: '继续游戏', detail: 'resume()' },
  { label: 'is_paused', kind: CompletionItemKind.Function, insertText: 'is_paused', documentation: '检查游戏是否暂停', detail: 'is_paused() -> bool' },
  { label: 'stop', kind: CompletionItemKind.Function, insertText: 'stop', documentation: '停止游戏（退出 run 循环）', detail: 'stop()' },
  { label: 'stop_game', kind: CompletionItemKind.Function, insertText: 'stop_game', documentation: '停止游戏（抛出异常中断 generator）', detail: 'stop_game()' },
  { label: 'run', kind: CompletionItemKind.Function, insertText: 'run', documentation: '启动游戏循环（经典 while True 模式）\n每帧调用 loop() 函数', detail: 'run()' },
  { label: 'start_game', kind: CompletionItemKind.Function, insertText: 'start_game', documentation: '启动游戏（generator 调度模式）\n自动发现并运行项目中的 Python 脚本', detail: 'start_game()' },

  // 渲染
  { label: 'show_fps', kind: CompletionItemKind.Function, insertText: 'show_fps', documentation: '显示/隐藏帧率计数器\n\nshow_fps() → 显示\nshow_fps(False) → 隐藏', detail: 'show_fps(visible=True)' },
  { label: 'show_collision', kind: CompletionItemKind.Function, insertText: 'show_collision', documentation: '显示精灵的碰撞箱可视化', detail: 'show_collision(sprite)' },
  { label: 'draw_text', kind: CompletionItemKind.Function, insertText: 'draw_text', documentation: '在屏幕指定位置绘制文字\n\ndraw_text(100, 50, "分数:", score)', detail: 'draw_text(x, y, *args)' },
  { label: 'shake', kind: CompletionItemKind.Function, insertText: 'shake', documentation: '屏幕震动效果\n\nshake(intensity=5, duration=0.3)', detail: 'shake(intensity=5, duration=0.3)' },

  // 音频
  { label: 'play_sound', kind: CompletionItemKind.Function, insertText: 'play_sound', documentation: '播放音效\n\nplay_sound("音效名")\nplay_sound("音效名", loop=True)', detail: 'play_sound(sound_name, loop=False)' },
  { label: 'stop_sound', kind: CompletionItemKind.Function, insertText: 'stop_sound', documentation: '停止音效。不传参数则停止所有音效\n\nstop_sound("音效名")\nstop_sound()', detail: 'stop_sound(sound_name=None)' },

  // 地图 / 摄像机
  { label: 'load_map', kind: CompletionItemKind.Function, insertText: 'load_map', documentation: '加载并显示地图\n\nload_map("地图名")\n地图名对应 assets/maps/ 下的地图包', detail: 'load_map(map_name) -> bool' },
  { label: 'follow', kind: CompletionItemKind.Function, insertText: 'follow', documentation: '设置摄像机跟随指定精灵\n\nfollow(sprite)', detail: 'follow(sprite)' },

  // 随机工具
  { label: 'random_int', kind: CompletionItemKind.Function, insertText: 'random_int', documentation: '在 min_val 和 max_val 之间取随机整数（包含两端）\n\nrandom_int(1, 10)', detail: 'random_int(min_val, max_val) -> int' },
  { label: 'random_float', kind: CompletionItemKind.Function, insertText: 'random_float', documentation: '在 min_val 和 max_val 之间取随机浮点数\n\nrandom_float(0, 1)', detail: 'random_float(min_val=0.0, max_val=1.0) -> float' },

  // 生成器
  { label: 'register_generator', kind: CompletionItemKind.Function, insertText: 'register_generator', documentation: '注册一个 generator 到调度器', detail: 'register_generator(gen)' },
  { label: 'unregister_generator', kind: CompletionItemKind.Function, insertText: 'unregister_generator', documentation: '从调度器移除一个 generator', detail: 'unregister_generator(gen)' },
]

/** 全局对象 */
const globalObjects: EngineCompletionItem[] = [
  { label: 'mouse', kind: CompletionItemKind.Variable, insertText: 'mouse', documentation: '全局鼠标对象\n\nmouse.x → 鼠标水平位置\nmouse.y → 鼠标垂直位置', detail: 'mouse object' },
  { label: 'GameStop', kind: CompletionItemKind.Class, insertText: 'GameStop', documentation: '游戏停止异常\n由 stop_game() 抛出，用于中断 generator', detail: 'class GameStop(Exception)' },
]

/** mouse 对象属性（通过 . 触发时显示） */
const mouseProperties: EngineCompletionItem[] = [
  { label: 'x', kind: CompletionItemKind.Property, insertText: 'x', documentation: '鼠标水平位置（游戏坐标）', detail: 'float' },
  { label: 'y', kind: CompletionItemKind.Property, insertText: 'y', documentation: '鼠标垂直位置（游戏坐标）', detail: 'float' },
]

// ─── 汇总导出 ───

/** 引擎 API 全量列表（全局补全时使用） */
export const allEngineCompletions: EngineCompletionItem[] = [
  ...spriteMethods,
  ...spriteProperties,
  ...timerCompletions,
  ...globalFunctions,
  ...globalObjects,
]

/** 点号触发时，按变量名映射的方法/属性列表 */
export const dotCompletions: Record<string, EngineCompletionItem[]> = {
  // Sprite 实例的方法 + 属性（不包含 Sprite 类本身）
  sprite: [...spriteMethods.filter(c => c.label !== 'Sprite'), ...spriteProperties],
  // Timer 实例的方法
  timer: timerMethods,
  // mouse 对象的属性
  mouse: mouseProperties,
}

/** Sprite 实例方法（点号触发时的默认补全，变量名无法识别时使用） */
export const spriteDotDefault: EngineCompletionItem[] = [
  ...spriteMethods.filter(c => c.label !== 'Sprite'),
  ...spriteProperties,
]

// ─── Python 标准库补全（代码模式使用） ───

/** Python 内置函数 */
const pythonBuiltins: EngineCompletionItem[] = [
  { label: 'print', kind: CompletionItemKind.Function, insertText: 'print', documentation: '打印输出到控制台', detail: 'print(*objects, sep=" ", end="\\n")' },
  { label: 'len', kind: CompletionItemKind.Function, insertText: 'len', documentation: '返回对象的长度', detail: 'len(obj) -> int' },
  { label: 'range', kind: CompletionItemKind.Function, insertText: 'range', documentation: '生成一个整数序列', detail: 'range(stop) / range(start, stop[, step])' },
  { label: 'int', kind: CompletionItemKind.Function, insertText: 'int', documentation: '转换为整数', detail: 'int(x=0) / int(x, base=10)' },
  { label: 'str', kind: CompletionItemKind.Function, insertText: 'str', documentation: '转换为字符串', detail: 'str(object="")' },
  { label: 'float', kind: CompletionItemKind.Function, insertText: 'float', documentation: '转换为浮点数', detail: 'float(x=0.0)' },
  { label: 'list', kind: CompletionItemKind.Function, insertText: 'list', documentation: '创建列表或转换为列表', detail: 'list(iterable=[])' },
  { label: 'dict', kind: CompletionItemKind.Function, insertText: 'dict', documentation: '创建字典', detail: 'dict(**kwarg) / dict(mapping)' },
  { label: 'tuple', kind: CompletionItemKind.Function, insertText: 'tuple', documentation: '创建元组', detail: 'tuple(iterable=())' },
  { label: 'set', kind: CompletionItemKind.Function, insertText: 'set', documentation: '创建集合', detail: 'set(iterable=set())' },
  { label: 'type', kind: CompletionItemKind.Function, insertText: 'type', documentation: '返回对象的类型', detail: 'type(object)' },
  { label: 'input', kind: CompletionItemKind.Function, insertText: 'input', documentation: '从标准输入读取一行', detail: 'input(prompt="")' },
  { label: 'open', kind: CompletionItemKind.Function, insertText: 'open', documentation: '打开文件', detail: 'open(file, mode="r", encoding=None)' },
  { label: 'abs', kind: CompletionItemKind.Function, insertText: 'abs', documentation: '返回绝对值', detail: 'abs(x)' },
  { label: 'max', kind: CompletionItemKind.Function, insertText: 'max', documentation: '返回最大值', detail: 'max(iterable) / max(a, b, ...)' },
  { label: 'min', kind: CompletionItemKind.Function, insertText: 'min', documentation: '返回最小值', detail: 'min(iterable) / min(a, b, ...)' },
  { label: 'sum', kind: CompletionItemKind.Function, insertText: 'sum', documentation: '求和', detail: 'sum(iterable[, start])' },
  { label: 'sorted', kind: CompletionItemKind.Function, insertText: 'sorted', documentation: '返回排序后的新列表', detail: 'sorted(iterable, *, key=None, reverse=False)' },
  { label: 'reversed', kind: CompletionItemKind.Function, insertText: 'reversed', documentation: '返回反转的迭代器', detail: 'reversed(seq)' },
  { label: 'enumerate', kind: CompletionItemKind.Function, insertText: 'enumerate', documentation: '返回带索引的枚举', detail: 'enumerate(iterable, start=0)' },
  { label: 'zip', kind: CompletionItemKind.Function, insertText: 'zip', documentation: '将多个可迭代对象打包', detail: 'zip(*iterables, strict=False)' },
  { label: 'map', kind: CompletionItemKind.Function, insertText: 'map', documentation: '对每个元素应用函数', detail: 'map(function, iterable, ...)' },
  { label: 'filter', kind: CompletionItemKind.Function, insertText: 'filter', documentation: '过滤元素', detail: 'filter(function, iterable)' },
  { label: 'isinstance', kind: CompletionItemKind.Function, insertText: 'isinstance', documentation: '判断对象是否是某个类型的实例', detail: 'isinstance(object, classinfo)' },
  { label: 'hasattr', kind: CompletionItemKind.Function, insertText: 'hasattr', documentation: '判断对象是否有某个属性', detail: 'hasattr(object, name)' },
  { label: 'getattr', kind: CompletionItemKind.Function, insertText: 'getattr', documentation: '获取对象的属性值', detail: 'getattr(object, name[, default])' },
  { label: 'setattr', kind: CompletionItemKind.Function, insertText: 'setattr', documentation: '设置对象的属性值', detail: 'setattr(object, name, value)' },
  { label: 'round', kind: CompletionItemKind.Function, insertText: 'round', documentation: '四舍五入', detail: 'round(number[, ndigits])' },
  { label: 'bool', kind: CompletionItemKind.Function, insertText: 'bool', documentation: '转换为布尔值', detail: 'bool(x=False)' },
  { label: 'chr', kind: CompletionItemKind.Function, insertText: 'chr', documentation: '整数转字符', detail: 'chr(i)' },
  { label: 'ord', kind: CompletionItemKind.Function, insertText: 'ord', documentation: '字符转整数', detail: 'ord(c)' },
  { label: 'hex', kind: CompletionItemKind.Function, insertText: 'hex', documentation: '转十六进制字符串', detail: 'hex(number)' },
  { label: 'oct', kind: CompletionItemKind.Function, insertText: 'oct', documentation: '转八进制字符串', detail: 'oct(number)' },
  { label: 'bin', kind: CompletionItemKind.Function, insertText: 'bin', documentation: '转二进制字符串', detail: 'bin(number)' },
  { label: 'id', kind: CompletionItemKind.Function, insertText: 'id', documentation: '返回对象的唯一标识', detail: 'id(object)' },
  { label: 'hash', kind: CompletionItemKind.Function, insertText: 'hash', documentation: '返回对象的哈希值', detail: 'hash(object)' },
]

/** Python 关键字 */
const pythonKeywords: EngineCompletionItem[] = [
  { label: 'def', kind: CompletionItemKind.Keyword, insertText: 'def', documentation: '定义函数', detail: 'def function_name():' },
  { label: 'class', kind: CompletionItemKind.Keyword, insertText: 'class', documentation: '定义类', detail: 'class ClassName:' },
  { label: 'if', kind: CompletionItemKind.Keyword, insertText: 'if', documentation: '条件判断', detail: 'if condition:' },
  { label: 'elif', kind: CompletionItemKind.Keyword, insertText: 'elif', documentation: '否则如果', detail: 'elif condition:' },
  { label: 'else', kind: CompletionItemKind.Keyword, insertText: 'else', documentation: '否则', detail: 'else:' },
  { label: 'for', kind: CompletionItemKind.Keyword, insertText: 'for', documentation: '循环', detail: 'for item in iterable:' },
  { label: 'while', kind: CompletionItemKind.Keyword, insertText: 'while', documentation: '循环', detail: 'while condition:' },
  { label: 'return', kind: CompletionItemKind.Keyword, insertText: 'return', documentation: '返回值', detail: 'return value' },
  { label: 'import', kind: CompletionItemKind.Keyword, insertText: 'import', documentation: '导入模块', detail: 'import module_name' },
  { label: 'from', kind: CompletionItemKind.Keyword, insertText: 'from', documentation: '从模块导入', detail: 'from module import name' },
  { label: 'try', kind: CompletionItemKind.Keyword, insertText: 'try', documentation: '异常处理', detail: 'try:' },
  { label: 'except', kind: CompletionItemKind.Keyword, insertText: 'except', documentation: '捕获异常', detail: 'except ExceptionType:' },
  { label: 'finally', kind: CompletionItemKind.Keyword, insertText: 'finally', documentation: '最终执行', detail: 'finally:' },
  { label: 'with', kind: CompletionItemKind.Keyword, insertText: 'with', documentation: '上下文管理器', detail: 'with expression as variable:' },
  { label: 'pass', kind: CompletionItemKind.Keyword, insertText: 'pass', documentation: '空语句占位', detail: 'pass' },
  { label: 'break', kind: CompletionItemKind.Keyword, insertText: 'break', documentation: '跳出循环', detail: 'break' },
  { label: 'continue', kind: CompletionItemKind.Keyword, insertText: 'continue', documentation: '跳过本次循环', detail: 'continue' },
  { label: 'yield', kind: CompletionItemKind.Keyword, insertText: 'yield', documentation: '生成器', detail: 'yield value' },
  { label: 'lambda', kind: CompletionItemKind.Keyword, insertText: 'lambda', documentation: '匿名函数', detail: 'lambda arguments: expression' },
  { label: 'raise', kind: CompletionItemKind.Keyword, insertText: 'raise', documentation: '抛出异常', detail: 'raise Exception("message")' },
  { label: 'assert', kind: CompletionItemKind.Keyword, insertText: 'assert', documentation: '断言', detail: 'assert condition, "message"' },
  { label: 'and', kind: CompletionItemKind.Keyword, insertText: 'and', documentation: '逻辑与', detail: 'a and b' },
  { label: 'or', kind: CompletionItemKind.Keyword, insertText: 'or', documentation: '逻辑或', detail: 'a or b' },
  { label: 'not', kind: CompletionItemKind.Keyword, insertText: 'not', documentation: '逻辑非', detail: 'not a' },
  { label: 'in', kind: CompletionItemKind.Keyword, insertText: 'in', documentation: '成员测试', detail: 'item in iterable' },
  { label: 'is', kind: CompletionItemKind.Keyword, insertText: 'is', documentation: '身份测试', detail: 'a is b' },
  { label: 'True', kind: CompletionItemKind.Keyword, insertText: 'True', documentation: '布尔真值', detail: 'True' },
  { label: 'False', kind: CompletionItemKind.Keyword, insertText: 'False', documentation: '布尔假值', detail: 'False' },
  { label: 'None', kind: CompletionItemKind.Keyword, insertText: 'None', documentation: '空值', detail: 'None' },
  { label: 'global', kind: CompletionItemKind.Keyword, insertText: 'global', documentation: '声明全局变量', detail: 'global variable_name' },
  { label: 'nonlocal', kind: CompletionItemKind.Keyword, insertText: 'nonlocal', documentation: '声明外层变量', detail: 'nonlocal variable_name' },
]

/** Python list 方法 */
const listMethods: EngineCompletionItem[] = [
  { label: 'append', kind: CompletionItemKind.Method, insertText: 'append', documentation: '在末尾添加元素', detail: 'list.append(object)' },
  { label: 'extend', kind: CompletionItemKind.Method, insertText: 'extend', documentation: '扩展列表', detail: 'list.extend(iterable)' },
  { label: 'insert', kind: CompletionItemKind.Method, insertText: 'insert', documentation: '在指定位置插入元素', detail: 'list.insert(index, object)' },
  { label: 'remove', kind: CompletionItemKind.Method, insertText: 'remove', documentation: '移除第一个匹配项', detail: 'list.remove(value)' },
  { label: 'pop', kind: CompletionItemKind.Method, insertText: 'pop', documentation: '移除并返回指定位置的元素', detail: 'list.pop(index=-1)' },
  { label: 'clear', kind: CompletionItemKind.Method, insertText: 'clear', documentation: '清空列表', detail: 'list.clear()' },
  { label: 'index', kind: CompletionItemKind.Method, insertText: 'index', documentation: '返回第一个匹配项的索引', detail: 'list.index(value[, start[, stop]])' },
  { label: 'count', kind: CompletionItemKind.Method, insertText: 'count', documentation: '计算出现次数', detail: 'list.count(value)' },
  { label: 'sort', kind: CompletionItemKind.Method, insertText: 'sort', documentation: '原地排序', detail: 'list.sort(*, key=None, reverse=False)' },
  { label: 'reverse', kind: CompletionItemKind.Method, insertText: 'reverse', documentation: '原地反转', detail: 'list.reverse()' },
  { label: 'copy', kind: CompletionItemKind.Method, insertText: 'copy', documentation: '浅拷贝', detail: 'list.copy()' },
]

/** Python dict 方法 */
const dictMethods: EngineCompletionItem[] = [
  { label: 'get', kind: CompletionItemKind.Method, insertText: 'get', documentation: '获取值（不存在返回默认值）', detail: 'dict.get(key, default=None)' },
  { label: 'setdefault', kind: CompletionItemKind.Method, insertText: 'setdefault', documentation: '设置默认值', detail: 'dict.setdefault(key, default=None)' },
  { label: 'update', kind: CompletionItemKind.Method, insertText: 'update', documentation: '更新字典', detail: 'dict.update([other])' },
  { label: 'pop', kind: CompletionItemKind.Method, insertText: 'pop', documentation: '移除并返回值', detail: 'dict.pop(key[, default])' },
  { label: 'popitem', kind: CompletionItemKind.Method, insertText: 'popitem', documentation: '移除并返回最后一对', detail: 'dict.popitem()' },
  { label: 'keys', kind: CompletionItemKind.Method, insertText: 'keys', documentation: '返回所有键', detail: 'dict.keys()' },
  { label: 'values', kind: CompletionItemKind.Method, insertText: 'values', documentation: '返回所有值', detail: 'dict.values()' },
  { label: 'items', kind: CompletionItemKind.Method, insertText: 'items', documentation: '返回所有键值对', detail: 'dict.items()' },
  { label: 'clear', kind: CompletionItemKind.Method, insertText: 'clear', documentation: '清空字典', detail: 'dict.clear()' },
  { label: 'copy', kind: CompletionItemKind.Method, insertText: 'copy', documentation: '浅拷贝', detail: 'dict.copy()' },
  { label: 'fromkeys', kind: CompletionItemKind.Method, insertText: 'fromkeys', documentation: '从键序列创建字典', detail: 'dict.fromkeys(seq[, value])' },
]

/** Python str 方法 */
const strMethods: EngineCompletionItem[] = [
  { label: 'upper', kind: CompletionItemKind.Method, insertText: 'upper', documentation: '转大写', detail: 'str.upper()' },
  { label: 'lower', kind: CompletionItemKind.Method, insertText: 'lower', documentation: '转小写', detail: 'str.lower()' },
  { label: 'strip', kind: CompletionItemKind.Method, insertText: 'strip', documentation: '去除首尾空白', detail: 'str.strip([chars])' },
  { label: 'split', kind: CompletionItemKind.Method, insertText: 'split', documentation: '分割字符串', detail: 'str.split(sep=None, maxsplit=-1)' },
  { label: 'join', kind: CompletionItemKind.Method, insertText: 'join', documentation: '用字符串连接', detail: 'str.join(iterable)' },
  { label: 'replace', kind: CompletionItemKind.Method, insertText: 'replace', documentation: '替换子串', detail: 'str.replace(old, new[, count])' },
  { label: 'find', kind: CompletionItemKind.Method, insertText: 'find', documentation: '查找子串（返回索引或-1）', detail: 'str.find(sub[, start[, end]])' },
  { label: 'startswith', kind: CompletionItemKind.Method, insertText: 'startswith', documentation: '是否以指定字符串开头', detail: 'str.startswith(prefix[, start[, end]])' },
  { label: 'endswith', kind: CompletionItemKind.Method, insertText: 'endswith', documentation: '是否以指定字符串结尾', detail: 'str.endswith(suffix[, start[, end]])' },
  { label: 'isdigit', kind: CompletionItemKind.Method, insertText: 'isdigit', documentation: '是否全为数字', detail: 'str.isdigit()' },
  { label: 'isalpha', kind: CompletionItemKind.Method, insertText: 'isalpha', documentation: '是否全为字母', detail: 'str.isalpha()' },
  { label: 'isalnum', kind: CompletionItemKind.Method, insertText: 'isalnum', documentation: '是否全为字母或数字', detail: 'str.isalnum()' },
  { label: 'format', kind: CompletionItemKind.Method, insertText: 'format', documentation: '格式化字符串', detail: 'str.format(*args, **kwargs)' },
  { label: 'encode', kind: CompletionItemKind.Method, insertText: 'encode', documentation: '编码为字节', detail: 'str.encode(encoding="utf-8", errors="strict")' },
]

/** 代码模式补全 — Python 标准库 */
export const pythonCompletions: EngineCompletionItem[] = [
  ...pythonKeywords,
  ...pythonBuiltins,
]

/** 代码模式点号触发 — 常见类型的实例方法 */
export const pythonDotCompletions: Record<string, EngineCompletionItem[]> = {
  list: listMethods,
  dict: dictMethods,
  str: strMethods,
}
