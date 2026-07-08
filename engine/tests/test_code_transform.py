import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from code_transform import transform_while_true

def test_simple_while_true():
    code = """
while True:
    x = 1
    y = 2
"""
    result = transform_while_true(code)
    assert "yield" in result
    assert "while True:" in result

def test_nested_while_true():
    code = """
while True:
    for i in range(10):
        x = i
"""
    result = transform_while_true(code)
    assert "yield" in result

def test_no_while_true():
    code = """
x = 1
y = 2
def foo():
    pass
"""
    result = transform_while_true(code)
    assert result == code  # 无转换，原样返回

def test_generator_function_wrapping():
    """验证 while True 代码被包装在 generator 函数中"""
    code = """
while True:
    x = 1
    y = 2
"""
    result = transform_while_true(code)
    assert "def __game__()" in result
    assert "yield" in result
    # 验证生成的代码是有效的 Python 并产生 generator
    exec_globals = {}
    exec(result, exec_globals)
    game_func = exec_globals.get("__game__")
    assert game_func is not None, "__game__ function not found"
    import types
    gen = game_func()
    assert isinstance(gen, types.GeneratorType), "Not a generator"

if __name__ == "__main__":
    test_simple_while_true()
    test_nested_while_true()
    test_no_while_true()
    test_generator_function_wrapping()
    print("All tests passed!")
