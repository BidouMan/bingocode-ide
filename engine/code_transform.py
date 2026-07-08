"""
AST 代码转换模块：将 while True: 循环转换为 generator
"""
import ast
import sys

class WhileTrueTransformer(ast.NodeTransformer):
    """将 while True: 循环体转换为 generator，插入 yield 语句"""

    def visit_While(self, node):
        # 检查是否是 while True: 或 while 1:
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            # 在循环体开头插入 yield
            yield_stmt = ast.Expr(value=ast.Yield(value=ast.Constant(value=None)))
            node.body.insert(0, yield_stmt)
            return node
        elif isinstance(node.test, ast.Constant) and node.test.value == 1:
            # while 1: 也支持
            yield_stmt = ast.Expr(value=ast.Yield(value=ast.Constant(value=None)))
            node.body.insert(0, yield_stmt)
            return node
        return node

def transform_while_true(source_code: str) -> str:
    """
    将源代码中的 while True: 循环转换为 generator

    Args:
        source_code: Python 源代码字符串

    Returns:
        转换后的源代码字符串
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return source_code  # 语法错误则原样返回

    # 检查是否有 while True 循环
    has_while_true = False
    for node in ast.walk(tree):
        if isinstance(node, ast.While):
            if isinstance(node.test, ast.Constant) and node.test.value is True:
                has_while_true = True
                break
            elif isinstance(node.test, ast.Constant) and node.test.value == 1:
                has_while_true = True
                break

    if not has_while_true:
        return source_code  # 无 while True，原样返回

    # 转换
    transformer = WhileTrueTransformer()
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)

    return ast.unparse(new_tree)

if __name__ == "__main__":
    # 测试
    test_code = """
while True:
    x = 1
    if key_down('a'):
        hero.move(5)
"""
    print("Original:")
    print(test_code)
    print("\nTransformed:")
    print(transform_while_true(test_code))
