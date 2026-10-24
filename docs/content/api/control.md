# 控制

控制类 API 用于管理游戏流程：让游戏跑起来、暂停、继续、结束。

## 游戏循环

### while True — 主循环

```python
while True:
    # 游戏逻辑写在这里
    # 每帧执行一次
    if key_down("right"):
        hero.add_x(5)
```

这是游戏的核心。引擎每帧自动执行循环体内的代码，游戏就是这样「跑」起来的。

## 游戏控制

### pause — 暂停游戏

```python
pause()
```

暂停后所有角色停止移动，但程序还在运行。可以随时 `resume`。

### resume — 继续游戏

```python
resume()
```

让暂停的游戏重新运行。

### is_paused — 是否暂停

```python
if is_paused():
    print("游戏已暂停")
```

返回 True/False。

### stop — 结束游戏

```python
stop()
```

结束游戏，画面停住，退出 run 循环。用于「游戏结束」或「通关」。

## 完整示例

```python
hero = Sprite("玩家")
game_over = False

while True:
    if key_down("left"):
        hero.add_x(-5)
    if key_down("right"):
        hero.add_x(5)

    if key_pressed("space") and hero.is_on_ground():
        hero.jump()

    if game_over:
        stop()
```
