# while True 迁移指南

BingoCode IDE 现在支持直接使用 `while True:` 编写游戏循环，更加直观易懂。

## 旧写法（仍然支持）

```python
from bingo_engine import *

def loop():
    if key_down('a'):
        hero.move(5)

run()
```

## 新写法（推荐）

```python
from bingo_engine import *

while True:
    if key_down('a'):
        hero.move(5)
```

引擎会自动将 `while True:` 转换为 generator，无需手动定义 `loop()` 函数和调用 `run()`。

## 多文件项目

BingoCode IDE 会自动发现项目目录下的所有 `.py` 文件，并自动注入 import 语句。

### 示例项目结构

```
my_game/
  main.py     # 主逻辑，包含 while True
  player.py   # 玩家相关函数
  enemy.py    # 敌人相关函数
```

### main.py

```python
from bingo_engine import *

while True:
    if key_down('a'):
        hero.move(-5)
    if key_down('d'):
        hero.move(5)
    if key_down('w'):
        hero.jump(10)
    
    # 敌人AI
    enemy.look_at(hero)
    enemy.move(2)
    
    # 摄像机跟随
    follow(hero)
```

### player.py

```python
from bingo_engine import *

hero = Sprite("洛克人")
```

### enemy.py

```python
from bingo_engine import *

enemy = Sprite("哥布林")
```

引擎会自动将 `player.py` 和 `enemy.py` 的内容合并到主脚本中，无需手动 import。

## 支持的语法

- `while True:` - 标准写法
- `while 1:` - 等效写法

引擎会检测这些模式并自动转换为 generator。

## 运行示例

在 IDE 中打开 `examples/while_true_demo/` 目录，即可查看完整的多角色协作示例。
