"""学生代码报错：统一翻译成小学生能看懂的中文提示（带出错文件和行号）。

什么时候来这里改：报错文案、行号定位规则、错误类型 → 中文提示的映射。
所有面向学生的报错都输出到 stderr（前端按红色错误显示），
stdout 只留给游戏渲染协议和学生的 print 输出。

提示写法原则：
- 直接说「哪一行、哪里不对、要怎么改」，不要只说「语法错误」「缩进不对」
- 尽量带出学生写的那一行内容（「while True:」），一眼能找到位置
- 名字写错时给出正确的名字（是不是想写 move？）
"""
import os
import re
import sys
import traceback
import unicodedata

_ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))

# 语句关键字 → 冒号后面要写什么，用于「冒号后面没写内容」的提示
_BLOCK_WORDS = {
    'while': '要重复做的事',
    'for': '要重复做的事',
    'if': '条件成立时要做什么',
    'elif': '条件成立时要做什么',
    'else': '这里要做的事',
    'def': '这个函数要做的事',
    'class': '这个类里面的内容',
    'with': '这里要做的事',
    'try': '这里要做的事',
    'except': '出错时要做什么',
    'finally': '最后要做的事',
}

# 括号英文 → 中文名，用于「括号没配对」的提示
_BRACKET_PAIRS = {'(': ')', '[': ']', '{': '}'}

# 中文标点的名字：学生用了中文逗号/括号时，直接说出名字，比只贴符号清楚
_FULLWIDTH_NAMES = {
    '，': '逗号', '。': '句号', '：': '冒号', '；': '分号',
    '（': '左括号', '）': '右括号', '【': '左方括号', '】': '右方括号',
    '！': '感叹号', '？': '问号', '、': '顿号',
}

# 中文引号不会被 NFKC 转成英文引号，单独映射
_QUOTE_CHARS = {'“': '"', '”': '"', '‘': "'", '’': "'"}


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


def _short(text: str, limit: int = 40) -> str:
    """把学生写的长行截短，避免整条提示被挤爆"""
    text = (text or '').strip()
    return text if len(text) <= limit else text[:limit] + '…'


def _quote_line(text: str) -> str:
    """把学生写的那一行原样带出来（后面补一个空格便于拼接），没有就返回空串"""
    text = _short(text)
    return f'{text} ' if text else ''


def _syntax_hint(msg: str, text: str = '', prev: str = '') -> str:
    """把 Python 的英文语法错误说明翻译成小学生能看懂的话。

    text = 出错那一行的源码；prev = 相关的上一行语句（如 for i in range(10):）。
    """
    msg = (msg or '').strip()
    line = _quote_line(text)
    prev_line = _quote_line(prev)

    # 已经是我们自己写好的中文提示（如缩进规范检查），直接原样显示
    if re.search(r'[\u4e00-\u9fff]', msg):
        return msg

    # ── 冒号后面没内容 / 有内容但没缩进（最高频的「写一半」错误）──────────
    if 'expected an indented block' in msg:
        if prev_line and line:
            # 下一行写了代码，只是没缩进：说清要写在 for ... 的里面
            return f'{line}要缩进 4 个空格，写在 {prev_line}的里面'
        matched = re.search(r"after '(\w+)' statement", msg)
        if 'function definition' in msg:
            todo = '这个函数要做的事'
        elif 'class definition' in msg:
            todo = '这个类里面的内容'
        else:
            todo = _BLOCK_WORDS.get(matched.group(1), '这里要做的事') if matched else '这里要做的事'
        if line:
            return f'{line}下面还没写内容，请缩进 4 个空格后写{todo}'
        return f'这一行下面还没写内容，请缩进 4 个空格后写{todo}'

    # ── 少了冒号 ──────────────────────────────────────────────────
    if "expected ':'" in msg:
        if line:
            return f'{line}末尾少了冒号，if、for、while、def 这类语句写完都要加冒号'
        return '这一行末尾少了冒号，if、for、while、def 这类语句写完都要加冒号'

    # ── 缩进问题 ──────────────────────────────────────────────────
    if 'unexpected indent' in msg:
        if line:
            return f'{line}前面多了空格，要和上面的代码对齐'
        return '这一行前面多了空格，要和上面的代码对齐'
    if 'unindent does not match' in msg or 'inconsistent use of tabs' in msg:
        return '这一行前面的空格数和上面不一样，要和上一行对齐'

    # ── 中文标点（小学生极高频）────────────────────────────────────
    if 'invalid non-printable character' in msg:
        # 典型情况：全角空格。这种字符看不见，必须说清楚
        matched = re.search(r'U\+([0-9A-Fa-f]+)', msg)
        char = chr(int(matched.group(1), 16)) if matched else ''
        if char == '　':
            return '这里输入的是全角空格，要换成普通的空格'
        return '这一行里有一个看不见的特殊符号，删掉重新输入'

    if 'invalid character' in msg:
        bad = re.search(r"invalid character ['\"‘’“”]?(.+?)['\"‘’“”]? ?\(U\+", msg)
        char = bad.group(1) if bad else ''
        fixed = _QUOTE_CHARS.get(char) or unicodedata.normalize('NFKC', char)
        if char and fixed != char and fixed.isprintable():
            if char in _QUOTE_CHARS:
                return f'这里输入的是中文引号，要换成英文的引号 {fixed}'
            name = _FULLWIDTH_NAMES.get(char)
            if name:
                return f'这里输入的是中文的{name}，要换成英文的 {fixed}'
            return f'这里输入的是中文符号（{char}），要换成英文的（{fixed}）'
        return '这里有一个打错的符号（常见原因是用了中文标点）'

    # ── 括号 / 引号没配对（「写一半」的另一大来源）───────────────────
    if 'was never closed' in msg:
        matched = re.search(r"'([\(\[\{])' was never closed", msg)
        if matched:
            opener = matched.group(1)
            return f'左括号 {opener} 没有配上对，少了一个右括号 {_BRACKET_PAIRS[opener]}'
        return '括号或者引号没有配上对，检查一下有没有漏掉另一半'
    if 'unmatched' in msg:
        return '括号多写了一个，检查一下左右括号是不是成对的'
    if 'unexpected EOF' in msg or 'unexpected end of file' in msg:
        return '代码没写完：可能有括号或引号只写了一半'
    if 'unterminated string' in msg or 'EOL while scanning string literal' in msg:
        return '引号少了另一半，一个引号要成对出现'

    # ── 语句位置不对 ───────────────────────────────────────────────
    if "'return' outside function" in msg:
        return 'return 只能写在函数里面'
    if "'break' outside loop" in msg:
        return 'break 只能写在循环（for / while）里面'
    if "'continue' not properly in loop" in msg:
        return 'continue 只能写在循环（for / while）里面'

    # ── 其它 ─────────────────────────────────────────────────────
    if 'cannot assign to' in msg:
        return '等号左边要写一个变量名，这里不能这样赋值'
    if 'invalid decimal literal' in msg:
        return '数字写错了（常见原因：数字后面直接跟了字母）'
    if 'invalid syntax' in msg:
        base = '这一行写得不对'
        if line:
            base = f'{line}写得不对'
        return base + '（常见原因：少了冒号、括号没配对、用了中文标点）'
    return f'语法错误：{msg}' if msg else '语法错误，检查一下这一行'


def _api_names() -> list:
    """引擎公开的 API 名字，用于「是不是想写 xxx」提示（函数内导入避免循环依赖）"""
    try:
        import bingo_engine
        return [n for n in getattr(bingo_engine, '__all__', []) if not n.startswith('_')]
    except Exception:
        return []


def _sprite_names() -> list:
    """角色可用的方法名（Hero.move / Sprite.play ...），拼错时用来猜正确写法"""
    try:
        from sprite import Sprite
        return [n for n in dir(Sprite) if not n.startswith('_')]
    except Exception:
        return []


def _builtin_names() -> list:
    try:
        import builtins
        return [n for n in dir(builtins) if not n.startswith('_')]
    except Exception:
        return []


def _suggest(name: str, candidates) -> str:
    """在候选名字里找最接近的一个（拼错时提示「是不是想写 xxx」）"""
    import difflib
    try:
        matched = difflib.get_close_matches(name, list(candidates), n=1, cutoff=0.72)
    except Exception:
        return ''
    return matched[0] if matched else ''


# 参数名 → 中文意思：把「少了参数 distance」变成学生看得懂的说明。
# 先按 (函数名, 参数名) 精确查，查不到再按参数名兜底；都没有就只显示原名。
# 新增/改名 API 时同步维护这里，查不到只会显示英文参数名，不会报错。
_PARAM_MEANINGS = {
    # 引擎全局函数
    ('key_down', 'key'): '按键名，如 "a" 或 "space"',
    ('key_pressed', 'key'): '按键名，如 "a" 或 "space"',
    ('key_up', 'key'): '按键名，如 "a" 或 "space"',
    ('time_passed', 'seconds'): '秒数',
    ('wait', 'seconds'): '秒数',
    ('broadcast', 'event_name'): '广播的名字',
    ('receive', 'event_name'): '广播的名字',
    ('on_receive', 'event_name'): '广播的名字',
    ('on_receive', 'callback'): '收到广播时要执行的函数',
    ('load_map', 'map_name'): '地图的名字',
    ('get_marker', 'name'): '标记的名字',
    ('get_markers', 'marker_type'): '标记的类型，如 "出生点"',
    ('raycast', 'x'): '射线的起点横坐标',
    ('raycast', 'y'): '射线的起点纵坐标',
    ('raycast', 'direction'): '方向，如 "right" 或角度数字',
    ('raycast', 'distance'): '射线长度，单位像素',
    ('camera_follow', 'sprite'): '要跟随的角色',
    ('play_sound', 'sound_name'): '音效的名字',
    ('play_sound', 'loop'): '是否循环播放',
    ('show_collision', 'sprite'): '要显示碰撞的角色',
    ('random_int', 'min_val'): '最小值',
    ('random_int', 'max_val'): '最大值',
    ('random_float', 'min_val'): '最小值',
    ('random_float', 'max_val'): '最大值',
    ('random_float', 'decimals'): '小数点后保留几位',
    ('stop_sound', 'sound_name'): '音效的名字',
    ('shake', 'intensity'): '震动强度',
    ('shake', 'duration'): '持续几秒',
    # 角色方法
    ('move', 'distance'): '移动的距离，单位像素',
    ('say', 'text'): '要说的话',
    ('say', 'seconds'): '说几秒，0 表示一直显示',
    ('play', 'animation_name'): '动画的名字',
    ('play', 'transition_time'): '切换动画的过渡秒数',
    ('set_angle', 'angle'): '角度：0=右，90=上，180=左，270=下',
    ('set_scale', 'value'): '缩放百分比，100 是原大小',
    ('add_scale', 'value'): '要增加的百分比',
    ('set_speed', 'speed'): '速度，每帧移动多少像素',
    ('set_rotation_mode', 'style'): '旋转模式："all" / "left_right" / "none"',
    ('jump', 'power'): '跳跃力度',
    ('smart_jump', 'power'): '跳跃力度',
    ('is_touch', 'target'): '要检测的对象：角色、鼠标或图块标签',
    ('is_touch_group', 'group_name'): '组的名字',
    ('add_to_group', 'group_name'): '组的名字',
    ('on_clicked', 'callback'): '被点到时要执行的函数',
    ('on_hit', 'group'): '组的名字',
    ('on_hit', 'callback'): '碰到时要执行的函数',
    ('on_touch_group', 'group'): '组的名字',
    ('on_touch_group', 'callback'): '碰到时要执行的函数',
    ('on_sensor_enter', 'tag'): '感应区的标签',
    ('on_sensor_enter', 'callback'): '进入时要执行的函数',
    ('on_sensor_exit', 'tag'): '感应区的标签',
    ('on_sensor_exit', 'callback'): '离开时要执行的函数',
    ('follow', 'target'): '要跟随的角色',
    ('follow', 'flip'): '是否跟着左右翻转',
    ('look_at', 'target'): '要看向的角色或鼠标',
    ('distance_to', 'target'): '目标角色或鼠标',
}

# 兜底：这些参数名在各处含义都一样
_PARAM_FALLBACK = {
    'x': '横坐标',
    'y': '纵坐标',
    'seconds': '秒数',
    'text': '文字内容',
    'distance': '距离，单位像素',
    'speed': '速度',
    'angle': '角度',
    'name': '名字',
    'value': '数值',
    'target': '目标',
    'callback': '要执行的函数',
    'group_name': '组的名字',
}


def _param_label(func: str, param: str) -> str:
    """把参数名拼成「distance（移动的距离）」；查不到意思时只显示原名"""
    base = func.split('.')[-1]
    meaning = _PARAM_MEANINGS.get((base, param)) or _PARAM_FALLBACK.get(param, '')
    return f'{param}（{meaning}）' if meaning else param


def _short_func_name(func: str) -> str:
    """把函数名缩成学生看得懂的样子。

    Python 报的可能是内部全名 `__game_游戏脚本_1__.<locals>.move`（游戏循环转换后
    学生的函数变成了嵌套函数），这里只保留 `move`；`Sprite.move` 这种正常名字原样保留。
    """
    if '<locals>' in func:
        return func.split('.')[-1]
    return func


def _type_error_hint(msg: str) -> str:
    """函数调用的参数不对 / 数据类型不对：把 Python 的英文提示翻成中文"""
    # 函数名：允许 __game_x__.<locals>.move 这种带尖括号的内部全名
    func_re = r"([\w\.<>]+)"

    # ── 少了必须写的参数（漏写参数）────────────────────────────────
    matched = re.search(
        func_re + r"\(\) missing \d+ required (?:positional|keyword-only) arguments?: (.+)$", msg
    )
    if matched:
        func = _short_func_name(matched.group(1))
        params = re.findall(r"'([^']+)'", matched.group(2))
        labels = '、'.join(_param_label(matched.group(1), p) for p in params)
        return f'{func}() 少了参数 {labels}，括号里要补上'

    matched = re.search(func_re + r"\(\) missing \d+ required argument", msg)
    if matched:
        return f'{_short_func_name(matched.group(1))}() 少了必须写的参数，检查一下括号里有没有漏'

    # ── 参数个数不对 ─────────────────────────────────────────────
    matched = re.search(func_re + r"\(\) takes no arguments", msg)
    if matched:
        return f'{_short_func_name(matched.group(1))}() 不用写参数，括号里留空就行'

    matched = re.search(
        func_re + r"\(\) takes (\d+) positional arguments? but (\d+) (?:was|were) given", msg
    )
    if matched:
        return (
            f'{_short_func_name(matched.group(1))}() 只接受 {matched.group(2)} 个参数，'
            f'这里写了 {matched.group(3)} 个'
        )

    matched = re.search(
        func_re + r"\(\) takes from (\d+) to (\d+) positional arguments but (\d+) were given", msg
    )
    if matched:
        return (
            f'{_short_func_name(matched.group(1))}() 只能写 {matched.group(2)}～'
            f'{matched.group(3)} 个参数，这里写了 {matched.group(4)} 个'
        )

    matched = re.search(func_re + r"\(\) takes exactly \d+ arguments? \(\d+ given\)", msg)
    if matched:
        return f'{_short_func_name(matched.group(1))}() 写的参数个数不对，检查一下括号里有几个'

    matched = re.search(func_re + r"\(\) got an unexpected keyword argument '(\w+)'", msg)
    if matched:
        return (
            f'{_short_func_name(matched.group(1))}() 里没有叫 {matched.group(2)} 的参数，'
            '检查一下参数名字'
        )

    # ── 数字和文字混着算 ─────────────────────────────────────────
    if 'unsupported operand type' in msg or 'can only concatenate' in msg:
        if 'NoneType' in msg:
            return '这里是空值（None），不能参与计算'
        if 'str' in msg:
            return '数字和文字不能直接相加，数字要先用 str() 变成文字'
        return f'这两种数据不能这样计算（{msg}）'

    return f'类型用错了：{msg}'


def _hint(exc) -> str:
    """把异常翻译成一句小学生能看懂的话"""
    name = type(exc).__name__
    msg = str(exc)

    if isinstance(exc, NameError):
        target = getattr(exc, 'name', None)
        if not target:
            matched = re.search(r"name '([^']+)' is not defined", msg)
            target = matched.group(1) if matched else ''
        if not target:
            return '有名字没有定义，检查一下拼写'
        tip = _suggest(target, _api_names() + _sprite_names() + _builtin_names())
        if tip:
            return f'名字 {target} 没有定义，是不是想写 {tip}？'
        return f'名字 {target} 没有定义，检查一下是不是拼错了'

    if isinstance(exc, AttributeError):
        matched = (
            re.search(r"'([^']+)' object has no attribute '([^']+)'", msg)
            or re.search(r"module '([^']+)' has no attribute '([^']+)'", msg)
        )
        if matched:
            obj, attr = matched.group(1), matched.group(2)
            if obj == 'NoneType':
                return f'这里还是个空值（None），不能使用 {attr}'
            tip = _suggest(attr, _sprite_names() if obj == 'Sprite' else _api_names())
            if tip:
                return f'{obj} 没有 {attr} 这个方法，是不是想写 {tip}？'
            return f'类型 {obj} 没有 {attr} 这个方法或属性，检查一下名字有没有写错'
        return f'没有这个方法或属性，检查一下名字（{msg}）'

    if isinstance(exc, ModuleNotFoundError):
        return f"找不到模块 {getattr(exc, 'name', '')}，检查一下 import 后面的名字"
    if isinstance(exc, ImportError):
        return f'导入失败：{msg}'
    if isinstance(exc, ZeroDivisionError):
        return '不能除以 0'
    if isinstance(exc, IndexError):
        return '列表或字符串没有那么长（下标超出范围了）'
    if isinstance(exc, KeyError):
        key = msg.strip('\'"')
        return f'字典里没有 {key} 这个键'
    if isinstance(exc, FileNotFoundError):
        filename = getattr(exc, 'filename', '') or ''
        return f'找不到文件 {filename}'.strip()
    if isinstance(exc, TypeError):
        return _type_error_hint(msg)
    if isinstance(exc, ValueError):
        return f'数值或内容不对：{msg}'
    if isinstance(exc, RecursionError):
        return '函数自己调用自己的次数太多了'
    if isinstance(exc, (IndentationError, TabError, SyntaxError)):
        return _syntax_hint(getattr(exc, 'msg', None) or msg)
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
    """语法错误：errors = [(文件名, 行号, 原始说明, 出错行源码, 上一行语句源码)]，一次性全部列出来"""
    for name, line, msg, text, prev in errors:
        _emit(f'[错误] {name} 第 {line} 行：{_syntax_hint(msg, text, prev)}')


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
