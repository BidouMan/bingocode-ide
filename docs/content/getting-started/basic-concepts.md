# 核心概念

本章介绍 BingoCodeIDE 游戏开发的核心概念，帮助你理解游戏是如何运作的。

## 游戏循环

游戏的核心是一个不断重复的循环，叫做「游戏循环」。

```python
while True:
    # 每帧执行的代码
    # 处理输入
    # 更新游戏状态
    # 渲染画面
```

### 什么是"帧"？

游戏画面每秒刷新约 60 次，每次刷新叫做一帧。`while True` 循环每帧执行一次，所以游戏才能动起来。

### 游戏循环的结构

```python
while True:
    # 1. 处理输入
    if key_down("right"):
        hero.add_x(5)
    
    # 2. 更新状态
    # （引擎自动处理物理、碰撞等）
    
    # 3. 渲染画面
    # （引擎自动处理）
```

## 坐标系统

BingoCodeIDE 的坐标系以**地图**为准。默认地图是 640×480 像素的单屏地图（40×30 格、每格 16 像素）。

```
(0,480) ──────────────── (640,480)
  │                            │
  │                            │
  │         地图区域            │
  │        640 × 480           │
  │                            │
(0,0) ─────────────────── (640,0)
```

### 坐标说明

- **x 轴**：水平方向，地图左边是 0，右边是地图宽度
- **y 轴**：垂直方向，地图下边是 0，上边是地图高度（向上移动，y 变大）
- **原点**：地图左下角 (0, 0)
- **中心点**：单屏地图是 (320, 240)

> 地图比 640×480 大时，y 的范围会变成 `0 ~ 地图高度`，y=0 仍然是地图底部。

### 常用位置（默认 640×480 地图）

| 位置 | 坐标 |
|------|------|
| 左下角 | (0, 0) |
| 右下角 | (640, 0) |
| 左上角 | (0, 480) |
| 右上角 | (640, 480) |
| 画面中心 | (320, 240) |

## 精灵（Sprite）

精灵是游戏中的角色、道具、敌人等所有可移动的物体。

### 创建精灵

```python
hero = Sprite("洛克人")
```

- 括号里的名字必须和资源面板中添加的角色名字一致
- 创建后精灵会出现在默认地图中心 (320, 240)
- 精灵默认大小 100%，朝向右方 (0°)

### 精灵属性

| 属性 | 说明 | 示例 |
|------|------|------|
| `x` | 水平位置 (0~地图宽度) | `hero.x = 100` |
| `y` | 垂直位置 (0~地图高度，向上增大) | `hero.y = 200` |
| `scale` | 大小百分比 | `hero.scale = 200` |
| `angle` | 朝向角度 | `hero.angle = 90` |
| `layer` | 图层顺序 | `hero.layer = 10` |

跳跃前用 `hero.is_on_ground()` 判断角色是否站在地面上（详见「侦测」）。

### 角度系统

```
        90° (上)
          │
          │
180° (左) ─┼─ 0° (右)
          │
          │
        270° (下)
```

- 0° = 朝右
- 90° = 朝上
- 180° = 朝左
- 270° = 朝下

## 输入系统

游戏通过检测键盘和鼠标输入来响应玩家操作。

### 键盘输入

```python
# 持续按住检测（每帧都检测）
if key_down("space"):
    print("空格键被按住")

# 单次按下检测（只检测按下那一瞬间）
if key_pressed("space"):
    print("空格键刚刚被按下")

# 单次松开检测
if key_up("space"):
    print("空格键刚刚被松开")
```

### 常用按键名

| 按键 | 名称 |
|------|------|
| 空格 | `"space"` |
| 回车 | `"enter"` |
| 左方向键 | `"left"` |
| 右方向键 | `"right"` |
| 上方向键 | `"up"` |
| 下方向键 | `"down"` |
| A-Z | `"a"` ~ `"z"` |
| 数字 0-9 | `"0"` ~ `"9"` |

### 鼠标输入

```python
# 鼠标按下检测
if mouse_down():
    print("鼠标左键被按住")

if mouse_pressed():
    print("鼠标左键刚刚被点击")

# 鼠标位置
print(mouse.x, mouse.y)
```

## 碰撞检测

精灵之间可以检测是否发生碰撞。

### 基本碰撞检测

```python
hero = Sprite("玩家")
enemy = Sprite("敌人")

while True:
    # 检测是否碰到敌人
    if hero.is_touch(enemy):
        print("碰到敌人了！")
```

### 检测碰到画面边缘

```python
if hero.is_touch_edge():
    print("碰到画面边缘了！")
```

### 检测组碰撞

```python
# 把敌人加入组
enemy1.add_to_group("enemies")
enemy2.add_to_group("enemies")

# 检测子弹是否碰到组内任意成员
bullet = Sprite("子弹")
hit = bullet.is_touch_group("enemies")
if hit:
    print("打中了！")
    hit.delete()
    bullet.delete()
```

## 物理系统

引擎内置了简单的物理系统，包括重力和碰撞。

### 重力

精灵会自动受到重力影响。设置 `vy`（垂直速度）可以让精灵上升或下降（正数向上、负数向下）：

```python
# 向上跳
hero.vy = 10

# 向下落
hero.vy = -10
```

### 地面检测

```python
# 检测是否站在地面上
if hero.is_on_ground():
    print("在地面上，可以跳")
else:
    print("在空中")
```

### 跳跃原理

```python
while True:
    # 按空格跳
    if key_pressed("space") and hero.is_on_ground():
        hero.jump(10)  # 施加向上的力
    
    # 松手时停止跳跃（可选）
    if key_up("space"):
        hero.stop_jump()
```

## 广播系统

广播可以在不同精灵之间传递消息。

### 发送广播

```python
# 游戏开始时发送广播
broadcast("游戏开始")
```

### 接收广播

最简单的写法是每帧检查一次：

```python
while True:
    if enemy.receive("游戏开始"):
        enemy.show()
        print("收到游戏开始信号！")
```

广播发出后的下一帧返回一次 True，所以要写在 `while True` 里。

如果要做的事比较多，也可以写成一个函数，注册一次就行：

```python
def 收到游戏开始():
    enemy.show()
    print("收到游戏开始信号！")

on_receive("游戏开始", 收到游戏开始)
```

### 实际应用

```python
hero = Sprite("玩家")
enemy = Sprite("敌人")
enemy.hide()

while True:
    if key_pressed("1"):
        broadcast("游戏开始")

    if enemy.receive("游戏开始"):
        enemy.show()
```

## 下一步

了解了核心概念后，你可以：

- 前往 [API 参考](../api/sprite.md) 查看完整的 API 文档
- 尝试 [教学案例](../tutorials/platformer.md) 学习更复杂的游戏制作
- 探索 [编辑器指南](../editor/sprite-editor.md) 学习如何制作角色
