# 外观

外观类 API 用于控制精灵的显示、隐藏、大小、动画等。

## 显示和隐藏

### show — 显示

```python
hero.show()
```

让角色显示出来。

### hide — 隐藏

```python
hero.hide()
```

把角色藏起来。藏起来不代表删除了，还可以再 `show` 出来。

```python
# 隐藏后再显示
hero.hide()
wait(2)  # 等 2 秒
hero.show()
```

## 说话气泡

### say — 说话

```python
hero.say("你好！")        # 永久显示
hero.say("得分+1", 2)    # 2 秒后消失
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `text` | 字符串 | - | 要说的话 |
| `seconds` | 数字 | 0 | 显示时间，0 = 永久 |

```python
# 角色对话
hero.say("欢迎来到我的游戏！")
wait(3)
hero.say("准备好冒险了吗？")
```

## 大小控制

### set_scale — 设置大小

```python
hero.set_scale(150)  # 变成 150% 大小
hero.set_scale(50)   # 变成 50% 大小
```

### add_scale — 增减大小

```python
hero.add_scale(20)   # 变大 20%
hero.add_scale(-20)  # 变小 20%
```

在当前大小基础上增减。

```python
# 吃到道具变大
if hero.is_touch(power_up):
    hero.add_scale(20)
    power_up.delete()

# 被攻击变小
if hero.is_touch(enemy):
    hero.add_scale(-10)
```

## 旋转模式

### set_rotation_mode — 旋转方式

```python
hero.set_rotation_mode("all")        # 自由旋转（默认）
hero.set_rotation_mode("left_right") # 只左右翻转
hero.set_rotation_mode("none")       # 不旋转
```

| 模式 | 说明 |
|------|------|
| `"all"` | 任意旋转（默认） |
| `"left_right"` | 只左右翻转，不旋转图片 |
| `"none"` | 完全不旋转 |

```python
# 平台游戏角色通常只左右翻转
hero.set_rotation_mode("left_right")
```

## 动画播放

### play — 播放动画

```python
hero.play("walk")            # 播放走路动画
hero.play("attack", 0.2)     # 0.2 秒过渡到攻击动画
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` | 字符串 | - | 动画名称 |
| `transition` | 数字 | 0.1 | 过渡时间（秒） |

需要角色资源里提前做好动画。

```python
# 根据状态播放动画
if key_down("left") or key_down("right"):
    hero.play("walk")
else:
    hero.play("idle")

if key_pressed("z"):
    hero.play("attack")
```

## 完整示例

```python
# 角色外观控制
hero = Sprite("玩家")
hero.goto(320, 240)
hero.set_rotation_mode("left_right")  # 只左右翻转

while True:
    # 移动
    if key_down("left"):
        hero.add_x(-5)
        hero.set_angle(180)
        hero.play("walk")
    elif key_down("right"):
        hero.add_x(5)
        hero.set_angle(0)
        hero.play("walk")
    else:
        hero.play("idle")
    
    # 跳跃
    if key_pressed("space") and hero.on_ground:
        hero.jump(10)
        hero.play("jump")
    
    # 吃道具变大
    if hero.touch_group("powerups"):
        hit = hero.touch_group("powerups")
        hit.delete()
        hero.add_scale(20)
        hero.say("变大了！", 1)
```
