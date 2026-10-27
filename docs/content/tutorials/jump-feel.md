# 跳跃手感：郊狼时间与跳跃缓冲

做平台跳跃游戏时，有两类「明明按了跳却没跳」的情况，几乎每个玩家都会遇到：

- 已经走到平台边缘、脚刚离开地面才按下跳跃键 → 角色直接掉下去
- 还没落地就提前按下跳跃键，落地那一下其实已经松开了 → 落地后站着不动

这两种都不是玩家的错，而是**判定窗口卡得太死**。成熟的商业游戏普遍用两个小技巧来救：

| 技巧 | 解决的问题 | 一句话解释 |
| --- | --- | --- |
| 跳跃缓冲（jump buffer） | 提前按跳 | 落地前按下的那一下，落地瞬间补上 |
| 郊狼时间（coyote time） | 延迟按跳 | 离开平台后还有极短一段时间可以起跳 |

引擎**没有内置**这两个功能。这不是缺功能：它们需要在多帧之间保存状态，而「跨帧记住一件事」恰好是编程里很重要的基本功。本教程用引擎现有的函数手写实现，两段代码都不到十行。

## 先分清两个按键信号

写之前必须先分清 `key_down` 和 `key_pressed`，这两个用错，后面全错。

| 函数 | 含义 | 按住不放时 |
| --- | --- | --- |
| `key_down("space")` | 键**当前**是否被按住 | 每帧都返回 `True` |
| `key_pressed("space")` | 键是否**刚被按下** | 只有按下那一帧返回 `True` |
| `key_up("space")` | 键是否**刚被松开** | 只有松开那一帧返回 `True` |

口诀：**想让它每帧都发生，用 `key_down`；只该发生一次，用 `key_pressed`。**

所以移动用 `key_down`（按住一直走），跳跃用 `key_pressed`（按一次跳一次）。这是本教程所有代码的前提。

## 跳跃缓冲：把提前按下的跳存起来

思路很简单：按下跳跃键时不要马上去跳，而是先记一个「还有几帧有效」的倒计时；真正落地的那一帧，如果倒计时还没走完，就替他跳出去。

```python
buffer = 0   # 还剩几帧「刚按过跳」

while True:
    # 按下跳跃键：记下这次按键，最多保留 6 帧
    if key_pressed("space"):
        buffer = 6

    # 落地了，而且之前按过跳：补上这一跳
    if buffer > 0 and hero.is_on_ground():
        hero.jump(12)
        buffer = 0

    # 没落地就一直消耗，过期作废
    elif buffer > 0:
        buffer -= 1
```

流程是这样的：

1. 玩家在空中提前按下跳跃键 → `buffer` 变成 6，但 `is_on_ground()` 是 `False`，所以这一帧不跳，只把「想跳」这个意图留着。
2. 每一帧 `buffer` 减一。
3. 只要在 6 帧内落地，`is_on_ground()` 变 `True` 的那一帧，`buffer` 还大于 0 → 立刻 `jump()`。
4. 如果 6 帧内没落地，`buffer` 归零，这次按键作废，等玩家再按一次。

三个容易踩的坑：

- **必须用 `key_pressed`**。换成 `key_down` 的话，按住不放会每帧都把 `buffer` 重新填满，落地就无限连跳。
- **`buffer` 要在跳完之后清零**，否则一次按键会被兑换成两次起跳。
- **`is_on_ground()` 不能省**。`jump()` 本身不判断地面，少了它，空中按一下就会当场起跳，缓冲也就没意义了。

## 郊狼时间：离开平台后还留一点机会

思路和缓冲相反：站在地面上时，把「还能跳」的倒计时补满；一旦离地，就开始消耗；只要在倒计时走完之前按下跳跃键，就仍然允许起跳。

```python
coyote = 0   # 离地后还剩几帧可以起跳

while True:
    if hero.is_on_ground():
        coyote = 6          # 站在地上：一直补满
    elif coyote > 0:
        coyote -= 1         # 离地了：每帧消耗一格

    if key_pressed("space") and coyote > 0:
        hero.jump(12)
        coyote = 0          # 用掉了，避免一次按键跳两次
```

关键在于判断条件从 `is_on_ground()` 换成了 `coyote > 0`：角色明明已经离开平台，但 `coyote` 还没走完，所以这一跳依然成立。

同样的三个坑：

- 用 `key_pressed`，不要用 `key_down`。
- 起跳后把 `coyote` 清零，否则同一个按键会被反复兑换。
- 这个判断只对 `jump()` 有效（见下面「为什么不能配 smart_jump」）。

## 两个一起用

实际项目里通常两个都要，再加上大小跳（松手提前落下），完整写法如下：

```python
BUFFER_FRAMES = 6     # 提前按跳的宽限
COYOTE_FRAMES = 6     # 离地后的宽限

hero = Sprite("玩家")
hero.goto(100, 300)
load_map("平台关卡")
camera_follow(hero)

buffer = 0
coyote = 0

while True:
    # 左右移动
    if key_down("left"):
        hero.add_x(-5)
        hero.set_angle(180)
    if key_down("right"):
        hero.add_x(5)
        hero.set_angle(0)

    # 更新郊狼倒计时
    if hero.is_on_ground():
        coyote = COYOTE_FRAMES
    elif coyote > 0:
        coyote -= 1

    # 更新缓冲倒计时
    if key_pressed("space"):
        buffer = BUFFER_FRAMES

    # 两个宽限都在，才允许起跳
    if buffer > 0 and coyote > 0:
        hero.jump(12)
        buffer = 0
        coyote = 0
    elif buffer > 0:
        buffer -= 1

    # 松手提前落下（大小跳）
    if key_up("space"):
        hero.stop_jump()
```

## 和两段/多段跳配合

郊狼时间和跳跃计数是天然兼容的：把「第一次起跳的资格」从 `is_on_ground()` 换成 `coyote > 0` 就行，空中跳的次数仍由计数器负责。

```python
jump_count = 0
coyote = 0

while True:
    if hero.is_on_ground():
        jump_count = 0
        coyote = 6
    elif coyote > 0:
        coyote -= 1

    if key_pressed("space"):
        if jump_count == 0 and coyote > 0:
            hero.jump(12)      # 第一跳：地面或刚离开平台
            jump_count = 1
            coyote = 0
        elif jump_count == 1:
            hero.jump(10)      # 第二跳：空中
            jump_count = 2
```

注意这里走路掉下平台时 `jump_count` 仍会被重置成 0，所以掉下去之后用掉的那一跳算第一跳，空中跳还在——这是符合玩家预期的。

## 宽限开多少帧

引擎的循环每秒大约执行 60 次（每次约 1/60 秒），所以帧数可以直接换算成时间：

| 帧数 | 约等于 | 手感 |
| --- | --- | --- |
| 4 | 0.07 秒 | 很严格，几乎等于没开 |
| 6 | 0.1 秒 | 推荐起点，大部分人感觉不到它存在 |
| 8 | 0.13 秒 | 明显宽容，适合手机触屏 |
| 12 | 0.2 秒 | 太宽容，会出现「明明离地很远了还能跳」的错觉 |

不要为了「保险」把两个值开大。这两个功能的价值在于**让玩家感觉不到它存在**，一旦能感觉到，就变成新的困惑。

## 调参时怎么看效果

用 `show_text` 把计数值打在屏幕上，边跑边看，比猜更靠谱：

```python
while True:
    # ...前面的倒计时逻辑...

    show_text(10, 10, "buffer: ", buffer)
    show_text(10, 30, "coyote: ", coyote)
```

## 为什么不能配 smart_jump

这两套写法都只对 `jump()` 有效。`smart_jump()` 内部会把「是不是站在地面上」再判断一次，外部怎么计数都影响不到它，所以：

| 写法 | 郊狼 / 缓冲 | 说明 |
| --- | --- | --- |
| `key_pressed` + `is_on_ground()` + `jump()` | 可以手写 | 本教程的做法 |
| `key_down` + `smart_jump()` | 不行 | 引擎内部判断地面，外部计数无效 |

代价是：想要这两个宽限，就得从「一行搞定的 `smart_jump`」升级到自己写 `jump()` + `stop_jump()`。等你需要精确控制起跳时机（头顶撞到天花板立刻落下、敌人 AI 的固定跳跃节奏）时，反正也必须走这条路。

## 常见错误速查

| 现象 | 原因 |
| --- | --- |
| 按住跳跃键一直连跳 | 用了 `key_down` 去跳，换成 `key_pressed` |
| 按一次跳两下 | 跳完忘记把 `buffer` / `coyote` 清零 |
| 空中按跳立刻起跳 | 少了 `is_on_ground()` 或 `coyote > 0` 的判断 |
| 角色一直往下掉、落地检测不生效 | 地图属性里没开启「重力」 |
| 写法和教程一样但没效果 | 用的是 `smart_jump()`，它内部判断地面，外部计数无效 |
