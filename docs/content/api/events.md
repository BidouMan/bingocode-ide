# 事件

事件就是「发生了某件事」。广播用来在角色之间传递消息：一个角色喊话，其他角色听到后各自行动。

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
