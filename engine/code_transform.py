"""
AST 代码转换模块：将 while True: 循环转换为 generator
"""
import ast


def transform_while_true(source_code: str) -> str:
    """
    将源代码中的 while True: 循环转换为 generator

    策略：用 AST 分离 import 语句（留在模块级别）和其余代码（包进 def __game__()）
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return source_code

    # 检查是否有 while True 循环
    has_while_true = False
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            test = node.test
            if (isinstance(test, ast.Constant) and test.value is True) or \
               (isinstance(test, ast.Constant) and test.value == 1):
                has_while_true = True
                break

    if not has_while_true:
        return source_code

    # 用 AST 分离 import 语句和非 import 语句
    import_stmts = []
    other_stmts = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_stmts.append(ast.unparse(node))
        else:
            other_stmts.append(node)

    # 对非 import 语句：插入 yield，包进 def __game__()
    if other_stmts:
        # 找到 while True 节点并插入 yield
        for node in other_stmts:
            if isinstance(node, ast.While):
                test = node.test
                if (isinstance(test, ast.Constant) and test.value is True) or \
                   (isinstance(test, ast.Constant) and test.value == 1):
                    yield_stmt = ast.Expr(value=ast.Yield(value=ast.Constant(value=None)))
                    node.body.insert(0, yield_stmt)

        # 构建新的模块：import 语句 + def __game__()
        new_body = []
        for stmt in import_stmts:
            new_body.append(ast.parse(stmt).body[0])

        # 创建 def __game__(): 函数节点
        func_body = []
        for stmt in other_stmts:
            func_body.append(stmt)

        func_def = ast.FunctionDef(
            name='__game__',
            args=ast.arguments(posonlyargs=[], args=[], vararg=None, kwonlyargs=[], kw_defaults=[], kwarg=None, defaults=[]),
            body=func_body,
            decorator_list=[],
            returns=None,
        )
        new_body.append(func_def)

        new_tree = ast.Module(body=new_body, type_ignores=[])
        ast.fix_missing_locations(new_tree)
        return ast.unparse(new_tree)
    else:
        # 只有 import 语句，没有其他代码 — 不需要 generator
        return source_code


if __name__ == "__main__":
    test_code = """import sys
from bingo_engine import *

hero = Sprite('弓箭手')
load_map('地图1')

while True:
    if key_down('d'):
        hero.move(5)
"""
    print("Original:")
    print(test_code)
    print("\nTransformed:")
    print(transform_while_true(test_code))
