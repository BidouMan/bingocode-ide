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

if __name__ == "__main__":
    test_simple_while_true()
    test_nested_while_true()
    test_no_while_true()
    print("All tests passed!")
