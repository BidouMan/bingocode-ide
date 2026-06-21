import os
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, Signal
from PySide6.QtGui import QFont, QColor, QClipboard, QIcon
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QScrollArea, QFrame, QApplication,
)


HELP_DATA = [
    {
        "name": "精灵",
        "color": "#5B9BF5",
        "sections": [
            {
                "title": "创建角色",
                "items": [
                    {
                        "name": "Sprite",
                        "short": "创建角色",
                        "badge": "module",
                        "desc": "创建一个新的精灵角色对象",
                        "definition": "Sprite(filename)",
                        "params": "filename: 角色文件夹名称（在 assets/sprites/ 下）",
                        "returns": "Sprite 实例",
                        "example": 'hero = Sprite("英雄")\nenemy = Sprite("敌人")',
                    },
                ],
            },
            {
                "title": "位置属性",
                "items": [
                    {
                        "name": "x / y",
                        "short": "读写坐标",
                        "badge": "property",
                        "desc": "读取或设置角色的屏幕坐标位置",
                        "definition": "sprite.x = value\nsprite.y = value",
                        "params": "value: 数字（像素坐标）",
                        "returns": "读取时返回当前坐标",
                        "example": "hero.x = 320\nhero.y = 240\nprint(hero.x)",
                    },
                    {
                        "name": "angle",
                        "short": "读写角度",
                        "badge": "property",
                        "desc": "读取或设置角色的旋转角度",
                        "definition": "sprite.angle = value",
                        "params": "value: 角度（0-360）",
                        "returns": "读取时返回当前角度",
                        "example": "hero.angle = 90\nhero.angle += 5",
                    },
                    {
                        "name": "scale",
                        "short": "读写缩放",
                        "badge": "property",
                        "desc": "读取或设置角色的缩放比例，100为原始大小",
                        "definition": "sprite.scale = value",
                        "params": "value: 百分比（100=原始大小）",
                        "returns": "读取时返回当前缩放",
                        "example": "hero.scale = 50   # 缩小一半\nhero.scale = 200  # 放大一倍",
                    },
                    {
                        "name": "layer",
                        "short": "读写层级",
                        "badge": "property",
                        "desc": "读取或设置角色的渲染层级，数字越大越靠前",
                        "definition": "sprite.layer = value",
                        "params": "value: 整数，数字越大越靠前",
                        "returns": "读取时返回当前层级",
                        "example": "hero.layer = 10\nenemy.layer = 5",
                    },
                ],
            },
            {
                "title": "删除",
                "items": [
                    {
                        "name": "delete",
                        "short": "删除角色",
                        "badge": "object",
                        "desc": "彻底删除角色，包括视觉显示、物理碰撞和内存",
                        "definition": "sprite.delete()",
                        "params": "无",
                        "returns": "无",
                        "example": "enemy.delete()",
                    },
                ],
            },
        ],
    },
    {
        "name": "运动",
        "color": "#7C6BF5",
        "sections": [
            {
                "title": "坐标移动",
                "items": [
                    {
                        "name": "goto",
                        "short": "移到坐标",
                        "badge": "object",
                        "desc": "将角色移动到指定的屏幕坐标位置",
                        "definition": "goto(x, y)",
                        "params": "x: X坐标\ny: Y坐标",
                        "returns": "无",
                        "example": "hero.goto(320, 240)",
                    },
                    {
                        "name": "set_xy",
                        "short": "设置坐标",
                        "badge": "object",
                        "desc": "设置角色坐标，功能同 goto",
                        "definition": "set_xy(x, y)",
                        "params": "x: X坐标\ny: Y坐标",
                        "returns": "无",
                        "example": "hero.set_xy(100, 200)",
                    },
                    {
                        "name": "set_x / set_y",
                        "short": "设置单轴",
                        "badge": "object",
                        "desc": "单独设置 X 或 Y 坐标",
                        "definition": "set_x(x)\nset_y(y)",
                        "params": "x 或 y: 数字",
                        "returns": "无",
                        "example": "hero.set_x(320)\nhero.set_y(240)",
                    },
                    {
                        "name": "add_x / add_y",
                        "short": "增量移动",
                        "badge": "object",
                        "desc": "将坐标增加指定数值，可为负数",
                        "definition": "add_x(dx)\nadd_y(dy)",
                        "params": "dx/dy: 增量（可为负数）",
                        "returns": "无",
                        "example": "hero.add_x(5)\nhero.add_y(-3)",
                    },
                    {
                        "name": "goto_rand",
                        "short": "随机位置",
                        "badge": "object",
                        "desc": "将角色移到舞台内的随机位置",
                        "definition": "goto_rand()",
                        "params": "无",
                        "returns": "无",
                        "example": "hero.goto_rand()",
                    },
                ],
            },
            {
                "title": "方向移动",
                "items": [
                    {
                        "name": "move",
                        "short": "方向移动",
                        "badge": "object",
                        "desc": "朝当前角度方向移动指定距离",
                        "definition": "move(distance)",
                        "params": "distance: 移动像素数",
                        "returns": "无",
                        "example": "hero.set_angle(0)\nhero.move(10)",
                    },
                    {
                        "name": "set_angle",
                        "short": "设置角度",
                        "badge": "object",
                        "desc": "设置角色的旋转角度",
                        "definition": "set_angle(angle)",
                        "params": "angle: 角度（0-360）",
                        "returns": "无",
                        "example": "hero.set_angle(90)",
                    },
                    {
                        "name": "look_at",
                        "short": "朝向目标",
                        "badge": "object",
                        "desc": "让角色朝向另一个角色或鼠标",
                        "definition": "look_at(target)",
                        "params": "target: Sprite 实例或 mouse",
                        "returns": "无",
                        "example": "hero.look_at(enemy)\nhero.look_at(mouse)",
                    },
                    {
                        "name": "edge_bounce",
                        "short": "边缘反弹",
                        "badge": "object",
                        "desc": "碰到舞台边缘时自动反弹",
                        "definition": "edge_bounce()",
                        "params": "无",
                        "returns": "无",
                        "example": "def loop():\n    hero.move(5)\n    hero.edge_bounce()",
                    },
                ],
            },
            {
                "title": "跳跃（平台游戏）",
                "items": [
                    {
                        "name": "jump",
                        "short": "跳跃",
                        "badge": "object",
                        "desc": "角色跳跃，power 越大跳越高",
                        "definition": "jump(power=10)",
                        "params": "power: 跳跃力度，默认10",
                        "returns": "无",
                        "example": "hero.jump(12)",
                    },
                    {
                        "name": "cut_jump",
                        "short": "截断跳跃",
                        "badge": "object",
                        "desc": "提前下落，松开跳跃键时调用",
                        "definition": "cut_jump()",
                        "params": "无",
                        "returns": "无",
                        "example": "if key_up('up'):\n    hero.cut_jump()",
                    },
                    {
                        "name": "drop_through",
                        "short": "穿越跳板",
                        "badge": "object",
                        "desc": "从跳板下方穿过下落",
                        "definition": "drop_through()",
                        "params": "无",
                        "returns": "无",
                        "example": "if key_down('down'):\n    hero.drop_through()",
                    },
                    {
                        "name": "is_on_floor",
                        "short": "检测地面",
                        "badge": "object",
                        "desc": "检测角色是否站在地面上",
                        "definition": "is_on_floor()",
                        "params": "无",
                        "returns": "True / False",
                        "example": "if hero.is_on_floor():\n    hero.jump(10)",
                    },
                    {
                        "name": "set_speed",
                        "short": "设置速度",
                        "badge": "object",
                        "desc": "设置持续速度，引擎每帧自动移动",
                        "definition": "set_speed(speed)",
                        "params": "speed: 每帧移动像素数",
                        "returns": "无",
                        "example": "hero.set_speed(3)",
                    },
                    {
                        "name": "set_rotation_mode",
                        "short": "旋转模式",
                        "badge": "object",
                        "desc": "设置角色的旋转模式",
                        "definition": "set_rotation_mode(style)",
                        "params": 'style: "all"(任意) / "left_right"(翻转) / "none"(不旋转)',
                        "returns": "无",
                        "example": 'hero.set_rotation_mode("left_right")',
                    },
                ],
            },
        ],
    },
    {
        "name": "外观",
        "color": "#B07CE8",
        "sections": [
            {
                "title": "显示控制",
                "items": [
                    {
                        "name": "show",
                        "short": "显示角色",
                        "badge": "object",
                        "desc": "让隐藏的角色重新显示",
                        "definition": "show()",
                        "params": "无",
                        "returns": "无",
                        "example": "hero.show()",
                    },
                    {
                        "name": "hide",
                        "short": "隐藏角色",
                        "badge": "object",
                        "desc": "隐藏角色，物体还在内存中",
                        "definition": "hide()",
                        "params": "无",
                        "returns": "无",
                        "example": "hero.hide()",
                    },
                ],
            },
            {
                "title": "缩放",
                "items": [
                    {
                        "name": "set_scale",
                        "short": "设置缩放",
                        "badge": "object",
                        "desc": "设置缩放比例，100为原始大小",
                        "definition": "set_scale(value)",
                        "params": "value: 百分比（5-1000）",
                        "returns": "无",
                        "example": "hero.set_scale(50)",
                    },
                    {
                        "name": "add_scale",
                        "short": "增减缩放",
                        "badge": "object",
                        "desc": "在当前缩放基础上增加百分比",
                        "definition": "add_scale(value)",
                        "params": "value: 增量百分比",
                        "returns": "无",
                        "example": "hero.add_scale(10)  # 变大10%",
                    },
                ],
            },
            {
                "title": "说话与动画",
                "items": [
                    {
                        "name": "say",
                        "short": "角色说话",
                        "badge": "object",
                        "desc": "让角色头顶显示文字，新话替换旧话",
                        "definition": "say(text, seconds=0)",
                        "params": "text: 要说的话\nseconds: 显示秒数，0=永久",
                        "returns": "无",
                        "example": 'hero.say("你好！")\nhero.say("得分+1", 2)',
                    },
                    {
                        "name": "play",
                        "short": "播放动画",
                        "badge": "object",
                        "desc": "播放角色的指定动画",
                        "definition": "play(animation_name, transition_time=0.1)",
                        "params": "animation_name: 动画名称\ntransition_time: 过渡时间（秒）",
                        "returns": "无",
                        "example": 'hero.play("walk")\nhero.play("idle")',
                    },
                ],
            },
        ],
    },
    {
        "name": "侦测",
        "color": "#4EC9C9",
        "sections": [
            {
                "title": "碰撞检测",
                "items": [
                    {
                        "name": "is_touch",
                        "short": "检测碰撞",
                        "badge": "object",
                        "desc": "判断是否碰到目标（角色、鼠标或图块标签）",
                        "definition": "is_touch(target)",
                        "params": "target: Sprite / mouse / 字符串标签",
                        "returns": "True / False",
                        "example": 'if hero.is_touch(enemy):\n    print("碰到敌人")\nif hero.is_touch("lava"):\n    print("掉进岩浆")',
                    },
                    {
                        "name": "is_touch_edge",
                        "short": "碰边检测",
                        "badge": "object",
                        "desc": "判断角色是否碰到舞台边缘",
                        "definition": "is_touch_edge()",
                        "params": "无",
                        "returns": "True / False",
                        "example": "if hero.is_touch_edge():\n    hero.edge_bounce()",
                    },
                    {
                        "name": "is_out_side",
                        "short": "出界检测",
                        "badge": "object",
                        "desc": "判断角色是否完全离开舞台",
                        "definition": "is_out_side()",
                        "params": "无",
                        "returns": "True / False",
                        "example": "if hero.is_out_side():\n    hero.delete()",
                    },
                ],
            },
            {
                "title": "距离与组",
                "items": [
                    {
                        "name": "distance_to",
                        "short": "计算距离",
                        "badge": "object",
                        "desc": "计算到目标的像素距离",
                        "definition": "distance_to(target)",
                        "params": "target: Sprite 或 mouse",
                        "returns": "数字（像素距离）",
                        "example": "d = hero.distance_to(enemy)\nif d < 50:\n    print('很近')",
                    },
                    {
                        "name": "touch_group",
                        "short": "组碰撞",
                        "badge": "object",
                        "desc": "检测是否碰到组内成员，碰到返回那个成员",
                        "definition": "touch_group(group_name)",
                        "params": "group_name: 组名字符串",
                        "returns": "碰到的成员 / None",
                        "example": 'hit = hero.touch_group("enemies")\nif hit:\n    hit.delete()',
                    },
                    {
                        "name": "add_to_group",
                        "short": "加入分组",
                        "badge": "object",
                        "desc": "将角色归类到指定组",
                        "definition": "add_to_group(group_name)",
                        "params": "group_name: 组名字符串",
                        "returns": "无",
                        "example": 'enemy.add_to_group("enemies")',
                    },
                ],
            },
        ],
    },
    {
        "name": "输入",
        "color": "#E8A040",
        "sections": [
            {
                "title": "键盘检测",
                "items": [
                    {
                        "name": "key_down",
                        "short": "按住检测",
                        "badge": "module",
                        "desc": "按键按住时每帧返回 True",
                        "definition": "key_down(key)",
                        "params": "key: 按键名称字符串",
                        "returns": "True / False",
                        "example": "if key_down('right'):\n    hero.add_x(3)",
                    },
                    {
                        "name": "key_pressed",
                        "short": "单次按下",
                        "badge": "module",
                        "desc": "按键按下瞬间返回 True，只触发一次",
                        "definition": "key_pressed(key)",
                        "params": "key: 按键名称字符串",
                        "returns": "True / False",
                        "example": "if key_pressed('space'):\n    shoot()",
                    },
                ],
            },
            {
                "title": "鼠标检测",
                "items": [
                    {
                        "name": "mouse_down",
                        "short": "鼠标按住",
                        "badge": "module",
                        "desc": "鼠标按下时返回 True",
                        "definition": "mouse_down()",
                        "params": "无",
                        "returns": "True / False",
                        "example": "if mouse_down():\n    hero.look_at(mouse)",
                    },
                    {
                        "name": "mouse_pressed",
                        "short": "鼠标单击",
                        "badge": "module",
                        "desc": "鼠标点击瞬间返回 True",
                        "definition": "mouse_pressed()",
                        "params": "无",
                        "returns": "True / False",
                        "example": "if mouse_pressed():\n    create_bullet()",
                    },
                    {
                        "name": "mouse.x / mouse.y",
                        "short": "鼠标坐标",
                        "badge": "module",
                        "desc": "获取鼠标的 X / Y 坐标",
                        "definition": "mouse.x\nmouse.y",
                        "params": "无",
                        "returns": "数字（像素坐标）",
                        "example": "print(mouse.x, mouse.y)",
                    },
                ],
            },
            {
                "title": "按键名称",
                "items": [],
                "note": "方向键: 'up' 'down' 'left' 'right'\n字母键: 'a' 'b' 'c' ... 'z'\n空格: 'space'\n回车: 'enter'\nESC: 'escape'\nShift: 'shift'\nCtrl: 'ctrl'",
            },
        ],
    },
    {
        "name": "控制",
        "color": "#E86840",
        "sections": [
            {
                "title": "游戏循环",
                "items": [
                    {
                        "name": "run",
                        "short": "启动游戏",
                        "badge": "module",
                        "desc": "启动游戏循环，必须放在脚本最后",
                        "definition": "run()",
                        "params": "无",
                        "returns": "无（阻塞）",
                        "example": "# 脚本末尾\nrun()",
                    },
                    {
                        "name": "stop",
                        "short": "停止游戏",
                        "badge": "module",
                        "desc": "停止游戏，退出 run 循环",
                        "definition": "stop()",
                        "params": "无",
                        "returns": "无",
                        "example": "if key_pressed('q'):\n    stop()",
                    },
                ],
            },
            {
                "title": "暂停与恢复",
                "items": [
                    {
                        "name": "pause",
                        "short": "暂停游戏",
                        "badge": "module",
                        "desc": "暂停游戏，精灵停止移动但 loop 仍运行",
                        "definition": "pause()",
                        "params": "无",
                        "returns": "无",
                        "example": "pause()",
                    },
                    {
                        "name": "resume",
                        "short": "继续游戏",
                        "badge": "module",
                        "desc": "继续已暂停的游戏",
                        "definition": "resume()",
                        "params": "无",
                        "returns": "无",
                        "example": "resume()",
                    },
                    {
                        "name": "is_paused",
                        "short": "检测暂停",
                        "badge": "module",
                        "desc": "检查游戏是否处于暂停状态",
                        "definition": "is_paused()",
                        "params": "无",
                        "returns": "True / False",
                        "example": "if is_paused():\n    resume()\nelse:\n    pause()",
                    },
                ],
            },
            {
                "title": "定时器",
                "items": [
                    {
                        "name": "wait",
                        "short": "简易定时",
                        "badge": "module",
                        "desc": "每 N 秒触发一次，无需创建对象",
                        "definition": "wait(seconds)",
                        "params": "seconds: 间隔秒数",
                        "returns": "True（触发时）/ False",
                        "example": 'if wait(0.2):\n    print("每0.2秒执行")',
                    },
                    {
                        "name": "Timer",
                        "short": "精细定时器",
                        "badge": "module",
                        "desc": "支持循环/单次/启停的定时器",
                        "definition": "Timer(seconds, loop=True, autostart=False)",
                        "params": "seconds: 间隔秒数\nloop: 是否循环\nautostart: 创建即启动",
                        "returns": "Timer 实例",
                        "example": 't = Timer(1.0, autostart=True)\nif t.is_timeout():\n    print("1秒到了")\nt.stop()',
                    },
                ],
            },
        ],
    },
    {
        "name": "地图",
        "color": "#50C878",
        "sections": [
            {
                "title": "地图操作",
                "items": [
                    {
                        "name": "load_map",
                        "short": "加载地图",
                        "badge": "module",
                        "desc": "加载指定名称的地图文件",
                        "definition": "load_map(map_name)",
                        "params": "map_name: 地图文件夹名称",
                        "returns": "无",
                        "example": 'load_map("关卡1")',
                    },
                    {
                        "name": "follow",
                        "short": "摄像机跟随",
                        "badge": "module",
                        "desc": "让摄像机跟随指定角色移动",
                        "definition": "follow(target)",
                        "params": "target: Sprite 实例",
                        "returns": "无",
                        "example": "follow(hero)",
                    },
                    {
                        "name": "show_collision",
                        "short": "显示碰撞盒",
                        "badge": "module",
                        "desc": "调试用，显示角色的碰撞盒范围",
                        "definition": "show_collision(sprite)",
                        "params": "sprite: 要显示碰撞盒的角色",
                        "returns": "无",
                        "example": "show_collision(hero)",
                    },
                ],
            },
        ],
    },
    {
        "name": "音频",
        "color": "#D870C8",
        "sections": [
            {
                "title": "音效播放",
                "items": [
                    {
                        "name": "play_sound",
                        "short": "播放音效",
                        "badge": "module",
                        "desc": "播放指定的音效文件",
                        "definition": "play_sound(name, loop=False)",
                        "params": "name: 音效名称\nloop: 是否循环播放",
                        "returns": "无",
                        "example": 'play_sound("爆炸")\nplay_sound("背景音乐", loop=True)',
                    },
                    {
                        "name": "stop_sound",
                        "short": "停止音效",
                        "badge": "module",
                        "desc": "停止指定音效或所有音效",
                        "definition": "stop_sound(name=None)",
                        "params": "name: 要停止的音效名称，不传则停止所有",
                        "returns": "无",
                        "example": 'stop_sound("爆炸")\nstop_sound()  # 停止所有',
                    },
                ],
            },
        ],
    },
    {
        "name": "绘图",
        "color": "#E85878",
        "sections": [
            {
                "title": "屏幕绘制",
                "items": [
                    {
                        "name": "draw_text",
                        "short": "绘制文字",
                        "badge": "module",
                        "desc": "在屏幕指定位置绘制文字",
                        "definition": "draw_text(x, y, *args)",
                        "params": "x, y: 坐标\n*args: 多个参数自动拼接",
                        "returns": "无",
                        "example": 'draw_text(10, 10, "分数:", score)\ndraw_text(10, 10)  # 清除文字',
                    },
                    {
                        "name": "shake",
                        "short": "屏幕震动",
                        "badge": "module",
                        "desc": "屏幕震动效果，常用于打击反馈",
                        "definition": "shake(intensity=5, duration=0.3)",
                        "params": "intensity: 震动强度\nduration: 持续时间（秒）",
                        "returns": "无",
                        "example": "shake()         # 默认震动\nshake(10, 0.5)  # 强度10，持续0.5秒",
                    },
                    {
                        "name": "show_fps",
                        "short": "显示帧率",
                        "badge": "module",
                        "desc": "调试用，显示/隐藏当前帧率",
                        "definition": "show_fps()",
                        "params": "无",
                        "returns": "无",
                        "example": "show_fps()",
                    },
                ],
            },
            {
                "title": "随机数",
                "items": [
                    {
                        "name": "random_int",
                        "short": "随机整数",
                        "badge": "module",
                        "desc": "生成指定范围内的随机整数（包含两端）",
                        "definition": "random_int(a, b)",
                        "params": "a: 最小值\nb: 最大值",
                        "returns": "整数",
                        "example": "hero.set_angle(random_int(0, 360))",
                    },
                    {
                        "name": "random_float",
                        "short": "随机浮点",
                        "badge": "module",
                        "desc": "生成指定范围内的随机浮点数",
                        "definition": "random_float(a, b)",
                        "params": "a: 最小值\nb: 最大值",
                        "returns": "浮点数",
                        "example": "x = random_float(0.0, 1.0)",
                    },
                ],
            },
        ],
    },
    {
        "name": "广播",
        "color": "#E8C840",
        "sections": [
            {
                "title": "事件通信",
                "items": [
                    {
                        "name": "broadcast",
                        "short": "发送广播",
                        "badge": "module",
                        "desc": "发送全局广播事件",
                        "definition": 'broadcast("event_name")',
                        "params": "event_name: 事件名称字符串",
                        "returns": "无",
                        "example": 'broadcast("game_over")',
                    },
                    {
                        "name": "sprite.broadcast",
                        "short": "角色广播",
                        "badge": "object",
                        "desc": "角色发送广播事件",
                        "definition": 'sprite.broadcast("event_name")',
                        "params": "event_name: 事件名称字符串",
                        "returns": "无",
                        "example": 'enemy.broadcast("died")',
                    },
                    {
                        "name": "receive",
                        "short": "接收广播",
                        "badge": "module",
                        "desc": "注册接收广播事件的回调函数",
                        "definition": 'receive("event_name", callback)',
                        "params": "event_name: 事件名称\ncallback: 回调函数",
                        "returns": "无",
                        "example": 'receive("died", on_enemy_died)',
                    },
                ],
            },
        ],
    },
]


class ScratchCatBtn(QWidget):
    clicked = Signal()

    def __init__(self, name, color, parent=None):
        super().__init__(parent)
        self._name = name
        self._color = color
        self._checked = False
        self.setObjectName("scratchCatBtn")
        self.setFixedSize(48, 48)
        self.setCursor(Qt.PointingHandCursor)

        self._bg = QFrame(self)
        self._bg.setObjectName("scratchCatBg")
        self._bg.setGeometry(2, 2, 44, 44)

        bg_layout = QVBoxLayout(self._bg)
        bg_layout.setContentsMargins(0, 4, 0, 4)
        bg_layout.setSpacing(2)

        self._dot = QLabel()
        self._dot.setFixedSize(12, 12)
        self._dot.setStyleSheet(f"background-color: {color}; border-radius: 6px;")
        bg_layout.addWidget(self._dot, 0, Qt.AlignCenter)

        self._label = QLabel(name[:2])
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setStyleSheet("background: transparent; border: none;")
        bg_layout.addWidget(self._label, 0, Qt.AlignCenter)

        self._update_style()

    def _update_style(self):
        if self._checked:
            self._bg.setStyleSheet(
                "background-color: rgba(255,255,255,0.07); border-radius: 8px;"
            )
            self._label.setStyleSheet(
                f"color: {self._color}; font-size: 10px; background: transparent; border: none;"
            )
        else:
            self._bg.setStyleSheet("background-color: transparent; border-radius: 8px;")
            self._label.setStyleSheet(
                "color: rgb(180,180,180); font-size: 10px; background: transparent; border: none;"
            )

    def setChecked(self, checked):
        self._checked = checked
        self._update_style()

    def isChecked(self):
        return self._checked

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.click()
        super().mousePressEvent(event)

    def click(self):
        self.setChecked(True)
        self.clicked.emit()


class FunctionCard(QFrame):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.setObjectName("helpFunctionCard")
        self._expanded = False
        self._data = data

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(0)

        header = QHBoxLayout()
        header.setSpacing(6)

        icons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icons")
        right_arrow_icon = QIcon(os.path.join(icons_dir, "right_arrow.svg"))
        down_arrow_icon = QIcon(os.path.join(icons_dir, "down_arrow.svg"))

        self._expand_arrow = QPushButton()
        self._expand_arrow.setObjectName("helpExpandArrow")
        self._expand_arrow.setFixedSize(20, 20)
        self._expand_arrow.setIcon(right_arrow_icon)
        self._expand_arrow.setIconSize(QSize(14, 14))
        self._expand_arrow.setCursor(Qt.PointingHandCursor)
        self._expand_arrow.clicked.connect(self.toggle_expand)
        header.addWidget(self._expand_arrow)

        badge = QLabel()
        badge.setObjectName("helpBadge")
        badge_type = data.get("badge", "module")
        if badge_type == "module":
            badge.setText("模块函数")
            badge.setProperty("badgeType", "module")
        elif badge_type == "object":
            badge.setText("对象函数")
            badge.setProperty("badgeType", "object")
        else:
            badge.setText("属性")
            badge.setProperty("badgeType", "property")
        badge.setFixedHeight(24)
        badge.setMinimumWidth(60)
        badge.setMaximumWidth(80)
        badge.setAlignment(Qt.AlignCenter)
        header.addWidget(badge)

        name_label = QLabel(data["name"])
        name_label.setObjectName("helpFuncName")
        name_label.setMaximumWidth(120)
        header.addWidget(name_label)

        brief_label = QLabel(data.get("short", data["name"]))
        brief_label.setObjectName("helpFuncBrief")
        brief_label.setWordWrap(True)
        header.addWidget(brief_label, 1)

        layout.addLayout(header)

        self._detail_widget = QWidget()
        self._detail_widget.setObjectName("helpDetailWidget")
        detail_layout = QVBoxLayout(self._detail_widget)
        detail_layout.setContentsMargins(0, 8, 0, 0)
        detail_layout.setSpacing(6)

        desc = data.get("desc", "")
        if desc:
            desc_label = QLabel(desc)
            desc_label.setObjectName("helpDescText")
            desc_label.setWordWrap(True)
            detail_layout.addWidget(desc_label)

        def_def = data.get("definition", "")
        if def_def:
            def_title = QLabel("定义")
            def_title.setObjectName("helpMarkdownTitle")
            font = def_title.font()
            font.setBold(True)
            def_title.setFont(font)
            detail_layout.addWidget(def_title)
            def_label = QLabel(def_def)
            def_label.setObjectName("helpCodeInline")
            def_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            def_label.setWordWrap(True)
            detail_layout.addWidget(def_label)

        params = data.get("params", "")
        if params:
            params_title = QLabel("参数")
            params_title.setObjectName("helpMarkdownTitle")
            font = params_title.font()
            font.setBold(True)
            params_title.setFont(font)
            detail_layout.addWidget(params_title)
            params_label = QLabel(params)
            params_label.setObjectName("helpDetailText")
            params_label.setWordWrap(True)
            detail_layout.addWidget(params_label)

        returns = data.get("returns", "")
        if returns:
            ret_title = QLabel("返回")
            ret_title.setObjectName("helpMarkdownTitle")
            font = ret_title.font()
            font.setBold(True)
            ret_title.setFont(font)
            detail_layout.addWidget(ret_title)
            ret_label = QLabel(returns)
            ret_label.setObjectName("helpDetailText")
            detail_layout.addWidget(ret_label)

        example = data.get("example", "")
        if example:
            ex_title = QLabel("示例代码")
            ex_title.setObjectName("helpMarkdownTitle")
            font = ex_title.font()
            font.setBold(True)
            ex_title.setFont(font)
            detail_layout.addWidget(ex_title)

            code_frame = QFrame()
            code_frame.setObjectName("helpCodeFrame")
            code_layout = QVBoxLayout(code_frame)
            code_layout.setContentsMargins(8, 6, 8, 6)
            code_layout.setSpacing(4)

            code_label = QLabel(example)
            code_label.setObjectName("helpCodeText")
            code_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            code_label.setWordWrap(True)
            font = QFont("Menlo, Consolas")
            font.setPointSize(11)
            code_label.setFont(font)
            code_layout.addWidget(code_label)

            detail_layout.addWidget(code_frame)

        self._detail_widget.setVisible(False)
        layout.addWidget(self._detail_widget)

        self.setCursor(Qt.PointingHandCursor)

    def _copy_code(self, code):
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(code)

    def toggle_expand(self):
        self._expanded = not self._expanded
        self._detail_widget.setVisible(self._expanded)
        icons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icons")
        if self._expanded:
            self._expand_arrow.setIcon(QIcon(os.path.join(icons_dir, "down_arrow.svg")))
        else:
            self._expand_arrow.setIcon(QIcon(os.path.join(icons_dir, "right_arrow.svg")))
        self.setProperty("expanded", self._expanded)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.toggle_expand()
        super().mousePressEvent(event)


class HelpPanelManager:
    def __init__(self, ui):
        self.ui = ui
        self._visible = False
        self._panel = None
        self._category_btns = []
        self._category_positions = []
        self._build_panel()

    def _build_panel(self):
        self._panel = QWidget()
        self._panel.setObjectName("helpPanel")
        self._panel.setFixedWidth(380)

        main_layout = QHBoxLayout(self._panel)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("helpScrollArea")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        content_widget = QWidget()
        content_widget.setObjectName("helpContentWidget")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 12, 16, 12)
        content_layout.setSpacing(10)

        for cat in HELP_DATA:
            cat_card = QFrame()
            cat_card.setObjectName("helpCatCard")
            cat_card_layout = QVBoxLayout(cat_card)
            cat_card_layout.setContentsMargins(12, 10, 12, 10)
            cat_card_layout.setSpacing(4)

            cat_label = QLabel(cat["name"])
            cat_label.setObjectName("helpCatTitle")
            cat_label.setStyleSheet(
                f"font-size: 15px; font-weight: bold; color: {cat['color']}; padding: 0px 0px 4px 0px;"
            )
            cat_card_layout.addWidget(cat_label)

            for section in cat.get("sections", []):
                sec_label = QLabel(section["title"])
                sec_label.setObjectName("helpSectionTitle")
                sec_label.setStyleSheet("font-size: 13px; color: rgb(160,160,160); padding: 6px 0px 4px 0px;")
                cat_card_layout.addWidget(sec_label)

                for item in section.get("items", []):
                    card = FunctionCard(item)
                    cat_card_layout.addWidget(card)

                note = section.get("note")
                if note:
                    note_label = QLabel(note)
                    note_label.setObjectName("helpNoteText")
                    note_label.setWordWrap(True)
                    note_label.setStyleSheet("color: rgb(140,140,140); padding: 4px 0px; font-size: 12px;")
                    cat_card_layout.addWidget(note_label)

            content_layout.addWidget(cat_card)
            self._category_positions.append((cat, cat_card))

        content_layout.addStretch()

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll, 1)

        cat_bar = QWidget()
        cat_bar.setObjectName("helpCategoryBar")
        cat_bar.setFixedWidth(56)
        cat_layout = QVBoxLayout(cat_bar)
        cat_layout.setContentsMargins(2, 6, 2, 6)
        cat_layout.setSpacing(2)

        for cat in HELP_DATA:
            btn = ScratchCatBtn(cat["name"], cat["color"])
            btn.clicked.connect(lambda c=cat, b=btn: self._on_cat_click(c, b))
            cat_layout.addWidget(btn)
            self._category_btns.append(btn)

        cat_layout.addStretch()
        main_layout.addWidget(cat_bar)

        self._scroll_area = scroll
        self._content_widget = content_widget

        self._panel.setVisible(False)

        frame = self.ui.editor_code_web.findChild(QFrame, "frame")
        if frame:
            layout = frame.layout()
            if layout:
                layout.addWidget(self._panel)

    def _on_cat_click(self, cat, clicked_btn):
        for btn in self._category_btns:
            btn.setChecked(False)
        clicked_btn.setChecked(True)

        for c, widget in self._category_positions:
            if c["name"] == cat["name"]:
                scrollbar = self._scroll_area.verticalScrollBar()
                target = widget.y() - 10
                scrollbar.setValue(max(0, target))
                break

    def toggle(self):
        self._visible = not self._visible
        if self._panel:
            self._panel.setVisible(self._visible)
            if self._visible and self._category_btns:
                for btn in self._category_btns:
                    btn.setChecked(False)
                self._category_btns[0].setChecked(True)

    def show(self):
        self._visible = True
        if self._panel:
            self._panel.setVisible(True)

    def hide(self):
        self._visible = False
        if self._panel:
            self._panel.setVisible(False)
