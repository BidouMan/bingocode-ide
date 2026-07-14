# 地图

地图类 API 用于加载和管理游戏地图。

## 加载地图

### load_map — 加载地图

```python
load_map("我的地图")
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | 字符串 | 地图名称（和资源面板中一致） |

地图需要先在资源面板中添加好，然后写上名字即可。

```python
# 加载地图
load_map("关卡1")

# 加载后可以创建角色在地图上活动
hero = Sprite("玩家")
```

## 摄像机

### follow — 镜头跟随

```python
follow(hero)
```

让摄像机（画面的"眼睛"）跟着指定角色移动。用了之后画面就会跟着角色走。

```python
# 加载大地图
load_map("大型关卡")

# 创建玩家
hero = Sprite("玩家")

# 让镜头跟着玩家
follow(hero)

# 现在移动玩家时，画面会自动滚动
while True:
    if key_down("right"):
        hero.move(5)
```

## 地图使用示例

### 基本地图游戏

```python
# 加载地图
load_map("关卡1")

# 创建玩家
hero = Sprite("玩家")
hero.goto(100, 300)  # 放在地图起始位置

# 镜头跟随
follow(hero)

while True:
    # 左右移动
    if key_down("left"):
        hero.add_x(-5)
    if key_down("right"):
        hero.add_x(5)
    
    # 跳跃
    if key_pressed("space") and hero.on_ground:
        hero.jump(12)
    
    if key_up("space"):
        hero.cut_jump()
```

### 带敌人的地图游戏

```python
load_map("关卡1")

hero = Sprite("玩家")
hero.goto(100, 300)
follow(hero)

# 生成敌人
enemy_timer = Timer(3)

while True:
    # 玩家移动
    if key_down("left"):
        hero.add_x(-5)
    if key_down("right"):
        hero.add_x(5)
    if key_pressed("space") and hero.on_ground:
        hero.jump(12)
    if key_up("space"):
        hero.cut_jump()
    
    # 每 3 秒生成敌人
    if enemy_timer.is_timeout():
        enemy = Sprite("敌人")
        enemy.goto_rand()
        enemy.add_to_group("enemies")
    
    # 碰撞检测
    if hero.touch_group("enemies"):
        hit = hero.touch_group("enemies")
        hit.delete()
        shake(8, 0.3)
```

## 注意事项

- 地图需要先在资源面板中添加
- 地图名必须和资源面板中显示的名字完全一致
- 加载地图后，之前的精灵不会消失
- `follow` 只能跟随一个角色，多次调用会覆盖
