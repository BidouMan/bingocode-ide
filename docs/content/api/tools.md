# 工具函数

工具类 API 提供各种辅助功能，如绘制文字、屏幕震动、计时器等。

## 绘制文字

### draw_text — 在画面上写字

```python
draw_text(100, 50, "得分：", score)
```

在画面指定位置显示文字。多个参数会自动拼接。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | 数字 | x 坐标 |
| `y` | 数字 | y 坐标 |
| `...args` | 任意 | 要显示的内容，会自动转为字符串并拼接 |

```python
# 显示分数
score = 0
draw_text(10, 10, "得分：", score)

# 显示多个信息
draw_text(10, 30, "生命：", lives, "  关卡：", level)

# 拼接字符串
name = "小明"
draw_text(100, 50, "玩家：", name)
```

## 屏幕效果

### shake — 画面震动

```python
shake(8, 0.5)
```

让画面抖动，适合用在角色被撞到、爆炸等场景。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `intensity` | 数字 | 5 | 震动强度，越大越厉害 |
| `duration` | 数字 | 0.3 | 震动时间（秒） |

```python
# 轻微震动
shake(3, 0.2)

# 强烈震动
shake(10, 0.5)

# 被敌人撞到时震动
if hero.is_touch(enemy):
    shake(8, 0.3)
    hero.delete()
```

### show_fps — 显示帧率

```python
show_fps()        # 显示帧率
show_fps(True)    # 显示帧率
show_fps(False)   # 隐藏帧率
```

在画面角落显示游戏运行速度（每秒刷新多少次）。用于调试性能。

### show_collision — 显示碰撞范围

```python
show_collision(hero)  # 显示角色的碰撞范围
```

把角色的碰撞范围画出来（一个彩色框），方便检查碰撞检测是否正确。

## 计时器

### Timer — 创建计时器

```python
clock = Timer(2)        # 每 2 秒提醒一次（循环）
clock = Timer(2, False) # 只提醒一次
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `seconds` | 数字 | - | 间隔秒数 |
| `loop` | 布尔 | True | 是否循环 |

### is_timeout — 时间到了吗

```python
clock = Timer(2)

while True:
    if clock.is_timeout():
        print("每 2 秒执行一次")
```

时间到了返回 True，然后自动重置。`loop=False` 时只触发一次。

### Timer 的方法

```python
clock = Timer(2)

clock.start()    # 启动计时器
clock.stop()     # 停止计时器
clock.is_timeout()  # 检查是否到期
```

### 实际应用

```python
# 每 2 秒生成一个敌人
spawn_timer = Timer(2)

while True:
    if spawn_timer.is_timeout():
        enemy = Sprite("敌人")
        enemy.goto_rand()
        enemy.add_to_group("enemies")
```

## wait — 定时器

```python
if wait(1):
    print("每隔 1 秒执行一次")
```

每隔指定时间返回一次 True。比 Timer 更简单，但功能较少。

```python
while True:
    # 每 0.5 秒发射一颗子弹
    if wait(0.5):
        bullet = Sprite("子弹")
        bullet.goto(hero.x, hero.y)
        bullet.set_speed(10)
```

## 随机数

### random_int — 随机整数

```python
n = random_int(1, 6)  # 1 到 6 之间的随机整数
```

就像掷骰子，可能返回 1~6 中的任意一个。

| 参数 | 类型 | 说明 |
|------|------|------|
| `min` | 数字 | 最小值（包含） |
| `max` | 数字 | 最大值（包含） |

### random_float — 随机小数

```python
f = random_float(0, 1)  # 0 到 1 之间的随机小数
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `min` | 数字 | 最小值 |
| `max` | 数字 | 最大值 |

## 完整示例

```python
# 带计时和得分的游戏
hero = Sprite("玩家")
score = 0
enemy_timer = Timer(1.5)
score_timer = Timer(5)

while True:
    # 玩家移动
    if key_down("left"):
        hero.add_x(-5)
    if key_down("right"):
        hero.add_x(5)
    if key_pressed("space") and hero.on_ground:
        hero.jump(10)
    if key_up("space"):
        hero.cut_jump()
    
    # 每 1.5 秒生成敌人
    if enemy_timer.is_timeout():
        enemy = Sprite("敌人")
        enemy.goto_rand()
        enemy.set_speed(2)
        enemy.add_to_group("enemies")
    
    # 每 5 秒加 10 分
    if score_timer.is_timeout():
        score += 10
        draw_text(10, 10, "得分：", score)
    
    # 碰撞检测
    if hero.touch_group("enemies"):
        hit = hero.touch_group("enemies")
        hit.delete()
        shake(8, 0.3)
        score -= 5
```
