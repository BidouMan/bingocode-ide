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

朝着当前 angle 方向移动指定像素。移动时会自动检测碰撞，会拆分成小步避免穿墙。

### add_x / add_y — 直接修改坐标

```python
hero.add_x(5)   # 向右移动 5 像素
hero.add_x(-5)  # 向左移动 5 像素
hero.add_y(5)   # 向下移动 5 像素
hero.add_y(-5)  # 向上移动 5 像素
```

直接修改坐标，不检测碰撞。正数向右/下，负数向左/上。

### set_x / set_y — 设置坐标

```python
hero.set_x(300)  # 设置 x 坐标
hero.set_y(200)  # 设置 y 坐标
```

设置坐标，会自动检测碰撞。比 `add_x`/`add_y` 更安全。

## 朝向控制

### set_angle — 设置朝向

```python
hero.set_angle(90)  # 朝下
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

### 跳跃

```python
hero.jump(10)  # 施加向上的力
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `power` | 数字 | 10 | 跳跃力度，越大跳得越高 |

注意：`jump` 只是施加向上的力，需要自己用 `on_ground` 判断能否跳。

### cut_jump — 截断跳跃

```python
hero.cut_jump()
```

松手时调用，让角色提前下落。用于实现按住跳得高、轻点跳得矮的效果。

```python
if key_pressed("space") and hero.on_ground:
    hero.jump(12)

if key_up("space"):
    hero.cut_jump()
```

### drop_through — 穿过跳板

```python
hero.drop_through()
```

让角色穿过脚下的跳板掉下去。

## 速度属性

### vy — 垂直速度

```python
print(hero.vy)  # 当前垂直速度
```

- 正数 = 下落中
- 负数 = 上升中
- 0 = 静止

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
    if key_pressed("space") and hero.on_ground:
        hero.jump(12)
    
    if key_up("space"):
        hero.cut_jump()
    
    # 边界限制
    if hero.x < 0:
        hero.x = 0
    if hero.x > 640:
        hero.x = 640
```
