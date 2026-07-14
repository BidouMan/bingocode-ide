# 常见问题

## 安装问题

### Q: macOS 提示"无法打开，因为无法验证开发者"

这是 macOS 的安全机制导致的。解决方法：

1. 打开「系统设置 → 隐私与安全性」
2. 在「安全性」部分找到 BingoCodeIDE
3. 点击「仍然打开」

或者在终端执行：
```bash
xattr -cr /Applications/BingoCodeIDE.app
```

### Q: Windows 提示"Windows 已保护你的电脑"

1. 点击「更多信息」
2. 点击「仍要运行」

### Q: 应用启动后黑屏或闪退

1. 确保系统已更新到最新版本
2. 尝试以管理员身份运行
3. 检查是否有杀毒软件拦截
4. 重新下载安装最新版本

## 运行错误

### Q: "NameError: name 'xxx' is not defined"

这个错误表示你使用了一个未定义的变量或函数。

```python
# 错误示例
print(name)  # name 未定义

# 正确做法
name = "小明"
print(name)
```

### Q: "Sprite not found" 或角色不显示

1. 检查角色名是否拼写正确（区分大小写）
2. 确认已经添加了角色资源
3. 检查角色资源文件是否完整

```python
# 错误：名字拼写错误
hero = Sprite("洛克人")  # 如果资源名是"洛克人"

# 正确：名字必须完全匹配
hero = Sprite("洛克人")
```

### Q: "IndentationError" 缩进错误

Python 用缩进来表示代码块，必须用 4 个空格：

```python
# 错误：缩进不一致
if key_down("right"):
hero.add_x(5)    # 缺少缩进

# 正确：4 个空格缩进
if key_down("right"):
    hero.add_x(5)
```

### Q: 游戏运行但角色不动

1. 确保代码在 `while True:` 循环里
2. 检查按键名称是否正确
3. 确认游戏窗口获得焦点（点击一下预览窗口）

```python
# 错误：没有循环
if key_down("right"):
    hero.add_x(5)

# 正确：需要在循环里
while True:
    if key_down("right"):
        hero.add_x(5)
```

### Q: jump() 不起作用

`jump()` 只是施加向上的力，需要自己判断是否在地面：

```python
# 错误：没有判断地面
if key_pressed("space"):
    hero.jump(10)  # 可以无限跳

# 正确：判断地面
if key_pressed("space") and hero.on_ground:
    hero.jump(10)
```

## 编辑器问题

### Q: 如何添加自己的角色？

1. 准备好角色图片（PNG 格式）
2. 在资源面板点击「角色」标签
3. 点击「+」按钮
4. 选择你的图片文件
5. 给角色命名

### Q: 如何制作动画？

1. 在角色编辑器中打开角色
2. 添加多个帧（每个帧是一张图片）
3. 设置每帧的显示时间
4. 保存动画

### Q: 地图编辑器怎么用？

1. 先导入瓦片集（tileset）
2. 选择瓦片在地图上绘制
3. 设置碰撞区域
4. 保存地图

## 性能问题

### Q: 游戏卡顿怎么办？

1. 减少同屏精灵数量
2. 使用 `hide()` 隐藏不在画面内的精灵
3. 避免每帧创建大量新精灵
4. 使用 `show_collision()` 检查碰撞范围是否合理

### Q: 如何显示帧率？

```python
show_fps(True)  # 显示帧率
show_fps(False) # 隐藏帧率
```

帧率 60 表示流畅，低于 30 可能会感觉卡顿。

## Python 相关

### Q: 不能使用 import 语句

BingoCodeIDE 引擎有自己的 API，不需要 import：

```python
# 错误：不能 import
import random
random.randint(1, 6)

# 正确：使用引擎 API
random_int(1, 6)
```

### Q: 不能使用标准库

引擎不支持 Python 标准库（如 random、math、os 等），请使用引擎提供的 API：

| 标准库 | 引擎替代 |
|--------|----------|
| `random.randint()` | `random_int()` |
| `random.random()` | `random_float()` |
| `math.sqrt()` | 自己计算或用 `distance_to()` |

### Q: lambda 是什么？

`lambda` 是一种简短的匿名函数，常用于回调：

```python
# 普通函数
def on_hit(bullet, enemy):
    bullet.delete()
    enemy.delete()

bullet.on_hit("enemies", on_hit)

# 等价的 lambda 写法
bullet.on_hit("enemies", lambda b, e: (b.delete(), e.delete()))
```

## 其他问题

### Q: 如何暂停游戏？

```python
pause()     # 暂停
resume()    # 继续
is_paused() # 检查是否暂停
```

### Q: 如何结束游戏？

```python
stop()  # 结束游戏
```

### Q: 画面尺寸是多少？

默认画面尺寸是 640×480 像素：
- x 范围：0 ~ 640
- y 范围：0 ~ 480
- 原点在左上角 (0, 0)

### Q: 如何联系技术支持？

如果以上内容都无法解决你的问题，请：
1. 查看控制台的错误信息
2. 检查代码是否有拼写错误
3. 参考本文档的 API 参考部分
4. 使用内置的 AI 编程助手（Ctrl+点击帮助按钮）
