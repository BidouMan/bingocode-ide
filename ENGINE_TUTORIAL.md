# BingoEngine 引擎教程

> 这是一份面向初学者的引擎使用指南。所有功能按类别分组，方便查找。

---

## 快速开始

```python
from bingo_engine import *

hero = Sprite("角色名")

def loop():
    if key_down('right'):
        hero.add_x(3)

run()
```

---

## 运动模块

控制角色的位置和移动。

| 方法 | 说明 | 示例 |
|------|------|------|
| `goto(x, y)` | 移到指定坐标 | `hero.goto(320, 240)` |
| `set_xy(x, y)` | 设置坐标（同 goto） | `hero.set_xy(100, 200)` |
| `set_x(x)` | 设置 X 坐标 | `hero.set_x(320)` |
| `set_y(y)` | 设置 Y 坐标 | `hero.set_y(240)` |
| `add_x(dx)` | X 坐标增加 | `hero.add_x(5)` |
| `add_y(dy)` | Y 坐标增加 | `hero.add_y(-5)` |
| `move(distance)` | 朝当前方向移动 | `hero.move(10)` |
| `set_angle(angle)` | 设置朝向角度 | `hero.set_angle(90)` |
| `look_at(target)` | 朝向目标 | `hero.look_at(enemy)` |
| `edge_bounce()` | 碰到边缘反弹（自动适配地图边界） | `hero.edge_bounce()` |
| `goto_rand()` | 移到随机位置 | `hero.goto_rand()` |

### 属性访问

```python
hero.x = 320        # 设置 X
hero.y = 240        # 设置 Y
hero.angle = 90     # 设置角度
print(hero.x)       # 读取 X
```

### 跳跃（平台游戏）

| 方法 | 说明 |
|------|------|
| `jump(power)` | 跳跃，power 越大跳越高 |
| `cut_jump()` | 提前下落（松开跳跃键时调用） |
| `drop_through()` | 从跳板下方穿过 |
| `is_on_floor()` | 检测是否在地面上 |

```python
def loop():
    if key_down('up') and hero.is_on_floor():
        hero.jump(12)
    if key_up('up'):
        hero.cut_jump()
```

---

## 外观模块

控制角色的显示、缩放和动画。

| 方法 | 说明 | 示例 |
|------|------|------|
| `show()` | 显示角色 | `hero.show()` |
| `hide()` | 隐藏角色 | `hero.hide()` |
| `set_scale(value)` | 设置缩放（100=原始大小） | `hero.set_scale(50)` |
| `add_scale(value)` | 增加缩放 | `hero.add_scale(10)` |
| `set_rotation_mode(style)` | 旋转模式 | 见下方说明 |
| `say(text)` | 角色说话（永久显示） | `hero.say("你好！")` |
| `say(text, seconds)` | 角色说话（N秒后消失） | `hero.say("得分+1", 2)` |
| `play(name)` | 播放动画 | `hero.play("walk")` |

### 旋转模式

```python
hero.set_rotation_mode("all")       # 任意旋转（默认）
hero.set_rotation_mode("left_right") # 左右翻转
hero.set_rotation_mode("none")       # 不旋转
```

### 层级

```python
hero.layer = 10  # 数字越大越靠前
```

---

## 侦测模块

检测碰撞、距离和输入状态。

### 碰撞检测

| 方法 | 说明 | 返回值 |
|------|------|--------|
| `is_touch(target)` | 是否碰到目标 | True / False |
| `is_touch_edge()` | 是否碰到舞台边缘 | True / False |
| `is_out_side()` | 是否完全离开舞台 | True / False |
| `distance_to(target)` | 到目标的距离 | 数字 |
| `touch_group(name)` | 碰到组内成员 | 那个成员 / None |

```python
# 碰到另一个角色
if hero.is_touch(enemy):
    print("碰到敌人了")

# 碰到鼠标
if hero.is_touch(mouse):
    print("鼠标在角色上")

# 碰到特定标签的图块
if hero.is_touch("lava"):
    print("掉进岩浆了")

# 计算距离
d = hero.distance_to(enemy)
if d < 50:
    print("距离很近")
```

### 组操作

```python
enemy.add_to_group("enemies")     # 加入组
hit = hero.touch_group("enemies") # 检测碰到组内成员
```

---

## 输入模块

检测键盘和鼠标。

| 函数 | 说明 | 示例 |
|------|------|------|
| `key_down(key)` | 按住时每帧返回 True | `if key_down('space'):` |
| `key_pressed(key)` | 按下瞬间返回 True | `if key_pressed('space'):` |
| `mouse_down()` | 鼠标按下时返回 True | `if mouse_down():` |
| `mouse_pressed()` | 鼠标点击瞬间返回 True | `if mouse_pressed():` |

### 鼠标位置

```python
print(mouse.x)  # 鼠标 X 坐标
print(mouse.y)  # 鼠标 Y 坐标
```

### 按键名称

方向键：`'up'` `'down'` `'left'` `'right'`
字母键：`'a'` `'b'` `'c'` ... `'z'`
空格：`'space'`
回车：`'enter'`

---

## 控制模块

定时器、等待和游戏循环控制。

### wait() 定时函数

每 N 秒触发一次，无需创建对象。

```python
def loop():
    if wait(0.2):  # 每 0.2 秒触发
        print("定时执行")

    if key_down('space') and wait(0.1):  # 配合按键限频
        bullet = Sprite("子弹")
```

### Timer 计时器

更精细的定时控制，支持停止、重启、单次触发。

```python
# 创建计时器
t = Timer(1.0)                          # 1秒循环
t = Timer(3.0, loop=False)              # 3秒一次性
t = Timer(0.5, autostart=True)          # 创建即启动

# 控制
t.start()       # 启动/重启
t.stop()        # 停止
t.is_timeout()  # 时间到了返回 True
```

### 完整示例

```python
shoot_timer = Timer(0.2, autostart=True)
skill_timer = Timer(5.0, loop=False)

def loop():
    # 普通射击
    if key_down('space') and shoot_timer.is_timeout():
        bullet = Sprite("子弹")
        ...

    # 大招冷却
    if skill_timer.is_timeout():
        print("大招冷却完毕")

    # 释放大招
    if key_down('e') and skill_timer.is_timeout():
        hero.play("skill")
        skill_timer.start()  # 重新冷却
```

### 暂停和停止

| 函数 | 说明 |
|------|------|
| `pause()` | 暂停游戏（精灵停止移动，loop 仍运行） |
| `resume()` | 继续游戏 |
| `is_paused()` | 检查是否暂停 |
| `stop()` | 停止游戏（退出 run 循环） |

```python
def loop():
    # 按 P 暂停/继续
    if key_pressed('p'):
        if is_paused():
            resume()
        else:
            pause()
    
    # 按 Q 停止游戏
    if key_pressed('q'):
        stop()
```

---

## 子弹模块

发射子弹和碰撞回调。

### 创建子弹

```python
bullet = Sprite("子弹图片")
bullet.goto(hero.x, hero.y)
bullet.set_angle(hero.angle)
bullet.set_speed(8)              # 自动移动
bullet.auto_destroy = True       # 飞出屏幕自动销毁
bullet.add_to_group("bullets")
bullet.on_hit("enemies", damage) # 碰到敌人触发回调
```

### 碰撞回调

```python
def damage(bullet, other):
    other.hp -= 1       # 扣血
    bullet.delete()     # 子弹消失
    if other.hp <= 0:
        other.delete()  # 敌人死亡
```

### 不写回调

```python
bullet.on_hit("enemies")  # 碰到 enemies 组 → 双方都删除
```

### 完整射击示例

```python
from bingo_engine import *

hero = Sprite("英雄")
enemy = Sprite("敌人")
enemy.hp = 3
enemy.add_to_group("enemies")

def damage(bullet, other):
    other.hp -= 1
    bullet.delete()
    if other.hp <= 0:
        other.delete()

def loop():
    # 移动
    if key_down('right'):
        hero.add_x(3)
    if key_down('left'):
        hero.add_x(-3)

    # 射击
    if key_down('space') and wait(0.2):
        bullet = Sprite("子弹")
        bullet.goto(hero.x, hero.y)
        bullet.set_angle(hero.angle)
        bullet.set_speed(8)
        bullet.auto_destroy = True
        bullet.add_to_group("bullets")
        bullet.on_hit("enemies", damage)

run()
```

---

## 声音模块

播放和停止音效。

```python
play_sound("sound_name")           # 播放一次
play_sound("sound_name", loop=True) # 循环播放
stop_sound("sound_name")           # 停止指定音效
stop_sound()                       # 停止所有音效
```

---

## 广播模块

角色之间或全局的事件通信。

| 函数 | 说明 |
|------|------|
| `broadcast("事件名")` | 发送全局广播 |
| `sprite.broadcast("事件名")` | 角色发送广播 |
| `receive("事件名", 函数名)` | 注册接收广播 |

### 基本用法

```python
# 发送广播
enemy.broadcast("died")      # 角色广播
broadcast("game_over")       # 全局广播

# 接收广播
receive("died", 加分)
receive("game_over", 停止游戏)
```

### 完整示例

```python
from bingo_engine import *

score = 0

def 加分():
    global score
    score += 10
    print(f"得分: {score}")

def 游戏结束():
    print("Game Over")

# 注册接收
receive("enemy_died", 加分)
receive("game_over", 游戏结束)

hero = Sprite("英雄")
enemy = Sprite("敌人")
enemy.hp = 3

def loop():
    if key_down('space') and wait(0.2):
        bullet = Sprite("子弹")
        bullet.goto(hero.x, hero.y)
        bullet.set_angle(hero.angle)
        bullet.set_speed(8)
        bullet.on_hit("enemies", 击中敌人)

def 击中敌人(bullet, other):
    other.hp -= 1
    bullet.delete()
    if other.hp <= 0:
        other.broadcast("enemy_died")  # 广播死亡
        other.delete()

run()
```

---

## 地图模块

加载和显示地图。

```python
load_map("map_name")  # 加载地图
follow(hero)          # 摄像机跟随角色
```

---

## 随机数模块

生成随机数，无需 import。

| 函数 | 说明 | 示例 |
|------|------|------|
| `random_int(a, b)` | 随机整数（包含两端） | `random_int(1, 10)` |
| `random_float(a, b)` | 随机浮点数 | `random_float(0.0, 1.0)` |

```python
# 随机方向
hero.set_angle(random_int(0, 360))

# 随机位置
hero.goto(random_int(0, 640), random_int(0, 480))

# 随机大小
hero.set_scale(random_int(50, 150))
```

---

## 屏幕文字模块

在屏幕任意位置绘制文字，显示分数、血量等信息。

| 函数 | 说明 |
|------|------|
| `draw_text(x, y, *args)` | 在指定位置绘制文字，多个参数自动拼接 |

```python
score = 100

# 显示分数
draw_text(10, 10, "分数:", score)

# 同一位置多次调用会覆盖旧文字
draw_text(10, 10, "分数:", 200)

# 清除文字（空内容）
draw_text(10, 10)
```

### 完整计分示例

```python
from bingo_engine import *

hero = Sprite("英雄")
enemy = Sprite("敌人")
enemy.add_to_group("enemies")
score = 0

def damage(bullet, other):
    global score
    score += 10
    bullet.delete()
    other.delete()

def loop():
    draw_text(10, 10, "分数:", score)

    if key_down('right'):
        hero.add_x(3)
    if key_down('left'):
        hero.add_x(-3)

    if key_down('space') and wait(0.2):
        bullet = Sprite("子弹")
        bullet.goto(hero.x, hero.y)
        bullet.set_angle(hero.angle)
        bullet.set_speed(8)
        bullet.auto_destroy = True
        bullet.on_hit("enemies", damage)

run()
```

---

## 屏幕效果模块

| 函数 | 说明 | 示例 |
|------|------|------|
| `shake(intensity, duration)` | 屏幕震动 | `shake()` |

```python
# 默认震动
shake()

# 自定义强度和时长
shake(10, 0.5)  # 强度10，持续0.5秒

# 被打中时震动反馈
if hero.is_touch(enemy):
    shake(8, 0.3)
    hero.say("ouch!", 1)
```

---

## 调试工具

```python
show_fps()             # 显示帧率
show_collision(sprite) # 显示角色碰撞盒
```

---

## 程序结构

```python
from bingo_engine import *

# 1. 创建角色
hero = Sprite("角色名")
enemy = Sprite("敌人名")

# 2. 定义回调函数
def on_hit(bullet, other):
    other.delete()
    bullet.delete()

# 3. 定义主循环
def loop():
    # 显示信息
    draw_text(10, 10, "分数:", score)

    # 输入检测
    if key_down('right'):
        hero.add_x(3)

    # 发射子弹
    if key_down('space') and wait(0.2):
        bullet = Sprite("子弹")
        bullet.goto(hero.x, hero.y)
        bullet.set_speed(8)
        bullet.on_hit("enemies", on_hit)

# 4. 启动游戏
run()
```

> **注意：** `run()` 必须放在最后，它会启动游戏循环并自动调用 `loop()` 函数。
