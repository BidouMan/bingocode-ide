"""
多文件发现与拼接模块：自动发现项目 .py 文件，自动注入 import
"""
import os
import ast
from code_transform import transform_while_true

def find_main_file(project_dir: str) -> str:
    """
    查找包含 while True 的主文件

    优先级：main.py > 包含 while True 的文件 > 第一个 .py 文件
    """
    py_files = []
    for f in os.listdir(project_dir):
        if f.endswith(".py") and not f.startswith("_"):
            py_files.append(f)

    if not py_files:
        return None

    # 优先找 main.py
    if "main.py" in py_files:
        return "main.py"

    # 找包含 while True 的文件
    for f in py_files:
        filepath = os.path.join(project_dir, f)
        with open(filepath, "r", encoding="utf-8") as fh:
            content = fh.read()
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.While):
                    if isinstance(node.test, ast.Constant) and node.test.value is True:
                        return f
                    elif isinstance(node.test, ast.Constant) and node.test.value == 1:
                        return f
        except SyntaxError:
            continue

    # 返回第一个 .py 文件
    return py_files[0]

def discover_and_merge(project_dir: str) -> str:
    """
    发现项目所有 .py 文件并合并为一个脚本

    Args:
        project_dir: 项目目录路径

    Returns:
        合并后的 Python 脚本字符串
    """
    # 查找所有 .py 文件
    py_files = []
    for f in sorted(os.listdir(project_dir)):
        if f.endswith(".py") and not f.startswith("_"):
            py_files.append(f)

    if not py_files:
        return ""

    # 查找主文件
    main_file = find_main_file(project_dir)
    if not main_file:
        main_file = py_files[0]

    # 生成 import 语句
    imports = []
    for f in py_files:
        if f == main_file:
            continue
        module_name = f[:-3]  # 去掉 .py
        imports.append(f"from {module_name} import *")

    # 读取主文件内容
    main_path = os.path.join(project_dir, main_file)
    with open(main_path, "r", encoding="utf-8") as fh:
        main_content = fh.read()

    # 转换 while True
    main_content = transform_while_true(main_content)

    # 拼接
    if imports:
        import_block = "\n".join(imports) + "\n\n"
        result = import_block + main_content
    else:
        result = main_content

    return result

if __name__ == "__main__":
    # 测试
    import sys
    if len(sys.argv) > 1:
        project_dir = sys.argv[1]
    else:
        project_dir = os.getcwd()

    result = discover_and_merge(project_dir)
    print(result)
