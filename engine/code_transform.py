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


# 循环里出现这些「增量 / 按时间」动作时，学生想看到过程，循环才逐帧让出：
# 增量移动、逐步显示（say）、按时间播放动画（play）、等待
_STEP_CALLS = {
    "move", "add_x", "add_y", "add_scale", "edge_bounce",
    "say", "play", "wait", "time_passed",
}
# 增量赋值（s.x += 5）同上；绝对赋值（s.x = 30 / goto）算「一次性摆好位置」，
# 批量创建角色后摆位不应该被拖成逐帧出现
_STEP_AUG_ATTRS = {"x", "y", "pos", "angle", "scale"}


def _collect_functions(node: ast.AST) -> dict:
    """收集作用域内的函数定义（含嵌套），供穿透分析用户自定义函数"""
    funcs = {}
    for sub in ast.walk(node):
        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs[sub.name] = sub
    return funcs


def _call_name(node: ast.Call) -> str:
    """取调用名：s.move(...) -> move；move(...) -> move"""
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _has_step_op(stmts, funcs: dict, seen=None) -> bool:
    """判断一段语句里有没有「必须逐帧才看得见」的操作。

    规则对齐学生写法：增量动作（move / add_x / s.x += 5 / say / play）逐帧，
    绝对动作（Sprite() 创建、s.x = 30、goto、delete）同一帧直接生效。
    嵌套循环体内的动作由嵌套循环自己让出帧，这里不重复计算；
    调用用户自定义函数时递归穿透函数体（函数体不会被插入 yield）。
    """
    seen = seen or frozenset()
    stack = list(stmts)
    while stack:
        node = stack.pop()
        # 函数/类定义不在本层执行，交给调用处穿透分析
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            # 嵌套循环自己会 yield，只看它的迭代/条件表达式
            stack.append(node.iter if isinstance(node, ast.For) else node.test)
            continue
        if isinstance(node, ast.Call):
            name = _call_name(node)
            if name in _STEP_CALLS:
                return True
            func = funcs.get(name)
            if func is not None and name not in seen:
                if _has_step_op(func.body, funcs, seen | {name}):
                    return True
        elif isinstance(node, ast.AugAssign):
            target = node.target
            if isinstance(target, ast.Attribute) and target.attr in _STEP_AUG_ATTRS:
                return True
        stack.extend(ast.iter_child_nodes(node))
    return False


def _insert_loop_yields(node: ast.AST, funcs: dict = None):
    """
    递归在循环体中插入 yield（Scratch 语义：循环每轮让出一帧）。

    - for：只有循环体里有「看得见的过程」（增量移动 / say / play / 等待）
      才在每轮结束 yield；纯创建、纯摆位、纯计算、纯列表操作同一帧跑完，
      否则 for 批量创建角色会一个一个蹦出来
    - while（含 while True 和条件 while）：循环体开头 yield（保持原有
      while True 时序；并让 "while not 按键: continue" 这类等待写法
      不会在单帧内死循环卡死引擎）

    不进入函数/类定义——用户函数体里插 yield 会把函数变成 generator，
    调用处拿到 generator 对象而不再执行（旧式 def loop()+run() 写法同理保留）。
    """
    funcs = funcs or {}
    for child in ast.iter_child_nodes(node):
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(child, ast.For):
            if _has_step_op(child.body, funcs):
                child.body.append(_make_yield())
            _insert_loop_yields(child, funcs)
        elif isinstance(child, ast.While):
            # while True 与条件 while 均在开头 yield：保持原有 while True 时序，
            # 并让 "while not 按键: continue" 这类等待写法不会单帧死循环
            child.body.insert(0, _make_yield())
            _insert_loop_yields(child, funcs)
        else:
            _insert_loop_yields(child, funcs)


def _has_own_yield(stmts) -> bool:
    """判断生成函数的自身作用域里有没有 yield（不进入嵌套函数/类）"""
    stack = list(stmts)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        if isinstance(node, (ast.Yield, ast.YieldFrom)):
            return True
        stack.extend(ast.iter_child_nodes(node))
    return False


def _has_top_level_loop(tree: ast.Module) -> bool:
    """检查模块顶层（不在函数/类内）是否有 for / while 循环"""
    return any(isinstance(n, (ast.For, ast.While)) for n in tree.body)


def _target_names(node) -> list:
    """收集赋值目标里的变量名（支持 Name / 元组 / 列表 / 星号）"""
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, (ast.Tuple, ast.List)):
        names = []
        for elt in node.elts:
            names.extend(_target_names(elt))
        return names
    if isinstance(node, ast.Starred):
        return _target_names(node.value)
    return []


def _scope_bound_names(stmts) -> set:
    """收集生成函数作用域内绑定的变量名（不进入嵌套函数/类）

    转换会把整个模块塞进一个函数，原本的模块级变量（score、hero…）都变成了
    这个函数的局部变量。嵌套函数里的 `global score` 仍指向模块全局，会找不到
    变量，因此需要识别出这些"其实是外层局部变量"的名字，把 global 改写成 nonlocal。
    """
    bound = set()
    declared_global = set()
    stack = list(stmts)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            # 函数/类名本身绑定在外层作用域，但不进入其函数体
            bound.add(node.name)
            continue
        if isinstance(node, ast.Lambda):
            continue
        if isinstance(node, ast.Global):
            declared_global.update(node.names)
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                bound.update(_target_names(target))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            bound.update(_target_names(node.target))
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            bound.update(_target_names(node.target))
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    bound.update(_target_names(item.optional_vars))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound.add(alias.asname or alias.name.split('.')[0])
        stack.extend(ast.iter_child_nodes(node))
    return bound - declared_global


class _GlobalToNonlocal(ast.NodeTransformer):
    """把生成函数内部直接嵌套函数里的 global 改写成 nonlocal

    只处理"生成函数的直接嵌套函数"（回调最常见的位置）；更深层的嵌套函数
    其 global 指向中间函数，保持原样避免误改。
    """

    def __init__(self, bound_names):
        self._bound = bound_names
        self._depth = 0

    def visit_FunctionDef(self, node):
        self._depth += 1
        # 深度 1 = 生成函数本身，深度 2 = 直接嵌套的回调函数；
        # 两者都要向下遍历才能找到 global，深度 3 起不再进入
        if self._depth <= 2:
            self.generic_visit(node)
        self._depth -= 1
        return node

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node):
        # lambda 里不能写 global，无需处理
        return node

    def visit_Global(self, node):
        # 只改写直接嵌套函数里的 global（生成函数自身作用域的 global 保持原样）
        if self._depth != 2:
            return node
        converted = [n for n in node.names if n in self._bound]
        kept = [n for n in node.names if n not in self._bound]
        nodes = []
        if converted:
            nodes.append(ast.copy_location(ast.Nonlocal(names=converted), node))
        if kept:
            nodes.append(ast.copy_location(ast.Global(names=kept), node))
        return nodes or node


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

    # 嵌套函数（on_receive / on_touch_group 回调）里的 global 其实指向生成函数的
    # 局部变量，改写成 nonlocal，否则 score += 1 会报 name 'score' is not defined
    bound_names = _scope_bound_names(func_def.body)
    if bound_names:
        _GlobalToNonlocal(bound_names).visit(func_def)

    # 递归给函数体内（while True 及嵌套的 for / 条件 while）插入 yield
    # funcs 用于穿透分析循环体里调用的用户自定义函数
    _insert_loop_yields(func_def, _collect_functions(func_def))

    # 一次 yield 都没插进去时（例如脚本只有「顶层 for 批量创建角色」），
    # 这个函数就不是 generator，调用后立刻返回 None，
    # register_generator(None) 会让主循环报「'NoneType' object is not an iterator」。
    # 这类脚本本来就是一帧跑完，直接返回原源码同步执行即可。
    if not _has_own_yield(func_def.body):
        return source_code

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
