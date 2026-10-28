---
title: 精灵 Sprite
description: 角色、敌人、子弹和道具都从 Sprite 开始。本页完整说明创建、属性、动画、分组、碰撞回调和挂点跟随。
---

`Sprite` 是游戏里所有“看得见、动得了”的东西的基类。角色、敌人、子弹、道具，本质上都是一个 `Sprite` 对象。

<!-- api-index -->

## 类概览

<div class="callout note">
  <strong>先记住三件事</strong>
  <p>创建后角色会自动显示，不需要自己画；准备代码写在 <code>while True</code> 外面，只执行一次；每帧逻辑写在循环里面，才会持续生效。</p>
</div>

| 你会用到 | 成员 |
|----------|------|
| 创建与删除 | `Sprite(名字)`、`delete()` |
| 位置与尺寸 | `x`、`y`、`pos`、`scale`、`angle`、`layer`、`vy` |
| 显示与动画 | `show()`、`hide()`、`say()`、`play()`、`set_rotation_mode()` |
| 分组与碰撞回调 | `add_to_group()`、`is_touch_group()`、`on_touch_group()` |
| 标记与跟随 | `get_marker()`、`follow()`、`unfollow()` |

## 创建与删除

### Sprite — 创建角色

<div class="api-sig"><span class="badge class">类</span><code>Sprite(名字)</code><span class="sig-note">返回 Sprite</span></div>

根据资源面板里的角色名创建一个角色对象。创建后角色会立刻出现在画面中心 `(320, 240)`，默认大小 `100`、朝向 `0°`、层级 `0`。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `名字` | 字符串 | 是 | 资源面板中添加的角色名称，必须完全一致 |

```python
hero = Sprite("玩家")

print(hero.x, hero.y)   # 320 240
print(hero.scale)       # 100
print(hero.angle)       # 0
```

- 名字包含空格、数字或标点时，也要原样写进字符串，例如 `Sprite("玩家 1")`。
- 名字写错时，控制台会提示“角色不存在”，程序会停止；不会出现一个看不见的空角色。
- 每次 `Sprite(...)` 都会创建一个新对象。需要两个敌人，就创建两次；不要把同一个变量重复创建。
- 变量名可以自己取，`hero`、`player`、`小猫` 都可以；括号里的名字才对应资源。

> **提示：** 角色资源需要先在资源面板里添加。内置资源库里的素材可以直接拖入项目后使用。

### delete — 彻底删除角色

<div class="api-sig"><span class="badge method">方法</span><code>hero.delete()</code><span class="sig-note">返回 None</span></div>

把角色从画面、碰撞系统和内存里一起移除。删除后这个对象不能再使用；如果还需要，只能重新 `Sprite(...)` 创建一个。

```python
enemy = Sprite("史莱姆")

# 碰到玩家后删除
if enemy.is_touch(player):
    enemy.delete()
```

- 删除会同时把角色从所有分组里移除。
- 删除后继续调用 `enemy.x` 等属性不会报错，但数据已经没有意义，不建议这样写。
- 隐藏用 `hide()`，删除用 `delete()`：隐藏只是看不见，对象仍然存在；删除才是永久移除。

## 位置与尺寸

### x — 横坐标

<div class="api-sig"><span class="badge prop">属性</span><code>hero.x</code><span class="sig-note">读 / 写</span></div>

角色在画面上的水平位置。画面左边是 `0`，向右增大。

```python
print(hero.x)       # 读取当前横坐标

hero.x = 100        # 直接设置
hero.x += 10        # 向右移动 10 像素
hero.x -= 10        # 向左移动 10 像素
```

- 赋值后引擎会立即做一次碰撞修正：如果终点和墙重叠，会被推到墙外。
- 它只检查“终点”，不检查中间路径；一次从 `0` 设到 `640` 可能直接穿过薄墙。需要可靠移动时用 `move()`。
- 使用地图时，可移动范围由地图尺寸决定，不一定还是 `0 ~ 640`。

### y — 纵坐标

<div class="api-sig"><span class="badge prop">属性</span><code>hero.y</code><span class="sig-note">读 / 写</span></div>

角色在画面上的垂直位置。画面下边是 `0`，**向上**增大。

```python
print(hero.y)       # 读取当前纵坐标

hero.y = 200        # 直接设置
hero.y += 10        # 向上移动 10 像素
hero.y -= 10        # 向下移动 10 像素
```

- 记住：`y` 越大越靠上。这和很多图形库“y 向下增大”的习惯相反，但对数学坐标更直观。
- 和 `x` 一样，赋值只检查终点，不检查路径。

### pos — 一次性获取坐标

<div class="api-sig"><span class="badge prop">属性</span><code>hero.pos</code><span class="sig-note">只读</span></div>

把 `x` 和 `y` 作为一个元组一次性返回，可以直接拆包。

```python
x, y = hero.pos
print(f"角色在 ({x}, {y})")

# 与下面两行完全等价
# x = hero.x
# y = hero.y
```

- `pos` 是只读属性，不能写 `hero.pos = (100, 200)`；要改位置请分别设置 `hero.x`、`hero.y` 或使用 `goto()`。
- 适合需要同时读取两个坐标的场景，例如记录出生点、保存关卡数据。

### scale — 角色大小

<div class="api-sig"><span class="badge prop">属性</span><code>hero.scale</code><span class="sig-note">读 / 写 | 单位 %</span></div>

角色的大小百分比。`100` 是原始大小，`200` 是两倍大，`50` 是一半大。

```python
hero.scale = 200    # 放大到两倍
hero.scale = 50     # 缩小到一半
hero.scale += 10    # 在当前基础上变大 10%
```

- 有效范围是 `5 ~ 1000`；超出范围会被自动限制到边界值。
- 缩放会同时影响视觉大小和碰撞范围。
- 如果只想临时改变大小，记得在合适的时候改回 `100`。

### angle — 角色朝向

<div class="api-sig"><span class="badge prop">属性</span><code>hero.angle</code><span class="sig-note">读 / 写 | 单位 °</span></div>

角色面朝的方向，逆时针为正。

| 角度 | 朝向 |
|------|------|
| `0` | 右 |
| `90` | 上 |
| `180` | 左 |
| `270` | 下 |

```python
hero.angle = 90     # 朝上
hero.angle = 180    # 朝左

print(hero.angle)   # 读取当前角度
```

- 角度决定 `move()` 的移动方向，也会影响 `left_right` 模式下的左右翻转。
- 如果 `set_rotation_mode("none")`，角度仍然可以读写，但画面不会旋转。
- 想要“面向另一个角色或鼠标”，用 `look_at()` 更直接。

### layer — 图层顺序

<div class="api-sig"><span class="badge prop">属性</span><code>hero.layer</code><span class="sig-note">读 / 写 | 默认 0</span></div>

角色之间的前后遮挡顺序。**数字越大越靠前**，可以是负数。

```python
background = Sprite("背景板")
background.layer = -10

hero.layer = 0
effect = Sprite("特效")
effect.layer = 5      # 盖在角色前面
```

- 默认值是 `0`，所以写 `1`、`2`、`3` 就能逐步盖到别的角色前面。
- `layer` 只控制角色之间的顺序；地图图层的顺序由地图编辑器管理。
- 设置后立即生效，不需要重新创建角色。

### vy — 垂直速度

<div class="api-sig"><span class="badge prop">属性</span><code>hero.vy</code><span class="sig-note">读 / 写 | 正数向上</span></div>

角色的垂直速度。正数表示向上运动，负数表示向下运动，`0` 表示垂直方向静止。

```python
print(hero.vy)      # 跳跃上升时为正，下落时为负

hero.vy = 8         # 给一个向上的初速度
hero.vy = 0         # 清除垂直速度
```

- 开启重力后，引擎每个物理步都会自动修改 `vy`，通常不需要手动设置。
- 需要“跳一下”时优先用 `jump()` 或 `smart_jump()`，它们比直接改 `vy` 更直观。
- 没有地图物理时，修改 `vy` 不会自动让角色上下移动；它只是一个被记录的速度值。

## 显示、说话与动画

### show / hide — 显示与隐藏

<div class="api-sig"><span class="badge method">方法</span><code>hero.show()</code> <code>hero.hide()</code><span class="sig-note">返回 None</span></div>

控制角色可见性。隐藏后对象还在，只是看不见；还可以再 `show()` 出来。

```python
enemy.hide()

# 几秒后重新出现
if time_passed(2):
    enemy.show()
```

- 隐藏的角色不会参与碰撞检测，`is_touch()` 会返回 `False`。
- 隐藏不会停止角色自身的持续移动、动画或跟随；需要彻底停下请把速度设为 `0`。
- 删除请用 `delete()`，不要用 `hide()` 代替。

### say — 头顶对话气泡

<div class="api-sig"><span class="badge method">方法</span><code>hero.say(text, seconds=0)</code><span class="sig-note">返回 None</span></div>

在角色头顶显示一句话。新的话会替换旧的话。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `text` | 字符串 | 必填 | 要说的话，数字会自动转成字符串 |
| `seconds` | 数字 | `0` | 显示秒数；`0` 表示一直显示 |

```python
hero.say("你好！")          # 一直显示
hero.say("得分 +1", 2)      # 2 秒后自动消失
hero.say("")                # 立即清空气泡
```

- 连续调用 `say()` 时，只保留最后一句话。
- 带秒数的气泡会由引擎自动隐藏，不需要自己写计时器。
- 适合做提示、对话和得分反馈；大量文字建议用 `show_text()`。

### play — 播放动画

<div class="api-sig"><span class="badge method">方法</span><code>hero.play(动画名, transition_time=0.1)</code><span class="sig-note">返回 None</span></div>

播放角色资源里已经做好的动画片段，例如 `idle`、`walk`、`attack`。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `动画名` | 字符串 | 必填 | 角色资源里的动画片段名称 |
| `transition_time` | 数字 | `0.1` | 兼容旧代码的参数；当前引擎会直接切换动画 |

```python
hero.play("idle")

while True:
    if key_down("left") or key_down("right"):
        hero.play("walk")
    else:
        hero.play("idle")
```

- 动画名写错时，控制台会列出这个角色可用的动画名，按提示修改即可。
- 片段是否循环、每秒几帧，由角色编辑器里的动画设置决定。
- 动画只改变显示的帧，不会自动移动角色；移动仍然要靠 `add_x()`、`move()` 或 `set_speed()`。
- 资源里没有动画时，`play()` 不会产生效果。

### set_rotation_mode — 设置旋转方式

<div class="api-sig"><span class="badge method">方法</span><code>hero.set_rotation_mode(模式)</code><span class="sig-note">返回 None</span></div>

决定 `angle` 怎样影响画面。

| 模式 | 效果 | 适合 |
|------|------|------|
| `"all"` | 任意角度旋转，默认 | 飞机、子弹、指针 |
| `"left_right"` | 只左右翻转，不整体旋转 | 平台跳跃、横版角色 |
| `"none"` | 始终正向，不旋转也不翻转 | 固定朝向的装饰、UI 角色 |

```python
hero.set_rotation_mode("left_right")
hero.angle = 180    # 画面上变成朝左
```

- `left_right` 模式下，`0°` 朝右、`180°` 朝左；上下方向不会让角色倒过来。
- 旋转方式只影响显示，不影响 `move()` 的移动方向。
- 一般只需要设置一次，写在 `while True` 外面即可。

## 分组与碰撞回调

### add_to_group — 加入分组

<div class="api-sig"><span class="badge method">方法</span><code>hero.add_to_group(组名)</code><span class="sig-note">返回 None</span></div>

把角色登记到一个命名分组里。分组本身不会产生任何效果，但 `is_touch_group()` 和 `on_touch_group()` 会用到它。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `组名` | 字符串 | 是 | 自己起的组名，例如 `"enemies"`、`"子弹"` |

```python
enemy1.add_to_group("enemies")
enemy2.add_to_group("enemies")

bullet.add_to_group("bullets")
```

- 同一个角色重复加入同一个组，不会被重复登记。
- 组名要完全一致；`"enemies"` 和 `"Enemies"` 是两个不同的组。
- 角色被 `delete()` 后会自动从组里移除。

### is_touch_group — 是否碰到组内成员

<div class="api-sig"><span class="badge method">方法</span><code>hero.is_touch_group(组名)</code><span class="sig-note">返回 Sprite 或 None</span></div>

检测自己是否碰到某个组里的任意成员。碰到时返回**那个成员**，没碰到返回 `None`。

```python
hit = bullet.is_touch_group("enemies")

if hit:
    hit.delete()
    bullet.delete()
```

- 返回的是碰到的角色对象，可以直接继续操作它，例如 `.say()`、`.delete()`。
- 会排除自己，所以把自己也加进同一个组不会误判。
- 隐藏或已删除的角色不参与检测。
- 需要“碰到后自动处理”，用 `on_touch_group()` 更省代码。

### on_touch_group — 碰到时自动执行

<div class="api-sig"><span class="badge method">方法</span><code>hero.on_touch_group(组名, callback=None)</code><span class="sig-note">注册一次即可</span></div>

给角色注册一个碰撞回调。引擎每帧自动检测，碰到组内成员时执行动作，不需要自己写 `if`。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `组名` | 字符串 | 必填 | 对方必须先用 `add_to_group()` 加入这个组 |
| `callback` | 函数 | `None` | 不传时默认双方自动删除；传入时执行 `callback(自己, 对方)` |

```python
# 写法一：碰到后双方自动消失
bullet.on_touch_group("enemies")

# 写法二：自己决定发生什么
def 子弹命中(子弹, 敌人):
    敌人.say("命中！", 1)
    敌人.delete()
    子弹.delete()
    broadcast("得分 +1")

bullet.on_touch_group("enemies", 子弹命中)
```

- 注册写在 `while True` **外面**；写在循环里会重复注册。
- 默认不传 `callback` 时，主动方和被动方都会 `delete()`。
- 传了 `callback` 后，引擎不再自动删除，删不删由函数决定。
- 子弹是循环里新建的，就要在每次新建后注册一次；角色只创建一次，就注册一次。
- 对方忘了 `add_to_group()`，回调永远不会触发，这是最常见的问题。

## 标记与跟随

### get_marker — 获取角色标记

<div class="api-sig"><span class="badge method">方法</span><code>hero.get_marker(name="标记")</code><span class="sig-note">返回标记引用或 None</span></div>

读取角色编辑器「标记」图层里标注的锚点。标记会跟随角色的位置、旋转、缩放和翻转实时变化。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` | 字符串 | `"标记"` | 角色编辑器里给标记起的名字 |

```python
hand = hero.get_marker("手")
gun.goto(hand)          # 把枪放到手上
gun.follow(hand)        # 让枪一直跟着手

print(hand.x, hand.y)   # 标记当前的世界坐标（用户坐标）
```

- 只有 `.bsf` 角色支持标记；普通单图角色需要先在角色编辑器里完成标注，保存后会转换为 `.bsf`。
- 名字不存在时返回 `None`，同时在控制台列出这个角色已有的标记名。
- 返回值不是元组，而是“标记引用”；可以直接传给 `goto()`、`follow()` 使用。
- 标记位置会随动画帧变化；同一角色不同帧的标记可以不同。

### follow — 持续跟随目标

<div class="api-sig"><span class="badge method">方法</span><code>hero.follow(target, flip=True)</code><span class="sig-note">返回 None</span></div>

让当前角色每帧自动跟随另一个角色或标记的位置。只跟随位置，不会复制目标的朝向和大小。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `target` | Sprite / 标记引用 | 必填 | 要跟随的角色或 `get_marker()` 的返回值 |
| `flip` | 布尔 | `True` | 是否继承目标的左右翻转；武器瞄准鼠标时可设为 `False` |

```python
# 剑跟着角色的手
sword.follow(hero.get_marker("手"))

# 准星跟随鼠标位置，但不继承玩家翻转
crosshair.follow(hero, flip=False)
```

- 跟随由引擎每帧自动更新，不需要在 `while True` 里手动写 `goto()`。
- 目标被删除后会自动停止跟随，不会报错。
- 跟随不会改变自身的 `angle`；需要瞄准时另外调用 `look_at()`。
- 只想跟随一次、之后自由移动，用 `goto()` 而不是 `follow()`。

### unfollow — 解除跟随

<div class="api-sig"><span class="badge method">方法</span><code>hero.unfollow()</code><span class="sig-note">返回 None</span></div>

停止跟随目标。解除后会保留最后一次继承到的左右朝向，不会突然翻回正面。

```python
sword.follow(hero.get_marker("手"))

# 角色死亡，武器掉在原地
sword.unfollow()
```

- 不需要传参数。
- 解除后角色停在当前位置，之后可以自由移动。
- 再次 `follow()` 会重新开始跟随，并重新继承目标的翻转状态。

## 完整示例

```python
# 准备阶段：只执行一次
player = Sprite("玩家")
player.goto(320, 100)
player.set_rotation_mode("left_right")
player.layer = 2
player.say("准备好了吗？", 3)

enemy = Sprite("史莱姆")
enemy.goto(520, 100)
enemy.set_scale(80)
enemy.add_to_group("enemies")

while True:
    # 左右移动
    if key_down("left"):
        player.add_x(-4)
        player.set_angle(180)

    if key_down("right"):
        player.add_x(4)
        player.set_angle(0)

    # 大小跳
    if key_down("space"):
        player.smart_jump(12)

    # 碰到敌人
    if player.is_touch_group("enemies"):
        enemy.delete()
        player.say("碰到了！", 2)
```

## 相关 API

<div class="legend-grid">
  <article class="path-card" data-href="{{PREFIX}}api/movement.html">
    <span class="path-num">继续阅读</span>
    <div class="card-title">运动</div>
    <p>移动、朝向、持续速度、跳跃和边界反弹的完整用法。</p>
    <span class="card-link">查看运动 API →</span>
  </article>
  <article class="path-card" data-href="{{PREFIX}}editor/sprite-editor.html">
    <span class="path-num">继续阅读</span>
    <div class="card-title">角色编辑器</div>
    <p>中心点、碰撞体和标记怎样影响代码里的角色行为。</p>
    <span class="card-link">查看编辑器指南 →</span>
  </article>
</div>
