"""
多文件发现与拼接模块：自动发现项目 .py 文件，自动注入 import
"""
import os
import ast
import keyword
from code_transform import transform_while_true, _has_while_true


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


def discover_and_merge(project_dir: str) -> str:
    """
    发现项目所有 .py 文件并合并为一个脚本

    策略：每个文件的 while True 都变成独立的 generator，各自注册到调度器。
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

    # 收集所有 import 语句（去重）
    all_imports = []
    seen_imports = set()

    # 收集所有非 import 代码块
    code_blocks = []

    for f in py_files:
        filepath = os.path.join(search_dir, f)
        with open(filepath, 'r', encoding='utf-8') as fh:
            content = fh.read()

        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue

        # 提取 import 语句
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                stmt_str = ast.unparse(node)
                if stmt_str not in seen_imports:
                    seen_imports.add(stmt_str)
                    all_imports.append(stmt_str)

        # 检查是否有 while True
        if _has_while_true(tree):
            # 用文件名作为 generator 函数名（去掉 .py 后缀）
            module_name = f[:-3]
            func_name = f'__game_{module_name}__'
            # 确保函数名合法
            if not _is_valid_identifier(func_name):
                func_name = f'__game_{py_files.index(f)}__'
            transformed = transform_while_true(content, func_name=func_name)
            code_blocks.append(transformed)
        else:
            # 没有 while True 的文件，直接作为模块级代码
            code_blocks.append(content)

    # 拼接：import 语句 + 所有代码块
    parts = []
    if all_imports:
        parts.append('\n'.join(all_imports))
    parts.extend(code_blocks)

    return '\n\n'.join(parts)


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        project_dir = sys.argv[1]
    else:
        project_dir = os.getcwd()

    result = discover_and_merge(project_dir)
    print(result)
