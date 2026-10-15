"""
AST 代码转换模块：将 while True: 循环转换为 generator
循环语义对齐 Scratch——for / while 循环每轮让出一帧，移动过程动画可见
"""
import ast


def _has_while_true(tree: ast.Module) -> bool:
    """检查 AST 中是否有 while True 循环"""
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            test = node.test
            if (isinstance(test, ast.Constant) and test.value is True) or \
               (isinstance(test, ast.Constant) and test.value == 1):
                return True
    return False


def _make_yield() -> ast.Expr:
    return ast.Expr(value=ast.Yield(value=ast.Constant(value=None)))


def _insert_loop_yields(node: ast.AST):
    """
    递归在循环体中插入 yield（Scratch 语义：循环每轮让出一帧）。

    - for：每轮结束 yield（对应 Scratch "重复执行 N 次"）
    - while（含 while True 和条件 while）：循环体开头 yield（保持原有
      while True 时序；并让 "while not 按键: continue" 这类等待写法
      不会在单帧内死循环卡死引擎）

    不进入函数/类定义——用户函数体里插 yield 会把函数变成 generator，
    调用处拿到 generator 对象而不再执行（旧式 def loop()+run() 写法同理保留）。
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(child, ast.For):
            child.body.append(_make_yield())
            _insert_loop_yields(child)
        elif isinstance(child, ast.While):
            # while True 与条件 while 均在开头 yield：保持原有 while True 时序，
            # 并让 "while not 按键: continue" 这类等待写法不会单帧死循环
            child.body.insert(0, _make_yield())
            _insert_loop_yields(child)
        else:
            _insert_loop_yields(child)


def _has_top_level_loop(tree: ast.Module) -> bool:
    """检查模块顶层（不在函数/类内）是否有 for / while 循环"""
    return any(isinstance(n, (ast.For, ast.While)) for n in tree.body)


def transform_while_true(source_code: str, func_name: str = '__game__') -> str:
    """
    将源代码转换为 generator，循环每轮让出一帧（Scratch 语义）

    两类脚本会被转换：
    1. 含 while True: 的游戏主循环脚本（原逻辑）
    2. 无 while True 但顶层含 for / while 循环的启动脚本
       （如 `for i in range(10): f.x += 5`——否则整段在启动瞬间同步跑完）

    Args:
        source_code: Python 源代码
        func_name: 生成的 generator 函数名
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return source_code

    if not _has_while_true(tree) and not _has_top_level_loop(tree):
        return source_code

    # 分离 import 语句和非 import 语句
    import_stmts = []
    other_stmts = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_stmts.append(ast.unparse(node))
        else:
            other_stmts.append(node)

    if not other_stmts:
        return source_code

    # 构建新模块：import 语句 + def func_name(): + 注册调用
    new_body = []
    for stmt in import_stmts:
        new_body.append(ast.parse(stmt).body[0])

    # 创建 def func_name(): 函数节点
    func_def = ast.FunctionDef(
        name=func_name,
        args=ast.arguments(posonlyargs=[], args=[], vararg=None,
                           kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
        body=other_stmts,
        decorator_list=[],
        returns=None,
    )

    # 递归给函数体内（while True 及嵌套的 for / 条件 while）插入 yield
    _insert_loop_yields(func_def)

    new_body.append(func_def)

    # 添加 register_generator(func_name()) 调用
    register_call = ast.parse(
        f'register_generator({func_name}())'
    ).body[0]
    new_body.append(register_call)

    new_tree = ast.Module(body=new_body, type_ignores=[])
    ast.fix_missing_locations(new_tree)
    return ast.unparse(new_tree)


if __name__ == '__main__':
    # 测试单文件
    test1 = """import sys
from bingo_engine import *

hero = Sprite('弓箭手')
load_map('地图1')

while True:
    if key_down('d'):
        hero.move(5)
"""
    print('=== 单文件 ===')
    print(transform_while_true(test1))

    # 测试带自定义函数名
    print('\n=== 自定义函数名 ===')
    print(transform_while_true(test1, func_name='__game_player__'))

    # 测试 for 循环与条件 while 的 yield 插入
    test2 = """x = 0
for i in range(3):
    x += 10
while x < 100:
    x += 1

def run10():
    for i in range(10):
        x += 1

while True:
    y = x
"""
    print('\n=== for / 条件 while / 用户函数 ===')
    print(transform_while_true(test2))
