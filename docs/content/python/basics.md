# Python 基础语法

本章介绍 BingoCodeIDE 中用到的 Python 基础知识。

## 变量

变量是用来存储数据的容器。

```python
# 字符串
name = "小明"

# 整数
age = 10

# 浮点数
score = 95.5

# 布尔值
is_ok = True
```

### 变量命名规则

- 只能用字母、数字、下划线
- 不能以数字开头
- 区分大小写（`name` 和 `Name` 是不同的变量）

```python
# 正确
player_name = "小明"
score1 = 100

# 错误
1st_place = "冠军"  # 不能以数字开头
```

## 数据类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `int` | 整数 | `10`, `-5`, `1000000` |
| `float` | 浮点数 | `3.14`, `-2.5` |
| `str` | 字符串 | `"hello"`, `'world'` |
| `bool` | 布尔值 | `True`, `False` |

### 类型转换

```python
int("123")    # 字符串转整数
float("3.14") # 字符串转浮点数
str(100)      # 整数转字符串
```

## 运算符

### 算术运算符

```python
10 + 3    # 13  加法
10 - 3    # 7   减法
10 * 3    # 30  乘法
10 / 3    # 3.333...  除法
10 // 3   # 3   整除
10 % 3    # 1   取余
2 ** 3    # 8   幂运算
```

### 比较运算符

```python
5 == 5    # True   等于
5 != 3    # True   不等于
5 > 3     # True   大于
5 < 3     # False  小于
5 >= 5    # True   大于等于
5 <= 3    # False  小于等于
```

### 逻辑运算符

```python
True and False  # False  两个都为真才是真
True or False   # True   有一个为真就是真
not True        # False  取反
```

## 字符串

### f-string 格式化

```python
name = "小明"
age = 10
score = 95.5

print(f"我叫{name}，今年{age}岁")
print(f"成绩是{score:.1f}")  # 保留1位小数
```

### 字符串方法

```python
s = "Hello World"
s.lower()      # "hello world"
s.upper()      # "HELLO WORLD"
s.strip()      # 去除首尾空白
s.replace("World", "Python")  # "Hello Python"
s.split()      # ["Hello", "World"]
```

## 列表

列表可以存储多个值。

```python
fruits = ["苹果", "香蕉", "橙子"]

print(fruits[0])     # 苹果
print(fruits[-1])    # 橙子
print(len(fruits))   # 3

fruits.append("西瓜")  # 添加
fruits.remove("香蕉")  # 删除
```

## 控制流

### if 语句

```python
score = 85

if score >= 90:
    print("优秀")
elif score >= 80:
    print("良好")
elif score >= 60:
    print("及格")
else:
    print("不及格")
```

### for 循环

```python
# 遍历列表
for fruit in ["苹果", "香蕉"]:
    print(fruit)

# 遍历范围
for i in range(5):  # 0,1,2,3,4
    print(i)
```

### while 循环

```python
count = 0
while count < 5:
    print(count)
    count += 1

# 无限循环
while True:
    # 游戏主循环
    pass
```

## 函数

```python
# 定义函数
def greet(name):
    print(f"你好, {name}!")

# 调用函数
greet("小明")

# 带返回值
def add(a, b):
    return a + b

result = add(3, 5)  # 8
```

## 异常处理

```python
try:
    num = int(input("输入数字: "))
    result = 100 / num
except ValueError:
    print("输入的不是数字！")
except ZeroDivisionError:
    print("不能除以零！")
```

## 常见错误

### NameError

变量未定义：

```python
# 错误
print(name)  # NameError: name 'name' is not defined

# 正确
name = "小明"
print(name)
```

### IndentationError

缩进错误：

```python
# 错误
if True:
print("hello")  # IndentationError

# 正确
if True:
    print("hello")  # 4个空格
```

### TypeError

类型错误：

```python
# 错误
"hello" + 123  # TypeError

# 正确
"hello" + str(123)
```

## 下一步

- 学习 [常用编程模式](common-patterns.md)
- 查看 [API 参考](../api/sprite.md) 了解引擎功能
