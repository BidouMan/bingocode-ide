# 地图

地图类 API 用于加载和管理游戏地图。

## 加载地图

### load_map — 加载地图

```python
map = load_map("我的地图")
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | 字符串 | 地图名称（和资源面板中一致） |

地图需要先在资源面板中添加好，然后写上名字即可。返回值是地图对象，后面可以用它取标记。

```python
# 加载地图
map = load_map("关卡1")

# 加载后可以创建角色在地图上活动
hero = Sprite("玩家")
```

## 标记

地图编辑器里可以在地图上放「标记」（带名字的小图钉），代码里能直接取到摆好的坐标。

### map.get_marker — 按名字取标记

```python
map = load_map("地图1")

pos = map.get_marker("出生点")   # 返回标记，可以直接当坐标用
player = Sprite("小猫")
player.goto(pos)                 # 直接把角色放到标记位置

print(pos.x, pos.y)              # 读取坐标：左下角原点，y 向上
x, y = pos                       # 也可以拆包
```

不写名字时默认取名为「标记」的那个；找不到时返回 `None`。

### map.get_markers — 按类型取一组标记

标记可以在属性面板里设置类型（出生点 / 敌人 / 道具 / 触发器 / 镜头 / 存档点）。

```python
# 所有「敌人」类型的标记，逐个放到标记位置
for m in map.get_markers("敌人"):
    enemy = Sprite("史莱姆")
    enemy.goto(m)

# 不传类型：拿到全部标记
for m in map.get_markers():
    print(m.name, m.x, m.y)
```

没有匹配的标记时返回空列表，`for` 循环自然不执行。

> 也可以直接调用全局的 `get_marker("出生点")` / `get_markers("敌人")`，效果相同。

## 地形查询

### map.is_solid — 这个点是不是实心

```python
map = load_map("我的地图")

if map.is_solid(x, y):
    hero.say("这里有地面")
```

检查用户坐标点是否被实心地形占据（形状层「阻挡 / 阻挡 + 感应」、图像碰撞、实心图块）。感应区域不算；跳板算实心。
坐标和角色的 `x / y` 一致：地图左下角为原点，y 向上。

## 摄像机

### camera_follow — 镜头跟随

```python
camera_camera_follow(hero)
```

让摄像机（画面的"眼睛"）跟着指定角色移动。用了之后画面就会跟着角色走。

```python
# 加载大地图
load_map("大型关卡")

# 创建玩家
hero = Sprite("玩家")

# 让镜头跟着玩家
camera_follow(hero)

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
camera_follow(hero)

while True:
    # 左右移动
    if key_down("left"):
        hero.add_x(-5)
    if key_down("right"):
        hero.add_x(5)
    
    # 跳跃
    if key_pressed("space") and hero.is_on_ground():
        hero.jump(12)
    
    if key_up("space"):
        hero.stop_jump()
```

### 带敌人的地图游戏

```python
load_map("关卡1")

hero = Sprite("玩家")
hero.goto(100, 300)
camera_follow(hero)

# 生成敌人
enemy_timer = Timer(3)

while True:
    # 玩家移动
    if key_down("left"):
        hero.add_x(-5)
    if key_down("right"):
        hero.add_x(5)
    if key_pressed("space") and hero.is_on_ground():
        hero.jump(12)
    if key_up("space"):
        hero.stop_jump()
    
    # 每 3 秒生成敌人
    if enemy_timer.is_timeout():
        enemy = Sprite("敌人")
        enemy.goto_rand()
        enemy.add_to_group("enemies")
    
    # 碰撞检测
    if hero.is_touch_group("enemies"):
        hit = hero.is_touch_group("enemies")
        hit.delete()
        shake(8, 0.3)
```

## 注意事项

- 地图需要先在资源面板中添加
- 地图名必须和资源面板中显示的名字完全一致
- 加载地图后，之前的精灵不会消失
- `camera_follow` 只能跟随一个角色，多次调用会覆盖
