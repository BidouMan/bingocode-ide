"""
多文件发现与编译模块：自动发现项目 .py 文件，逐个编译成可执行代码对象

每个文件单独编译、在同一个 globals 里按顺序执行（与旧「拼接成一个大脚本」
行为一致），好处是运行时报错能定位到具体文件和学生编辑器里的真实行号。
"""
import os
import re
import io
import ast
import tokenize
import inspect
import keyword
from code_transform import build_transformed_tree


class CodeErrors(Exception):
    """学生代码有语法错误：errors = [(文件名, 行号, 原始说明, 出错行源码, 上一行语句源码)]"""

    def __init__(self, errors):
        self.errors = errors
        super().__init__(
            '; '.join(f'{name} 第 {line} 行 {msg}' for name, line, msg, _text, _prev in errors)
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


def _syntax_error_info(exc, lines: list, display_name: str) -> tuple:
    """把 SyntaxError 整理成 (文件名, 行号, 原始说明, 出错行源码, 上一行语句源码)。

    「expected an indented block after 'for' statement on line 1」有两种情况，提示要分开：
    - 下一行是空的/没有内容 → 指到「for i in range(10):」这一行，说「下面还没写内容」
    - 下一行写了代码但没缩进 → 指到那一行，并把「for ...:」一起带出来，
      否则学生会以为「我明明写了啊」
    """
    msg = exc.msg or '语法错误'
    lineno = exc.lineno or 1

    def line_text(n: int) -> str:
        return lines[n - 1] if 0 < n <= len(lines) else ''

    matched = re.search(r'on line (\d+)', msg)

    if 'expected an indented block' in msg and matched:
        stmt_line = int(matched.group(1))
        code_text = line_text(lineno)
        # lineno > stmt_line 说明下一行确实写了代码（只是没缩进）；
        # 文件在冒号行就结束（EOF）时 lineno 会等于 stmt_line
        if lineno > stmt_line and code_text.strip():
            return (display_name, lineno, msg, code_text, line_text(stmt_line))
        return (display_name, stmt_line, msg, line_text(stmt_line), '')

    return (display_name, max(1, lineno), msg, line_text(lineno), '')


def _check_indent(content: str, display_name: str):
    """缩进规范检查：每层缩进必须是 4 个空格的整数倍，且不使用 Tab。

    Python 本身只要同一层缩进一致就能运行——缩进 1 个空格、3 个空格甚至 Tab 都跑得起来。
    但小学生应该统一用 4 个空格（编辑器 Tab 键插入的就是 4 个空格），
    这里提前拦下来，提示比 Python 自带的 IndentationError 更直接。

    返回 (文件名, 行号, 说明, 源码行, 上一行语句源码) 或 None（缩进没问题）。
    """
    lines = content.splitlines()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(content).readline):
            if tok.type != tokenize.INDENT:
                continue
            lineno = tok.start[0]
            text = lines[lineno - 1] if 0 < lineno <= len(lines) else ''
            if '\t' in tok.string:
                return (display_name, lineno, '缩进请用空格，不要用 Tab 键', text, '')
            width = len(tok.string.expandtabs(4))
            if width % 4:
                return (
                    display_name,
                    lineno,
                    f'缩进要用 4 个空格（这一行缩进了 {width} 个空格）',
                    text,
                    '',
                )
    except (tokenize.TokenError, IndentationError, SyntaxError):
        # 括号没闭合时 tokenize 会中断，这类问题交给语法错误提示处理
        return None
    return None


def _callable_member_names():
    """角色（Sprite）上所有「方法」的名字（不含属性如 x / y / angle）。

    用于抓「忘了写括号」：`if s.is_clicked:` 里的方法对象永远是真值，
    Python 不报错，游戏却会一直条件成立。
    """
    try:
        from sprite import Sprite
    except Exception:
        return frozenset()

    names = set()
    for name in dir(Sprite):
        if name.startswith('_'):
            continue
        # 属性（property）不会被算进来：if s.x: 是正常写法
        if callable(getattr(Sprite, name, None)):
            names.add(name)
    return frozenset(names)


def _engine_function_names():
    """引擎提供的全局函数（key_down / time_passed / is_touch ...），同样不能漏括号"""
    try:
        import bingo_engine
    except Exception:
        return frozenset()

    names = set()
    for name in getattr(bingo_engine, '__all__', []):
        if name.startswith('_'):
            continue
        # 只认函数：Sprite / Timer 这类类和常量不算，if Sprite: 不是本条要管的问题
        if inspect.isfunction(getattr(bingo_engine, name, None)):
            names.add(name)
    return frozenset(names)


def _user_function_names(tree):
    """学生自己在文件里定义的函数（def is_win(): ...）"""
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
    return names


def _iter_condition_operands(node):
    """拆开条件表达式，取出真正被判断的那几段（处理 not / and / or / 比较）"""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        yield from _iter_condition_operands(node.operand)
    elif isinstance(node, ast.BoolOp):
        for value in node.values:
            yield from _iter_condition_operands(value)
    elif isinstance(node, ast.Compare):
        yield from _iter_condition_operands(node.left)
        for comparator in node.comparators:
            yield from _iter_condition_operands(comparator)
    else:
        yield node


def _check_bare_call(tree, lines, display_name):
    """查「函数/方法忘了写括号」——两种写法都会被 Python 静默放过：

    1. 条件里直接用：`if s.is_clicked:` / `if is_win:`，永远成立
    2. 单独一行写：`s.goto` / `is_win`，什么也不做，程序照常往下跑

    检查三种来源：角色方法、引擎全局函数、学生自己 def 的函数。
    """
    member_names = _callable_member_names()
    function_names = _engine_function_names() | _user_function_names(tree)

    def bare_target(node):
        """这个节点是不是「光秃秃引用了一个函数/方法」"""
        if isinstance(node, ast.Attribute) and node.attr in member_names:
            return True
        if isinstance(node, ast.Name) and node.id in function_names:
            return True
        return False

    hits = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.While)):
            operands = list(_iter_condition_operands(node.test))
        elif isinstance(node, ast.Expr):
            # 单独一行的表达式：值被丢掉，`s.goto` 等于什么也没做
            operands = [node.value]
        else:
            continue

        for operand in operands:
            if bare_target(operand):
                hits.append(operand)

    if not hits:
        return None

    # 按行号取最靠前的一个，学生从上往下改
    target = min(hits, key=lambda n: (n.lineno, n.col_offset))
    try:
        expr = ast.unparse(target)
    except Exception:
        expr = getattr(target, 'attr', None) or getattr(target, 'id', '')
    lineno = target.lineno
    text = lines[lineno - 1] if 0 < lineno <= len(lines) else ''
    return (
        display_name,
        lineno,
        f'{expr} 后面少了一对括号，要写成 {expr}()',
        text,
        '',
    )


def _check_while_in_function(tree, lines, display_name):
    """自定义函数/类里禁止写 while 循环（对初学者统一的最粗规则）。

    函数体和类体都是普通 Python：执行时没有机会让出一帧。
    只要 while 的条件没当场变成 False（等按键、等碰撞、条件写错），
    整个游戏就会卡死在这一帧。与其让学生理解"等待型 while vs 有限 while"，
    不如统一规定：函数/类里只写 for，重复/等待的动作放回 while True 主循环。
    """
    hits = []  # [(while 节点, 作用域名)]

    def visit(node, scope_name):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                visit(child, child.name)
            elif isinstance(child, ast.While):
                if scope_name:
                    hits.append((child, scope_name))
                visit(child, scope_name)
            else:
                visit(child, scope_name)

    visit(tree, "")
    if not hits:
        return None

    node, scope_name = min(hits, key=lambda item: item[0].lineno)
    lineno = node.lineno
    text = lines[lineno - 1] if 0 < lineno <= len(lines) else ''
    return (
        display_name,
        lineno,
        f'自定义函数/类「{scope_name}」里不能写 while 循环，游戏会卡在这一帧。'
        '要重复执行请写在 while True 主循环里，固定次数请用 for i in range(...)',
        text,
        '',
    )


def _compile_file(filepath: str, display_name: str, index: int):
    """读取并编译单个文件。

    返回 (代码对象, None)；语法错误时返回 (None, (文件名, 行号, 说明, 源码行, 上一行语句))，
    不抛异常，方便一次性收集所有写错的文件。
    """
    with open(filepath, 'r', encoding='utf-8') as fh:
        content = fh.read()

    # 去掉前端注入的 import 头，让行号与编辑器一致
    offset = _auto_import_offset(content)
    if offset:
        content = '\n'.join(content.splitlines()[offset:])

    lines = content.splitlines()

    try:
        tree = ast.parse(content, filename=filepath)
    except SyntaxError as e:
        return None, _syntax_error_info(e, lines, display_name)

    # 语法没问题后再查缩进：1 / 3 / 6 个空格虽然 Python 能跑，但小学生要统一用 4 个
    bad_indent = _check_indent(content, display_name)
    if bad_indent:
        return None, bad_indent

    # 函数/方法忘了写括号：if s.is_clicked: / if is_win: 永远成立，不拦下来会一直执行
    bare_call = _check_bare_call(tree, lines, display_name)
    if bare_call:
        return None, bare_call

    # 自定义函数里不允许 while（函数体不会让出帧，容易把整个游戏卡死）
    while_in_function = _check_while_in_function(tree, lines, display_name)
    if while_in_function:
        return None, while_in_function

    # 含 while True 或顶层循环的文件转 generator（循环逐帧可见）
    new_tree = build_transformed_tree(tree, _func_name(display_name, index))
    if new_tree is None:
        new_tree = tree

    try:
        return compile(new_tree, filepath, 'exec'), None
    except SyntaxError as e:
        # ast.parse 放行、compile 才报的语法问题（如模块级 return）
        return None, _syntax_error_info(e, lines, display_name)


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
        for name, line, msg, text, prev in err.errors:
            print(f'{name} 第 {line} 行 {msg} | {text.strip()} | {prev.strip()}')
