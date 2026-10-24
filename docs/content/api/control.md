# 控制

控制类 API 用于管理游戏流程、分组、广播等。

## 游戏循环

### while True — 主循环

```python
while True:
    # 游戏逻辑写在这里
    # 每帧执行一次
    if key_down("right"):
        hero.add_x(5)
```

这是游戏的核心。引擎每帧自动执行循环体内的代码，游戏就是这样"跑"起来的。

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

结束游戏，画面停住，退出 run 循环。用于"游戏结束"或"通关"。

## 分组管理

### add_to_group — 加入组

```python
enemy1.add_to_group("enemies")
enemy2.add_to_group("enemies")
bullet.add_to_group("bullets")
```

把精灵归到某个组里，方便批量管理。

### 组的用途

```python
# 批量碰撞检测
hit = bullet.is_touch_group("enemies")

# 批量操作（需要自己遍历）
# 引擎没有提供遍历组的方法，需要自己管理
```

## 广播系统

广播可以在不同精灵之间传递消息，类似于学校广播站喊话。

### broadcast — 发送广播

```python
broadcast("游戏开始")
broadcast("得分+1")
broadcast("关卡通过")
```

发送一条广播消息，所有"听到"这条消息的接收器都会执行对应代码。

### on_receive — 接收广播

```python
# 用普通函数注册（推荐）
def on_game_start():
    enemy.show()
    hero.goto(320, 400)

on_receive("游戏开始", on_game_start)

# 一行代码也可以用 lambda
on_receive("得分+1", lambda: print("得分！"))
```

- 回调函数**不需要参数**，也不用写 return
- 必须在 `broadcast` **之前**注册
- 注册要写在 `while True` **外面**：放进循环会每帧重复注册，一次广播执行很多次
- 回调里修改外面的计数器可以直接用 `global 变量名`
- 回调出错只会打印提示，不会中断整个游戏

**常见错误**：`monster.on_receive("start")` —— `on_receive` 是**全局函数**，不是角色的方法，也不返回 True/False，不能写在 `if` 里。它只负责"注册"：

```python
# 正确：把「收到广播后要做什么」写成函数，注册一次
def 怪物收到开始():
    怪物.show()
    print("收到广播")

on_receive("start", 怪物收到开始)

while True:
    if key_down("1"):
        player.broadcast("start")
```

**重要**：接收器必须在发送广播之前注册好。

### 广播的使用场景

```python
# 场景 1：游戏状态切换
broadcast("游戏开始")    # 通知所有角色游戏开始了
broadcast("游戏暂停")    # 通知暂停
broadcast("游戏结束")    # 通知结束

# 场景 2：事件通知
broadcast("得分+1")      # 通知分数变化
broadcast("获得道具")    # 通知获得道具

# 场景 3：角色间通信
# 玩家死亡时通知 UI
on_receive("玩家死亡", lambda: show_game_over())
```

## 完整示例

```python
# 简单的计分游戏
hero = Sprite("玩家")
score = 0

# 分数显示
on_receive("得分+1", lambda: update_score())

def update_score():
    global score
    score += 1
    draw_text(10, 10, "得分：", score)

# 游戏开始
broadcast("得分+1")  # 初始化显示

while True:
    if key_down("left"):
        hero.add_x(-5)
    if key_down("right"):
        hero.add_x(5)
    
    if key_pressed("space") and hero.is_on_ground():
        hero.jump(10)
    
    if key_up("space"):
        hero.stop_jump()
```
