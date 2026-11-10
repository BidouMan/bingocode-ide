"""
多文件发现与编译模块：自动发现项目 .py 文件，逐个编译成可执行代码对象

每个文件单独编译、在同一个 globals 里按顺序执行（与旧「拼接成一个大脚本」
行为一致），好处是运行时报错能定位到具体文件和学生编辑器里的真实行号。
"""
import os
import ast
import keyword
from code_transform import build_transformed_tree


class CodeErrors(Exception):
    """学生代码有语法错误：errors = [(文件名, 行号, 说明)]"""

    def __init__(self, errors):
        self.errors = errors
        super().__init__(
            '; '.join(f'{name} 第 {line} 行 {msg}' for name, line, msg in errors)
        )


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
    编译前要去掉这 4 行，否则报错行号会比学生编辑器里看到的行号大 4。
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


def _func_name(display_name: str, index: int) -> str:
    """用文件名生成 generator 函数名（去掉 .py 后缀），非法时用序号兜底"""
    name = f'__game_{display_name[:-3]}__'
    if not name.isidentifier() or keyword.iskeyword(name):
        return f'__game_{index}__'
    return name


def _compile_file(filepath: str, display_name: str, index: int):
    """读取并编译单个文件。

    返回 (代码对象, None)；语法错误时返回 (None, (文件名, 行号, 说明))，
    不抛异常，方便一次性收集所有写错的文件。
    """
    with open(filepath, 'r', encoding='utf-8') as fh:
        content = fh.read()

    # 去掉前端注入的 import 头，让行号与编辑器一致
    offset = _auto_import_offset(content)
    if offset:
        content = '\n'.join(content.splitlines()[offset:])

    try:
        tree = ast.parse(content, filename=filepath)
    except SyntaxError as e:
        return None, (display_name, max(1, e.lineno or 1), e.msg or '语法错误')

    # 含 while True 或顶层循环的文件转 generator（循环逐帧可见）
    new_tree = build_transformed_tree(tree, _func_name(display_name, index))
    if new_tree is None:
        new_tree = tree

    try:
        return compile(new_tree, filepath, 'exec'), None
    except SyntaxError as e:
        # ast.parse 放行、compile 才报的语法问题（如模块级 return）
        return None, (display_name, max(1, e.lineno or 1), e.msg or '语法错误')


def load_scripts(project_dir: str, target_file: str = None) -> list:
    """发现并编译本次要运行的所有 .py，返回 [(文件路径, 代码对象)]。

    策略：每个文件的 while True 都变成独立的 generator，各自注册到调度器。
    任何一个文件有语法错误都抛 CodeErrors（一次性列全，学生改起来更省事）。
    """
    # 如果指定了目标文件，只运行这一个文件
    if target_file and os.path.isfile(target_file):
        code, error = _compile_file(target_file, os.path.basename(target_file), 0)
        if error:
            raise CodeErrors([error])
        return [(target_file, code)]

    # 确定扫描目录：优先 code/ 子目录
    code_dir = os.path.join(project_dir, 'code')
    search_dir = code_dir if os.path.isdir(code_dir) else project_dir

    py_files = _list_py_files(search_dir)

    # 有运行清单时只执行清单里的文件：避免目录里的杂项 .py 被拼进来导致游戏跑不动
    manifest = _read_run_manifest(search_dir)
    if manifest is not None:
        available = set(py_files)
        py_files = [name for name in manifest if name in available]

    results = []
    errors = []
    for index, f in enumerate(py_files):
        filepath = os.path.join(search_dir, f)
        code, error = _compile_file(filepath, f, index)
        if error:
            errors.append(error)
        else:
            results.append((filepath, code))

    if errors:
        raise CodeErrors(errors)
    return results


if __name__ == '__main__':
    import sys
    project_dir = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    try:
        for path, code in load_scripts(project_dir):
            print(path, code.co_filename)
    except CodeErrors as err:
        for name, line, msg in err.errors:
            print(f'{name} 第 {line} 行 {msg}')
