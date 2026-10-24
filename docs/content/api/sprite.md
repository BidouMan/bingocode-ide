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
- 下边是 0，上边是 480（向上移动，y 变大）
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
hero.angle = 90  # 朝上
```

- 角度单位：度
- 0° = 朝右，90° = 朝上，180° = 朝左，270° = 朝下

### layer — 图层顺序

```python
hero.layer = 10  # 设置图层层级
```

- 数字越大越在前面，越小越在后面（可以是负数）
- 默认值：0（直接写 1、2、3 就能盖在别的角色前面）
- 用于控制精灵之间的前后遮挡关系

### vy — 垂直速度

```python
print(hero.vy)  # 当前垂直速度
```

- 正数 = 向上运动（跳跃上升时）
- 负数 = 向下运动（下落时）
- 0 = 垂直方向静止

## 方法

### goto — 传送到指定位置

```python
hero.goto(100, 200)
```

瞬间传送到指定坐标，自动检测碰撞。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` | 数字 | 目标 x 坐标 (0~640) |
| `y` | 数字 | 目标 y 坐标 (0~480，向上增大) |

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

| 参数 | 类型 | 说明 |
|------|------|------|
| `步数` | 数字 | 移动的像素数 |

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

### is_touch_group — 组碰撞检测

```python
hit = bullet.is_touch_group("enemies")
if hit:
    hit.delete()    # 删除被击中的敌人
    bullet.delete()  # 删除子弹
```

检测是否碰到组内成员，碰到返回那个精灵，没碰到返回 None。

### is_on_ground — 是否站在地面上

```python
if hero.is_on_ground():
    print("脚底有地面，可以跳")
    hero.jump(10)
```

角色是否真正站在地面上（由物理落地的碰撞接触决定）：站着为 True，跳起来、下落中、从下方穿过跳板都为 False。

`jump()` 不会自己判断，跳跃前要用它检查，否则会变成空中二段跳。

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
    if key_pressed("space") and hero.is_on_ground():
        hero.jump(12)
    
    # 停止跳跃（松手就提前落下）
    if key_up("space"):
        hero.stop_jump()
    
    # 边界限制
    if hero.x < 0:
        hero.x = 0
    if hero.x > 640:
        hero.x = 640
```
