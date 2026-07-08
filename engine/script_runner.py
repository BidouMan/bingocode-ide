"""
多文件发现与拼接模块：自动发现项目 .py 文件，自动注入 import
"""
import os
import ast
import keyword
from code_transform import transform_while_true


def _is_valid_identifier(name: str) -> bool:
    """检查是否是合法的 Python 标识符"""
    return name.isidentifier() and not keyword.iskeyword(name)


def _list_py_files(directory: str) -> list:
    """列出目录下所有 .py 文件，忽略隐藏文件和临时文件"""
    files = []
    for f in sorted(os.listdir(directory)):
        if not f.endswith('.py'):
            continue
        if f.startswith('.'):
            continue
        files.append(f)
    return files


def find_main_file(search_dir: str) -> str:
    """
    查找包含 while True 的主文件

    优先级：main.py > 包含 while True 的文件 > 第一个 .py 文件
    """
    py_files = _list_py_files(search_dir)
    if not py_files:
        return None

    # 优先找 main.py
    if 'main.py' in py_files:
        return 'main.py'

    # 找包含 while True 的文件
    for f in py_files:
        filepath = os.path.join(search_dir, f)
        with open(filepath, 'r', encoding='utf-8') as fh:
            content = fh.read()
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.While):
                    test = node.test
                    if (isinstance(test, ast.Constant) and test.value is True) or \
                       (isinstance(test, ast.Constant) and test.value == 1):
                        return f
        except SyntaxError:
            continue

    # 返回第一个 .py 文件
    return py_files[0]


def discover_and_merge(project_dir: str) -> str:
    """
    发现项目所有 .py 文件并合并为一个脚本

    扫描策略：
    1. 优先查找 project_dir/code/ 子目录
    2. 如果不存在，扫描 project_dir 本身

    Args:
        project_dir: 项目目录路径

    Returns:
        合并后的 Python 脚本字符串
    """
    # 确定扫描目录：优先 code/ 子目录
    code_dir = os.path.join(project_dir, 'code')
    if os.path.isdir(code_dir):
        search_dir = code_dir
    else:
        search_dir = project_dir

    # 查找所有 .py 文件
    py_files = _list_py_files(search_dir)
    if not py_files:
        return ''

    # 查找主文件
    main_file = find_main_file(search_dir)
    if not main_file:
        main_file = py_files[0]

    # 读取主文件内容
    main_path = os.path.join(search_dir, main_file)
    with open(main_path, 'r', encoding='utf-8') as fh:
        main_content = fh.read()

    # 转换 while True
    main_content = transform_while_true(main_content)

    # 生成其他文件的 import 语句（只处理合法标识符的文件）
    imports = []
    for f in py_files:
        if f == main_file:
            continue
        module_name = f[:-3]
        if _is_valid_identifier(module_name):
            imports.append(f'from {module_name} import *')

    # 拼接
    if imports:
        import_block = '\n'.join(imports) + '\n\n'
        result = import_block + main_content
    else:
        result = main_content

    return result


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        project_dir = sys.argv[1]
    else:
        project_dir = os.getcwd()

    result = discover_and_merge(project_dir)
    print(result)
