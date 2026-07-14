# 益智游戏

本教程将带你制作一个简单的推箱子或记忆翻牌类益智游戏。

## 目标

- 实现基本的益智游戏逻辑
- 使用地图编辑器创建关卡
- 添加计时和计分系统

## 方案一：记忆翻牌

### 游戏规则

- 翻开两张牌
- 如果相同则消除
- 如果不同则翻回去
- 全部消除则过关

### 步骤 1：创建牌

```python
# 创建4x4的牌阵
cards = []
card_values = []

for row in range(4):
    for col in range(4):
        card = Sprite("卡牌")
        card.goto(160 + col * 80, 80 + row * 80)
        cards.append(card)
        
        # 随机分配值（1-8，每对两个）
        if len(card_values) < 8:
            card_values.append(random_int(1, 8))
            card_values.append(random_int(1, 8))

# 打乱顺序
# (简化版，实际需要更复杂的打乱算法)
```

### 步骤 2：翻牌逻辑

```python
flipped = []
matched = 0

while True:
    if mouse_pressed():
        # 检测点击了哪张牌
        for i, card in enumerate(cards):
            if card.is_touch(mouse) and card not in matched:
                card.say(str(card_values[i]))
                flipped.append(i)
                
                if len(flipped) == 2:
                    # 检查是否匹配
                    if card_values[flipped[0]] == card_values[flipped[1]]:
                        matched.extend(flipped)
                        flipped = []
                    else:
                        # 不匹配，翻回去
                        wait(0.5)
                        cards[flipped[0]].say("")
                        cards[flipped[1]].say("")
                        flipped = []
```

## 方案二：推箱子

### 游戏规则

- 玩家推动箱子到目标位置
- 所有箱子到位则过关

### 步骤 1：使用地图

1. 在地图编辑器中创建推箱子地图
2. 标记墙壁、地板、目标点

```python
load_map("推箱子关卡1")
hero = Sprite("玩家")
```

### 步骤 2：推动逻辑

```python
# 简化的推动逻辑
def try_push(direction):
    # 计算目标位置
    target_x = hero.x + direction[0] * 32
    target_y = hero.y + direction[1] * 32
    
    # 检查是否有箱子
    for box in _GROUPS.get("boxes", []):
        if hero.distance_to(box) < 40:
            # 尝试推动箱子
            new_box_x = box.x + direction[0] * 32
            new_box_y = box.y + direction[1] * 32
            
            # 检查目标位置是否可通行
            if is_walkable(new_box_x, new_box_y):
                box.goto(new_box_x, new_box_y)
                return True
    return False

while True:
    if key_pressed("right"):
        if not try_push((1, 0)):
            hero.add_x(32)
    if key_pressed("left"):
        if not try_push((-1, 0)):
            hero.add_x(-32)
    if key_pressed("down"):
        if not try_push((0, 1)):
            hero.add_y(32)
    if key_pressed("up"):
        if not try_push((0, -1)):
            hero.add_y(-32)
```

## 计时系统

```python
game_time = 60  # 60秒限时
clock = Timer(1)

while True:
    if clock.is_timeout():
        game_time -= 1
        draw_text(300, 10, "时间：", game_time)
        
        if game_time <= 0:
            stop()
```

## 下一步

- 尝试其他益智游戏类型
- 学习 [地图编辑器](../editor/map-editor.md) 创建复杂关卡
- 查看 [控制 API](../api/control.md) 了解更多游戏控制功能
