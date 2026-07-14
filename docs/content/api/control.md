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
hit = bullet.touch_group("enemies")

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

### receive — 接收广播

```python
# 注册广播接收器（要在发送广播之前注册）
receive("游戏开始", lambda: print("收到！"))

# 也可以用普通函数
def on_game_start():
    enemy.show()
    hero.goto(320, 400)

receive("游戏开始", on_game_start)
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
receive("玩家死亡", lambda: show_game_over())
```

## 完整示例

```python
# 简单的计分游戏
hero = Sprite("玩家")
score = 0

# 分数显示
receive("得分+1", lambda: update_score())

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
    
    if key_pressed("space") and hero.on_ground:
        hero.jump(10)
    
    if key_up("space"):
        hero.cut_jump()
```
