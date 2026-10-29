# 碰撞检测与回调 API 速查

## 1. 相关 API 一览

| API | 作用 | 用法 |
|------|------|------|
| `add_to_group("组名")` | 把角色加入组 | `enemy.add_to_group("enemies")` |
| `is_touch(目标)` | 是否碰到某个角色 / 鼠标 | `hero.is_touch(enemy)`、`hero.is_touch(mouse)` |
| `is_touch_group("组名")` | 是否碰到组里任意成员，返回那个成员 | `hit = bullet.is_touch_group("enemies")` |
| `is_touch_edge()` | 是否碰到地图边界 | `hero.is_touch_edge()` |
| `is_out_screen()` | 是否整个角色都飞出游戏画面 | `bullet.is_out_screen()` |
| `on_touch_group("组名")` | 注册碰撞处理：碰到组员时由引擎自动执行 | `bullet.on_touch_group("enemies")` |

---

## 2. is_touch_group —— 主动检测

**每帧调用一次，返回碰到的角色；没碰到返回 `None`。**

```python
enemy.add_to_group("enemies")

while True:
    ...
    if bullet.is_touch_group("enemies"):
        hit = bullet.is_touch_group("enemies")
        hit.delete()
        bullet.delete()
        bullet = None
```

- 必须写在 `while True` 里
- 两个角色都必须在场景中（`Sprite(...)` 创建过）
- 组里没有任何成员时永远返回 `None`

---

## 3. on_touch_group —— 注册回调，引擎自动检测

### 最简用法：碰到后双方自动消失

```python
enemy.add_to_group("enemies")   # ① 对方先进组
bullet.on_touch_group("enemies")        # ② 注册一次
```

注册后，子弹一碰到 `enemies` 组里的任何角色，引擎默认执行：

```python
bullet.delete()   # 自己消失
enemy.delete()    # 碰到的那个角色消失
```

不需要再写 `is_touch_group` 判断，也不需要自己 `delete()`。

### 自定义碰撞后的行为

```python
def 子弹碰到敌人(子弹, 敌人):
    敌人.delete()
    子弹.delete()
    broadcast("得分+1")

bullet.on_touch_group("enemies", 子弹碰到敌人)
```

- 函数会收到两个参数：`(自己, 碰到的角色)`
- **传了函数后，引擎不再自动删除**，删不删由函数决定

### 注册时机（重要）

| 场景 | 注册方式 |
|------|----------|
| 角色只创建一次 | 循环外注册一次 |
| 每次发射都新建子弹 | 在新建子弹后立刻注册一次 |

```python
while True:
    if key_pressed("z"):
        bullet = Sprite("子弹")     # 新对象
        bullet.goto(hero.x, hero.y)
        bullet.set_speed(10)
        bullet.on_touch_group("enemies")     # 新子弹各注册一次
```

> 不要每帧注册：重复注册会让回调叠加，碰一次执行多次。

---

## 4. is_touch_group 和 on_touch_group 的区别

| | `is_touch_group("enemies")` | `on_touch_group("enemies")` |
|---|---|---|
| 谁来检测 | 你在 `while True` 里每帧调用 | 注册一次，引擎每帧自动检测 |
| 结果 | 返回碰到的角色，由你处理 | 自动处理（默认双方删除，或执行你传入的函数） |
| 适合场景 | 需要按条件决定做什么（拿金币、扣血） | 子弹、道具这类"碰到就自动处理"的对象 |

底层碰撞判定完全相同，区别只在「谁检测」和「结果怎么处理」。

---

## 5. 常见错误

| 现象 | 原因 | 解决 |
|------|------|------|
| 怎么都不触发 | 对方没有 `add_to_group("组名")` | 先把对方加入组 |
| 碰一次执行了好几次 | `on_touch_group` 写在循环里每帧注册 | 改到循环外，或每个新对象只注册一次 |
| 传了函数但双方没有消失 | 传函数后引擎不再自动删除 | 在函数里自己调用 `delete()` |
| 子弹消失后仍对它操作 | 变量还指向已删除的子弹 | 用 `if bullet:` 判断，或重新创建 |

---

## 6. 完整可运行示例

```python
hero = Sprite("玩家")
enemy = Sprite("敌人")
enemy.add_to_group("enemies")   # 敌人进组

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
        bullet.on_touch_group("enemies")    # 碰到敌人：子弹和敌人自动消失

    # 子弹飞出画面后清理
    if bullet and bullet.is_out_screen():
        bullet.delete()
        bullet = None
```
