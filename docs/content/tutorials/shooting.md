# 射击游戏

本教程将带你制作一个类似太空侵略者的射击游戏。

## 目标

- 玩家可以左右移动和射击
- 敌人从上方出现并移动
- 子弹击中敌人得分
- 敌人碰到玩家游戏结束

## 准备工作

1. 创建新项目
2. 添加角色：玩家、子弹、敌人
3. 添加音效：射击、爆炸

## 步骤 1：基础移动

```python
# 创建角色
hero = Sprite("玩家")
hero.goto(320, 420)  # 底部中央

while True:
    # 左右移动
    if key_down("left"):
        hero.add_x(-5)
    if key_down("right"):
        hero.add_x(5)
    
    # 边界限制
    if hero.x < 30:
        hero.x = 30
    if hero.x > 610:
        hero.x = 610
```

## 步骤 2：射击

```python
shoot_timer = Timer(0.3)  # 射击间隔

while True:
    # ... 移动代码 ...
    
    # 射击
    if shoot_timer.is_timeout() and key_down("z"):
        bullet = Sprite("子弹")
        bullet.goto(hero.x, hero.y - 20)
        bullet.set_speed(10)
        play_sound("shoot")
```

## 步骤 3：敌人生成

```python
enemy_timer = Timer(1.5)  # 每1.5秒生成敌人

while True:
    # ... 其他代码 ...
    
    # 生成敌人
    if enemy_timer.is_timeout():
        enemy = Sprite("敌人")
        enemy.goto_rand()
        enemy.y = 0  # 从顶部出现
        enemy.set_speed(2)
        enemy.add_to_group("enemies")
```

## 步骤 4：碰撞检测

```python
while True:
    # ... 其他代码 ...
    
    # 子弹击中敌人
    for bullet in _GROUPS.get("bullets", []):
        hit = bullet.touch_group("enemies")
        if hit:
            bullet.delete()
            hit.delete()
            score += 100
            play_sound("explosion")
            shake(5, 0.2)
    
    # 敌人碰到玩家
    if hero.touch_group("enemies"):
        play_sound("gameover")
        stop()
```

## 完整代码

```python
# 射击游戏
hero = Sprite("玩家")
hero.goto(320, 420)

score = 0
shoot_timer = Timer(0.3)
enemy_timer = Timer(1.5)

while True:
    # 玩家移动
    if key_down("left"):
        hero.add_x(-5)
    if key_down("right"):
        hero.add_x(5)
    
    # 边界限制
    if hero.x < 30:
        hero.x = 30
    if hero.x > 610:
        hero.x = 610
    
    # 射击
    if shoot_timer.is_timeout() and key_down("z"):
        bullet = Sprite("子弹")
        bullet.goto(hero.x, hero.y - 20)
        bullet.set_speed(10)
        bullet.add_to_group("bullets")
        play_sound("shoot")
    
    # 生成敌人
    if enemy_timer.is_timeout():
        enemy = Sprite("敌人")
        enemy.goto_rand()
        enemy.y = 0
        enemy.set_speed(2)
        enemy.add_to_group("enemies")
    
    # 子弹击中敌人
    for bullet in _GROUPS.get("bullets", []):
        if bullet.is_out_side():
            bullet.delete()
            continue
        hit = bullet.touch_group("enemies")
        if hit:
            bullet.delete()
            hit.delete()
            score += 100
            play_sound("explosion")
            shake(5, 0.2)
    
    # 敌人碰到玩家
    if hero.touch_group("enemies"):
        play_sound("gameover")
        stop()
    
    # 显示分数
    draw_text(10, 10, "得分：", score)
```

## 进阶功能

### 多种敌人

```python
# 不同类型的敌人
def spawn_enemy():
    type = random_int(1, 3)
    enemy = Sprite(f"敌人{type}")
    enemy.goto_rand()
    enemy.y = 0
    
    if type == 1:
        enemy.set_speed(2)
    elif type == 2:
        enemy.set_speed(3)
    else:
        enemy.set_speed(1.5)
    
    enemy.add_to_group("enemies")
```

### 道具系统

```python
powerup_timer = Timer(10)  # 每10秒生成道具

while True:
    # 生成道具
    if powerup_timer.is_timeout():
        powerup = Sprite("道具")
        powerup.goto_rand()
        powerup.add_to_group("powerups")
    
    # 拾取道具
    hit = hero.touch_group("powerups")
    if hit:
        hit.delete()
        # 获得双倍射击
        shoot_interval = 0.15
```

## 下一步

- 尝试 [益智游戏](puzzle.md) 教程
- 学习 [声音 API](../api/sound.md) 添加更多音效
- 查看 [工具函数](../api/tools.md) 了解屏幕震动等效果
