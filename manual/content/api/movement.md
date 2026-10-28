---
title: 运动
description: 移动、朝向、持续速度、跳跃和边界反弹。本页说明每个运动 API 的移动方式、碰撞行为和常见写法。
---

运动 API 决定角色怎样改变位置和方向。它们都作用在 `Sprite` 对象上，所以先有角色，再调用运动方法。

<!-- api-index -->

## 位置移动

### goto — 传送到指定位置

<div class="api-sig"><span class="badge method">方法</span><code>hero.goto(x, y)</code> <code>hero.goto(目标)</code><span class="sig-note">瞬间移动</span></div>

把角色瞬间传送到指定坐标，或者在标记、另一个角色所在的位置。传送后会立即做一次碰撞修正。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | 数字 | 目标横坐标 |
| `y` | 数字 | 目标纵坐标；向上为正 |
| `目标` | 标记引用 / Sprite | 写到标记或角色身上；只传一个参数 |

```python
hero.goto(320, 240)              # 传送到画面中心

hand = hero.get_marker("手")
gun.goto(hand)                   # 传送到手的标记位置

hero.goto(enemy)                 # 传送到敌人所在位置
```

- 不是“走过去”，而是瞬间出现在目标点；需要移动过程请用 `move()` 或 `add_x()/add_y()`。
- 只检查最终落点，不检查中间路径，所以可以直接从墙的一侧传到另一侧。
- 落点和墙重叠时会被推到最近的一侧。
- 传送到标记或角色时，使用的是对方的注册点/标记位置，不需要自己算坐标。

### move — 朝当前方向移动

<div class="api-sig"><span class="badge method">方法</span><code>hero.move(distance)</code><span class="sig-note">每帧调用</span></div>

沿着当前 `angle` 方向移动指定像素。移动过程会自动拆分小步并处理碰撞。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `distance` | 数字 | 是 | 移动像素数；负数表示朝反方向移动 |

```python
hero.angle = 0
hero.move(5)        # 向右移动 5 像素

hero.angle = 90
hero.move(5)        # 向上移动 5 像素

hero.move(-5)       # 朝当前朝向的反方向移动 5 像素
```

- 写在 `while True` 里，每帧移动一次；`move(5)` 约等于每秒 300 像素（按 60 帧计算）。
- 位移超过 16 像素时会被拆成多个小步，所以比直接改 `x/y` 更不容易穿墙。
- 撞墙时会停下或贴着墙滑动，但**不会自己绕路**；它不是寻路算法。
- 移动方向只由 `angle` 决定，和角色图片实际朝哪边没有关系。

### add_x / add_y — 增加坐标

<div class="api-sig"><span class="badge method">方法</span><code>hero.add_x(dx)</code> <code>hero.add_y(dy)</code><span class="sig-note">相对移动</span></div>

在当前坐标上增加一个值。`add_x` 正数向右，`add_y` 正数向上。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `dx` | 数字 | 是 | 横向增量；正数向右，负数向左 |
| `dy` | 数字 | 是 | 纵向增量；正数向上，负数向下 |

```python
hero.add_x(5)       # 向右 5 像素
hero.add_x(-5)      # 向左 5 像素

hero.add_y(5)       # 向上 5 像素
hero.add_y(-5)      # 向下 5 像素
```

- 和 `hero.x += 5`、`hero.y += 5` 等价。
- 改完会立即做一次碰撞修正：小步移动会被墙挡住，从墙里会被推出来。
- 和 `move()` 不同，它不会自动拆成小步。一次 `add_x(100)` 可能直接穿过薄墙。
- 逐帧移动建议用 `move()`；只需要微调坐标时用 `add_x/add_y` 更直接。

### set_x / set_y — 设置坐标

<div class="api-sig"><span class="badge method">方法</span><code>hero.set_x(x)</code> <code>hero.set_y(y)</code><span class="sig-note">绝对坐标</span></div>

把横坐标或纵坐标直接设成某个值，另一个坐标保持不变。

```python
hero.set_x(300)     # 横坐标设为 300
hero.set_y(200)     # 纵坐标设为 200

# 与下面两行分别等价
# hero.x = 300
# hero.y = 200
```

- 设置后立即检查落点：和墙重叠时会被推到最近的一侧。
- 只检查终点，不检查中间路径；可以从墙的一侧直接设到另一侧。
- 设置 `y` 时记得：数字越大越靠上。

### goto_rand — 随机传送

<div class="api-sig"><span class="badge method">方法</span><code>hero.goto_rand()</code><span class="sig-note">返回 None</span></div>

把角色随机传送到画面中的某个位置。

```python
hero.goto_rand()
```

- 横坐标范围是 `0 ~ 地图宽度`，纵坐标范围是 `0 ~ 地图高度`（默认地图是 640×480）。
- **不会做碰撞修正**，可能落在墙里；需要安全随机位置时，自己生成坐标并用 `goto()` 检查。
- 使用大地图时会在整张地图范围内随机。

## 朝向与持续运动

### set_angle — 设置朝向

<div class="api-sig"><span class="badge method">方法</span><code>hero.set_angle(angle)</code><span class="sig-note">单位 °</span></div>

设置角色朝向，逆时针为正。`0` 右、`90` 上、`180` 左、`270` 下。

```python
hero.set_angle(90)      # 朝上

# 与下面一行等价
# hero.angle = 90
```

- 设置角度后，`move()` 会沿新方向移动。
- 画面是否旋转由 `set_rotation_mode()` 决定；`left_right` 模式下只做左右翻转。
- 角度会保留，不会自动回到 `0`。

### look_at — 看向目标

<div class="api-sig"><span class="badge method">方法</span><code>hero.look_at(target)</code><span class="sig-note">每帧调用可保持瞄准</span></div>

让角色自动转向另一个角色或鼠标位置。只接受 `Sprite` 对象或 `mouse`。

| 参数 | 类型 | 说明 |
|------|------|------|
| `target` | Sprite / `mouse` | 要看向的角色，或鼠标对象 |

```python
# 枪口一直对准鼠标
while True:
    gun.look_at(mouse)

# 敌人一直面向玩家
enemy.look_at(player)
```

- 只改变角度，不会让角色移动，也不会持续跟随目标位置。
- 需要一直瞄准时，把 `look_at()` 写进 `while True`。
- 目标的角色被删除后，函数不会改变当前角度。
- 传入字符串、数字等无效参数时不会报错，但也不会旋转。

### set_speed — 设置持续速度

<div class="api-sig"><span class="badge method">方法</span><code>hero.set_speed(speed)</code><span class="sig-note">每帧自动移动</span></div>

设置一个持续速度。设置后引擎每帧自动沿当前朝向移动，不需要再在循环里调用 `move()`。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `speed` | 数字 | 是 | 每帧移动像素数；`0` 表示停止 |

```python
bullet = Sprite("子弹")
bullet.set_angle(90)
bullet.set_speed(6)         # 每帧向上 6 像素

# 想停下
bullet.set_speed(0)
```

- 适合子弹、敌人、移动平台等“发出去就不用管”的对象。
- 只对大于 `0` 的速度生效。想反向移动，先把 `angle` 转 180°，再设置正速度。
- 速度会被碰撞检测处理；撞墙时不会穿墙。
- 角色被删除后自动停止，不需要手动清零。

### edge_bounce — 碰到边界反弹

<div class="api-sig"><span class="badge method">方法</span><code>hero.edge_bounce()</code><span class="sig-note">每帧调用</span></div>

碰到地图边界时自动反弹，并修正角色位置，避免卡在边缘。

```python
ball = Sprite("小球")
ball.set_angle(45)
ball.set_speed(4)

while True:
    ball.edge_bounce()
```

- 必须在每一帧调用，才能持续检测边界。
- 边界是当前地图的可玩区域；没有地图时是 `640 × 480` 舞台。
- 只有角色正在朝边界移动时才会反弹；沿边缘滑动不会误触发。
- 反弹只改变角度，不改变速度大小。

## 跳跃与地面

### is_on_ground — 是否站在地面上

<div class="api-sig"><span class="badge method">方法</span><code>hero.is_on_ground()</code><span class="sig-note">返回 True / False</span></div>

角色真正站在有碰撞的地面上时返回 `True`。上升中、下落中、从跳板下方穿过时都返回 `False`。

```python
if hero.is_on_ground():
    print("可以跳了")
```

- 需要地图开启重力，角色才会落地并被判定为“站在地面上”。
- `jump()` 自己不会判断地面，所以跳跃前通常要配合这个函数使用。
- 站在普通墙顶、地面、实心平台上都算在地面上；跳板也算，但从下方穿过时不算。
- 旧名字 `is_on_floor()` 仍然可用，但新代码建议用 `is_on_ground()`。

### jump — 跳跃

<div class="api-sig"><span class="badge method">方法</span><code>hero.jump(power=10)</code><span class="sig-note">起跳一次</span></div>

给角色一个向上的起跳速度。力度越大跳得越高。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `power` | 数字 | `10` | 起跳力度；默认重力下 `10` 大约跳 100 像素 |

```python
if key_pressed("space") and hero.is_on_ground():
    hero.jump(12)
```

- **不会自动判断地面**：在空中调用就是二段跳。需要限制时自己加 `is_on_ground()`。
- 跳起来后不会因为松手而提前落下；需要“松手就落”请配合 `stop_jump()`，或直接用 `smart_jump()`。
- 需要地图开启重力，角色才会自然落回地面。
- 只在按下的那一帧调用即可，用 `key_pressed()` 而不是 `key_down()`。

### smart_jump — 大小跳（推荐）

<div class="api-sig"><span class="badge method">方法</span><code>hero.smart_jump(power=10)</code><span class="sig-note">每帧调用</span></div>

按下起跳、按住跳得高、松手提前落下。引擎会自动处理松手，不需要自己写 `stop_jump()`。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `power` | 数字 | `10` | 最大跳跃力度；越大跳得越高 |

```python
while True:
    if key_down("space"):
        hero.smart_jump(12)
```

- 推荐写在 `if key_down(...)` 里，每帧调用一次；引擎会记录起跳键，松手后自动停止上升。
- 必须每帧持续调用，不要只在按下的那一帧调用。
- 重复调用不会连续起跳；角色在空中时调用不会再次起跳。
- 需要地图开启重力，否则角色不会落下，看起来就像“飘在空中”。
- 和 `jump()` 的区别：`jump()` 只负责起跳，松手不会提前落下；`smart_jump()` 把两者合在一起。

### stop_jump — 停止上升

<div class="api-sig"><span class="badge method">方法</span><code>hero.stop_jump()</code><span class="sig-note">配合 jump 使用</span></div>

角色正在上升时调用，会停止继续上升并提前落下，用来实现“轻点跳得矮、按住跳得高”。

```python
while True:
    if key_pressed("space") and hero.is_on_ground():
        hero.jump(12)

    if key_up("space"):
        hero.stop_jump()
```

- **它自己不会让角色跳起来**；必须先用 `jump()` 或 `vy` 让角色上升。
- 只在上升阶段有效；在平地上或下落中调用没有任何效果，也不会报错。
- 角色已经在下落时继续调用也没问题。
- 松手判断可以用 `key_up("space")`，也可以用 `if not key_down("space")`。
- 觉得两步太麻烦，直接用 `smart_jump()`。

### drop_down — 从跳板掉下去

<div class="api-sig"><span class="badge method">方法</span><code>hero.drop_down()</code><span class="sig-note">站在跳板上时有效</span></div>

让角色从脚下的“跳板”掉到下一层。只有地图里碰撞类型设为「跳板」的地面才有效。

```python
while True:
    if key_down("down"):
        hero.drop_down()
```

- 站在普通墙体或实心地面上调用不会生效。
- 角色不在地面上时调用会被自动忽略，不需要自己判断 `is_on_ground()`。
- 掉下去后约 0.16 秒内忽略跳板碰撞，之后恢复正常。
- 需要地图编辑器里把对应碰撞体类型设为「跳板」。

## 完整示例：平台跳跃

```python
player = Sprite("玩家")
player.goto(100, 100)
player.set_rotation_mode("left_right")

while True:
    # 左右移动
    if key_down("left"):
        player.add_x(-4)
        player.set_angle(180)

    if key_down("right"):
        player.add_x(4)
        player.set_angle(0)

    # 按住空格：跳得更高；松手：提前落下
    if key_down("space"):
        player.smart_jump(12)

    # 从跳板向下穿过
    if key_down("down"):
        player.drop_down()
```

## 常见错误

| 现象 | 原因 | 修改 |
|------|------|------|
| 跳起来后不落下 | 地图没有开启重力 | 在地图属性里打开重力 |
| 在空中还能继续跳 | 没用 `is_on_ground()` 限制 | 跳跃前判断是否在地面 |
| `set_speed(3)` 没反应 | 速度为负或角色已被删除 | 使用正数，反向请改 `angle` |
| 角色穿过薄墙 | 一次 `add_x()` / `set_x()` 跨度太大 | 改用 `move()` 分步移动 |
| `goto_rand()` 卡在墙里 | 随机传送不做碰撞修正 | 自己生成安全坐标后用 `goto()` |
| `look_at()` 没反应 | 传入了字符串或数字 | 只传 `Sprite` 对象或 `mouse` |

## 相关 API

<div class="legend-grid">
  <article class="path-card" data-href="{{PREFIX}}api/sprite.html">
    <span class="path-num">继续阅读</span>
    <div class="card-title">精灵 Sprite</div>
    <p>坐标、大小、层级、动画和分组，角色对象的总览。</p>
    <span class="card-link">查看精灵 API →</span>
  </article>
  <article class="path-card" data-href="{{PREFIX}}guide/getting-started.html">
    <span class="path-num">回到入门</span>
    <div class="card-title">快速入门</div>
    <p>从主界面、坐标系到第一段可运行代码。</p>
    <span class="card-link">查看快速入门 →</span>
  </article>
</div>
