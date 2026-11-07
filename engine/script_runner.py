"""
多文件发现与拼接模块：自动发现项目 .py 文件，自动注入 import
"""
import os
import ast
import keyword
from code_transform import transform_while_true, _has_while_true, _has_top_level_loop


def _is_valid_identifier(name: str) -> bool:
    """检查是否是合法的 Python 标识符"""
    return name.isidentifier() and not keyword.iskeyword(name)


# 运行清单：IDE 每次运行前写入，列出本次项目真正要执行的 .py 文件名（每行一个）。
# 目录里残留的其它 .py（旧项目包带入的、手动拷进来的）不再参与运行。
_RUN_MANIFEST = '.bingo_run_files'


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


def _read_run_manifest(directory: str):
    """读取运行清单；没有清单时返回 None（兼容旧项目，保持原有全量扫描行为）"""
    path = os.path.join(directory, _RUN_MANIFEST)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            return [line.strip() for line in fh if line.strip()]
    except OSError:
        return None


def _auto_import_offset(content: str) -> int:
    """计算 IDE 自动插入的 import 头占了几行。

    游戏模式运行前，前端会在每个代码文件开头加 4 行（sys.path + from bingo_engine import *）。
    语法错误的行号要减掉这 4 行，否则学生在编辑器里找不到报错的那一行。
    """
    lines = content.splitlines()
    if len(lines) < 4:
        return 0
    if (
        lines[0].strip() == 'import sys'
        and 'not in sys.path' in lines[1]
        and lines[2].strip().startswith('sys.path.insert')
        and lines[3].strip() in ('from bingo_engine import *', 'import bingo_engine')
    ):
        return 4
    return 0


def discover_and_merge(project_dir: str, target_file: str = None) -> str:
    """
    发现项目所有 .py 文件并合并为一个脚本

    Args:
        project_dir: 项目目录
        target_file: 指定要运行的文件路径（只运行这一个文件）

    策略：每个文件的 while True 都变成独立的 generator，各自注册到调度器。
    """
    # 如果指定了目标文件，只运行这一个文件
    if target_file and os.path.isfile(target_file):
        with open(target_file, 'r', encoding='utf-8') as fh:
            content = fh.read()
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            offset = _auto_import_offset(content)
            raise SyntaxError(
                f"{os.path.basename(target_file)} 第 {max(1, e.lineno - offset)} 行语法错误：{e.msg}"
            ) from None

        # 含 while True 或顶层循环的文件都转 generator（循环逐帧可见）
        if _has_while_true(tree) or _has_top_level_loop(tree):
            module_name = os.path.basename(target_file)[:-3]
            func_name = f'__game_{module_name}__'
            if not _is_valid_identifier(func_name):
                func_name = '__game_main__'
            return transform_while_true(content, func_name=func_name)
        return content

    # 确定扫描目录：优先 code/ 子目录
    code_dir = os.path.join(project_dir, 'code')
    if os.path.isdir(code_dir):
        search_dir = code_dir
    else:
        search_dir = project_dir

    # 查找所有 .py 文件
    py_files = _list_py_files(search_dir)

    # 有运行清单时只执行清单里的文件：避免目录里的杂项 .py 被拼进来导致游戏跑不动
    manifest = _read_run_manifest(search_dir)
    if manifest is not None:
        available = set(py_files)
        py_files = [name for name in manifest if name in available]

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
        except SyntaxError as e:
            # 任何一个文件有语法错误都直接报出来并停止运行。
            # 以前是跳过这个文件、继续跑其它文件：学生代码写了一半（少冒号/括号）时，
            # 坏文件被悄悄丢掉，剩下的文件照常运行，看起来像 IDE 卡住且没有任何提示。
            offset = _auto_import_offset(content)
            raise SyntaxError(f"{f} 第 {max(1, e.lineno - offset)} 行语法错误：{e.msg}") from None

        # 提取 import 语句
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                stmt_str = ast.unparse(node)
                if stmt_str not in seen_imports:
                    seen_imports.add(stmt_str)
                    all_imports.append(stmt_str)

        # 含 while True 或顶层循环的文件转 generator（循环逐帧可见）
        if _has_while_true(tree) or _has_top_level_loop(tree):
            # 用文件名作为 generator 函数名（去掉 .py 后缀）
            module_name = f[:-3]
            func_name = f'__game_{module_name}__'
            # 确保函数名合法
            if not _is_valid_identifier(func_name):
                func_name = f'__game_{py_files.index(f)}__'
            transformed = transform_while_true(content, func_name=func_name)
            code_blocks.append(transformed)
        else:
            # 纯函数/常量定义文件，直接作为模块级代码
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
