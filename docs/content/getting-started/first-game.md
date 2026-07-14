# 第一个游戏

本教程将带你从零开始创建一个简单的角色移动游戏。完成后，你将掌握 BingoCodeIDE 的基本使用方法。

## 目标

创建一个可以控制角色上下左右移动的小游戏。

<!-- screenshot: getting-started/first-game-preview.png -->
<!-- alt: 第一个游戏运行效果 -->
<!-- description: 一个角色在画面中央，可以通过键盘控制移动 -->

## 步骤 1：创建新项目

1. 点击菜单栏的「项目」
2. 选择「新建项目」
3. 输入项目名称，如 `我的第一个游戏`
4. 选择保存位置

<!-- screenshot: getting-started/new-project.png -->
<!-- alt: 新建项目对话框 -->
<!-- description: 显示项目名称输入框和保存位置选择 -->

## 步骤 2：添加角色

1. 在左侧面板点击「角色」标签
2. 点击「+」按钮或从内置库中选择一个角色
3. 选择一个你喜欢的角色（如小猫、小人等）

<!-- screenshot: getting-started/add-sprite.png -->
<!-- alt: 添加角色界面 -->
<!-- description: 显示角色库和添加按钮 -->

## 步骤 3：编写移动代码

1. 点击菜单栏的「代码」按钮，切换到代码编辑器
2. 输入以下代码：

```python
# 创建角色
hero = Sprite("你的角色名")  # 替换成你添加的角色名

# 游戏主循环
while True:
    # 左右移动
    if key_down("left"):
        hero.add_x(-5)
    if key_down("right"):
        hero.add_x(5)
    
    # 上下移动
    if key_down("up"):
        hero.add_y(-5)
    if key_down("down"):
        hero.add_y(5)
```

**注意**：将 `"你的角色名"` 替换成你在步骤 2 中添加的角色名称。

## 步骤 4：运行游戏

1. 点击工具栏的绿色「运行」按钮
2. 游戏会在右侧预览窗口中运行
3. 使用键盘方向键控制角色移动

<!-- screenshot: getting-started/run-game.png -->
<!-- alt: 运行游戏界面 -->
<!-- description: 显示代码编辑器和游戏预览窗口 -->

## 代码解释

让我们逐行理解这段代码：

```python
hero = Sprite("角色名")
```
这行代码创建了一个角色（精灵），并把它赋值给变量 `hero`。括号里的名字要和你添加的角色资源名字一致。

```python
while True:
```
这是游戏的主循环。`while True` 会不断重复执行缩进里面的代码，游戏就是这样"跑"起来的。

```python
if key_down("left"):
    hero.add_x(-5)
```
`key_down("left")` 检查左方向键是否被按住。如果按住了，就把角色的 x 坐标减 5（向左移动）。

## 进阶：添加跳跃

让我们给游戏添加跳跃功能：

```python
hero = Sprite("你的角色名")

while True:
    # 左右移动
    if key_down("left"):
        hero.add_x(-5)
    if key_down("right"):
        hero.add_x(5)
    
    # 跳跃（按空格键）
    if key_pressed("space") and hero.on_ground:
        hero.jump(12)
```

**关键点**：
- `key_pressed("space")` 只在按下那一瞬间返回 True（适合做跳跃）
- `hero.on_ground` 检查角色是否在地面上
- 只有在地面上才能跳，防止空中无限跳

## 进阶：添加边界限制

防止角色跑到画面外面：

```python
hero = Sprite("你的角色名")

while True:
    # 左右移动
    if key_down("left"):
        hero.add_x(-5)
    if key_down("right"):
        hero.add_x(5)
    
    # 上下移动
    if key_down("up"):
        hero.add_y(-5)
    if key_down("down"):
        hero.add_y(5)
    
    # 边界限制
    if hero.x < 0:
        hero.x = 0
    if hero.x > 640:
        hero.x = 640
    if hero.y < 0:
        hero.y = 0
    if hero.y > 480:
        hero.y = 480
```

## 完整示例

```python
# 第一个游戏 - 角色移动
hero = Sprite("你的角色名")

# 设置初始位置
hero.goto(320, 240)

while True:
    # 左右移动
    if key_down("left"):
        hero.add_x(-5)
    if key_down("right"):
        hero.add_x(5)
    
    # 跳跃
    if key_pressed("space") and hero.on_ground:
        hero.jump(12)
    
    # 边界限制
    if hero.x < 0:
        hero.x = 0
    if hero.x > 640:
        hero.x = 640
    if hero.y < 0:
        hero.y = 0
    if hero.y > 480:
        hero.y = 480
```

## 常见问题

### 角色不显示
- 检查角色名是否拼写正确
- 确认已经添加了角色资源

### 按键没反应
- 确保游戏窗口获得焦点（点击一下预览窗口）
- 检查按键名称是否正确（`left`, `right`, `up`, `down`, `space`）

### 角色移动卡顿
- 这是正常现象，因为每次移动是固定的 5 像素
- 后续可以学习更平滑的移动方式

## 下一步

恭喜你完成了第一个游戏！接下来学习 [核心概念](basic-concepts.md)，了解游戏开发的基础知识。
