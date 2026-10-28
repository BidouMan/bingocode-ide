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
  { label: 'goto', kind: CompletionItemKind.Method, insertText: 'goto', documentation: '移到指定坐标；也接受标记引用或另一个角色\n\ngoto(320, 240)\ngoto(player.get_marker())  # 武器对准角色的「标记」\ngoto(enemy)  # 对齐另一个角色的注册点', detail: 'goto(x, y)' },
  { label: 'set_xy', kind: CompletionItemKind.Method, insertText: 'set_xy', documentation: '设置坐标（带碰撞检测）\n\nset_xy(x, y)', detail: 'set_xy(x, y)' },
  { label: 'set_x', kind: CompletionItemKind.Method, insertText: 'set_x', documentation: '设置水平位置；落点与墙重叠时会被推到最近一侧（不检查中间路径）\n\nset_x(x)', detail: 'set_x(x)' },
  { label: 'set_y', kind: CompletionItemKind.Method, insertText: 'set_y', documentation: '设置垂直位置（y 向上为正，地图左下角为 0）；落点与墙重叠时会被推到最近一侧\n\nset_y(y)', detail: 'set_y(y)' },
  { label: 'add_x', kind: CompletionItemKind.Method, insertText: 'add_x', documentation: '将 x 坐标增加（或减少）一定数值；改完做一次碰撞修正，小步会被墙挡住，一次移动太远可能穿墙\n\nadd_x(delta_x)', detail: 'add_x(delta_x)' },
  { label: 'add_y', kind: CompletionItemKind.Method, insertText: 'add_y', documentation: '将 y 坐标增加（或减少）一定数值（正数向上）；改完做一次碰撞修正，小步会被墙挡住\n\nadd_y(delta_y)', detail: 'add_y(delta_y)' },
  { label: 'move', kind: CompletionItemKind.Method, insertText: 'move', documentation: '朝着当前 angle 方向移动 distance 像素\n\nmove(distance)', detail: 'move(distance)' },
  { label: 'goto_rand', kind: CompletionItemKind.Method, insertText: 'goto_rand', documentation: '移到地图内的随机位置', detail: 'goto_rand()' },
  { label: 'set_speed', kind: CompletionItemKind.Method, insertText: 'set_speed', documentation: '设置持续速度，引擎每帧自动沿当前方向移动\n\nset_speed(speed)', detail: 'set_speed(speed)' },

  // 物理 / 平台跳跃
  { label: 'jump', kind: CompletionItemKind.Method, insertText: 'jump', documentation: '角色跳跃：给一个向上的起跳速度\n\njump(power=10)\npower: 起跳力度（默认10，约 95 像素高）\n不会自己判断能否跳，需配合 is_on_ground() 使用；松手不会提前落下', detail: 'jump(power=10)' },
  { label: 'smart_jump', kind: CompletionItemKind.Method, insertText: 'smart_jump', documentation: '大小跳：按下起跳，按住跳得高，松手就落下\n\nsmart_jump(power=10)\n必须写在 if key_down("up"): 里面，每帧调用一次，例如：\nif key_down("up"):\n    hero.smart_jump(12)\n松手时引擎会自动停止跳跃，不需要自己写 stop_jump', detail: 'smart_jump(power=10)' },
  { label: 'stop_jump', kind: CompletionItemKind.Method, insertText: 'stop_jump', documentation: '停止跳跃：角色正在上升时调用，停止继续上升并提前落下，自己不会起跳\n需要先 jump（或给 vy 一个正值）\n普通按键跳跃直接用 smart_jump 更简单；敌人、撞天花板等没有松手的场景用这个', detail: 'stop_jump()' },
  { label: 'drop_down', kind: CompletionItemKind.Method, insertText: 'drop_down', documentation: '从跳板掉下去：角色站在碰撞类型为「跳板」的平台上时调用，穿过脚下的跳板下落\n不在地面上时调用会被自动忽略，不需要自己判断 is_on_ground()', detail: 'drop_down()' },

  // 外观
  { label: 'set_scale', kind: CompletionItemKind.Method, insertText: 'set_scale', documentation: '设置缩放比例（5-1000）\n\nset_scale(value)', detail: 'set_scale(value)' },
  { label: 'add_scale', kind: CompletionItemKind.Method, insertText: 'add_scale', documentation: '在当前缩放比例的基础上增加 value（单位为百分比）\n例如：add_scale(10) 会让角色变大 10%', detail: 'add_scale(value)' },
  { label: 'set_rotation_mode', kind: CompletionItemKind.Method, insertText: 'set_rotation_mode', documentation: '设置旋转模式\n\nset_rotation_mode(style)\n- "all": 自由旋转（默认）\n- "left_right": 仅水平翻转\n- "none": 不旋转', detail: 'set_rotation_mode(style)' },
  { label: 'show', kind: CompletionItemKind.Method, insertText: 'show', documentation: '显示角色', detail: 'show()' },
  { label: 'hide', kind: CompletionItemKind.Method, insertText: 'hide', documentation: '隐藏角色（仅仅是看不见，物体还在内存里）', detail: 'hide()' },
  { label: 'say', kind: CompletionItemKind.Method, insertText: 'say', documentation: '让角色说话。新话会替换旧话\n\nsay("你好") → 永久显示\nsay("得分+1", 2) → 2秒后自动消失', detail: 'say(text, seconds=0)' },
  { label: 'play', kind: CompletionItemKind.Method, insertText: 'play', documentation: '播放指定名称的动画\n\nplay("idle")\nplay("walk", 0.2) → 0.2秒过渡', detail: 'play(animation_name, transition_time=0.1)' },
  { label: 'set_angle', kind: CompletionItemKind.Method, insertText: 'set_angle', documentation: '设置朝向角度（0=右 90=上 180=左 270=下，逆时针为正）\n\nset_angle(angle)', detail: 'set_angle(angle)' },

  // 朝向
  { label: 'look_at', kind: CompletionItemKind.Method, insertText: 'look_at', documentation: '让当前角色看向另一个角色或鼠标（自动旋转角度）\n\ntarget 可以是另一个 Sprite 或 mouse 对象', detail: 'look_at(target)' },

  // 标记（.bsf 角色编辑器「标记」图层标注的锚点，默认名「标记」，新建自动编号）
  { label: 'get_marker', kind: CompletionItemKind.Method, insertText: 'get_marker', documentation: '获取标记引用（武器/道具挂载锚点）\n\nm = player.get_marker()      # 默认第一个标记\nm2 = player.get_marker("标记2")\nw.goto(m)        # 一次性到位\nw.follow(m)      # 持续跟随\nm.x / m.y        # 读标记世界坐标', detail: 'get_marker(name="标记")' },
  { label: 'follow', kind: CompletionItemKind.Method, insertText: 'follow', documentation: '持续跟随目标的位置（每帧自动更新，只跟位置不跟朝向）\n\nw.follow(player.get_marker())\nw.follow(enemy)\nw.follow(m, flip=False)  # 不继承左右翻转（鼠标瞄准武器）\n默认继承目标的左右翻转（父翻面武器跟着翻）；朝向仍可独立控制（如 w.look_at(mouse)）；目标被删除时自动停止', detail: 'follow(target, flip=True)' },
  { label: 'unfollow', kind: CompletionItemKind.Method, insertText: 'unfollow', documentation: '停止跟随', detail: 'unfollow()' },

  // 边界
  { label: 'edge_bounce', kind: CompletionItemKind.Method, insertText: 'edge_bounce', documentation: '基于 Hitbox 的精准反弹，自动识别世界边界\n碰到边界时自动反转角度', detail: 'edge_bounce()' },

  // 感知 / 碰撞
  { label: 'is_touch_edge', kind: CompletionItemKind.Method, insertText: 'is_touch_edge', documentation: '精准边界检测：判定角色的实际视觉边缘是否接触或越过地图边界', detail: 'is_touch_edge() -> bool' },
  { label: 'is_out_side', kind: CompletionItemKind.Method, insertText: 'is_out_side', documentation: '完全出界检测：只有当角色整体（所有像素）都离开地图边界时才返回 True', detail: 'is_out_side() -> bool' },
  { label: 'is_touch', kind: CompletionItemKind.Method, insertText: 'is_touch', documentation: '判断是否碰到另一个 Sprite、鼠标或带有指定标签的图块 / 形状\n\nis_touch(target)\ntarget 可以是 Sprite、mouse 或字符串（图块标签或形状层里填的标签）', detail: 'is_touch(target) -> bool' },
  { label: 'is_touch_group', kind: CompletionItemKind.Method, insertText: 'is_touch_group', documentation: '判断是否撞到了某个组里的任意成员\n如果撞到了，返回那个成员；没撞到返回 None', detail: 'is_touch_group(group_name) -> Sprite or None' },
  { label: 'distance_to', kind: CompletionItemKind.Method, insertText: 'distance_to', documentation: '计算当前角色到目标（Sprite 或 mouse）的像素距离\n按角色位置点测距，和 goto()/look_at() 用的是同一个点', detail: 'distance_to(target) -> float' },
  { label: 'is_on_ground', kind: CompletionItemKind.Method, insertText: 'is_on_ground', documentation: '是否真正站在地面上：由物理落地接触决定，站着为 True；跳起来、下落中、从下方穿过跳板都为 False\n跳跃前用它判断能否跳', detail: 'is_on_ground() -> bool' },
  { label: 'is_blocked', kind: CompletionItemKind.Method, insertText: 'is_blocked', documentation: '前方是否有实心地形阻挡（俯视迷宫常用）\n\nis_blocked("right")\nis_blocked("down", 8)\n只查形状层 solid、图像碰撞和实心图块；感应区域不算阻挡\n跳板只在向下且从上方靠近时算阻挡', detail: 'is_blocked(direction, distance=2) -> bool' },
  { label: 'is_on_wall', kind: CompletionItemKind.Method, insertText: 'is_on_wall', documentation: '左右两侧是否贴着墙（基于本帧接触结果）', detail: 'is_on_wall() -> bool' },
  { label: 'is_on_ceiling', kind: CompletionItemKind.Method, insertText: 'is_on_ceiling', documentation: '头顶是否撞到实体地形（基于本帧接触结果）\n\n跳跃撞头时停止上升：\nif hero.is_on_ceiling():\n    hero.stop_jump()\n开启「限制边界」时，撞到地图上边界也算', detail: 'is_on_ceiling() -> bool' },

  // 分组 / 事件
  { label: 'add_to_group', kind: CompletionItemKind.Method, insertText: 'add_to_group', documentation: '将角色归类，比如 "enemies", "bullets"\n\nadd_to_group(group_name)', detail: 'add_to_group(group_name)' },
  { label: 'on_touch_group', kind: CompletionItemKind.Method, insertText: 'on_touch_group', documentation: '注册碰撞处理（对方需先 add_to_group）\n\non_touch_group("enemies") 碰到组内成员时，引擎自动删除自己和对方\non_touch_group("enemies", 函数) 自定义处理，函数参数为 (自己, 碰到的角色)', detail: 'on_touch_group(group, callback=None)' },
  { label: 'on_sensor_enter', kind: CompletionItemKind.Method, insertText: 'on_sensor_enter', documentation: '进入某个感应形状时执行一次（形状层里把它设成「感应」或「阻挡 + 感应」并填上标签）\n\nhero.on_sensor_enter("水", 碰到水)\n函数参数为 (自己, 标签)，例如：\ndef 碰到水(who, tag):\n    who.say("好凉快")\n站在里面不会每帧重复触发', detail: 'on_sensor_enter(tag, callback)' },
  { label: 'on_sensor_exit', kind: CompletionItemKind.Method, insertText: 'on_sensor_exit', documentation: '离开某个感应形状时执行一次\n\nhero.on_sensor_exit("水", 离开水)\n函数参数为 (自己, 标签)', detail: 'on_sensor_exit(tag, callback)' },
  { label: 'broadcast', kind: CompletionItemKind.Method, insertText: 'broadcast', documentation: '发送广播（触发所有接收该事件的回调）\n\nbroadcast("事件名")', detail: 'broadcast(event_name)' },
  { label: 'receive', kind: CompletionItemKind.Method, insertText: 'receive', documentation: '这一帧有没有收到指定广播\n\nif enemy.receive("开始"):\n    enemy.show()\n广播发出后的下一帧返回一次 True；要写在 while True 里', detail: 'receive(event_name) -> bool' },

  // 生命周期
  { label: 'delete', kind: CompletionItemKind.Method, insertText: 'delete', documentation: '彻底删除（视觉移除 + 物理移除 + 内存清理）', detail: 'delete()' },
]

/** Sprite 属性（通过 . 触发时显示） */
const spriteProperties: EngineCompletionItem[] = [
  { label: 'x', kind: CompletionItemKind.Property, insertText: 'x', documentation: '水平位置（默认 320，正数向右）', detail: 'float' },
  { label: 'y', kind: CompletionItemKind.Property, insertText: 'y', documentation: '垂直位置（默认 240，正数向上，地图左下角为 0）', detail: 'float' },
  { label: 'pos', kind: CompletionItemKind.Property, insertText: 'pos', documentation: '一次性读取角色坐标 (x, y)，可直接拆包：x, y = hero.pos（只读）', detail: '(float, float)' },
  { label: 'angle', kind: CompletionItemKind.Property, insertText: 'angle', documentation: '朝向角度（度，逆时针为正：0=右 90=上 180=左 270=下）', detail: 'float' },
  { label: 'scale', kind: CompletionItemKind.Property, insertText: 'scale', documentation: '缩放比例（百分比，默认 100）', detail: 'float' },
  { label: 'layer', kind: CompletionItemKind.Property, insertText: 'layer', documentation: '图层顺序（越大越靠前）', detail: 'int' },
  { label: 'hitbox_scale', kind: CompletionItemKind.Property, insertText: 'hitbox_scale', documentation: '碰撞箱大小倍率（默认 1.0）', detail: 'float' },
  { label: 'gravity', kind: CompletionItemKind.Property, insertText: 'gravity', documentation: '是否受地图重力影响（默认 True）\n\nbullet.gravity = False → 地图开了重力也不会下坠，撞墙、落地等碰撞照常\n适合做子弹、会飞的敌人；关掉后用 jump() 会一直上升不落回', detail: 'bool' },
]

/** Timer 类 */
const timerCompletions: EngineCompletionItem[] = [
  { label: 'Timer', kind: CompletionItemKind.Class, insertText: 'Timer', documentation: '创建一个自动开始的计时器\n\nTimer(seconds, loop=True)\n- seconds: 间隔秒数\n- loop: True=循环，False=只触发一次\n\n需要手动控制时先 stop()，之后 start() 重新计时', detail: 'class Timer(seconds, loop=True)' },
]

/** Timer 方法（通过 . 触发时显示） */
const timerMethods: EngineCompletionItem[] = [
  { label: 'start', kind: CompletionItemKind.Method, insertText: 'start', documentation: '开始/重新开始计时（重置计时起点）', detail: 'start()' },
  { label: 'stop', kind: CompletionItemKind.Method, insertText: 'stop', documentation: '停止计时（再次 start() 后重新计时）', detail: 'stop()' },
  { label: 'is_timeout', kind: CompletionItemKind.Method, insertText: 'is_timeout', documentation: '时间到了返回 True；循环计时器会自动重新计时，loop=False 触发一次后停止\n计时使用游戏时间，暂停游戏时会冻结', detail: 'is_timeout() -> bool' },
]

/** 全局函数 */
const globalFunctions: EngineCompletionItem[] = [
  // 输入
  { label: 'key_down', kind: CompletionItemKind.Function, insertText: 'key_down', documentation: '判断某个键是否被按住（持续按住返回 True）\n\nkey_down("a")\nkey_down("space")\nkey_down("left")', detail: 'key_down(key) -> bool' },
  { label: 'key_pressed', kind: CompletionItemKind.Function, insertText: 'key_pressed', documentation: '只有按下的那一帧返回 True\n\nkey_pressed("a")', detail: 'key_pressed(key) -> bool' },
  { label: 'key_up', kind: CompletionItemKind.Function, insertText: 'key_up', documentation: '只有松开的那一帧返回 True\n\nkey_up("space")', detail: 'key_up(key) -> bool' },
  { label: 'mouse_down', kind: CompletionItemKind.Function, insertText: 'mouse_down', documentation: '判断鼠标是否按下（持续按住返回 True）', detail: 'mouse_down() -> bool' },
  { label: 'mouse_pressed', kind: CompletionItemKind.Function, insertText: 'mouse_pressed', documentation: '单次检测：只有在按下的那一帧返回 True', detail: 'mouse_pressed() -> bool' },
  { label: 'mouse_up', kind: CompletionItemKind.Function, insertText: 'mouse_up', documentation: '单次检测：只有在松开鼠标左键的那一帧返回 True', detail: 'mouse_up() -> bool' },

  // 事件
  { label: 'time_passed', kind: CompletionItemKind.Function, insertText: 'time_passed', documentation: '每隔几秒做一件事，就用它。\n比如 time_passed(1) 就是每 1 秒做一次。\n需要暂停、重新计时、只做一次，用 Timer。\n\n用法：if time_passed(1): do_something()', detail: 'time_passed(seconds) -> bool' },
  { label: 'broadcast', kind: CompletionItemKind.Function, insertText: 'broadcast', documentation: '发送全局广播（触发所有接收该事件的回调）\n\nbroadcast("事件名")', detail: 'broadcast(event_name)' },
  { label: 'receive', kind: CompletionItemKind.Function, insertText: 'receive', documentation: '这一帧有没有收到指定广播（不需要写函数，入门写法）\n\nif receive("开始"):\n    ...\n广播发出后的下一帧返回一次 True；要写在 while True 里', detail: 'receive(event_name) -> bool' },
  { label: 'on_receive', kind: CompletionItemKind.Function, insertText: 'on_receive', documentation: '当收到广播时执行自己写的函数（进阶写法）\n\non_receive("事件名", 函数)\n函数不需要参数；注册一次，写在循环外。\n入门场景可以直接用 if 角色.receive("事件名")', detail: 'on_receive(event_name, callback)' },

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
  { label: 'show_text', kind: CompletionItemKind.Function, insertText: 'show_text', documentation: '在屏幕指定位置显示文字（多个参数自动拼接）\n\nshow_text(100, 50, "分数:", score)', detail: 'show_text(x, y, *args)' },
  { label: 'shake', kind: CompletionItemKind.Function, insertText: 'shake', documentation: '屏幕震动效果\n\nshake(intensity=5, duration=0.3)', detail: 'shake(intensity=5, duration=0.3)' },

  // 音频
  { label: 'play_sound', kind: CompletionItemKind.Function, insertText: 'play_sound', documentation: '播放音效\n\nplay_sound("音效名")\nplay_sound("音效名", loop=True)', detail: 'play_sound(sound_name, loop=False)' },
  { label: 'stop_sound', kind: CompletionItemKind.Function, insertText: 'stop_sound', documentation: '停止音效。不传参数则停止所有音效\n\nstop_sound("音效名")\nstop_sound()', detail: 'stop_sound(sound_name=None)' },

  // 地图 / 摄像机
  { label: 'load_map', kind: CompletionItemKind.Function, insertText: 'load_map', documentation: '加载并显示地图，返回地图对象\n\nmap = load_map("地图名")\npos = map.get_marker("出生点")\nfor m in map.get_markers("敌人"):\n    ...\n地图名对应 assets/maps/ 下的地图包', detail: 'load_map(map_name) -> map' },
  { label: 'get_marker', kind: CompletionItemKind.Function, insertText: 'get_marker', documentation: '按名称获取地图标记（地图编辑器里放的图钉）\n\npos = map.get_marker("出生点")\nplayer.goto(pos)              # 直接放到标记位置\nx, y = pos                    # 也可以拆包\npos.x / pos.y / pos.pos / pos.type\n找不到返回 None', detail: 'get_marker(name) -> marker' },
  { label: 'get_markers', kind: CompletionItemKind.Function, insertText: 'get_markers', documentation: '按类型获取地图标记列表（类型在属性面板里设置），可直接 for 遍历\n\nfor m in map.get_markers("敌人"):\n    enemy = Sprite("史莱姆")\n    enemy.goto(m)\n没有时返回空列表', detail: 'get_markers(type) -> list' },
  { label: 'raycast', kind: CompletionItemKind.Function, insertText: 'raycast', documentation: '从用户坐标 (x, y) 射出射线，返回最近命中的实心地形\n\nhit = raycast(hero.x, hero.y, "right", 200)\nif hit:\n    print(hit.distance, hit.tag)\n\ndirection 支持 "left"/"right"/"up"/"down" 或角度（0右 90上）\n命中结果可读 .x/.y/.pos/.distance/.normal/.tag', detail: 'raycast(x, y, direction, distance=1000) -> hit or None' },
  { label: 'camera_follow', kind: CompletionItemKind.Function, insertText: 'camera_follow', documentation: '设置摄像机跟随指定精灵（镜头跟随）\n\ncamera_follow(hero)', detail: 'camera_follow(sprite)' },

  // 随机工具
  { label: 'random_int', kind: CompletionItemKind.Function, insertText: 'random_int', documentation: '在 min_val 和 max_val 之间取随机整数（包含两端）\n\nrandom_int(1, 10)', detail: 'random_int(min_val, max_val) -> int' },
  { label: 'random_float', kind: CompletionItemKind.Function, insertText: 'random_float', documentation: '在 min_val 和 max_val 之间取随机浮点数\n\nrandom_float(0, 1)       # 默认保留 2 位小数\nrandom_float(0, 1, 4)    # 保留 4 位\nrandom_float(0, 1, None) # 完整精度', detail: 'random_float(min_val=0.0, max_val=1.0, decimals=2) -> float' },

  // 生成器
  { label: 'register_generator', kind: CompletionItemKind.Function, insertText: 'register_generator', documentation: '注册一个 generator 到调度器', detail: 'register_generator(gen)' },
  { label: 'unregister_generator', kind: CompletionItemKind.Function, insertText: 'unregister_generator', documentation: '从调度器移除一个 generator', detail: 'unregister_generator(gen)' },
]

/** 全局对象 */
const globalObjects: EngineCompletionItem[] = [
  { label: 'mouse', kind: CompletionItemKind.Variable, insertText: 'mouse', documentation: '全局鼠标对象\n\nmouse.x → 鼠标水平位置\nmouse.y → 鼠标垂直位置\nmouse.pos → (x, y) 元组，可拆包：x, y = mouse.pos', detail: 'mouse object' },
  { label: 'GameStop', kind: CompletionItemKind.Class, insertText: 'GameStop', documentation: '游戏停止异常\n由 stop_game() 抛出，用于中断 generator', detail: 'class GameStop(Exception)' },
]

/** mouse 对象属性（通过 . 触发时显示） */
const mouseProperties: EngineCompletionItem[] = [
  { label: 'x', kind: CompletionItemKind.Property, insertText: 'x', documentation: '鼠标水平位置（游戏坐标）', detail: 'float' },
  { label: 'y', kind: CompletionItemKind.Property, insertText: 'y', documentation: '鼠标垂直位置（画面左下角为 0，正数向上）', detail: 'float' },
  { label: 'pos', kind: CompletionItemKind.Property, insertText: 'pos', documentation: '一次性获取鼠标坐标 (x, y)，可直接拆包：x, y = mouse.pos', detail: '(float, float)' },
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

/** Python 常用标准库模块 */
const pythonModules: EngineCompletionItem[] = [
  { label: 'random', kind: CompletionItemKind.Module, insertText: 'random', documentation: '随机数生成', detail: 'import random' },
  { label: 'math', kind: CompletionItemKind.Module, insertText: 'math', documentation: '数学函数', detail: 'import math' },
  { label: 'os', kind: CompletionItemKind.Module, insertText: 'os', documentation: '操作系统接口', detail: 'import os' },
  { label: 'sys', kind: CompletionItemKind.Module, insertText: 'sys', documentation: '系统相关参数', detail: 'import sys' },
  { label: 'time', kind: CompletionItemKind.Module, insertText: 'time', documentation: '时间访问和转换', detail: 'import time' },
  { label: 'datetime', kind: CompletionItemKind.Module, insertText: 'datetime', documentation: '日期和时间处理', detail: 'import datetime' },
  { label: 'json', kind: CompletionItemKind.Module, insertText: 'json', documentation: 'JSON 编码和解码', detail: 'import json' },
  { label: 're', kind: CompletionItemKind.Module, insertText: 're', documentation: '正则表达式', detail: 'import re' },
  { label: 'collections', kind: CompletionItemKind.Module, insertText: 'collections', documentation: '容器数据类型', detail: 'import collections' },
  { label: 'itertools', kind: CompletionItemKind.Module, insertText: 'itertools', documentation: '迭代器工具', detail: 'import itertools' },
  { label: 'functools', kind: CompletionItemKind.Module, insertText: 'functools', documentation: '高阶函数工具', detail: 'import functools' },
  { label: 'string', kind: CompletionItemKind.Module, insertText: 'string', documentation: '字符串常量和模板', detail: 'import string' },
  { label: 'copy', kind: CompletionItemKind.Module, insertText: 'copy', documentation: '浅拷贝和深拷贝', detail: 'import copy' },
  { label: 'pickle', kind: CompletionItemKind.Module, insertText: 'pickle', documentation: '对象序列化', detail: 'import pickle' },
  { label: 'hashlib', kind: CompletionItemKind.Module, insertText: 'hashlib', documentation: '安全哈希和消息摘要', detail: 'import hashlib' },
  { label: 'urllib', kind: CompletionItemKind.Module, insertText: 'urllib', documentation: 'URL 处理', detail: 'import urllib' },
  { label: 'pathlib', kind: CompletionItemKind.Module, insertText: 'pathlib', documentation: '面向对象的路径操作', detail: 'import pathlib' },
  { label: 'typing', kind: CompletionItemKind.Module, insertText: 'typing', documentation: '类型提示支持', detail: 'import typing' },
  { label: 'tkinter', kind: CompletionItemKind.Module, insertText: 'tkinter', documentation: 'GUI 图形界面', detail: 'import tkinter' },
  { label: 'turtle', kind: CompletionItemKind.Module, insertText: 'turtle', documentation: '海龟绘图', detail: 'import turtle' },
  { label: 'pygame', kind: CompletionItemKind.Module, insertText: 'pygame', documentation: '游戏开发库', detail: 'import pygame' },
  { label: 'PIL', kind: CompletionItemKind.Module, insertText: 'PIL', documentation: '图像处理（Pillow）', detail: 'import PIL' },
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
  ...pythonModules,
]

/** 代码模式点号触发 — 常见类型的实例方法 */
export const pythonDotCompletions: Record<string, EngineCompletionItem[]> = {
  list: listMethods,
  dict: dictMethods,
  str: strMethods,
}
