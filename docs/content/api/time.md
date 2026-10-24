# 时间

**每隔几秒做一件事 → 用 `time_passed`；需要暂停、重新计时、只做一次 → 用 `Timer`。**

## time_passed — 每隔几秒做一次

```python
while True:
    if time_passed(1):
        print("每 1 秒执行一次")
```

数字填几，就是每隔几秒做一次。两个地方各算各的，互不影响。

## Timer — 计时器

```python
clock = Timer(2)        # 每 2 秒，一直重复
once = Timer(2, False)  # 只做一次
```

创建后自动开始计时。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `seconds` | 数字 | — | 间隔几秒 |
| `loop` | 布尔 | True | True 一直重复，False 只触发一次 |

## is_timeout — 时间到了吗

```python
if clock.is_timeout():
    print("每 2 秒执行一次")
```

到点返回 True，然后重新计时。

## start / stop — 暂停和重新计时

```python
clock.stop()    # 暂停计时
clock.start()   # 重新开始（从 0 算起）
```

`Timer(秒数, False)` 只触发一次，触发后会自动停止。

## 完整示例

```python
hero = Sprite("玩家")
enemy_timer = Timer(1.5)
score_timer = Timer(5)
score = 0

while True:
    if key_down("left"):
        hero.add_x(-5)
    if key_down("right"):
        hero.add_x(5)

    # 每 1.5 秒生成一个敌人
    if enemy_timer.is_timeout():
        enemy = Sprite("敌人")
        enemy.goto_rand()
        enemy.add_to_group("enemies")

    # 每 5 秒加 10 分
    if score_timer.is_timeout():
        score += 10
        show_text(10, 10, "得分：", score)

    # 每隔 1 秒打一次招呼
    if time_passed(1):
        print("你好")
```
