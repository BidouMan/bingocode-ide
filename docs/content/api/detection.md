# 侦测

侦测类 API 用于检测碰撞、输入、距离等信息。

## 键盘输入

### key_down — 按键是否被按住

```python
if key_down("space"):
    print("空格键被按住")
```

持续检测：只要按键被按住，每帧都返回 True。

| 参数 | 类型 | 说明 |
|------|------|------|
| `key` | 字符串 | 按键名称 |

常用按键名：

| 按键 | 名称 |
|------|------|
| 空格 | `"space"` |
| 回车 | `"enter"` |
| 左 | `"left"` |
| 右 | `"right"` |
| 上 | `"up"` |
| 下 | `"down"` |
| A-Z | `"a"` ~ `"z"` |

### key_pressed — 按键是否刚刚按下

```python
if key_pressed("space"):
    hero.jump(10)
```

单次检测：只在按下那一瞬间返回 True。适合做跳跃、射击等一次性操作。

### key_up — 按键是否刚刚松开

```python
if key_up("space"):
    hero.stop_jump()
```

单次检测：只在松开那一瞬间返回 True。

## 鼠标输入

### mouse_down — 鼠标是否被按住

```python
if mouse_down():
    print("鼠标左键被按住")
```

### mouse_pressed — 鼠标是否刚刚点击

```python
if mouse_pressed():
    print("鼠标左键刚刚被点击")
```

### mouse_up — 鼠标是否刚刚松开

```python
if mouse_up():
    print("鼠标左键刚刚松开")
```

单次检测：只在松开鼠标左键的那一瞬间返回 True。

### mouse.x / mouse.y / mouse.pos — 鼠标位置

```python
print(mouse.x)  # 鼠标 x 坐标 (0~640)
print(mouse.y)  # 鼠标 y 坐标 (0~480，画面下边为 0，向上增大)

# 一次性拿到两个坐标
x, y = mouse.pos

# 让角色看向鼠标
hero.look_at(mouse)
```

## 碰撞检测

### is_touch — 碰撞检测

```python
# 检测是否碰到另一个精灵
if hero.is_touch(enemy):
    print("碰到敌人了！")

# 检测是否碰到鼠标（按角色真实碰撞轮廓判定）
if hero.is_touch(mouse):
    print("鼠标碰到角色了！")

# 检测是否碰到带标签的地形（形状层标签或图块标签）
if hero.is_touch("水"):
    print("碰到水了！")
```

返回 True/False。

- 标签可以是**形状层**里给形状填的标签，也可以是**图块**的标签
- 形状层三种能力都能检测：`阻挡`、`感应`、`阻挡 + 感应` 都算「碰到」
- 贴着边界（差不到半个像素）也算碰到，不会因为碰撞求解留下的细小间隙漏判
- 角色使用真实碰撞轮廓（`.bsf` 的胶囊 / 多边形 / 旋转 / 缩放都会考虑），不是简单的外接矩形

| 参数 | 类型 | 说明 |
|------|------|------|
| `target` | 精灵/字符串/mouse | 另一个精灵、标签字符串或 mouse 对象 |

### sweep_test — 用身体扫一下，前方是否被挡住

```python
if hero.sweep_test("right"):
    hero.say("右边是墙")

# 往前探 8 像素
if hero.sweep_test("down", 8):
    hero.say("前面要掉下去了")
```

用自己的身体形状朝一个方向做一次**扫掠测试**：只测试、不移动（对应 Godot 的 `test_move`、Bullet 的 `convexSweepTest`）。适合做俯视迷宫、下一步能不能迈、方向探测。

- **感应区域不算阻挡**
- 「跳板」只有向下、并且从上方靠近时才算阻挡
- 不受角色当前速度和朝向影响，只看你给的方向
- 和 `raycast` 的区别：`raycast` 是一条没有宽度的线，`sweep_test` 用的是整个身体，窄缝、头顶空间这类问题更准

| 参数 | 类型 | 说明 |
|------|------|------|
| `direction` | 字符串/数字 | `"left"` / `"right"` / `"up"` / `"down"`，也接受 `左/右/上/下` 或角度数字（0 右、90 上、180 左、270 下） |
| `distance` | 数字（可选） | 往前探多远，默认 2 像素 |

### raycast / hero.raycast — 打一条射线

```python
# 从角色所在点出发（最常用）
hit = hero.raycast("right", 200)
if hit:
    print("前方", hit.distance, "像素有东西，标签：", hit.tag)
    print("命中点：", hit.x, hit.y)

# 沿角色当前朝向
hit = hero.raycast(hero.angle, 300)

# 从任意点出发（鼠标、标记、预测位置）
hit = raycast(mouse.x, mouse.y, "down", 50)
```

朝一个方向射出看不见的线，返回最近碰到的实心地形；没碰到返回 `None`。

- `hero.raycast(direction, distance=1000)`：起点是角色位置（和 `goto` / `look_at` 用的是同一个点）
- `raycast(x, y, direction, distance=1000)`：起点是任意用户坐标点

适合做瞄准、视线遮挡、落地预测、探测器。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` / `y` | 数字 | 仅全局版需要：起点（用户坐标：地图左下角为原点，y 向上） |
| `direction` | 字符串/数字 | 同 `sweep_test` 的方向写法 |
| `distance` | 数字（可选） | 射线长度，默认 1000 像素 |

命中结果可以读：

| 字段 | 说明 |
|------|------|
| `hit.distance` | 从起点到命中点的距离 |
| `hit.x` / `hit.y` / `hit.pos` | 命中点坐标（用户坐标） |
| `hit.normal` | 命中表面的朝向 `(x, y)`，可用于反弹 |
| `hit.tag` | 命中形状/图块的标签（没有则为空字符串） |
| `hit.collision_type` | 物理属性（墙体 / 跳板 / 图像 / 自定义） |
| `hit.source` | 来源类型：`shape` 形状层 / `image` 图像 / `tile` 图块 |

### is_touch_edge — 是否碰到地图边界

```python
if hero.is_touch_edge():
    print("碰到地图边界了！")
```

只要有一边碰到就返回 True。

### is_out_screen — 是否完全飞出画面

```python
if hero.is_out_screen():
    print("角色完全飞出画面了")
```

只有整个角色都出了 640×480 的游戏画面才返回 True。

判断的是「画面」而不是「地图」：地图很长时，角色飞出一屏就会被判为出屏，不会一直飞到地图另一头；开启相机跟随时，画面中心会跟着角色移动，此时以移动后的画面为准。

### is_touch_group — 组碰撞检测

```python
# 检测子弹是否碰到 "enemies" 组
hit = bullet.is_touch_group("enemies")
if hit:
    # hit 是被碰到的那个精灵
    hit.delete()
    bullet.delete()
```

碰到返回那个精灵，没碰到返回 None。

### is_on_ground — 是否站在地面上

```python
if hero.is_on_ground():
    print("脚底有碰撞地形，可以跳")
```

角色是否真正站在地面上（由物理落地的碰撞接触决定）：站着为 True，跳起来、下落中、从下方穿过跳板都为 False。
`jump()` 不会自己判断，跳跃前要用它检查，否则会变成空中二段跳。

### is_on_wall — 是否贴着墙

```python
if hero.is_on_wall():
    hero.say("贴墙了")
```

左右两侧是否正贴着实体地形。和 `is_on_ground()` 一样来自**本帧的物理接触**：只有正顶着墙的那一帧为 True，离开墙或只是站在旁边为 False。

### is_on_ceiling — 头顶是否撞到东西

```python
if hero.is_on_ceiling():
    hero.stop_jump()
    hero.say("头好疼")
```

头顶是否撞到实体地形（天花板、墙顶；开启「限制边界」时撞到地图上边界也算）。
跳跃撞头的那一帧为 True，撞头时引擎会把向上速度清零，所以可以直接用它停止跳跃。

## 距离和位置

### distance_to — 距离计算

```python
dist = hero.distance_to(enemy)
print(f"距离：{dist} 像素")

# 近距离攻击
if hero.distance_to(enemy) < 50:
    hero.attack()
```

返回到目标的像素距离。

## 碰撞回调

碰撞 / 感应的回调注册（`on_touch_group`、`on_sensor_enter`、`on_sensor_exit`）属于「事件」类：注册一次，引擎自动检测并在条件满足时执行。完整说明见 [事件](events.md)。

## 完整示例

```python
hero = Sprite("玩家")
enemy = Sprite("敌人")
enemy.add_to_group("enemies")

bullet = None

while True:
    # 玩家移动
    if key_down("left"):
        hero.add_x(-5)
    if key_down("right"):
        hero.add_x(5)
    
    # 射击（按 Z 键）
    if key_pressed("z"):
        bullet = Sprite("子弹")
        bullet.goto(hero.x, hero.y)
        bullet.set_speed(10)
    
    # 子弹飞出画面后删除
    if bullet and bullet.is_out_screen():
        bullet.delete()
        bullet = None
    
    # 碰撞检测
    if bullet and bullet.is_touch_group("enemies"):
        hit = bullet.is_touch_group("enemies")
        hit.delete()
        bullet.delete()
        bullet = None
```
