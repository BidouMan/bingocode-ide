<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import iconRightArrow from '../../assets/icons/right_arrow.svg'
import iconDownArrow from '../../assets/icons/down_arrow.svg'

defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: [] }>()

const expandedCards = ref<Record<string, boolean>>({})
const activeCategory = ref(0)
const searchQuery = ref('')

function toggleCard(ci: number, fi: number) {
  const key = `${ci}-${fi}`
  expandedCards.value[key] = !expandedCards.value[key]
}

function scrollToCategory(index: number) {
  activeCategory.value = index
  nextTick(() => {
    document.getElementById(`py-help-cat-${index}`)?.scrollIntoView()
  })
}

interface FuncItem {
  label: string
  code: string
  desc: string
  badgeType: string
}

interface Category {
  name: string
  color: string
  funcs: FuncItem[]
}

const categories: Category[] = [
  // ════════ 基础语法 ════════
  {
    name: '基础语法',
    color: '#59C759',
    funcs: [
      { label: '变量赋值', code: 'name = "小明"\nage = 10\nscore = 95.5\nis_ok = True', desc: 'Python 不需要声明类型，直接用等号赋值。变量名用字母或下划线开头，不能用数字开头。', badgeType: 'keyword' },
      { label: '注释', code: '# 这是单行注释\n\n"""\n这是多行注释\n可以写很多行\n"""', desc: '注释是给程序员看的，Python 会忽略它们。# 开头是单行注释，三引号包裹是多行注释。', badgeType: 'keyword' },
      { label: '缩进（用空格代替花括号）', code: 'if age > 6:\n    print("可以上小学")\n    print("耶！")\nprint("这行不在 if 里面")', desc: 'Python 用缩进（4个空格）来表示代码块，不用花括号 {}。缩进对了代码才能正常运行。', badgeType: 'keyword' },
      { label: 'print 输出', code: 'print("你好世界")\nprint("名字:", name)\nprint("a =", 1, "b =", 2)', desc: 'print() 会在屏幕上显示内容。多个参数用逗号隔开，会自动加空格。', badgeType: 'function' },
      { label: 'input 用户输入', code: 'name = input("请输入你的名字: ")\nprint("你好,", name)', desc: 'input() 会等待用户输入，返回的永远是字符串。要得到数字需要用 int() 或 float() 转换。', badgeType: 'function' },
      { label: 'type() 查看类型', code: 'print(type(123))   # <class \'int\'>\nprint(type("abc")) # <class \'str\'>\nprint(type(3.14))  # <class \'float\'>', desc: 'type() 可以查看一个变量是什么类型。\n调试时很有用，\n帮你确认变量类型对不对。', badgeType: 'function' },
    ],
  },
  // ════════ 数据类型 ════════
  {
    name: '数据类型',
    color: '#4C97FF',
    funcs: [
      { label: 'int 整数', code: 'a = 10\nb = -5\nbig = 1000000\n\n# 类型转换\nx = int("42")    # 字符串转整数\ny = int(3.9)     # 浮点数转整数（截断）', desc: '整数没有大小限制。可以用 int() 从字符串或浮点数转换。浮点数转整数会直接截断小数部分。', badgeType: 'type' },
      { label: 'float 浮点数', code: 'pi = 3.14\ntemp = -2.5\n\n# 类型转换\nx = float("3.14")  # 字符串转浮点\ny = float(10)      # 整数转浮点', desc: '带小数点的数就是浮点数。注意浮点数计算可能有精度问题（如 0.1 + 0.2 != 0.3）。', badgeType: 'type' },
      { label: 'str 字符串', code: 's1 = "Hello"\ns2 = \'World\'\nmulti = """多行\n字符串"""\n\n# f-string 格式化（最常用）\nname = "小明"\nage = 10\nprint(f"我叫{name}，今年{age}岁")', desc: '字符串用引号包裹，单引号双引号都行。\nf-string 用 f"..." 写法，\n花括号里放变量名，是最方便的格式化方式。', badgeType: 'type' },
      { label: 'bool 布尔值', code: 'ok = True\nno = False\n\n# 比较运算返回布尔值\nprint(5 > 3)    # True\nprint(5 == 3)    # False\nprint(5 != 3)    # True', desc: '布尔值只有 True 和 False 两个。比较运算（>、<、==、!=）的结果就是布尔值。', badgeType: 'type' },
      { label: 'None 空值', code: 'result = None\n\nif result is None:\n    print("还没有结果")', desc: 'None 表示"什么都没有"。注意判断是否为 None 要用 is None，不要用 == None。', badgeType: 'type' },
      { label: '类型转换', code: 'int("123")    # 123\nfloat("3.14") # 3.14\nstr(100)      # "100"\nbool(0)       # False\nbool("")      # False\nbool("hello") # True', desc: '不同类型之间可以互相转换。\n空的值（0、空字符串、None）\n转 bool 是 False，其他都是 True。', badgeType: 'function' },
    ],
  },
  // ════════ 运算符 ════════
  {
    name: '运算符',
    color: '#FFAB19',
    funcs: [
      { label: '算术运算符', code: 'print(10 + 3)    # 13  加法\nprint(10 - 3)    # 7   减法\nprint(10 * 3)    # 30  乘法\nprint(10 / 3)    # 3.333...  除法\nprint(10 // 3)   # 3   整除\nprint(10 % 3)    # 1   取余\nprint(2 ** 3)    # 8   幂运算', desc: '/ 是真除法（结果带小数），// 是整除（取整），% 是取余数（求余），** 是幂运算（几次方）。', badgeType: 'operator' },
      { label: '比较运算符', code: 'print(5 == 5)    # True   等于\nprint(5 != 3)    # True   不等于\nprint(5 > 3)     # True   大于\nprint(5 < 3)     # False  小于\nprint(5 >= 5)    # True   大于等于\nprint(5 <= 3)    # False  小于等于', desc: '比较运算的结果是布尔值（True/False）。注意 == 是比较，= 是赋值，千万别搞混。', badgeType: 'operator' },
      { label: '逻辑运算符', code: 'a = True\nb = False\n\nprint(a and b)   # False  两个都为真才是真\nprint(a or b)    # True   有一个为真就是真\nprint(not a)     # False  取反', desc: 'and（与）、or（或）、not（非）。and 要求两个条件都满足，or 只需要一个满足，not 取反。', badgeType: 'operator' },
      { label: '赋值运算符', code: 'x = 10\nx += 5    # x = x + 5  → 15\nx -= 3    # x = x - 3  → 12\nx *= 2    # x = x * 2  → 24\nx //= 5   # x = x // 5 → 4\nx %= 3    # x = x % 3  → 1', desc: '简写赋值运算符，先运算再赋值。x += 5 等价于 x = x + 5，写起来更简洁。', badgeType: 'operator' },
      { label: '成员运算符', code: 'fruits = ["苹果", "香蕉", "橙子"]\n\nprint("苹果" in fruits)     # True\nprint("西瓜" not in fruits)  # True', desc: 'in 检查元素是否在序列中，not in 检查是否不在。常用于列表、字符串、字典的判断。', badgeType: 'operator' },
    ],
  },
  // ════════ 字符串 ════════
  {
    name: '字符串',
    color: '#9966FF',
    funcs: [
      { label: 'f-string 格式化', code: 'name = "小明"\nage = 10\nscore = 95.5\n\nprint(f"我叫{name}")\nprint(f"成绩是{score:.1f}")\n# 保留1位小数\nprint(f"编号: {42:05d}")\n# 补零: 00042', desc: 'f-string 是最常用的格式化方式。\n{变量名} 直接嵌入，\n:.1f 保留小数位，:05d 补零到5位。', badgeType: 'function' },
      { label: '字符串切片', code: 's = "Hello World"\n\nprint(s[0])    # H  第一个字符\nprint(s[-1])   # d  最后一个字符\nprint(s[0:5])  # Hello\n# 切片 [开始:结束]\nprint(s[::2])  # HloWrd  步长2\nprint(s[::-1]) # dlroW olleH  反转', desc: '字符串可以用索引取单个字符，\n用切片取子串。\n切片 [start:end] 不包含 end，\n[::step] 指定步长。', badgeType: 'function' },
      { label: '常用字符串方法', code: 's = "  Hello World  "\n\ns.strip()      # "Hello World"  去空白\ns.lower()      # "hello world"\ns.upper()      # "HELLO WORLD"\ns.replace("World", "Python")\n# "  Hello Python  "\ns.split()      # ["Hello", "World"]\n" ".join(["a","b"])  # "a b"\ns.startswith("  H")  # True\ns.find("World")      # 9', desc: '字符串有很多内置方法。strip() 去空白很常用，split() 和 join() 配合处理分割和拼接。', badgeType: 'function' },
      { label: '字符串长度和计数', code: 's = "Hello World"\n\nprint(len(s))       # 11 字符串长度\nprint(s.count("l")) # 3  出现次数\nprint(s.index("World"))  # 6', desc: 'len() 返回长度，\ncount() 数出现次数，\nindex() 找位置。\n找不到 index() 会报错，\n可以用 find() 代替（返回 -1）。', badgeType: 'function' },
    ],
  },
  // ════════ 列表 ════════
  {
    name: '列表',
    color: '#D65CD6',
    funcs: [
      { label: '创建和访问', code: 'fruits = ["苹果", "香蕉", "橙子"]\n\nprint(fruits[0])     # 苹果\nprint(fruits[-1])    # 橙子\nprint(len(fruits))   # 3  长度', desc: '列表用方括号 [] 创建，元素用逗号隔开。索引从 0 开始，-1 是最后一个。列表可以存不同类型的数据。', badgeType: 'type' },
      { label: '添加和删除', code: 'fruits = ["苹果", "香蕉"]\n\nfruits.append("橙子")     # 末尾加一个\nfruits.insert(1, "西瓜")  # 在位置1插入\nfruits.remove("香蕉")     # 删除指定元素\nfruits.pop()              # 删除并返回最后一个\nfruits.pop(0)             # 删除并返回位置0的\nfruits.clear()            # 清空列表', desc: 'append() 最常用，往末尾加。insert() 指定位置插入。remove() 按值删，pop() 按位置删。', badgeType: 'function' },
      { label: '切片操作', code: 'nums = [0, 1, 2, 3, 4, 5]\n\nprint(nums[1:4])    # [1, 2, 3]\nprint(nums[:3])     # [0, 1, 2] 前3个\nprint(nums[::2])    # [0, 2, 4] 步长2\nprint(nums[::-1])   # [5, 4, 3, 2, 1, 0] 反转', desc: '列表切片和字符串切片用法一样。切片返回新列表，不修改原列表。', badgeType: 'function' },
      { label: '列表排序', code: 'nums = [3, 1, 4, 1, 5, 9]\n\nnums.sort()  # 原地排序\n# [1, 1, 3, 4, 5, 9]\n\nnums.sort(reverse=True)\n# 降序: [9, 5, 4, 3, 1, 1]\n\nsorted(nums)  # 返回新列表\n# 不修改原列表', desc: 'sort() 直接修改原列表，sorted() 返回新列表。想保留原列表用 sorted()。', badgeType: 'function' },
      { label: '列表推导式', code: 'squares = [x**2 for x in range(5)]\n# [0, 1, 4, 9, 16]\n\nevens = [x for x in range(10)\n    if x % 2 == 0]\n# [0, 2, 4, 6, 8]\n\nwords = ["hello", "world"]\nupper = [w.upper() for w in words]\n# ["HELLO", "WORLD"]', desc: '列表推导式是创建列表的简洁写法。\n[表达式 for 变量 in 可迭代对象 if 条件]\n一行搞定循环+筛选+转换。', badgeType: 'keyword' },
      { label: '常用列表操作', code: 'a = [1, 2, 3]\nb = [4, 5, 6]\n\na + b    # [1,2,3,4,5,6] 合并\na * 3    # [1,2,3,1,2,3,1,2,3]\n\n3 in a   # True  是否包含\na.reverse()  # 原地反转\na.copy()     # 浅拷贝\n\n# enumerate 同时获取索引和值\nfor i, val in enumerate(["a", "b"]):\n    print(f"{i}: {val}")', desc: '列表可以相加合并、相乘重复。in 检查是否包含。enumerate() 遍历时同时获取索引和值。', badgeType: 'function' },
    ],
  },
  // ════════ 字典 ════════
  {
    name: '字典',
    color: '#4CBFE6',
    funcs: [
      { label: '创建和访问', code: 'person = {\n    "name": "小明",\n    "age": 10,\n    "score": 95.5\n}\n\nprint(person["name"])    # 小明\nprint(person.get("age")) # 10\nprint(person.get("gender", "未知"))  # 未知', desc: '字典用花括号 {} 创建，存键值对。用 ["键"] 或 .get("键") 取值。.get() 找不到返回 None 或默认值，不会报错。', badgeType: 'type' },
      { label: '增删改', code: 'd = {"a": 1, "b": 2}\n\nd["c"] = 3        # 添加新键值对\nd["a"] = 10       # 修改已有的值\ndel d["b"]        # 删除指定键\nd.pop("c")        # 删除并返回值\nd.clear()         # 清空字典', desc: '字典用 ["键"] = 值 来添加或修改。del 删除键值对，pop() 删除并返回值。', badgeType: 'function' },
      { label: '遍历字典', code: 'd = {"name": "小明", "age": 10}\n\nfor key in d:              # 遍历键\n    print(key, d[key])\n\nfor key, val in d.items(): # 遍历键值对\n    print(f"{key}: {val}")\n\nfor val in d.values():     # 遍历值\n    print(val)', desc: 'for key in d 遍历所有键。.items() 返回键值对，.values() 返回所有值。最常用的是 items() 同时获取键和值。', badgeType: 'function' },
      { label: '字典常用方法', code: 'd = {"name": "小明", "age": 10}\n\nprint(d.keys())    # 所有键\nprint(d.values())  # 所有值\nprint("name" in d) # True\n\nd.update({"age": 11})  # 批量更新\nd.setdefault("score", 0)\n# 没有 score 就设为 0', desc: '.keys() 取所有键，.values() 取所有值。\nin 检查键是否存在。\nupdate() 批量更新，setdefault() 设置默认值。', badgeType: 'function' },
      { label: '字典推导式', code: 'squares = {x: x**2 for x in range(5)}\n# {0: 0, 1: 1, 2: 4, 3: 9, 4: 16}\n\n# 两个列表合成字典\nkeys = ["name", "age"]\nvals = ["小明", 10]\nperson = dict(zip(keys, vals))\n# {"name": "小明", "age": 10}', desc: '字典推导式和列表推导式类似。\nzip() 把两个列表一一对应，\ndict() 转成字典。', badgeType: 'keyword' },
    ],
  },
  // ════════ 元组和集合 ════════
  {
    name: '元组与集合',
    color: '#2ECC71',
    funcs: [
      { label: 'tuple 元组', code: 'point = (10, 20)\n\nprint(point[0])    # 10\nprint(len(point))  # 2\n\n# 元组解包\nx, y = point\nprint(x)  # 10\nprint(y)  # 20', desc: '元组用圆括号 () 创建，和列表类似但不能修改（不可变）。常用于函数返回多个值、坐标等固定数据。', badgeType: 'type' },
      { label: 'set 集合', code: 's = {1, 2, 3, 3, 3}\nprint(s)   # {1, 2, 3} 自动去重\n\ns.add(4)       # 添加元素\ns.remove(1)    # 删除元素\n\na = {1, 2, 3}\nb = {3, 4, 5}\nprint(a | b)   # 并集 {1,2,3,4,5}\nprint(a & b)   # 交集 {3}\nprint(a - b)   # 差集 {1, 2}', desc: '集合用花括号 {} 创建（空集合要用 set()）。自动去重，支持并集 |、交集 &、差集 - 运算。', badgeType: 'type' },
    ],
  },
  // ════════ 控制流 ════════
  {
    name: '控制流',
    color: '#FF8C1A',
    funcs: [
      { label: 'if / elif / else', code: 'score = 85\n\nif score >= 90:\n    print("优秀")\nelif score >= 80:\n    print("良好")\nelif score >= 60:\n    print("及格")\nelse:\n    print("不及格")', desc: 'if 判断条件，elif 是"否则如果"，else 是"否则"。条件从上往下检查，满足第一个就执行，后面的不再检查。', badgeType: 'keyword' },
      { label: 'for 循环', code: '# 遍历列表\nfor fruit in ["苹果", "香蕉"]:\n    print(fruit)\n\n# 遍历范围\nfor i in range(5):  # 0,1,2,3,4\n    print(i)\n\nfor i in range(1, 6):  # 1~5\n    print(i)\n\nfor i in range(0, 10, 2):  # 步长2\n    print(i)  # 0,2,4,6,8', desc: 'for 循环依次取出每个元素。\nrange(n) 生成 0 到 n-1。\nrange(start, end, step) 指定起始和步长。', badgeType: 'keyword' },
      { label: 'while 循环', code: 'count = 0\nwhile count < 5:\n    print(count)\n    count += 1\n\n# 无限循环\nwhile True:\n    cmd = input("输入q退出: ")\n    if cmd == "q":\n        break', desc: 'while 在条件为 True 时一直执行。一定要有退出条件，否则会死循环。break 可以强制跳出循环。', badgeType: 'keyword' },
      { label: 'break 和 continue', code: '# break: 直接跳出循环\nfor i in range(10):\n    if i == 5:\n        break    # 遇到5就停\n    print(i)     # 0,1,2,3,4\n\n# continue: 跳过本次，继续下一次\nfor i in range(5):\n    if i == 2:\n        continue  # 跳过2\n    print(i)      # 0,1,3,4', desc: 'break 直接结束整个循环。continue 跳过当前这一次，继续下一次循环。常用于筛选或提前退出。', badgeType: 'keyword' },
      { label: '三元表达式', code: 'age = 15\nstatus = "成年" if age >= 18 else "未成年"\nprint(status)  # 未成年\n\n# 等价于\nif age >= 18:\n    status = "成年"\nelse:\n    status = "未成年"', desc: '三元表达式是 if/else 的简写。格式：值1 if 条件 else 值2。适合简单的二选一赋值。', badgeType: 'keyword' },
    ],
  },
  // ════════ 函数 ════════
  {
    name: '函数',
    color: '#9966FF',
    funcs: [
      { label: '定义和调用函数', code: 'def greet(name):\n    print(f"你好, {name}!")\n\ngreet("小明")   # 你好, 小明!\ngreet("小红")   # 你好, 小红!', desc: 'def 关键字定义函数，函数名后面加括号和参数。调用时写函数名加括号和实参。', badgeType: 'function' },
      { label: '返回值 return', code: 'def add(a, b):\n    return a + b\n\nresult = add(3, 5)\nprint(result)  # 8\n\n# 返回多个值\ndef get_pos():\n    return 10, 20\n\nx, y = get_pos()', desc: 'return 把结果返回给调用者。可以返回多个值（实际上是返回元组）。没有 return 或 return 后没值，返回 None。', badgeType: 'function' },
      { label: '默认参数', code: 'def greet(name, msg="你好"):\n    print(f"{msg}, {name}!")\n\ngreet("小明")            # 你好, 小明!\ngreet("小明", "早上好")   # 早上好, 小明!', desc: '给参数设默认值，调用时可以不传。有默认值的参数要放在没有默认值的后面。', badgeType: 'function' },
      { label: '可变参数 *args', code: 'def total(*numbers):\n    return sum(numbers)\n\nprint(total(1, 2, 3))  # 6\nprint(total(1, 2, 3, 4))  # 10\n\n# **kwargs 关键字参数\ndef info(**kwargs):\n    for k, v in kwargs.items():\n        print(f"{k}: {v}")\n\ninfo(name="小明", age=10)', desc: '*args 接收任意多个位置参数（元组）。\n**kwargs 接收任意多个关键字参数（字典）。\n不确定参数数量时用它们。', badgeType: 'function' },
      { label: 'lambda 匿名函数', code: 'add = lambda a, b: a + b\nprint(add(3, 5))  # 8\n\n# 常用场景：排序\nstudents = [("小明", 85), ("小红", 92)]\nstudents.sort(key=lambda s: s[1])\n# 按成绩排序\n\n# 降序排列\nnums = [3, 1, 4, 1, 5]\nresult = sorted(nums, key=lambda x: -x)', desc: 'lambda 是简短的一次性函数。\n格式：lambda 参数: 表达式。\n常用于 sorted() 的 key 参数。', badgeType: 'function' },
      { label: '作用域', code: 'x = "全局"\n\ndef demo():\n    x = "局部"\n    print(x)  # 局部\n\ndemo()\nprint(x)  # 全局\n\n# 用 global 修改全局变量\ncount = 0\ndef increment():\n    global count\n    count += 1', desc: '函数内定义的变量是局部的，函数外是全局的。函数内默认不能修改全局变量，要用 global 声明。', badgeType: 'keyword' },
    ],
  },
  // ════════ 类与对象 ════════
  {
    name: '类与对象',
    color: '#E74C3C',
    funcs: [
      { label: '定义类', code: 'class Dog:\n    def __init__(self, name, age):\n        self.name = name\n        self.age = age\n\n    def bark(self):\n        print(f"{self.name}: 汪汪！")\n\ndog = Dog("旺财", 3)\ndog.bark()   # 旺财: 汪汪！', desc: '__init__ 是构造方法，创建对象时自动调用。self 代表对象自身，第一个参数必须是 self。', badgeType: 'keyword' },
      { label: '类属性和实例属性', code: 'class Cat:\n    species = "猫科"  # 类属性\n\n    def __init__(self, name):\n        self.name = name  # 实例属性\n\ncat1 = Cat("小花")\ncat2 = Cat("小白")\nprint(Cat.species)  # 猫科\nprint(cat1.name)    # 小花', desc: '类属性定义在类里面、方法外面，\n所有实例共享。\n实例属性定义在 __init__ 里，\n用 self.名字，每个实例各有一份。', badgeType: 'keyword' },
      { label: '方法', code: 'class Calculator:\n    def __init__(self):\n        self.result = 0\n\n    def add(self, n):    # 普通方法\n        self.result += n\n        return self  # 支持链式调用\n\n    def reset(self):\n        self.result = 0\n\ncalc = Calculator()\ncalc.add(5).add(3)  # 链式调用\nprint(calc.result)   # 8', desc: '方法就是定义在类里的函数。return self 可以实现链式调用。方法的第一个参数永远是 self。', badgeType: 'function' },
      { label: '继承', code: 'class Animal:\n    def __init__(self, name):\n        self.name = name\n\n    def speak(self):\n        pass\n\nclass Cat(Animal):  # Cat 继承 Animal\n    def speak(self):  # 重写父类方法\n        print(f"{self.name}: 喵~")\n\ncat = Cat("小花")\ncat.speak()  # 小花: 喵~', desc: '继承让子类获得父类的功能。\nclass 子类(父类) 写在类名括号里。\n可以重写父类的方法来实现自己的行为。', badgeType: 'keyword' },
    ],
  },
  // ════════ 异常处理 ════════
  {
    name: '异常处理',
    color: '#E67E22',
    funcs: [
      { label: 'try / except', code: 'try:\n    num = int(input("输入数字: "))\n    result = 100 / num\n    print(f"结果: {result}")\nexcept ValueError:\n    print("输入的不是数字！")\nexcept ZeroDivisionError:\n    print("不能除以零！")', desc: 'try 里的代码如果出错，会跳到对应的 except。可以针对不同错误类型写不同的处理。', badgeType: 'keyword' },
      { label: 'try / except / else / finally', code: 'try:\n    f = open("data.txt")\n    content = f.read()\nexcept FileNotFoundError:\n    print("文件不存在")\nelse:\n    print(f"读取成功: {content}")\nfinally:\n    print("无论如何都会执行")\n    # 常用于关闭资源', desc: 'else 在没有异常时执行。\nfinally 无论是否出错都执行，\n常用于关闭文件、释放资源。', badgeType: 'keyword' },
      { label: '抛出异常', code: 'def set_age(age):\n    if age < 0:\n        raise ValueError("年龄不能为负数")\n    print(f"年龄: {age}")\n\n# 捕获自定义异常\ntry:\n    set_age(-5)\nexcept ValueError as e:\n    print(f"错误: {e}")', desc: 'raise 主动抛出异常。可以抛出内置异常或自定义异常。raise ValueError("消息") 常用于参数校验。', badgeType: 'keyword' },
    ],
  },
  // ════════ 文件操作 ════════
  {
    name: '文件操作',
    color: '#1ABC9C',
    funcs: [
      { label: '读取文件', code: '# 方法一：自动关闭（推荐）\nwith open("data.txt", "r") as f:\n    content = f.read()      # 读全部\n\n# 逐行读取\nwith open("data.txt", "r") as f:\n    for line in f:\n        print(line.strip())\n\n# 读所有行到列表\nwith open("data.txt", "r") as f:\n    lines = f.readlines()', desc: 'with open() 自动关闭文件，是最安全的方式。"r" 是读取模式，read() 读全部，readlines() 读所有行到列表。', badgeType: 'function' },
      { label: '写入文件', code: '# 写入（覆盖）\nwith open("out.txt", "w") as f:\n    f.write("第一行\\n")\n    f.write("第二行\\n")\n\n# 追加（不覆盖）\nwith open("out.txt", "a") as f:\n    f.write("追加的内容\\n")\n\n# 写入多行\nwith open("out.txt", "w") as f:\n    lines = ["行1\\n", "行2\\n", "行3\\n"]\n    f.writelines(lines)', desc: '"w" 写入模式会清空原文件，"a" 追加模式在末尾添加。write() 写字符串，writelines() 写字符串列表。', badgeType: 'function' },
      { label: '文件编码', code: '# 中文文件指定编码\nwith open("data.txt", "r", encoding="utf-8") as f:\n    content = f.read()\n\nwith open("out.txt", "w", encoding="utf-8") as f:\n    f.write("中文内容")', desc: '读写中文文件时建议指定 encoding="utf-8"，避免编码错误。', badgeType: 'keyword' },
    ],
  },
  // ════════ 内置函数 ════════
  {
    name: '内置函数',
    color: '#3498DB',
    funcs: [
      { label: 'print() 输出', code: 'print("Hello")\nprint("a", "b", "c")     # a b c\nprint("x", end="")        # 不换行\nprint("y")                # xy\nprint("a", sep="-")       # a（分隔符）', desc: 'print() 输出内容。end="" 让下次 print 不换行，sep="" 改变多个参数之间的分隔符。', badgeType: 'function' },
      { label: 'input() 输入', code: 'name = input("名字: ")\nage = int(input("年龄: "))\n# input 返回的永远是字符串', desc: 'input() 等待用户输入并返回字符串。要得到数字需要 int() 或 float() 转换。', badgeType: 'function' },
      { label: 'len() 长度', code: 'len("Hello")     # 5\nlen([1, 2, 3])   # 3\nlen({"a": 1})    # 1', desc: 'len() 返回字符串长度、列表元素个数、字典键值对个数等。最常用的内置函数之一。', badgeType: 'function' },
      { label: 'range() 范围', code: 'range(5)        # 0,1,2,3,4\nrange(1, 6)     # 1,2,3,4,5\nrange(0, 10, 2) # 0,2,4,6,8', desc: 'range() 生成整数序列，常和 for 循环搭配。range(n) 从 0 到 n-1。', badgeType: 'function' },
      { label: '类型相关', code: 'int("42")        # 转整数\nfloat("3.14")    # 转浮点数\nstr(100)         # 转字符串\nbool(0)          # False\nbool("hi")       # True\nlist("abc")      # ["a","b","c"]\ntuple([1,2,3])   # (1,2,3)\ndict([("a",1)])  # {"a":1}', desc: '这些函数用来进行类型转换。int/float/str 是最常用的三个。list() 可以把可迭代对象转成列表。', badgeType: 'function' },
      { label: 'max() / min() / sum()', code: 'nums = [3, 1, 4, 1, 5, 9]\nmax(nums)    # 9\nmin(nums)    # 1\nsum(nums)    # 23\nsum(nums, 10)  # 33  从10开始加', desc: 'max() 取最大值，min() 取最小值，sum() 求和。sum 的第二个参数是起始值。', badgeType: 'function' },
      { label: 'sorted() 排序', code: 'sorted([3, 1, 4])  # [1, 3, 4]\nsorted([3, 1, 4], reverse=True)\n# [4, 3, 1]\n\n# 按指定规则排序\nwords = ["banana", "apple"]\nsorted(words, key=len)\n# ["apple", "banana"]', desc: 'sorted() 返回排序后的新列表，\n不修改原列表。key 参数指定排序规则，\n常和 lambda 搭配。', badgeType: 'function' },
      { label: 'zip() 打包', code: 'names = ["小明", "小红"]\nscores = [85, 92]\n\nfor name, score in zip(names, scores):\n    print(f"{name}: {score}")\n\n# 转字典\nd = dict(zip(names, scores))\n# {"小明": 85, "小红": 92}', desc: 'zip() 把多个列表的元素一一配对。常用于同时遍历多个列表，或者用 dict() 转成字典。', badgeType: 'function' },
      { label: 'enumerate() 带索引遍历', code: 'fruits = ["苹果", "香蕉", "橙子"]\n\nfor i, fruit in enumerate(fruits):\n    print(f"{i}: {fruit}")\n# 0: 苹果  1: 香蕉  2: 橙子\n\n# 指定起始索引\nfor i, fruit in enumerate(fruits, 1):\n    print(f"{i}. {fruit}")\n# 1. 苹果  2. 香蕉  3. 橙子', desc: 'enumerate() 在遍历时同时给出索引和值。\n第二个参数可以指定起始索引\n（默认从 0 开始）。', badgeType: 'function' },
      { label: 'map() 和 filter()', code: '# map: 对每个元素应用函数\nnums = [1, 2, 3, 4]\nsquares = list(map(\n    lambda x: x**2, nums))\n# [1, 4, 9, 16]\n\n# filter: 筛选满足条件的元素\nevens = list(filter(\n    lambda x: x%2==0, nums))\n# [2, 4]\n\n# 推导式更常用\nsquares = [x**2 for x in nums]\nevens = [x for x in nums if x%2==0]', desc: 'map() 对每个元素做转换，\nfilter() 筛选元素。\n实际开发中列表推导式更常用。', badgeType: 'function' },
    ],
  },
  // ════════ 常用标准库 ════════
  {
    name: '常用标准库',
    color: '#8E44AD',
    funcs: [
      { label: 'os 文件与目录', code: 'import os\n\nos.getcwd()   # 当前目录\nos.listdir(".")  # 列出目录内容\n\n# 文件是否存在\nos.path.exists("f.txt")\n\n# 拼接路径\nos.path.join("a", "b")  # "a/b"\n\nos.makedirs("dir/sub",\n    exist_ok=True)', desc: 'os 模块处理文件和目录。\nos.path.join() 拼接路径\n（跨平台安全）。\nexist_ok=True 已存在不报错。', badgeType: 'module' },
      { label: 'json 序列化', code: 'import json\n\n# Python → JSON 字符串\ndata = {"name": "小明", "age": 10}\njson_str = json.dumps(data)\n\n# JSON → Python 对象\nobj = json.loads(json_str)\nprint(obj["name"])  # 小明\n\n# 读写 JSON 文件\nwith open("data.json", "w") as f:\n    json.dump(data, f)', desc: 'json 模块处理 JSON 数据。\ndumps() 转字符串，loads() 解析。\nensure_ascii=False 让中文正常显示。', badgeType: 'module' },
      { label: 'datetime 日期时间', code: 'from datetime import datetime, timedelta\n\nnow = datetime.now()\nprint(now.strftime("%Y-%m-%d"))\n# 2024-01-15\n\n# 解析字符串\ndt = datetime.strptime("2024-01-15",\n    "%Y-%m-%d")\n\n# 时间计算\nfuture = now + timedelta(days=7)\n# 7天后', desc: 'datetime 处理日期时间。\nstrftime() 格式化输出，\nstrptime() 解析字符串。\ntimedelta 做时间加减。', badgeType: 'module' },
      { label: 'random 随机数', code: 'import random\n\nrandom.randint(1, 6)   # 1~6 整数\nrandom.random()        # 0~1 小数\nrandom.choice(["a","b"])  # 随机选一个\nrandom.shuffle([1,2,3])  # 打乱列表\nrandom.sample(range(100), 5)\n# 随机选5个', desc: 'random 模块生成随机数。\nrandint(a,b) 生成 a 到 b 的整数。\nchoice() 随机选元素，\nshuffle() 打乱列表。', badgeType: 'module' },
      { label: 'math 数学', code: 'import math\n\nmath.pi       # 3.14159...\nmath.e        # 2.71828...\nmath.sqrt(16) # 4.0  开方\nmath.ceil(3.2)  # 4  向上取整\nmath.floor(3.8) # 3  向下取整\nmath.pow(2, 10) # 1024.0\nmath.log(100, 10) # 2.0', desc: 'math 模块提供数学常量和函数。\nsqrt() 开方，ceil/floor 取整，\npow() 幂运算，log() 对数。', badgeType: 'module' },
      { label: 'collections 容器工具', code: 'from collections import Counter\nfrom collections import defaultdict\n\n# Counter 计数\ntext = "hello world"\nc = Counter(text)\nprint(c.most_common(3))\n# [(\'l\', 3), (\'o\', 2)]\n\n# defaultdict 带默认值的字典\nd = defaultdict(list)\nd["fruits"].append("apple")\n# {"fruits": ["apple"]}', desc: 'Counter 统计元素出现次数。\ndefaultdict 创建带默认值的字典，\n省去 key 不存在时的判断。', badgeType: 'module' },
    ],
  },
]

function getBadgeColor(type?: string) {
  switch (type) {
    case 'keyword': return '#FFAB19'
    case 'function': return '#9966FF'
    case 'type': return '#4C97FF'
    case 'operator': return '#59C759'
    case 'module': return '#E74C3C'
    default: return '#9966FF'
  }
}

function getBadgeLabel(type?: string) {
  switch (type) {
    case 'keyword': return '关键字'
    case 'function': return '函数'
    case 'type': return '类型'
    case 'operator': return '运算符'
    case 'module': return '模块'
    default: return ''
  }
}

const filteredCategories = computed(() => {
  if (!searchQuery.value.trim()) return categories

  const query = searchQuery.value.toLowerCase()
  return categories
    .map(cat => ({
      ...cat,
      funcs: cat.funcs.filter(
        f =>
          f.label.toLowerCase().includes(query) ||
          f.desc.toLowerCase().includes(query) ||
          f.code.toLowerCase().includes(query)
      ),
    }))
    .filter(cat => cat.funcs.length > 0)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="help-slide">
      <div v-if="visible" class="help-overlay" @click.self="emit('close')">
        <div class="help-panel">
          <!-- 标题栏 -->
          <div class="help-header">
            <div class="help-title-row">
              <img src="../../assets/icons/help.svg" class="help-header-icon" />
              <span class="help-title">Python 语法参考</span>
            </div>
            <button class="help-close-btn" @click="emit('close')">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M1 1L13 13M13 1L1 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <!-- 搜索框 -->
          <div class="help-search">
            <div class="help-search-box">
              <svg class="help-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
              </svg>
              <input
                v-model="searchQuery"
                type="text"
                class="help-search-input"
                placeholder="搜索语法、函数、关键字..."
              />
              <button v-if="searchQuery" class="help-search-clear" @click="searchQuery = ''">
                <svg width="12" height="12" viewBox="0 0 14 14" fill="none">
                  <path d="M1 1L13 13M13 1L1 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
              </button>
            </div>
          </div>

          <!-- 主体：左侧分类 + 右侧内容 -->
          <div class="help-body">
            <!-- 左侧分类栏 -->
            <div class="help-sidebar">
              <button
                v-for="(cat, ci) in filteredCategories"
                :key="ci"
                class="help-sidebar-btn"
                :class="{ 'help-sidebar-btn-active': activeCategory === ci }"
                :style="{
                  borderLeftColor: activeCategory === ci ? cat.color : 'transparent',
                }"
                @click="scrollToCategory(ci)"
              >
                <span class="help-sidebar-dot" :style="{ background: cat.color }"></span>
                <span class="help-sidebar-name" :style="{ color: activeCategory === ci ? cat.color : '' }">{{ cat.name }}</span>
              </button>
            </div>

            <!-- 右侧内容 -->
            <div class="help-content">
              <div
                v-for="(cat, ci) in filteredCategories"
                :key="ci"
                :id="`py-help-cat-${ci}`"
                class="help-category-section"
              >
                <div class="help-category-header">
                  <span class="help-category-name" :style="{ color: cat.color }">{{ cat.name }}</span>
                  <div class="help-category-line" :style="{ background: cat.color }"></div>
                </div>

                <div class="help-card-list">
                  <div
                    v-for="(func, fi) in cat.funcs"
                    :key="fi"
                    class="help-func-card"
                    :class="{ 'help-func-card-expanded': expandedCards[`${ci}-${fi}`] }"
                  >
                    <button class="help-func-header" @click="toggleCard(ci, fi)">
                      <img
                        :src="expandedCards[`${ci}-${fi}`] ? iconDownArrow : iconRightArrow"
                        class="help-arrow-icon"
                      />
                      <span class="help-func-dot" :style="{ background: getBadgeColor(func.badgeType) }"></span>
                      <span class="help-func-label">{{ func.label }}</span>
                      <span class="help-func-badge" :style="{ background: getBadgeColor(func.badgeType) + '22', color: getBadgeColor(func.badgeType) }">{{ getBadgeLabel(func.badgeType) }}</span>
                    </button>
                    <div v-if="expandedCards[`${ci}-${fi}`]" class="help-func-body">
                      <div class="help-func-code">
                        <code>{{ func.code }}</code>
                      </div>
                      <div class="help-func-desc">{{ func.desc }}</div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 无搜索结果 -->
              <div v-if="filteredCategories.length === 0" class="help-empty">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5">
                  <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
                </svg>
                <span>没有找到匹配的内容</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.help-slide-enter-active,
.help-slide-leave-active { transition: opacity 0.25s ease; }
.help-slide-enter-active .help-panel,
.help-slide-leave-active .help-panel { transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.help-slide-enter-from,
.help-slide-leave-to { opacity: 0; }
.help-slide-enter-from .help-panel,
.help-slide-leave-to .help-panel { transform: translateX(100%); }

.help-overlay {
  position: fixed; inset: 0; z-index: 9000;
  display: flex; justify-content: flex-end;
  background: rgba(0, 0, 0, 0.3);
}

.help-panel {
  width: 480px; max-width: 92vw; height: 100%;
  display: flex; flex-direction: column;
  background: var(--bg-root);
  border-left: 1px solid var(--border);
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.4);
}

/* ── 标题栏 ── */
.help-header {
  display: flex; align-items: center; justify-content: space-between;
  height: 40px; min-height: 40px; padding: 0 16px;
  border-bottom: 1px solid var(--border);
}
.help-title-row { display: flex; align-items: center; gap: 8px; }
.help-header-icon { width: 20px; height: 20px; }
.help-title { font-size: 14px; font-weight: 600; color: white; }
.help-close-btn {
  display: flex; align-items: center; justify-content: center;
  width: 28px; height: 28px;
  background: transparent; border: none; border-radius: 4px;
  color: var(--text-secondary); cursor: pointer; transition: all 0.15s;
}
.help-close-btn:hover {   background: var(--bg-hover); color: white; }

/* ── 搜索框 ── */
.help-search {
  padding: 8px 12px; border-bottom: 1px solid var(--border);
}
.help-search-box {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px;
  background: var(--bg-hover);
  border-radius: 6px; border: 1px solid var(--border-light);
}
.help-search-icon { color: var(--text-muted); flex-shrink: 0; }
.help-search-input {
  flex: 1; background: transparent; border: none; outline: none;
  font-size: 13px; color: white;
}
.help-search-input::placeholder { color: var(--text-muted); }
.help-search-clear {
  display: flex; align-items: center; justify-content: center;
  width: 20px; height: 20px; padding: 0;
  background: transparent; border: none; border-radius: 3px;
  color: var(--text-muted); cursor: pointer; transition: all 0.15s;
}
.help-search-clear:hover { background: rgba(255,255,255,0.1); color: white; }

/* ── 主体布局 ── */
.help-body {
  flex: 1; min-height: 0; overflow: hidden;
  display: flex;
}

/* ── 左侧分类栏 ── */
.help-sidebar {
  width: 58px; min-width: 58px;
  display: flex; flex-direction: column;
  border-right: 1px solid var(--border);
  overflow-y: auto; padding: 0;
}
.help-sidebar::-webkit-scrollbar { display: none; }

.help-sidebar-btn {
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 4px;
  height: 46px; min-height: 46px;
  background: transparent;
  border: none; border-left: 3px solid transparent;
  cursor: pointer; transition: all 0.15s;
  padding: 0;
}
.help-sidebar-btn:hover { background: rgba(255, 255, 255, 0.04); }
.help-sidebar-btn-active { background: rgba(255, 255, 255, 0.06); }

.help-sidebar-dot {
  width: 10px; height: 10px; min-width: 10px; min-height: 10px;
  border-radius: 50%;
}
.help-sidebar-name {
  font-size: 11px; color: rgb(140, 140, 140);
  line-height: 1; white-space: nowrap;
}
.help-sidebar-btn-active .help-sidebar-name { font-weight: 600; }

/* ── 内容滚动区 ── */
.help-content {
  flex: 1; min-height: 0; overflow-y: auto; padding: 12px 16px 0;
}
.help-content::after {
  content: '';
  display: block;
  height: 50vh;
}
.help-content::-webkit-scrollbar { width: 6px; }
.help-content::-webkit-scrollbar-track { background: transparent; }
.help-content::-webkit-scrollbar-thumb { background: rgb(60, 63, 70); border-radius: 3px; }

/* ── 分类区块 ── */
.help-category-section { margin-bottom: 24px; }
.help-category-section:last-child { margin-bottom: 0; }
.help-category-header {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 10px; padding: 4px 0;
}
.help-category-name { font-size: 14px; font-weight: 700; white-space: nowrap; }
.help-category-line { flex: 1; height: 2px; border-radius: 1px; opacity: 0.3; }

/* ── 卡片列表 ── */
.help-card-list { display: flex; flex-direction: column; gap: 3px; }

.help-func-card {
  border-radius: 8px; border: 1px solid var(--border-light);
  background: transparent; overflow: hidden; transition: background 0.12s;
}
.help-func-card:hover { background: rgba(255, 255, 255, 0.04); }
.help-func-card-expanded { background: rgba(255, 255, 255, 0.06); }

.help-func-header {
  display: flex; align-items: center; gap: 8px;
  width: 100%; padding: 8px 12px;
  background: transparent; border: none;
  color: white; cursor: pointer; text-align: left;
}
.help-func-header:hover { background: rgba(255, 255, 255, 0.03); }

.help-arrow-icon { width: 14px; height: 14px; flex-shrink: 0; opacity: 0.5; }

.help-func-dot {
  width: 8px; height: 8px; min-width: 8px;
  border-radius: 50%; flex-shrink: 0;
}

.help-func-label {
  font-size: 13px; color: rgb(230, 230, 230);
  font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
}

.help-func-badge {
  font-size: 10px; padding: 1px 6px;
  border-radius: 4px; margin-left: auto;
  white-space: nowrap; font-weight: 500;
  font-family: -apple-system, BlinkMacSystemFont, sans-serif;
}

/* ── 展开内容 ── */
.help-func-body { padding: 0 12px 10px 34px; }

.help-func-code {
  margin-bottom: 6px; padding: 6px 10px;
  background: rgb(28, 28, 32);
  border-radius: 6px; border: 1px solid var(--border-light);
  overflow-x: auto;
}
.help-func-code::-webkit-scrollbar { height: 4px; }
.help-func-code::-webkit-scrollbar-track { background: transparent; }
.help-func-code::-webkit-scrollbar-thumb { background: rgb(60, 63, 70); border-radius: 2px; }
.help-func-code code {
  font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
  font-size: 12px; color: rgb(156, 227, 170);
  white-space: pre; user-select: all;
}

.help-func-desc {
  font-size: 12.5px; line-height: 1.7;
  color: rgb(180, 180, 180);
}

/* ── 空状态 ── */
.help-empty {
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 12px; padding: 60px 20px;
  color: var(--text-muted); font-size: 13px;
}
</style>
