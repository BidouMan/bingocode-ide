"""学生代码报错：统一翻译成小学生能看懂的中文提示（带出错文件和行号）。

什么时候来这里改：报错文案、行号定位规则、错误类型 → 中文提示的映射。
所有面向学生的报错都输出到 stderr（前端按红色错误显示），
stdout 只留给游戏渲染协议和学生的 print 输出。
"""
import os
import re
import sys
import traceback

_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))


def _is_engine_frame(filename: str) -> bool:
    """引擎自身的栈帧（game_loop / game_control ...）不算学生的出错位置"""
    try:
        return os.path.abspath(filename).startswith(_ENGINE_DIR + os.sep)
    except Exception:
        return False


def _locate(exc):
    """从异常栈里找出最后一条属于学生代码的帧，返回 (文件名, 行号)"""
    frames = traceback.extract_tb(exc.__traceback__)
    chosen = None
    for frame in frames:
        if not _is_engine_frame(frame.filename):
            chosen = frame
    if chosen is None and frames:
        chosen = frames[-1]
    if chosen is None or not chosen.filename:
        return None, None
    return os.path.basename(chosen.filename), chosen.lineno


def _syntax_hint(msg: str) -> str:
    """把 Python 的英文语法错误说明翻译成提示（未知的保留原文，方便老师排查）"""
    text = (msg or '').strip()
    rules = [
        ("expected ':'", '少了冒号（:）'),
        ("was never closed", '括号或引号没有闭合'),
        ("unexpected EOF", '代码没写完（括号或引号没闭合）'),
        ("unexpected end of file", '代码没写完（括号或引号没闭合）'),
        ("unmatched ')'", '多了一个右括号'),
        ("unmatched ']'", '多了一个右方括号'),
        ("unexpected indent", '多了缩进'),
        ("expected an indented block", '这一行应该往里缩进'),
        ("unindent does not match", '缩进没有对齐'),
        ("invalid character", '有打错的符号（比如中文标点）'),
        ("invalid decimal literal", '数字写错了'),
        ("cannot assign to", '这里不能赋值'),
        ("invalid syntax", '语法不对，检查一下这一行'),
    ]
    for key, hint in rules:
        if key in text:
            return hint
    return f'语法错误：{text}' if text else '语法错误，检查一下这一行'


def _hint(exc) -> str:
    """把异常翻译成一句小学生能看懂的话"""
    name = type(exc).__name__
    msg = str(exc)

    if isinstance(exc, NameError):
        target = getattr(exc, 'name', None)
        if not target:
            matched = re.search(r"name '([^']+)' is not defined", msg)
            target = matched.group(1) if matched else ''
        if target:
            return f"名字 '{target}' 没有定义，检查一下是不是写错了"
        return '有名字没有定义，检查一下拼写'

    if isinstance(exc, AttributeError):
        matched = (
            re.search(r"'([^']+)' object has no attribute '([^']+)'", msg)
            or re.search(r"module '([^']+)' has no attribute '([^']+)'", msg)
        )
        if matched:
            obj, attr = matched.group(1), matched.group(2)
            if obj == 'NoneType':
                return f"这里还是个空值（None），不能使用 '{attr}'"
            return f"类型 '{obj}' 没有 '{attr}' 这个方法或属性，检查一下名字有没有写错"
        return f'没有这个方法或属性，检查一下名字（{msg}）'

    if isinstance(exc, ModuleNotFoundError):
        return f"找不到模块 '{getattr(exc, 'name', '')}'，检查一下 import 后面的名字"
    if isinstance(exc, ImportError):
        return f'导入失败：{msg}'
    if isinstance(exc, ZeroDivisionError):
        return '不能除以 0'
    if isinstance(exc, IndexError):
        return '列表或字符串没有那么长（下标超出范围了）'
    if isinstance(exc, KeyError):
        return f'字典里没有 {msg} 这个键'
    if isinstance(exc, FileNotFoundError):
        filename = getattr(exc, 'filename', '') or ''
        return f'找不到文件 {filename}'.strip()
    if isinstance(exc, TypeError):
        return f'类型用错了：{msg}'
    if isinstance(exc, ValueError):
        return f'数值或内容不对：{msg}'
    if isinstance(exc, RecursionError):
        return '函数自己调用自己的次数太多了'
    if isinstance(exc, (IndentationError, TabError)):
        return '缩进不对，检查每一行前面的空格有没有对齐'
    if isinstance(exc, SyntaxError):
        return _syntax_hint(exc.msg or msg)
    return f'{name}: {msg}'


def _emit(text: str):
    """报错统一走 stderr：前端会以红色错误显示并自动打开控制台"""
    try:
        print(text, file=sys.stderr, flush=True)
    except Exception:
        pass


def report_error(message: str):
    """引擎自己发现的错误（例如没找到代码文件）"""
    _emit(f'[错误] {message}')


def report_code_errors(errors):
    """语法错误：errors = [(文件名, 行号, 说明)]，一次性全部列出来"""
    for name, line, msg in errors:
        _emit(f'[错误] {name} 第 {line} 行：{_syntax_hint(msg)}')


def report_user_error(exc):
    """运行出错：带上出错文件和学生编辑器里的真实行号"""
    filename, line = _locate(exc)
    if filename and line:
        where = f'{filename} 第 {line} 行'
    elif filename:
        where = filename
    else:
        where = '你的代码'
    _emit(f'[错误] {where}：{_hint(exc)}')
