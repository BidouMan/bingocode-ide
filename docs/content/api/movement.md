# 运动

运动类 API 用于控制精灵的移动、跳跃、物理效果等。

## 基本移动

### goto — 传送到指定位置

```python
hero.goto(100, 200)
```

瞬间传送到指定坐标，自动检测碰撞。

### goto_rand — 传送到随机位置

```python
hero.goto_rand()
```

随机传送到画面内的任意位置。

### move — 朝前走

```python
hero.move(5)
```

朝着当前 angle 方向移动指定像素。移动时会自动检测碰撞：撞到墙会停住、贴着墙滑动，不会穿墙（但**不会自己绕路**找出口）。

### add_x / add_y — 直接修改坐标

```python
hero.add_x(5)   # 向右移动 5 像素
hero.add_x(-5)  # 向左移动 5 像素
hero.add_y(5)   # 向上移动 5 像素
hero.add_y(-5)  # 向下移动 5 像素
```

直接修改坐标，正数向右/上，负数向左/下。改完会立即做一次碰撞修正：小步移动会被墙挡住、从墙里被推出来；但**一次加减太多（比如一次 100 像素）可能直接穿过薄墙**，因为它不会像 `move` 那样拆成小步。

### set_x / set_y — 设置坐标

```python
hero.set_x(300)  # 设置 x 坐标
hero.set_y(200)  # 设置 y 坐标
```

直接把坐标设成某个值，设置后立即做一次碰撞修正：落点和墙重叠时会被推到最近的一侧。它只检查"终点"、不检查中间路径，所以从墙的一侧直接设到另一侧是可以的。

## 朝向控制

### set_angle — 设置朝向

```python
hero.set_angle(90)  # 朝上
```

### look_at — 看向目标

```python
hero.look_at(enemy)    # 看向另一个精灵
hero.look_at(mouse)    # 看向鼠标
```

自动旋转角度，面向目标。

## 持续移动

### set_speed — 设置持续速度

```python
hero.set_speed(3)  # 持续向当前方向移动
hero.set_speed(0)  # 停止
```

设置持续移动速度，之后每帧自动沿当前方向移动。

### edge_bounce — 碰边反弹

```python
hero.edge_bounce()
```

碰到画面边缘时自动反弹。

## 物理效果

### smart_jump — 大小跳（推荐）

```python
while True:
    if key_down("up"):
        hero.smart_jump(12)
```

按下起跳、按住跳得高、松手就落下。松手时引擎会自动让角色提前落下，不用自己写 `stop_jump`。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `power` | 数字 | 10 | 最大跳跃力度，越大跳得越高 |

- **必须写在 `if key_down(...)` 里面**：引擎靠「这个函数本帧被调用过没有」来判断松手
- 按键不用重复写两遍，起跳键就是 `if key_down(...)` 里检查的那个键
- 重复调用不会连续起跳；站在空中时按它不会起跳
- 需要在地图属性里开启「重力」，角色才会自然落回地面

### jump — 跳跃（基础）

```python
if key_pressed("space") and hero.is_on_ground():
    hero.jump(10)
```

给角色一个向上的起跳速度。力度 10 大约能跳 95 像素高（按 16 像素的图块算约 6 格）。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `power` | 数字 | 10 | 起跳力度，越大跳得越高 |

- 引擎不会替你判断能不能跳：在空中调用会变成二段跳，所以要自己用 `is_on_ground()` 判断
- `jump` 只管「跳起来」，松手不会提前落下；要做到大小跳请配合 `stop_jump`，或直接用 `smart_jump`

### stop_jump — 停止跳跃（配合 jump 使用）

```python
if key_up("space"):
    hero.stop_jump()
```

用来实现「按住跳得高、轻点跳得矮」。

- **它自己不会让角色跳起来**：只有角色正在上升时才有效（把上升重力从 0.5 变成 2.8，让角色提前落下），所以必须先用 `jump`（或直接给 `vy` 一个正值）让角色上升
- 单独在平地上或下落中调用：没有任何效果，也不会报错
- 角色已经在下落时调用也没关系，所以松开键后每帧调用都可以
- 松手判断用 `key_up("space")`（也可以用 `if not key_down("space")`）
- 觉得两步太麻烦，直接用上面的 `smart_jump` 即可

```python
while True:
    if key_pressed("space") and hero.is_on_ground():
        hero.jump(12)

    # 松手就提前落下
    if key_up("space"):
        hero.stop_jump()
```

### drop_down — 从跳板掉下去

```python
# 站在跳板上时按下 ↓ 键，掉到跳板下面
if key_down("down"):
    hero.drop_down()
```

让角色从脚下的跳板掉下去。

- 只有站在碰撞类型为「跳板」的地面上才生效（在地图编辑器里把该碰撞类型设为「跳板」）
- 普通墙体不能穿过
- 角色不在地面上时调用会被自动忽略，不会报错，不需要自己判断 `is_on_ground()`
- 掉下去后约 0.16 秒内忽略跳板碰撞，之后恢复正常

## 速度属性

### vy — 垂直速度

```python
print(hero.vy)  # 当前垂直速度
```

- 正数 = 向上运动（跳跃上升时）
- 负数 = 向下运动（下落时）
- 0 = 垂直方向静止

## 完整示例

```python
hero = Sprite("玩家")
hero.goto(320, 400)
hero.set_rotation_mode("left_right")

while True:
    # 左右移动
    if key_down("left"):
        hero.add_x(-5)
    if key_down("right"):
        hero.add_x(5)
    
    # 跳跃
    if key_pressed("space") and hero.is_on_ground():
        hero.jump(12)
    
    if key_up("space"):
        hero.stop_jump()
    
    # 边界限制
    if hero.x < 0:
        hero.x = 0
    if hero.x > 640:
        hero.x = 640
```
