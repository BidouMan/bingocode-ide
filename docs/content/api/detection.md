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

# 检测是否碰到鼠标
if hero.is_touch(mouse):
    print("鼠标碰到角色了！")

# 检测是否碰到带标签的地形
if hero.is_touch("地面"):
    print("碰到地面了！")
```

返回 True/False。

| 参数 | 类型 | 说明 |
|------|------|------|
| `target` | 精灵/字符串 | 另一个精灵、mouse 对象或标签字符串 |

### is_touch_edge — 是否碰到画面边缘

```python
if hero.is_touch_edge():
    print("碰到画面边缘了！")
```

只要有一边碰到就返回 True。

### is_out_side — 是否完全在画面外

```python
if hero.is_out_side():
    print("角色完全在画面外面")
```

只有整个角色都在画面外才返回 True。

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

### on_touch_group — 碰到时自动执行

`on_touch_group` 对**同一个角色**只需注册一次（不是每帧调用），引擎会每帧自动帮你检测，不需要你在 `while True` 里自己判断。如果子弹是每次发射新建的，就在新建后给这个新子弹注册一次。

**最常见用法：只写组名，碰到后双方自动消失**

```python
# ① 先让敌人加入 "enemies" 组（不写这句，组是空的，永远不会触发）
enemy.add_to_group("enemies")

# ② 给子弹注册一次：以后碰到 enemies 组里的任何成员，
#     引擎自动删除「子弹自己」和「那个敌人」，不用你写 delete()
bullet.on_touch_group("enemies")
```

注意：`on_touch_group("enemies")` **不传第二个参数**时，引擎默认执行的就是：

```python
bullet.delete()   # 自己消失
enemy.delete()    # 碰到的那个敌人消失
```

**完整例子（可直接运行）**

```python
hero = Sprite("玩家")
enemy = Sprite("敌人")
enemy.add_to_group("enemies")   # 先让敌人进组

bullet = None

while True:
    if key_down("left"):
        hero.add_x(-5)
    if key_down("right"):
        hero.add_x(5)

    # 按 Z 发射子弹
    if key_pressed("z"):
        bullet = Sprite("子弹")
        bullet.goto(hero.x, hero.y)
        bullet.set_speed(10)
        bullet.on_touch_group("enemies")   # 注册：子弹碰到敌人 → 两者自动消失

    # 子弹飞出画面后清理
    if bullet and bullet.is_out_side():
        bullet.delete()
        bullet = None
```

对比一下：同样效果如果不用 `on_touch_group`，就得自己在 `while True` 里每帧写判断：

```python
if bullet and bullet.is_touch_group("enemies"):
    hit = bullet.is_touch_group("enemies")
    hit.delete()
    bullet.delete()
    bullet = None
```

**想自己决定碰到后做什么，就传一个函数**

函数会收到两个参数：`自己`、`碰到的角色`。传入函数后，引擎**不再自动删除**，一切由你的函数决定：

```python
def 子弹碰到敌人(子弹, 敌人):
    敌人.delete()
    子弹.delete()
    broadcast("得分+1")

bullet.on_touch_group("enemies", 子弹碰到敌人)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `group` | 字符串 | 组名，对方必须先用 `add_to_group("组名")` 加入 |
| `callback` | 函数（可选） | 碰到时执行，参数为 (自己, 碰到的精灵)；不写则默认双方自动消失 |

#### 和 is_touch_group 的区别

| | `is_touch_group("组名")` | `on_touch_group("组名")` |
|---|---|---|
| 谁来检测 | 你的 `while True` 里每帧主动调用 | 注册一次，引擎每帧自动检测 |
| 结果 | 返回碰到的角色（没碰到返回 `None`） | 自动处理（默认双方删除，或执行你传入的函数） |
| 适合场景 | 需要"碰到后按条件决定做什么"（拿金币、碰到敌人扣血） | 子弹/道具这类"碰到就自动处理、不用再管"的对象 |

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
    
    # 子弹碰边消失
    if bullet and bullet.is_out_side():
        bullet.delete()
        bullet = None
    
    # 碰撞检测
    if bullet and bullet.is_touch_group("enemies"):
        hit = bullet.is_touch_group("enemies")
        hit.delete()
        bullet.delete()
        bullet = None
```
