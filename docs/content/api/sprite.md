# 精灵 (Sprite)

精灵是游戏中的角色、道具、敌人等所有可移动的物体。

## 创建精灵

```python
hero = Sprite("角色名")
```

### 参数说明

| 参数 | 类型 | 说明 |
|------|------|------|
| `角色名` | 字符串 | 资源面板中添加的角色名称 |

### 示例

```python
# 创建一个叫"洛克人"的角色
hero = Sprite("洛克人")

# 创建后角色出现在画面中心 (320, 240)
print(hero.x)  # 320
print(hero.y)  # 240
```

### 注意事项

- 角色名必须和资源面板中添加的角色文件夹名一致
- 创建后不能重复创建同名角色
- 角色默认大小 100%，朝向右方 (0°)

## 删除精灵

```python
hero.delete()
```

删除角色后，角色从画面上移除，不能再使用。如果还需要，需要重新创建。

```python
hero = Sprite("洛克人")
# ... 游戏逻辑 ...
hero.delete()  # 彻底删除
```

## 属性

### x — 水平位置

```python
# 读取
print(hero.x)  # 当前 x 坐标

# 设置
hero.x = 100  # 移动到 x=100
```

- 范围：0 ~ 640
- 左边是 0，右边是 640
- 赋值时自动检测碰撞

### y — 垂直位置

```python
# 读取
print(hero.y)  # 当前 y 坐标

# 设置
hero.y = 200  # 移动到 y=200
```

- 范围：0 ~ 480
- 上边是 0，下边是 480
- 赋值时自动检测碰撞

### scale — 大小

```python
# 读取
print(hero.scale)  # 当前大小百分比

# 设置
hero.scale = 200  # 变成两倍大
hero.scale = 50   # 变成一半大
```

- 百分比表示：100 = 正常大小
- 200 = 两倍大
- 50 = 一半大

### angle — 朝向

```python
# 读取
print(hero.angle)  # 当前角度

# 设置
hero.angle = 90  # 朝下
```

- 角度单位：度
- 0° = 朝右，90° = 朝下，180° = 朝左，270° = 朝上

### layer — 图层顺序

```python
hero.layer = 10  # 设置图层层级
```

- 数字越大越在前面
- 默认值：1000
- 用于控制精灵的前后遮挡关系

### on_ground — 是否在地面

```python
if hero.on_ground:
    print("在地面上，可以跳")
    hero.jump(10)
```

- 布尔值：True = 在地面上，False = 在空中
- 每帧自动更新
- 用于判断能否跳跃

### vy — 垂直速度

```python
print(hero.vy)  # 当前垂直速度
```

- 正数 = 下落中
- 负数 = 上升中
- 0 = 静止

## 方法

### goto — 传送到指定位置

```python
hero.goto(100, 200)
```

瞬间传送到指定坐标，自动检测碰撞。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | 数字 | 目标 x 坐标 (0~640) |
| `y` | 数字 | 目标 y 坐标 (0~480) |

### goto_rand — 传送到随机位置

```python
hero.goto_rand()
```

随机传送到画面内的任意位置。

### move — 朝前走

```python
hero.move(5)
```

朝着当前 angle 方向移动指定像素。移动时会自动检测碰撞。

| 参数 | 类型 | 说明 |
|------|------|------|
| `步数` | 数字 | 移动的像素数 |

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

### set_speed — 持续移动

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

### jump — 跳跃

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

### show / hide — 显示/隐藏

```python
hero.show()  # 显示
hero.hide()  # 隐藏
```

隐藏后精灵还在，只是看不见了，可以再 `show` 出来。

### say — 说话

```python
hero.say("你好！")       # 永久显示
hero.say("得分+1", 2)   # 2 秒后消失
```

让角色头顶出现对话气泡。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `text` | 字符串 | - | 要说的话 |
| `seconds` | 数字 | 0 | 显示时间，0 = 永久 |

### set_scale — 设置大小

```python
hero.set_scale(150)  # 变成 150% 大小
```

### add_scale — 增减大小

```python
hero.add_scale(20)   # 变大 20%
hero.add_scale(-20)  # 变小 20%
```

在当前大小基础上增减。

### set_rotation_mode — 旋转方式

```python
hero.set_rotation_mode("all")        # 自由旋转（默认）
hero.set_rotation_mode("left_right") # 只左右翻转
hero.set_rotation_mode("none")       # 不旋转
```

### play — 播放动画

```python
hero.play("walk")           # 播放走路动画
hero.play("attack", 0.2)    # 0.2 秒过渡到攻击动画
```

需要角色资源里提前做好动画。

### is_touch — 碰撞检测

```python
if hero.is_touch(enemy):       # 碰到另一个精灵
if hero.is_touch(mouse):       # 碰到鼠标
if hero.is_touch("地面"):      # 碰到带标签的地形
    print("碰到！")
```

返回 True/False。

### is_touch_edge — 边缘检测

```python
if hero.is_touch_edge():
    print("碰到画面边缘了！")
```

### is_out_side — 完全出界检测

```python
if hero.is_out_side():
    print("角色完全在画面外")
```

### distance_to — 距离计算

```python
dist = hero.distance_to(enemy)
print(f"距离：{dist} 像素")
```

返回到目标的像素距离。

### touch_group — 组碰撞检测

```python
hit = bullet.touch_group("enemies")
if hit:
    hit.delete()    # 删除被击中的敌人
    bullet.delete()  # 删除子弹
```

检测是否碰到组内成员，碰到返回那个精灵，没碰到返回 None。

### is_on_floor — 地面检测

```python
if hero.is_on_floor():
    print("脚底有地面")
```

比 `on_ground` 更精确，但更耗性能。

### add_to_group — 加入组

```python
enemy1.add_to_group("enemies")
enemy2.add_to_group("enemies")
```

把精灵归到某个组里，方便批量管理。

### on_hit — 碰撞回调

```python
bullet.on_hit("enemies", lambda b, e: (b.delete(), e.delete()))
```

当子弹碰到 "enemies" 组的成员时，自动执行回调函数。

| 参数 | 类型 | 说明 |
|------|------|------|
| `group` | 字符串 | 组名 |
| `callback` | 函数 | 回调函数，参数为 (自己, 碰到的精灵) |

## 完整示例

```python
# 创建角色
hero = Sprite("洛克人")
hero.goto(320, 400)  # 放在画面下方
hero.set_rotation_mode("left_right")  # 只左右翻转

while True:
    # 左右移动
    if key_down("left"):
        hero.add_x(-5)
        hero.set_angle(180)  # 朝左
    if key_down("right"):
        hero.add_x(5)
        hero.set_angle(0)    # 朝右
    
    # 跳跃
    if key_pressed("space") and hero.on_ground:
        hero.jump(12)
    
    # 截断跳跃
    if key_up("space"):
        hero.cut_jump()
    
    # 边界限制
    if hero.x < 0:
        hero.x = 0
    if hero.x > 640:
        hero.x = 640
```
