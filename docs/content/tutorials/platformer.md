# 平台跳跃游戏

本教程将带你制作一个类似超级马里奥的平台跳跃游戏。

## 目标

- 角色可以在平台上跳跃
- 有敌人和碰撞
- 可以收集金币
- 有计分系统

<!-- screenshot: tutorials/platformer-preview.png -->
<!-- alt: 平台跳跃游戏效果 -->
<!-- description: 显示一个角色在平台上跳跃，有金币和敌人 -->

## 准备工作

1. 创建新项目
2. 添加角色：玩家、敌人、金币
3. 创建或导入一个平台跳跃地图

## 步骤 1：基础移动

首先实现角色的基础移动和跳跃：

```python
# 创建角色
hero = Sprite("玩家")
hero.goto(100, 300)  # 起始位置
hero.set_rotation_mode("left_right")  # 只左右翻转

# 加载地图
load_map("平台关卡")
follow(hero)  # 镜头跟随

while True:
    # 左右移动
    if key_down("left"):
        hero.add_x(-5)
        hero.set_angle(180)
    if key_down("right"):
        hero.add_x(5)
        hero.set_angle(0)
    
    # 跳跃
    if key_pressed("space") and hero.on_ground:
        hero.jump(12)
    
    # 截断跳跃（按住跳得高，轻点跳得矮）
    if key_up("space"):
        hero.cut_jump()
```

## 步骤 2：添加敌人

```python
# 生成敌人
enemy_timer = Timer(3)  # 每 3 秒生成一个敌人

while True:
    # ... 移动代码 ...
    
    # 生成敌人
    if enemy_timer.is_timeout():
        enemy = Sprite("敌人")
        enemy.goto_rand()
        enemy.set_speed(2)
        enemy.add_to_group("enemies")
    
    # 教人碰边反弹
    for enemy in _GROUPS.get("enemies", []):
        enemy.edge_bounce()
```

## 步骤 3：添加金币

```python
# 生成金币
coin_timer = Timer(2)

while True:
    # ... 其他代码 ...
    
    # 生成金币
    if coin_timer.is_timeout():
        coin = Sprite("金币")
        coin.goto_rand()
        coin.add_to_group("coins")
    
    # 收集金币
    hit = hero.touch_group("coins")
    if hit:
        hit.delete()
        score += 10
        play_sound("coin")
        draw_text(10, 10, "得分：", score)
```

## 步骤 4：碰撞检测

```python
# 碰撞检测
if hero.touch_group("enemies"):
    hit = hero.touch_group("enemies")
    hit.delete()
    hero.say("被击中！", 1)
    shake(8, 0.3)
```

## 完整代码

```python
# 平台跳跃游戏
hero = Sprite("玩家")
hero.goto(100, 300)
hero.set_rotation_mode("left_right")

load_map("平台关卡")
follow(hero)

score = 0
enemy_timer = Timer(3)
coin_timer = Timer(2)

while True:
    # 左右移动
    if key_down("left"):
        hero.add_x(-5)
        hero.set_angle(180)
    if key_down("right"):
        hero.add_x(5)
        hero.set_angle(0)
    
    # 跳跃
    if key_pressed("space") and hero.on_ground:
        hero.jump(12)
        play_sound("jump")
    
    if key_up("space"):
        hero.cut_jump()
    
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
    
    # 收集金币
    hit = hero.touch_group("coins")
    if hit:
        hit.delete()
        score += 10
        play_sound("coin")
    
    # 碰撞检测
    if hero.touch_group("enemies"):
        hit = hero.touch_group("enemies")
        hit.delete()
        shake(8, 0.3)
    
    # 显示分数
    draw_text(10, 10, "得分：", score)
```

## 进阶功能

### 双段跳

```python
jump_count = 0

while True:
    # 跳跃
    if key_pressed("space"):
        if hero.on_ground:
            hero.jump(12)
            jump_count = 1
        elif jump_count < 2:
            hero.jump(10)
            jump_count += 1
    
    # 落地重置
    if hero.on_ground:
        jump_count = 0
```

### 移动平台

```python
platform = Sprite("平台")
platform.set_speed(2)

while True:
    # 平台碰边反弹
    if platform.is_touch_edge():
        platform.set_angle(platform.angle + 180)
```

## 下一步

- 尝试 [射击游戏](shooting.md) 教程
- 学习 [地图编辑器](../editor/map-editor.md) 创建自定义地图
- 查看 [API 参考](../api/sprite.md) 了解更多功能
