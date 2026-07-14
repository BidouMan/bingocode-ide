# 常用编程模式

本章介绍 BingoCodeIDE 游戏开发中常用的编程模式。

## 计数器模式

用于计分、计时等场景。

```python
score = 0

while True:
    # 收集金币时加分
    if hero.touch_group("coins"):
        hit = hero.touch_group("coins")
        hit.delete()
        score += 10
    
    # 显示分数
    draw_text(10, 10, "得分：", score)
```

## 状态机模式

用于管理游戏状态（菜单、游戏中、暂停等）。

```python
game_state = "menu"  # menu, playing, paused, gameover

while True:
    if game_state == "menu":
        # 菜单逻辑
        if key_pressed("space"):
            game_state = "playing"
            hero.show()
    
    elif game_state == "playing":
        # 游戏逻辑
        if key_pressed("p"):
            game_state = "paused"
    
    elif game_state == "paused":
        # 暂停逻辑
        if key_pressed("p"):
            game_state = "playing"
    
    elif game_state == "gameover":
        # 游戏结束逻辑
        if key_pressed("space"):
            # 重新开始
            game_state = "playing"
```

## 生成器模式

用于定期生成敌人、道具等。

```python
enemy_timer = Timer(2)  # 每2秒生成一个敌人
coin_timer = Timer(3)   # 每3秒生成一个金币

while True:
    # 生成敌人
    if enemy_timer.is_timeout():
        enemy = Sprite("敌人")
        enemy.goto_rand()
        enemy.set_speed(2)
        enemy.add_to_group("enemies")
    
    # 生成金币
    if coin_timer.is_timeout():
        coin = Sprite("金币")
        coin.goto_rand()
        coin.add_to_group("coins")
```

## 边界检测模式

用于防止角色跑出画面。

```python
while True:
    # 水平边界
    if hero.x < 0:
        hero.x = 0
    if hero.x > 640:
        hero.x = 640
    
    # 垂直边界
    if hero.y < 0:
        hero.y = 0
    if hero.y > 480:
        hero.y = 480
```

## 碰撞处理模式

用于处理角色碰撞。

```python
while True:
    # 碰撞检测
    hit = hero.touch_group("enemies")
    if hit:
        hit.delete()
        shake(8, 0.3)
        hero.say("被击中！", 1)
```

## 输入缓冲模式

用于处理输入延迟。

```python
input_buffer = []

while True:
    # 收集输入
    if key_pressed("space"):
        input_buffer.append("jump")
    
    # 处理输入
    if "jump" in input_buffer and hero.on_ground:
        hero.jump(10)
        input_buffer.remove("jump")
    
    # 清空过期输入
    if len(input_buffer) > 5:
        input_buffer.pop(0)
```

## 动画状态模式

用于管理角色动画。

```python
current_animation = "idle"

while True:
    # 确定动画状态
    if key_down("left") or key_down("right"):
        current_animation = "walk"
    elif not hero.on_ground:
        current_animation = "jump"
    else:
        current_animation = "idle"
    
    # 播放动画
    hero.play(current_animation)
```

## 跟随模式

用于让物体跟随另一个物体。

```python
# 简单跟随
def follow_target(target, speed):
    if hero.x < target.x:
        hero.add_x(speed)
    elif hero.x > target.x:
        hero.add_x(-speed)
    
    if hero.y < target.y:
        hero.add_y(speed)
    elif hero.y > target.y:
        hero.add_y(-speed)

while True:
    follow_target(enemy, 3)
```

## 弹幕模式

用于射击游戏的子弹模式。

```python
shoot_timer = Timer(0.2)  # 每0.2秒发射一颗子弹

while True:
    # 玩家移动
    if key_down("left"):
        hero.add_x(-5)
    if key_down("right"):
        hero.add_x(5)
    
    # 自动射击
    if shoot_timer.is_timeout():
        bullet = Sprite("子弹")
        bullet.goto(hero.x, hero.y)
        bullet.set_speed(10)
        bullet.add_to_group("bullets")
    
    # 移除飞出屏幕的子弹
    for bullet in _GROUPS.get("bullets", []):
        if bullet.is_out_side():
            bullet.delete()
```

## 对象池模式

用于复用对象，减少创建销毁开销。

```python
bullets = []

def get_bullet():
    # 尝试复用已删除的子弹
    for b in bullets:
        if not b.visible:
            b.show()
            return b
    # 创建新子弹
    b = Sprite("子弹")
    bullets.append(b)
    return b

while True:
    if key_pressed("z"):
        bullet = get_bullet()
        bullet.goto(hero.x, hero.y)
        bullet.set_speed(10)
```

## 下一步

- 查看 [教学案例](../tutorials/platformer.md) 学习完整游戏制作
- 探索 [API 参考](../api/sprite.md) 了解更多功能
