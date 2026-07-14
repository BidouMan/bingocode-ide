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
    hero.cut_jump()
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

### mouse.x / mouse.y — 鼠标位置

```python
print(mouse.x)  # 鼠标 x 坐标 (0~640)
print(mouse.y)  # 鼠标 y 坐标 (0~480)

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

### touch_group — 组碰撞检测

```python
# 检测子弹是否碰到 "enemies" 组
hit = bullet.touch_group("enemies")
if hit:
    # hit 是被碰到的那个精灵
    hit.delete()
    bullet.delete()
```

碰到返回那个精灵，没碰到返回 None。

### is_on_floor — 地面检测

```python
if hero.is_on_floor():
    print("脚底有碰撞地形")
```

检测角色脚底下方是否存在带碰撞的图块。比 `on_ground` 更精确但更耗性能。

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

### on_hit — 注册碰撞回调

```python
# 子弹碰到敌人时，两者都消失
bullet.on_hit("enemies", lambda b, e: (b.delete(), e.delete()))
```

当精灵碰到指定组的成员时，自动执行回调函数。

| 参数 | 类型 | 说明 |
|------|------|------|
| `group` | 字符串 | 组名 |
| `callback` | 函数 | 回调函数，参数为 (自己, 碰到的精灵) |

回调函数可以是 lambda 或普通函数：

```python
def on_bullet_hit(bullet, enemy):
    bullet.delete()
    enemy.delete()
    broadcast("得分+1")

bullet.on_hit("enemies", on_bullet_hit)
```

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
    if bullet and bullet.touch_group("enemies"):
        hit = bullet.touch_group("enemies")
        hit.delete()
        bullet.delete()
        bullet = None
```
