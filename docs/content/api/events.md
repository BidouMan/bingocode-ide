# 事件

事件就是「发生了某件事」。广播用来在角色之间传递消息：一个角色喊话，其他角色听到后各自行动。碰撞和感应区也能在发生时自动执行你写的函数。

## receive — 收到广播了吗

```python
while True:
    if enemy.receive("开始"):
        enemy.show()
        print("收到广播")
```

- 广播发出后的**下一帧**返回一次 True，然后自动变回 False
- 要写在 `while True` 里，每帧检查
- 广播是全局的，`enemy.receive` 和 `receive` 结果一样，`.receive` 只是写法方便

## broadcast — 发送广播

```python
broadcast("开始")
player.broadcast("开始")   # 和上一行完全一样
```

发送一条消息。所有正在检查这条消息的地方，下一帧都会收到。

## on_receive — 收到时自动执行（进阶）

不想每帧检查，可以把要做的事写成一个函数，注册一次：

```python
def 怪物出现():
    monster.show()

on_receive("开始", 怪物出现)
```

注册后引擎会自动执行，不需要放进循环。

- 函数不需要参数，也不用写 return
- 要写在发送广播**之前**
- 要写在 `while True` **外面**；同一个事件重复注册会覆盖上一次（写进循环也不会重复执行、不会越积越多）

## 两种写法怎么选

| | `if enemy.receive("开始"):` | `on_receive("开始", 函数)` |
|---|---|---|
| 要写函数吗 | 不用 | 要 |
| 写在哪 | `while True` 里 | 循环外 |
| 适合 | 简单的一两句话 | 逻辑较多、多处复用 |

## 碰撞与感应事件

除了广播，碰撞和感应区也可以「注册一次、自动执行」。

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

提示：函数参数也可以只写 1 个（只接收自己）或不写；同一个组重复注册会**覆盖上一次**，写在循环里也不会重复执行。

#### 和 is_touch_group 的区别

| | `is_touch_group("组名")` | `on_touch_group("组名")` |
|---|---|---|
| 谁来检测 | 你的 `while True` 里每帧主动调用 | 注册一次，引擎每帧自动检测 |
| 结果 | 返回碰到的角色（没碰到返回 `None`） | 自动处理（默认双方删除，或执行你传入的函数） |
| 适合场景 | 需要"碰到后按条件决定做什么"（拿金币、碰到敌人扣血） | 子弹/道具这类"碰到就自动处理、不用再管"的对象 |

### on_sensor_enter / on_sensor_exit — 感应区进出

在形状层里把形状设成「感应」或「阻挡 + 感应」并填上标签，角色进入 / 离开这块区域时就会自动执行你写的函数。注册一次即可（写在循环外面），引擎每帧自动检测。

```python
def 碰到水(who):
    who.say("好凉快")

def 离开水(who):
    who.say("上岸了")

hero.on_sensor_enter("水", 碰到水)
hero.on_sensor_exit("水", 离开水)
```

规则：

- 只对「感应」「阻挡 + 感应」形状生效；纯「阻挡」形状不会触发进出事件，请用 `hero.is_touch("标签")` 主动查询
- **回调函数参数不用全写**，引擎会按你写的个数自动传（第一个参数永远是进入/离开的那个角色）：
  - `def f():` 不接收信息
  - `def f(who):` 只拿角色（最常用）
  - `def f(who, tag):` 再拿一个标签名
- 同一个标签**从无到有**只触发一次进入，**从有到无**只触发一次离开；站在里面不会每帧重复触发
- 同一个标签的多个感应区域视为一个整体：从一个区域直接走到另一个区域，不会触发「离开 → 进入」
- 判定留了缓冲带（进入 0.5px、离开 1px）：贴着感应区边缘停住或轻微抖动时，不会一帧进入、下一帧又离开地反复触发
- 同一个标签重复注册会**覆盖上一次**（把注册语句写在 `while True` 里也只保留最后一条，不会重复执行、也不会越积越多）
- 回调里写错代码只会在控制台提示，不会让整局游戏退出

| 参数 | 类型 | 说明 |
|------|------|------|
| `tag` | 字符串 | 形状层感应形状上填的标签 |
| `callback` | 函数 | 进入 / 离开时执行；参数可写 0 / 1 / 2 个：(角色, 标签) |

### 和 is_touch 的区别

| | `hero.is_touch("水")` | `hero.on_sensor_enter("水", 函数)` |
|---|---|---|
| 谁来检测 | 你的 `while True` 里每帧主动调用 | 注册一次，引擎每帧自动检测 |
| 结果 | 返回 True / False | 只在"刚进入"那一帧执行一次函数 |
| 适合场景 | 需要随时知道"现在在不在里面" | 进入后只处理一次（播放音效、扣血、传送） |

## 完整示例

```python
player = Sprite("玩家")
monster = Sprite("怪物")
monster.hide()

def 怪物出现():
    monster.show()
    print("怪物出现了")

on_receive("开始", 怪物出现)

while True:
    if key_pressed("1"):
        player.broadcast("开始")

    if player.receive("开始"):
        print("玩家也收到了广播")
```
