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
- 要写在 `while True` **外面**，否则会重复注册

## 两种写法怎么选

| | `if enemy.receive("开始"):` | `on_receive("开始", 函数)` |
|---|---|---|
| 要写函数吗 | 不用 | 要 |
| 写在哪 | `while True` 里 | 循环外 |
| 适合 | 简单的一两句话 | 逻辑较多、多处复用 |

## 碰撞与感应事件

除了广播，碰撞和感应区也可以「注册一次、自动执行」。

### on_touch_group — 碰到组时自动执行

```python
enemy.add_to_group("enemies")

# 默认：碰到后双方自动消失
bullet.on_touch_group("enemies")

# 自定义：函数参数为 (自己, 碰到的角色)，也可以只写 1 个（只接收自己）或不写
def 子弹碰到敌人(子弹, 敌人):
    敌人.delete()
    子弹.delete()

bullet.on_touch_group("enemies", 子弹碰到敌人)
```

同一个组重复注册会覆盖上一次，写在 `while True` 里也不会重复执行。

### on_sensor_enter / on_sensor_exit — 进出感应区

```python
def 碰到水(who):
    who.say("好凉快")

def 离开水(who):
    who.say("上岸了")

hero.on_sensor_enter("水", 碰到水)
hero.on_sensor_exit("水", 离开水)
```

- 只对形状层里「感应」「阻挡 + 感应」并填了标签的形状生效
- 回调参数可以不写、写 1 个（进入/离开的角色）或写 2 个（角色, 标签）
- 只在状态变化时各触发一次；边缘留了缓冲，站在边上轻微抖动不会反复触发
- 同一个标签重复注册会覆盖上一次

更完整的规则（同一标签多区域算一体、和 `is_touch` 的区别）见 [侦测 → 碰撞回调](detection.md)。

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
