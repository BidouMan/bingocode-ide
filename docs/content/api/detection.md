# 侦测

侦测类 API 用于检测碰撞、输入、距离等信息。

## 键盘输入

### key_down — 按键是否被按住

```python
if key_down("space"):
    print("空格键被按住")
```

持续检测：只要按键被按住，每帧都返回 True。

| 参数 | 类型 | 说明 |
|------|------|------|
| `key` | 字符串 | 按键名称 |

常用按键名：

| 按键 | 名称 |
|------|------|
| 空格 | `"space"` |
| 回车 | `"enter"` |
| 左 | `"left"` |
| 右 | `"right"` |
| 上 | `"up"` |
| 下 | `"down"` |
| A-Z | `"a"` ~ `"z"` |

### key_pressed — 按键是否刚刚按下

```python
if key_pressed("space"):
    hero.jump(10)
```

单次检测：只在按下那一瞬间返回 True。适合做跳跃、射击等一次性操作。

### key_up — 按键是否刚刚松开

```python
if key_up("space"):
    hero.stop_jump()
```

单次检测：只在松开那一瞬间返回 True。

## 鼠标输入

### mouse_down — 鼠标是否被按住

```python
if mouse_down():
    print("鼠标左键被按住")
```

### mouse_pressed — 鼠标是否刚刚点击

```python
if mouse_pressed():
    print("鼠标左键刚刚被点击")
```

### mouse_up — 鼠标是否刚刚松开

```python
if mouse_up():
    print("鼠标左键刚刚松开")
```

单次检测：只在松开鼠标左键的那一瞬间返回 True。

### mouse.x / mouse.y / mouse.pos — 鼠标位置

```python
print(mouse.x)  # 鼠标 x 坐标 (0~640)
print(mouse.y)  # 鼠标 y 坐标 (0~480，画面下边为 0，向上增大)

# 一次性拿到两个坐标
x, y = mouse.pos

# 让角色看向鼠标
hero.look_at(mouse)
```

## 碰撞检测

### is_touch — 碰撞检测

```python
# 检测是否碰到另一个精灵
if hero.is_touch(enemy):
    print("碰到敌人了！")

# 检测是否碰到鼠标（按角色真实碰撞轮廓判定）
if hero.is_touch(mouse):
    print("鼠标碰到角色了！")

# 检测是否碰到带标签的地形（形状层标签或图块标签）
if hero.is_touch("水"):
    print("碰到水了！")
```

返回 True/False。

- 标签可以是**形状层**里给形状填的标签，也可以是**图块**的标签
- 形状层三种能力都能检测：`阻挡`、`感应`、`阻挡 + 感应` 都算「碰到」
- 贴着边界（差不到半个像素）也算碰到，不会因为碰撞求解留下的细小间隙漏判
- 角色使用真实碰撞轮廓（`.bsf` 的胶囊 / 多边形 / 旋转 / 缩放都会考虑），不是简单的外接矩形

| 参数 | 类型 | 说明 |
|------|------|------|
| `target` | 精灵/字符串/mouse | 另一个精灵、标签字符串或 mouse 对象 |

### is_blocked — 前方是否有实心地形

```python
if hero.is_blocked("right"):
    hero.say("右边是墙")

# 往前探 8 像素
if hero.is_blocked("down", 8):
    hero.say("前面要掉下去了")
```

朝一个方向检查前方是否有实心地形（形状层 `阻挡` / `阻挡 + 感应`、图像碰撞、实心图块），适合做俯视迷宫、方向探测。

- **感应区域不算阻挡**
- 「跳板」只有向下、并且从上方靠近时才算阻挡
- 不受角色当前速度和朝向影响，只看你给的方向

| 参数 | 类型 | 说明 |
|------|------|------|
| `direction` | 字符串/数字 | `"left"` / `"right"` / `"up"` / `"down"`，也接受 `左/右/上/下` 或角度数字（0 右、90 上、180 左、270 下） |
| `distance` | 数字（可选） | 往前探多远，默认 2 像素 |

### raycast / hero.raycast — 打一条射线

```python
# 从角色所在点出发（最常用）
hit = hero.raycast("right", 200)
if hit:
    print("前方", hit.distance, "像素有东西，标签：", hit.tag)
    print("命中点：", hit.x, hit.y)

# 沿角色当前朝向
hit = hero.raycast(hero.angle, 300)

# 从任意点出发（鼠标、标记、预测位置）
hit = raycast(mouse.x, mouse.y, "down", 50)
```

朝一个方向射出看不见的线，返回最近碰到的实心地形；没碰到返回 `None`。

- `hero.raycast(direction, distance=1000)`：起点是角色位置（和 `goto` / `look_at` 用的是同一个点）
- `raycast(x, y, direction, distance=1000)`：起点是任意用户坐标点

适合做瞄准、视线遮挡、落地预测、探测器。

| 参数 | 类型 | 说明 |
|------|------|------|
| `x` / `y` | 数字 | 仅全局版需要：起点（用户坐标：地图左下角为原点，y 向上） |
| `direction` | 字符串/数字 | 同 `is_blocked` 的方向写法 |
| `distance` | 数字（可选） | 射线长度，默认 1000 像素 |

命中结果可以读：

| 字段 | 说明 |
|------|------|
| `hit.distance` | 从起点到命中点的距离 |
| `hit.x` / `hit.y` / `hit.pos` | 命中点坐标（用户坐标） |
| `hit.normal` | 命中表面的朝向 `(x, y)`，可用于反弹 |
| `hit.tag` | 命中形状/图块的标签（没有则为空字符串） |
| `hit.collision_type` | 物理属性（墙体 / 跳板 / 图像 / 自定义） |
| `hit.source` | 来源类型：`shape` 形状层 / `image` 图像 / `tile` 图块 |

### is_touch_edge — 是否碰到地图边界

```python
if hero.is_touch_edge():
    print("碰到地图边界了！")
```

只要有一边碰到就返回 True。

### is_out_side — 是否完全在地图外

```python
if hero.is_out_side():
    print("角色完全在地图外面")
```

只有整个角色都在地图外才返回 True。

### is_touch_group — 组碰撞检测

```python
# 检测子弹是否碰到 "enemies" 组
hit = bullet.is_touch_group("enemies")
if hit:
    # hit 是被碰到的那个精灵
    hit.delete()
    bullet.delete()
```

碰到返回那个精灵，没碰到返回 None。

### is_on_ground — 是否站在地面上

```python
if hero.is_on_ground():
    print("脚底有碰撞地形，可以跳")
```

角色是否真正站在地面上（由物理落地的碰撞接触决定）：站着为 True，跳起来、下落中、从下方穿过跳板都为 False。
`jump()` 不会自己判断，跳跃前要用它检查，否则会变成空中二段跳。

### is_on_wall — 是否贴着墙

```python
if hero.is_on_wall():
    hero.say("贴墙了")
```

左右两侧是否正贴着实体地形。和 `is_on_ground()` 一样来自**本帧的物理接触**：只有正顶着墙的那一帧为 True，离开墙或只是站在旁边为 False。

### is_on_ceiling — 头顶是否撞到东西

```python
if hero.is_on_ceiling():
    hero.stop_jump()
    hero.say("头好疼")
```

头顶是否撞到实体地形（天花板、墙顶；开启「限制边界」时撞到地图上边界也算）。
跳跃撞头的那一帧为 True，撞头时引擎会把向上速度清零，所以可以直接用它停止跳跃。

## 距离和位置

### distance_to — 距离计算

```python
dist = hero.distance_to(enemy)
print(f"距离：{dist} 像素")

# 近距离攻击
if hero.distance_to(enemy) < 50:
    hero.attack()
```

返回到目标的像素距离。

## 碰撞回调

### on_touch_group — 碰到时自动执行

`on_touch_group` 对**同一个角色**只需注册一次（不是每帧调用），引擎会每帧自动帮你检测，不需要你在 `while True` 里自己判断。如果子弹是每次发射新建的，就在新建后给这个新子弹注册一次。

**最常见用法：只写组名，碰到后双方自动消失**

```python
# ① 先让敌人加入 "enemies" 组（不写这句，组是空的，永远不会触发）
enemy.add_to_group("enemies")

# ② 给子弹注册一次：以后碰到 enemies 组里的任何成员，
#     引擎自动删除「子弹自己」和「那个敌人」，不用你写 delete()
bullet.on_touch_group("enemies")
```

注意：`on_touch_group("enemies")` **不传第二个参数**时，引擎默认执行的就是：

```python
bullet.delete()   # 自己消失
enemy.delete()    # 碰到的那个敌人消失
```

**完整例子（可直接运行）**

```python
hero = Sprite("玩家")
enemy = Sprite("敌人")
enemy.add_to_group("enemies")   # 先让敌人进组

bullet = None

while True:
    if key_down("left"):
        hero.add_x(-5)
    if key_down("right"):
        hero.add_x(5)

    # 按 Z 发射子弹
    if key_pressed("z"):
        bullet = Sprite("子弹")
        bullet.goto(hero.x, hero.y)
        bullet.set_speed(10)
        bullet.on_touch_group("enemies")   # 注册：子弹碰到敌人 → 两者自动消失

    # 子弹飞出画面后清理
    if bullet and bullet.is_out_side():
        bullet.delete()
        bullet = None
```

对比一下：同样效果如果不用 `on_touch_group`，就得自己在 `while True` 里每帧写判断：

```python
if bullet and bullet.is_touch_group("enemies"):
    hit = bullet.is_touch_group("enemies")
    hit.delete()
    bullet.delete()
    bullet = None
```

**想自己决定碰到后做什么，就传一个函数**

函数会收到两个参数：`自己`、`碰到的角色`。传入函数后，引擎**不再自动删除**，一切由你的函数决定：

```python
def 子弹碰到敌人(子弹, 敌人):
    敌人.delete()
    子弹.delete()
    broadcast("得分+1")

bullet.on_touch_group("enemies", 子弹碰到敌人)
```

| 参数 | 类型 | 说明 |
|------|------|------|
| `group` | 字符串 | 组名，对方必须先用 `add_to_group("组名")` 加入 |
| `callback` | 函数（可选） | 碰到时执行，参数为 (自己, 碰到的精灵)；不写则默认双方自动消失 |

提示：函数参数也可以只写 1 个（只接收自己）或不写；同一个组重复注册会**覆盖上一次**，写在循环里也不会重复执行。

#### 和 is_touch_group 的区别

| | `is_touch_group("组名")` | `on_touch_group("组名")` |
|---|---|---|
| 谁来检测 | 你的 `while True` 里每帧主动调用 | 注册一次，引擎每帧自动检测 |
| 结果 | 返回碰到的角色（没碰到返回 `None`） | 自动处理（默认双方删除，或执行你传入的函数） |
| 适合场景 | 需要"碰到后按条件决定做什么"（拿金币、碰到敌人扣血） | 子弹/道具这类"碰到就自动处理、不用再管"的对象 |

### on_sensor_enter / on_sensor_exit — 感应区进出

在形状层里把形状设成「感应」或「阻挡 + 感应」并填上标签，角色进入 / 离开这块区域时就会自动执行你写的函数。注册一次即可（写在循环外面），引擎每帧自动检测。

```python
def 碰到水(who):
    who.say("好凉快")

def 离开水(who):
    who.say("上岸了")

hero.on_sensor_enter("水", 碰到水)
hero.on_sensor_exit("水", 离开水)
```

规则：

- 只对「感应」「阻挡 + 感应」形状生效；纯「阻挡」形状不会触发进出事件，请用 `hero.is_touch("标签")` 主动查询
- **回调函数参数不用全写**，引擎会按你写的个数自动传（第一个参数永远是进入/离开的那个角色）：
  - `def f():` 不接收信息
  - `def f(who):` 只拿角色（最常用）
  - `def f(who, tag):` 再拿一个标签名
- 同一个标签**从无到有**只触发一次进入，**从有到无**只触发一次离开；站在里面不会每帧重复触发
- 同一个标签的多个感应区域视为一个整体：从一个区域直接走到另一个区域，不会触发「离开 → 进入」
- 判定留了缓冲带（进入 0.5px、离开 1px）：贴着感应区边缘停住或轻微抖动时，不会一帧进入、下一帧又离开地反复触发
- 同一个标签重复注册会**覆盖上一次**（把注册语句写在 `while True` 里也只保留最后一条，不会重复执行、也不会越积越多）
- 回调里写错代码只会在控制台提示，不会让整局游戏退出

| 参数 | 类型 | 说明 |
|------|------|------|
| `tag` | 字符串 | 形状层感应形状上填的标签 |
| `callback` | 函数 | 进入 / 离开时执行；参数可写 0 / 1 / 2 个：(角色, 标签) |

### 和 is_touch 的区别

| | `hero.is_touch("水")` | `hero.on_sensor_enter("水", 函数)` |
|---|---|---|
| 谁来检测 | 你的 `while True` 里每帧主动调用 | 注册一次，引擎每帧自动检测 |
| 结果 | 返回 True / False | 只在"刚进入"那一帧执行一次函数 |
| 适合场景 | 需要随时知道"现在在不在里面" | 进入后只处理一次（播放音效、扣血、传送） |

## 完整示例

```python
hero = Sprite("玩家")
enemy = Sprite("敌人")
enemy.add_to_group("enemies")

bullet = None

while True:
    # 玩家移动
    if key_down("left"):
        hero.add_x(-5)
    if key_down("right"):
        hero.add_x(5)
    
    # 射击（按 Z 键）
    if key_pressed("z"):
        bullet = Sprite("子弹")
        bullet.goto(hero.x, hero.y)
        bullet.set_speed(10)
    
    # 子弹碰边消失
    if bullet and bullet.is_out_side():
        bullet.delete()
        bullet = None
    
    # 碰撞检测
    if bullet and bullet.is_touch_group("enemies"):
        hit = bullet.is_touch_group("enemies")
        hit.delete()
        bullet.delete()
        bullet = None
```
