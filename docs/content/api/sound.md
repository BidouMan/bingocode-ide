# 声音

声音类 API 用于播放和控制音效、背景音乐。

## 播放音效

### play_sound — 播放音效

```python
play_sound("jump")           # 播放一次
play_sound("bgm", True)      # 循环播放
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `name` | 字符串 | - | 音效文件名（不带后缀） |
| `loop` | 布尔 | False | 是否循环播放 |

### 音效文件位置

音效文件放在 `assets/sounds/` 目录下，支持 `.wav`、`.mp3`、`.ogg` 格式。

写文件名时不需要带后缀，引擎会自动搜索：

```python
# 假设文件是 assets/sounds/jump.wav
play_sound("jump")

# 假设文件是 assets/sounds/bgm.mp3
play_sound("bgm", True)
```

### 停止音效

```python
stop_sound("jump")    # 停止指定音效
stop_sound()          # 停止所有音效
```

## 使用场景

### 背景音乐

```python
# 游戏开始时播放背景音乐
play_sound("bgm", True)
```

### 动作音效

```python
# 跳跃时
if key_pressed("space") and hero.on_ground:
    hero.jump(10)
    play_sound("jump")

# 射击时
if key_pressed("z"):
    play_sound("shoot")
    # ... 创建子弹

# 碰撞时
if hero.is_touch(enemy):
    play_sound("hit")
    shake(5, 0.3)
```

### 游戏结束

```python
if hero.is_touch(enemy):
    play_sound("gameover")
    stop_sound("bgm")  # 停止背景音乐
    stop()  # 结束游戏
```

## 完整示例

```python
# 带音效的简单游戏
hero = Sprite("玩家")

# 播放背景音乐
play_sound("bgm", True)

while True:
    # 移动
    if key_down("left"):
        hero.add_x(-5)
    if key_down("right"):
        hero.add_x(5)
    
    # 跳跃（带音效）
    if key_pressed("space") and hero.on_ground:
        hero.jump(10)
        play_sound("jump")
    
    if key_up("space"):
        hero.cut_jump()
    
    # 边界限制
    if hero.x < 0:
        hero.x = 0
    if hero.x > 640:
        hero.x = 640
```
