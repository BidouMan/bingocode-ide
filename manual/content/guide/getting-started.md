---
title: 快速入门：让角色动起来
description: 从认识主界面开始，写下第一段游戏循环，理解坐标、键盘输入和跳跃，做出一个可以控制的小游戏。
---

## 先看一遍完整流程

在 BingoCodeIDE 里做游戏，顺序通常是：**添加角色 → 写代码 → 点击运行 → 在画布上试玩**。下面的截图是游戏模式的主界面，后面所有操作都从这里开始。

<figure class="shot" data-file="ide-overview.png" data-caption="游戏模式主界面：资源面板、代码编辑器、画布和运行按钮" data-desc="建议截取完整的游戏模式界面，包含左侧资源面板、中间代码区、右侧画布和顶部运行按钮；不要加标注。"></figure>

| 区域 | 作用 |
|------|------|
| 左侧资源面板 | 添加角色、地图和音效，双击资源可以进入编辑器 |
| 中间代码编辑器 | 写 Python 代码，支持自动补全和错误提示 |
| 右侧画布 | 运行游戏后在这里试玩，键盘和鼠标事件只作用于画布 |
| 顶部运行按钮 | 启动或停止程序；运行后会变成停止样式 |

> **注意：** 如果代码里用到了 `Sprite`、`key_down` 等游戏函数，程序会交给引擎运行；普通 Python 练习则走代码模式，两者互不影响。

## 程序只有两部分

一个最小可运行的游戏，结构非常固定：

```python
hero = Sprite("玩家")

while True:
    # 这里的代码每帧执行一次
    if key_down("left"):
        hero.add_x(-4)
```

| 部分 | 写在哪里 | 作用 |
|------|----------|------|
| 准备阶段 | `while True` 外面 | 创建角色、地图、计时器；只执行一次 |
| 游戏循环 | `while True` 里面 | 每帧检查输入、移动角色、判断碰撞；重复执行 |

引擎会把顶层的 `while True` 转换成一个逐帧运行的循环，所以**不要自己写 `time.sleep()` 来控制速度**。引擎已经按约 60 帧/秒运行，每一帧都会执行一次循环体。

## 坐标系：左下角是原点，y 向上

这是最容易写错的地方。BingoCodeIDE 对外的坐标原点是**地图左下角**，y 轴**向上**为正，和数学课本里的平面直角坐标系一致。地图比一屏大时，y=0 仍然是地图底部。

<figure class="diagram">
<svg viewBox="0 0 680 480" role="img" aria-label="BingoCodeIDE 坐标系示意图">
  <rect x="60" y="30" width="560" height="420" class="dg-stage" rx="8" />
  <line x1="60" y1="135" x2="620" y2="135" class="dg-grid" />
  <line x1="60" y1="240" x2="620" y2="240" class="dg-grid" />
  <line x1="60" y1="345" x2="620" y2="345" class="dg-grid" />
  <line x1="200" y1="30" x2="200" y2="450" class="dg-grid" />
  <line x1="340" y1="30" x2="340" y2="450" class="dg-grid" />
  <line x1="480" y1="30" x2="480" y2="450" class="dg-grid" />

  <line x1="60" y1="450" x2="640" y2="450" class="dg-axis" />
  <line x1="60" y1="450" x2="60" y2="18" class="dg-axis" />
  <path d="M640 450l-9-4v8Z" class="dg-accent" />
  <path d="M60 18l-4 9h8Z" class="dg-accent" />

  <text x="646" y="455" class="dg-label">x</text>
  <text x="48" y="18" class="dg-label">y</text>
  <text x="70" y="468" class="dg-label">(0, 0)</text>
  <text x="540" y="468" class="dg-label">(640, 0)</text>
  <text x="22" y="42" class="dg-label">(0, 480)</text>
  <text x="548" y="44" class="dg-label">(640, 480)</text>
  <text x="314" y="236" class="dg-label">中心 (320, 240)</text>

  <circle cx="270" cy="187.5" r="13" class="dg-accent" fill-opacity="0.2" />
  <circle cx="270" cy="187.5" r="4" class="dg-accent" />
  <text x="291" y="181" class="dg-strong">角色 (240, 300)</text>
  <text x="292" y="199" class="dg-label">x 向右，y 向上</text>

  <text x="104" y="410" class="dg-strong">640 × 480 舞台</text>
  <text x="104" y="429" class="dg-label">有地图时，范围变成地图的像素尺寸</text>
</svg>
<figcaption>坐标轴只用于理解，实际画面里不会显示网格和数字。</figcaption>
</figure>

| 位置 | 坐标 |
|------|------|
| 左下角 | `(0, 0)` |
| 右下角 | `(640, 0)` |
| 左上角 | `(0, 480)` |
| 右上角 | `(640, 480)` |
| 画面中心 | `(320, 240)` |

- `hero.x = 100`：把角色放到距离左边 100 像素的位置。
- `hero.add_y(5)`：向上移动 5 像素；想向下就写 `hero.add_y(-5)`。
- 角色创建后默认在 `(320, 240)`，也就是画面中心。
- 使用地图后，可移动范围会变成地图的 `宽度 × 图块尺寸` 和 `高度 × 图块尺寸`，不一定还是 640 × 480。

## 让角色响应键盘

方向键和空格键是游戏里最常用的输入。按键名统一用小写字符串：

| 按键 | 写法 |
|------|------|
| 空格 | `"space"` |
| 回车 | `"enter"` |
| 上 / 下 / 左 / 右 | `"up"` / `"down"` / `"left"` / `"right"` |
| 字母 A 到 Z | `"a"` 到 `"z"` |
| 数字 0 到 9 | `"0"` 到 `"9"` |
| Esc | `"escape"` |
| Shift / Ctrl | `"shift"` / `"ctrl"` |

三个检测函数只差在“什么时候返回 True”：

| 函数 | 什么时候是 True | 适合做 |
|------|----------------|--------|
| `key_down("left")` | 按住期间，每一帧都是 True | 持续移动、按住加速 |
| `key_pressed("space")` | 刚按下的那一帧 True，只出现一次 | 开火、切换、单次动作 |
| `key_up("space")` | 刚松开的那一帧 True，只出现一次 | 松手停止跳跃、结束蓄力 |

## 完整示例：左右移动 + 大小跳

下面这段代码已经包含了移动、朝向和跳跃，可以直接复制到客户端里试：

```python
hero = Sprite("玩家")
hero.goto(320, 120)
hero.set_rotation_mode("left_right")

while True:
    # 按住左方向键：向左移动，并让角色朝左
    if key_down("left"):
        hero.add_x(-4)
        hero.set_angle(180)

    # 按住右方向键：向右移动，并让角色朝右
    if key_down("right"):
        hero.add_x(4)
        hero.set_angle(0)

    # 按住空格：起跳并保持上升；松手后自动落下
    if key_down("space"):
        hero.smart_jump(12)
```

> **重要：** `smart_jump()` 需要写在地图开启「重力」的项目里。没有地图或没有开启重力时，角色不会自然下落，跳跃也就看不到效果。

逐行理解：

| 代码 | 说明 |
|------|------|
| `Sprite("玩家")` | 创建角色；括号里的名字必须和资源面板里的角色名完全一致 |
| `goto(320, 120)` | 把角色放到 `x=320, y=120` 的位置 |
| `set_rotation_mode("left_right")` | 只做左右翻转，不整体旋转，适合平台跳跃角色 |
| `while True:` | 游戏主循环，每帧执行一次 |
| `key_down("left")` | 左方向键是否按住；按住期间持续为 True |
| `add_x(-4)` | 向左移动 4 像素；引擎会处理撞墙修正 |
| `set_angle(180)` | 朝向改为左；`0` 是右，`90` 是上，`270` 是下 |
| `smart_jump(12)` | 按下起跳、按住跳得高、松手提前落下；必须每帧调用 |

## 三个常见错误

> **错误 1：角色名对不上。** 代码写 `Sprite("玩家")`，资源面板里却叫 `玩家1`，控制台会提示角色不存在，程序会停止。名字必须完全一致，包括空格和标点。

> **错误 2：把 y 的方向写反。** `add_y(5)` 是**向上**，`add_y(-5)` 是**向下**。如果按上键角色却往下走，检查这里。

> **错误 3：跳跃前不判断地面。** `jump()` 不会自动判断角色是否站在地上，在空中调用就会变成二段跳。平台游戏里要写 `key_pressed("space") and hero.is_on_ground()`；如果想让松手提前落下，直接用 `smart_jump()` 更简单。

> **不要写 `time.sleep()`。** 游戏循环本身已经按帧运行；在循环里睡眠会让整个游戏卡住，输入也无法及时响应。

## 下一步

<div class="legend-grid">
  <article class="path-card" data-href="{{PREFIX}}api/sprite.html">
    <span class="path-num">继续查 API</span>
    <div class="card-title">精灵 Sprite</div>
    <p>角色对象有哪些属性和方法，创建、删除、动画、分组一次看全。</p>
    <span class="card-link">查看精灵 API →</span>
  </article>
  <article class="path-card" data-href="{{PREFIX}}api/movement.html">
    <span class="path-num">继续查 API</span>
    <div class="card-title">运动</div>
    <p>移动、朝向、持续速度、跳跃和边界反弹的完整用法。</p>
    <span class="card-link">查看运动 API →</span>
  </article>
</div>
