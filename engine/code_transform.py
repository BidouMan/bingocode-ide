"""
AST 代码转换模块：将 while True: 循环转换为 generator
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


def transform_while_true(source_code: str, func_name: str = '__game__') -> str:
    """
    将源代码中的 while True: 循环转换为 generator

    Args:
        source_code: Python 源代码
        func_name: 生成的 generator 函数名
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return source_code

    if not _has_while_true(tree):
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

    # 对非 import 语句：插入 yield，包进 generator 函数
    for node in other_stmts:
        if isinstance(node, ast.While):
            test = node.test
            if (isinstance(test, ast.Constant) and test.value is True) or \
               (isinstance(test, ast.Constant) and test.value == 1):
                yield_stmt = ast.Expr(value=ast.Yield(value=ast.Constant(value=None)))
                node.body.insert(0, yield_stmt)

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
