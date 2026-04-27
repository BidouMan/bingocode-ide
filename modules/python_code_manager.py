import sys, os
import jedi
import black
import re
from PySide6.QtWidgets import (QTextEdit, QWidget, QListView,QToolTip)
from PySide6.QtGui import (QColor, QFont, QSyntaxHighlighter, QTextCharFormat, 
                           QPainter, QStandardItemModel, 
                           QStandardItem, QKeyEvent, QTextCursor, QTextBlockFormat,QPalette,
                           QFontDatabase, QPen,QIcon)
from PySide6.QtCore import Qt, QRect, Property,QTimer,QPoint,QThread,Signal

def get_bingo_apis():
    try:
        # 确保 sys.path 已经包含了 modules 目录
        import bingo_engine
        # 如果你定义了 __all__，直接用 __all__
        if hasattr(bingo_engine, "__all__"):
            return set(bingo_engine.__all__)
        # 否则获取所有非下划线开头的名称
        return {name for name in dir(bingo_engine) if not name.startswith('_')}
    except Exception as e:
        print(f"警告: 无法预加载 bingo_engine API: {e}")
        return {"Sprite", "run"} # 兜底方案
try:
    import bingo_engine
    # 自动获取 bingo_engine 中所有不以 _ 开头的变量和类
    HIDDEN_IMPORTS = {name for name in dir(bingo_engine) if not name.startswith('_')}
except ImportError:
    HIDDEN_IMPORTS = set()

# 全局配置：内部库白名单（可根据需要扩展）
INTERNAL_LIBS = {"bingo_engine", "render_manager", "stage_manager", "script_runner"}
# 语法关键字（冒号检查）
COLON_KEYWORDS = ('if', 'else', 'elif', 'for', 'while', 'def', 'class', 'with', 'try', 'except', 'finally')
# 错误类型枚举（便于管理）
ERROR_TYPES = {
    "missing_colon": "语法错误: '{}' 语句末尾缺少冒号 ':'",
    "indent_error": "缩进错误: 缩进量必须是4个空格的倍数（或Tab）",
    "undefined_var": "变量名 '{}' 可能未定义"
}

def get_resource_path(relative_path):
    """ 处理 PyInstaller 打包后的资源路径 """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class JediWorker(QThread):
    completion_ready = Signal(list)
    names_ready = Signal(set)

    def __init__(self):
        super().__init__()
        self._task = None

    def request_completion(self, code, line, col):
        self._task = ("completion", code, line, col)
        if not self.isRunning():
            self.start()

    def request_names(self, code):
        self._task = ("names", code)
        if not self.isRunning():
            self.start()

    def run(self):
        if not self._task:
            return
        task_type = self._task[0]
        code = self._task[1]
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            modules_path = os.path.join(current_dir, "modules")
            project = jedi.Project(current_dir, sys_path=sys.path + [modules_path])

            if task_type == "completion":
                prefix = "from bingo_engine import *\n"
                full_code = prefix + code
                line_adj = self._task[2] + 1 + 1
                col = self._task[3]
                script = jedi.Script(full_code, path="main.py", project=project)
                comps = script.complete(line_adj, col)
                filtered = [c for c in comps[:20] if not c.name.startswith('__')]
                self.completion_ready.emit(filtered)
            elif task_type == "names":
                script = jedi.Script(code, path="main.py", project=project)
                jedi_names = {n.name for n in script.get_names(all_scopes=True)}
                self.names_ready.emit(jedi_names)
        except:
            pass
        finally:
            self._task = None

# --- 语法高亮逻辑 (保留) ---
class PygmentsHighlighter(QSyntaxHighlighter):
    # 保留你原有的高亮逻辑，无需修改
    RAINBOW_COLORS = ["#ffd700", "#da70d6", "#179fff", "#ff5d5d", "#41e1a4"]
    def __init__(self, parent, style_name='one-dark'):
        super().__init__(parent)
        from pygments.lexers import get_lexer_by_name
        from pygments.styles import get_style_by_name
        self.lexer = get_lexer_by_name('python')
        self.style = get_style_by_name(style_name)
        self.formats = {}

    def highlightBlock(self, text):
        prev_state = self.previousBlockState()
        level = prev_state if prev_state != -1 else 0
        for index, token, value in self.lexer.get_tokens_unprocessed(text):
            format = self.formats.get(token)
            if format is None:
                format = QTextCharFormat()
                style_item = self.style.style_for_token(token)
                if style_item['color']:
                    format.setForeground(QColor(f"#{style_item['color']}"))
                if style_item['bold']: format.setFontWeight(QFont.Bold)
                if style_item['italic']: format.setFontItalic(True)
                self.formats[token] = format
            self.setFormat(index, len(value), format)
        self.highlight_rainbow_brackets(text, level)

    def highlight_rainbow_brackets(self, text, level):
        bracket_pattern = re.compile(r"[\(\)\[\]\{\}]")
        for match in bracket_pattern.finditer(text):
            char = match.group()
            index = match.start()
            if char in "([{":
                color = QColor(self.RAINBOW_COLORS[level % len(self.RAINBOW_COLORS)])
                fmt = QTextCharFormat()
                fmt.setForeground(color)
                fmt.setFontWeight(QFont.Bold)
                self.setFormat(index, 1, fmt)
                level += 1
            else:
                level = max(0, level - 1)
                color = QColor(self.RAINBOW_COLORS[level % len(self.RAINBOW_COLORS)])
                fmt = QTextCharFormat()
                fmt.setForeground(color)
                fmt.setFontWeight(QFont.Bold)
                self.setFormat(index, 1, fmt)
        self.setCurrentBlockState(level)

# --- 补全框 (保留) ---
class CompleterWidget(QListView):
    # 保留你原有的补全框逻辑，无需修改
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_editor = parent
        self._list_bg_color = QColor("#2c313a")
        self._list_text_color = QColor("#abb2bf")
        self._item_selected_bg = QColor("#3e4451")
        self._item_selected_text = QColor("#ffffff")
        self._border_color = QColor("#4b5263")

        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setFocusPolicy(Qt.NoFocus) 
        self.setEditTriggers(QListView.EditTrigger.NoEditTriggers)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.model = QStandardItemModel()
        self.setModel(self.model)
        
        self.refresh_font()
        self.update_style()
        self.hide()

    def update_style(self):
        style = f"""
            QListView {{
                background-color: {self._list_bg_color.name()};
                border: 1px solid {self._border_color.name()};
                color: {self._list_text_color.name()};
                outline: none;
                border-radius: 4px;
            }}
            QListView::item {{ padding: 5px; }}
            QListView::item:selected {{
                background-color: {self._item_selected_bg.name()};
                color: {self._item_selected_text.name()};
                border-radius: 2px;
            }}
        """
        if self.styleSheet() != style:
            self.setStyleSheet(style)

    def refresh_font(self):
        f = QFont()
        f.setFamilies([self.parent_editor.font_family, self.parent_editor.zh_font_family])
        new_size = max(9, self.parent_editor.current_font_size - 2)
        f.setPointSize(new_size)
        self.setFont(f)
        self.setFixedWidth(self.parent_editor.current_font_size * 18)
        self.setFixedHeight(self.parent_editor.current_font_size * 10)
        p = max(2, self.parent_editor.current_font_size // 4)
        style = f"""
            QListView {{
                background-color: {self._list_bg_color.name()};
                border: 1px solid {self._border_color.name()};
                color: {self._list_text_color.name()};
                outline: none;
                border-radius: 4px;
            }}
            QListView::item {{ padding: {p}px; }}
            QListView::item:selected {{
                background-color: {self._item_selected_bg.name()};
                color: {self._item_selected_text.name()};
                border-radius: 2px;
            }}
        """
        self.setStyleSheet(style)

    def update_completions(self, completions):
        self.model.clear()
        if not completions:
            self.hide()
            return
        for c in completions:
            self.model.appendRow(QStandardItem(c.name))
        self.setCurrentIndex(self.model.index(0, 0))
        self.show()
        self.raise_()

    def wheelEvent(self, event):
        if self.model.rowCount() == 0: return
        row = self.currentIndex().row()
        if event.angleDelta().y() > 0:
            new_row = max(0, row - 1)
        else:
            new_row = min(self.model.rowCount() - 1, row + 1)
        self.setCurrentIndex(self.model.index(new_row, 0))
        event.accept()
    
    def move_selection(self, direction):
        if self.model.rowCount() == 0: return
        current_row = self.currentIndex().row()
        new_row = current_row + direction
        if new_row < 0: 
            new_row = self.model.rowCount() - 1
        elif new_row >= self.model.rowCount():
            new_row = 0
        self.setCurrentIndex(self.model.index(new_row, 0))

    @Property(QColor)
    def listBgColor(self): return self._list_bg_color
    @listBgColor.setter
    def listBgColor(self, c): self._list_bg_color = QColor(c); self.update_style()
    @Property(QColor)
    def listTextColor(self): return self._list_text_color
    @listTextColor.setter
    def listTextColor(self, c): self._list_text_color = QColor(c); self.update_style()
    @Property(QColor)
    def itemSelectedBg(self): return self._item_selected_bg
    @itemSelectedBg.setter
    def itemSelectedBg(self, c): self._item_selected_bg = QColor(c); self.update_style()
    @Property(QColor)
    def itemSelectedText(self): return self._item_selected_text
    @itemSelectedText.setter
    def itemSelectedText(self, c): self._item_selected_text = QColor(c); self.update_style()
    @Property(QColor)
    def listBorderColor(self): return self._border_color
    @listBorderColor.setter
    def listBorderColor(self, c): self._border_color = QColor(c); self.update_style()

# --- 核心编辑器类 (重构错误检查逻辑) ---
class QCodeEditor(QTextEdit):
    def __init__(self, language='python'):
        super().__init__()
        # 基础属性初始化
        self._line_number_bg = QColor("#23272e")
        self._line_number_text = QColor("#4b5263")
        self._line_number_border = QColor("#181a1f")
        self._current_line_color = QColor("#2c313a")
        self._indent_guide_color = QColor("#3b4048")
        self._indent_error_color = QColor(255, 0, 0, 40)

        self.last_hover_block = -1
        self.file_path = ""
        self.current_font_size = 18
        self.fixed_line_height = 20
        self.error_lines = {}  # 存储错误行: {行号: 错误信息}
        self.space_width = self.fontMetrics().horizontalAdvance(' ')
        self.indent_guide_width = self.space_width * 4
        self.last_line_idx = -1

        # 编辑器基础设置
        self.setAcceptRichText(False)
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled)
        
        # 初始化组件
        self.load_custom_font()
        # 只创建一次高亮器
        if not hasattr(self, 'highlighter'):
            self.highlighter = PygmentsHighlighter(self.document())
        # 只创建一次补全框
        if not hasattr(self, 'completer'):
            self.completer = CompleterWidget(self)
            self.completer.clicked.connect(self.insert_completion)
        # 只创建一次行号区域
        if not hasattr(self, 'line_number_area'):
            self.line_number_area = LineNumberArea(self)

        # 信号连接（确保只连接一次）
        if not hasattr(self, '_signals_connected'):
            self.document().blockCountChanged.connect(self.update_line_number_area_width)
            self.document().documentLayout().update.connect(lambda: self.line_number_area.update())
            self.verticalScrollBar().valueChanged.connect(lambda: self.line_number_area.update())
            self.cursorPositionChanged.connect(self.viewport().update)
            self.cursorPositionChanged.connect(self.handle_line_validation)
            self.textChanged.connect(self.request_analyze)
            self._signals_connected = True

        # 防抖定时器（避免实时输入频繁检查）
        self.analyze_timer = QTimer(self)
        self.analyze_timer.setSingleShot(True)
        self.analyze_timer.timeout.connect(self.check_all_errors)

        # Jedi 后台分析线程
        self._jedi_worker = JediWorker()
        self._jedi_worker.completion_ready.connect(self._on_completion_ready)
        self._jedi_worker.names_ready.connect(self._on_names_ready)
        self._pending_jedi_names = None

        # 初始化
        self.setup_font()
        self.update_font_metrics_cache()
        self.update_line_number_area_width(0)
        # 设置行号区域位置
        if hasattr(self, 'line_number_area'):
            self.line_number_area.setGeometry(0, 0, self.line_number_area.width(), self.viewport().height())
        QTimer.singleShot(50, self.init_validation)

    def init_validation(self):
        """初始化校验"""
        self.check_all_errors()

    def request_analyze(self):
        """触发防抖检查"""
        self.analyze_timer.start(200)  # 停止输入200ms后检查

    def check_all_errors(self):
        """核心：只检查3类指定错误，清空原有错误"""
        self.error_lines.clear()
        raw_code = self.toPlainText()
        if not raw_code.strip():
            self.line_number_area.set_blink_active(False)
            self.line_number_area.update()
            self.viewport().update()
            return

        lines = raw_code.split('\n')
        current_line = self.textCursor().blockNumber()

        # 1. 检查冒号缺失 + 缩进错误
        self._check_colon_and_indent(lines, current_line)
        # 2. 检查未定义变量（排除内部库）
        self._check_undefined_variable(lines, current_line, raw_code)

        # 按需启停闪烁定时器
        self.line_number_area.set_blink_active(bool(self.error_lines))

        # 刷新显示
        self.line_number_area.update()
        self.viewport().update()

    def _check_colon_and_indent(self, lines, current_line):
        """检查：1.冒号缺失 2.缩进错误（包含缩进量非4倍数）"""
        expect_indent = False  # 是否期望下一行缩进
        prev_indent = 0        # 上一行缩进量

        for i, line in enumerate(lines):
            # 跳过当前编辑行（避免输入中误报）
            if i == current_line:
                stripped = line.split('#')[0].strip()
                if stripped:
                    # 当前行以冒号结尾，标记下一行需要缩进
                    expect_indent = stripped.endswith(':')
                    prev_indent = len(line) - len(line.lstrip())
                continue

            # 剔除注释，只保留代码部分
            code_part = line.split('#')[0].rstrip()
            stripped = code_part.strip()
            if not stripped:
                expect_indent = False
                continue

            current_indent = len(code_part) - len(code_part.lstrip())
            
            # 新增：检查缩进量是否为4的倍数（核心修复点）
            if current_indent % 4 != 0:
                self.error_lines[i] = ERROR_TYPES["indent_error"].replace("(Tab 或 4个空格)", "缩进量必须是4个空格的倍数")
                expect_indent = False
                continue

            # 原有逻辑：检查上一行要求缩进，但当前行缩进不足
            if expect_indent and current_indent <= prev_indent:
                self.error_lines[i] = ERROR_TYPES["indent_error"]
                expect_indent = False  # 避免连环报错
                continue

            # 检查2：冒号缺失
            parts = stripped.split()
            first_word = parts[0].split('(')[0].split(':')[0] if parts else ""
            if first_word in COLON_KEYWORDS and not stripped.endswith(':'):
                self.error_lines[i] = ERROR_TYPES["missing_colon"].format(first_word)
                expect_indent = False
            else:
                # 重置缩进期望
                expect_indent = stripped.endswith(':')
                prev_indent = current_indent

    def _check_undefined_variable(self, lines, current_line, raw_code):
        """检查：未定义变量（排除内部库/关键字/内置函数）"""
        import keyword
        # 构建白名单
        safe_names = set(keyword.kwlist)  # 关键字
        safe_names.update(__builtins__.keys())  # 内置函数
        safe_names.update(INTERNAL_LIBS)  # 内部库
        safe_names.add("self")  # 类实例


        # 🚀 核心修复：注入 bingo_engine 的公开 API
        safe_names.update(get_bingo_apis())
        # 提取代码中定义的变量/函数/导入的模块
        defined_names = self._extract_defined_names(raw_code)
        safe_names.update(defined_names)

        # 遍历每行检查变量
        for i, line in enumerate(lines):
            # 跳过当前行/已有错误的行/空行
            if i == current_line or i in self.error_lines or not line.strip():
                continue

            # 剔除注释和字符串（避免误判字符串内的内容）
            clean_line = self._clean_line_for_var_check(line)
            # 提取所有可能的变量名
            words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', clean_line)

            for word in words:
                # 跳过白名单/定义过的变量/赋值语句中的变量
                if word in safe_names:
                    continue
                # 检查是否是赋值语句（赋值的变量不算未定义）
                after_word = clean_line.split(word, 1)[-1].lstrip()
                if after_word.startswith('='):
                    continue
                # 最终判定：未定义变量
                self.error_lines[i] = ERROR_TYPES["undefined_var"].format(word)
                break  # 每行只报一个变量错误

    def _extract_defined_names(self, raw_code):
        """提取代码中定义的变量/函数/导入的模块（新增：提取for循环迭代变量 + 跨文件扫描）"""
        defined_names = set()
        # 1. 提取导入的模块/变量
        import_pattern = re.compile(r'(?:from|import)\s+([\w\.]+)')
        from_import_pattern = re.compile(r'import\s+([\w\s,]+)')
        for line in raw_code.split('\n'):
            line = line.split('#')[0].strip()
            import_matches = import_pattern.findall(line)
            for m in import_matches:
                defined_names.update(m.split('.'))
            from_matches = from_import_pattern.findall(line)
            for names in from_matches:
                for name in names.split(','):
                    defined_names.add(name.strip())

        # 2. 提取赋值/函数/类定义的变量名
        assign_pattern = re.compile(r'\b([a-zA-Z_]\w*)\s*=')
        def_pattern = re.compile(r'def\s+([a-zA-Z_]\w*)')
        class_pattern = re.compile(r'class\s+([a-zA-Z_]\w*)')
        for_pattern = re.compile(r'for\s+([\w,\s]+)\s+in\s+')
        for line in raw_code.split('\n'):
            line = line.split('#')[0].strip()
            defined_names.update(assign_pattern.findall(line))
            defined_names.update(def_pattern.findall(line))
            defined_names.update(class_pattern.findall(line))
            
            for_match = for_pattern.search(line)
            if for_match:
                var_part = for_match.group(1).strip()
                for var in var_part.split(','):
                    var = var.strip()
                    if var and var.isidentifier():
                        defined_names.add(var)

        # 3. 扫描同目录下其他 .py 文件的顶层变量/函数/类定义
        if self.file_path:
            try:
                project_dir = os.path.dirname(os.path.abspath(self.file_path))
                for fname in os.listdir(project_dir):
                    if not fname.endswith('.py') or fname.startswith('.'):
                        continue
                    fpath = os.path.join(project_dir, fname)
                    if os.path.abspath(fpath) == os.path.abspath(self.file_path):
                        continue
                    try:
                        with open(fpath, 'r', encoding='utf-8') as f:
                            other_code = f.read()
                        for line in other_code.split('\n'):
                            line = line.split('#')[0].strip()
                            if not line:
                                continue
                            defined_names.update(assign_pattern.findall(line))
                            defined_names.update(def_pattern.findall(line))
                            defined_names.update(class_pattern.findall(line))
                            for_match = for_pattern.search(line)
                            if for_match:
                                var_part = for_match.group(1).strip()
                                for var in var_part.split(','):
                                    var = var.strip()
                                    if var and var.isidentifier():
                                        defined_names.add(var)
                    except:
                        pass
            except:
                pass

        # 4. 补充Jedi分析（异步：通过后台线程获取，结果暂存）
        if self._pending_jedi_names is not None:
            defined_names.update(self._pending_jedi_names)
            self._pending_jedi_names = None
        self._jedi_worker.request_names(raw_code)
            
        return defined_names

    def _on_names_ready(self, names):
        """后台线程 Jedi 名称分析结果回调"""
        self._pending_jedi_names = names

    def _clean_line_for_var_check(self, line):
        """清理行内容：移除注释、字符串，避免误判"""
        # 移除注释
        line = line.split('#')[0]
        # 移除字符串（单/双引号）
        line = re.sub(r"(['\"]).*?\1", lambda m: " " * len(m.group()), line)
        # 移除点调用（如 obj.xxx 中的xxx不检查）
        line = re.sub(r'\.\w+', lambda m: " " * len(m.group()), line)
        return line

    def handle_line_validation(self):
        """光标行切换时只记录行号，不触发错误检查"""
        curr_line = self.textCursor().blockNumber()
        if curr_line != self.last_line_idx:
            self.last_line_idx = curr_line

    # --- 保留原有UI/交互逻辑 ---
    def load_custom_font(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        asset_path = get_resource_path(os.path.join("assets", "font"))
        if sys.platform == "darwin":
            self.font_family = "Menlo"
            self.zh_font_family = "PingFang SC"
        elif sys.platform == "win32":
            self.font_family = "Consolas"
            self.zh_font_family = "Microsoft YaHei"
        else:
            self.font_family = "Monospace"
            self.zh_font_family = "sans-serif"

        font_config = [
            ("JetBrainsMono-Regular.ttf", "font_family"),
            ("HarmonyOS_Sans_SC_Regular.ttf", "zh_font_family")
        ]
        for f_name, attr in font_config:
            p = os.path.join(asset_path, f_name)
            if os.path.exists(p):
                fid = QFontDatabase.addApplicationFont(p)
                if fid != -1:
                    family = QFontDatabase.applicationFontFamilies(fid)[0]
                    setattr(self, attr, family)

    def setup_font(self):
        font = QFont()
        font.setFamilies([self.font_family, self.zh_font_family, "Consolas"])
        font.setPointSize(self.current_font_size)
        font.setFixedPitch(True)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        self.setFont(font)
        self.document().setDefaultFont(font)
        self.document().setDocumentMargin(0)

    def update_font_metrics_cache(self):
        metrics = self.fontMetrics()
        self.space_width = metrics.horizontalAdvance(' ')
        self.indent_guide_width = self.space_width * 4
        self.fixed_line_height = metrics.lineSpacing() + 2

    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        # 绘制当前行背景
        if not self.textCursor().hasSelection():
            crect = self.cursorRect()
            draw_rect = QRect(
                0, 
                crect.top() - 1, 
                self.viewport().width(), 
                crect.height() + 2
            )
            painter.fillRect(draw_rect, self._current_line_color)
        # 绘制缩进参考线
        self.draw_indent_guides(painter)
        # 绘制错误行背景
        self.draw_indent_errors(painter)
        # 绘制文字
        super().paintEvent(event)

    def draw_indent_guides(self, painter):
        painter.setPen(QPen(self._indent_guide_color, 1, Qt.PenStyle.SolidLine))
        indent_width = self.indent_guide_width 
        offset_x = self.document().documentMargin()
        scroll_y = self.verticalScrollBar().value()
        viewport_rect = self.viewport().rect()
        block = self.document().begin()
        layout = self.document().documentLayout()
        last_indent_levels = 0

        while block.isValid():
            rect = layout.blockBoundingRect(block)
            top = rect.top() - scroll_y
            bottom = top + rect.height()
            if top > viewport_rect.bottom(): break
            if bottom >= viewport_rect.top():
                text = block.text()
                stripped_text = text.lstrip()
                if not stripped_text:
                    indent_levels = last_indent_levels
                else:
                    indent_levels = (len(text) - len(stripped_text)) // 4
                    last_indent_levels = indent_levels
                for i in range(indent_levels):
                    x = offset_x + (i * indent_width)
                    painter.drawLine(x, top, x, bottom)
            block = block.next()

    def draw_indent_errors(self, painter):
        layout = self.document().documentLayout()
        scroll_y = self.verticalScrollBar().value()
        viewport_h = self.viewport().height()
        for line_num in self.error_lines:
            block = self.document().findBlockByNumber(line_num)
            if not block.isValid(): continue
            rect = layout.blockBoundingRect(block)
            top = rect.top() - scroll_y
            if top > viewport_h or top + rect.height() < 0: continue
            painter.fillRect(QRect(0, int(top), self.viewport().width(), int(rect.height())), self._indent_error_color)

    def wheelEvent(self, event):
        if event.modifiers() & Qt.ControlModifier:
            if event.angleDelta().y() > 0: self.zoom_in()
            else: self.zoom_out()
            event.accept()
        else: super().wheelEvent(event)

    def zoom_in(self):
        if self.current_font_size < 72:
            self.current_font_size += 2
            self.refresh_all_components()

    def zoom_out(self):
        if self.current_font_size > 6:
            self.current_font_size -= 2
            self.refresh_all_components()

    def refresh_all_components(self):
        self.setup_font()
        self.update_font_metrics_cache()
        self.completer.refresh_font()
        self.line_number_area.setFont(self.font())
        self.update_line_number_area_width(0)
        self.line_number_area.update()

    def keyPressEvent(self, event: QKeyEvent):
        key, mods = event.key(), event.modifiers()
        char = event.text()
        
        # 补全框交互
        if self.completer.isVisible():
            if key == Qt.Key_Up:
                self.completer.move_selection(-1)
                return
            if key == Qt.Key_Down:
                self.completer.move_selection(1)
                return
            if key in (Qt.Key_Enter, Qt.Key_Return, Qt.Key_Tab):
                self.insert_completion()
                return
            if key == Qt.Key_Escape:
                self.completer.hide()
                return
            if key in (Qt.Key_Space, Qt.Key_Backspace, Qt.Key_Left, Qt.Key_Right):
                self.completer.hide()

        # 快捷键
        if mods & Qt.ControlModifier:
            if key in (Qt.Key_Plus, Qt.Key_Equal):
                self.current_font_size = min(72, self.current_font_size + 2)
                self.refresh_all_components()
                return
            if key == Qt.Key_Minus:
                self.current_font_size = max(6, self.current_font_size - 2)
                self.refresh_all_components()
                return
            if key == Qt.Key_0: 
                self.current_font_size = 18
                self.refresh_all_components()
                return
            if key == Qt.Key_Slash: 
                self.toggle_comment()
                return
            if key == Qt.Key_F and (mods & Qt.ShiftModifier): 
                self.format_code()
                return
            if key == Qt.Key_V:
                super().keyPressEvent(event)
                return

        # 自动补全括号/引号
        bracket_pairs = {'(': ')', '[': ']', '{': '}', '"': '"', "'": "'"}
        if char in bracket_pairs:
            self.completer.hide()
            cursor = self.textCursor()
            if cursor.hasSelection():
                cursor.insertText(f"{char}{cursor.selectedText()}{bracket_pairs[char]}")
            else:
                self.insertPlainText(char + bracket_pairs[char])
                cursor = self.textCursor()
                cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, 1)
                self.setTextCursor(cursor)
            return

        # 智能退格
        if key == Qt.Key_Backspace:
            cursor = self.textCursor()
            if not cursor.hasSelection():
                line_text = cursor.block().text()[:cursor.columnNumber()]
                if line_text and line_text.isspace() and len(line_text) % 4 == 0:
                    cursor.beginEditBlock()
                    for _ in range(4): cursor.deletePreviousChar()
                    cursor.endEditBlock()
                    return

        # 换行自动缩进
        if key in (Qt.Key_Return, Qt.Key_Enter):
            line_text = self.textCursor().block().text()
            indent = len(line_text) - len(line_text.lstrip())
            if line_text.strip().endswith(':'): 
                indent += 4
            super().keyPressEvent(event) 
            self.insertPlainText(" " * indent)
            return

        # 块缩进/反缩进
        cursor = self.textCursor()
        if cursor.hasSelection():
            if key in (Qt.Key_Tab, Qt.Key_Backtab):
                self._handle_block_indent(key == Qt.Key_Backtab)
                return
        else:
            if key == Qt.Key_Tab:
                self.insertPlainText("    ")
                return
            if key == Qt.Key_Backtab:
                super().keyPressEvent(event)
                return

        # 默认处理
        super().keyPressEvent(event)
        if char.isalnum() or char == ".":
            self.trigger_completion()
        elif char and not char.isspace():
            self.completer.hide()

    def _handle_block_indent(self, is_unindent):
        cursor = self.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        start_block = self.document().findBlock(start)
        end_block = self.document().findBlock(end)
        if end_block.position() == end and start_block != end_block:
            end_block = end_block.previous()

        cursor.beginEditBlock()
        current_block = start_block
        while True:
            temp_cursor = QTextCursor(current_block)
            if is_unindent:
                text = current_block.text()
                if text.startswith("    "):
                    temp_cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 4)
                    temp_cursor.removeSelectedText()
                elif text.startswith(" "):
                    while temp_cursor.block().text().startswith(" "):
                        temp_cursor.movePosition(QTextCursor.MoveOperation.Right, QTextCursor.MoveMode.KeepAnchor, 1)
                        temp_cursor.removeSelectedText()
            else:
                temp_cursor.insertText("    ")
            if current_block == end_block:
                break
            current_block = current_block.next()
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def toggle_comment(self):
        cursor = self.textCursor()
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        cursor.setPosition(start); start_block = cursor.blockNumber()
        cursor.setPosition(end, QTextCursor.KeepAnchor); end_block = cursor.blockNumber()
        if cursor.columnNumber() == 0 and cursor.hasSelection(): end_block -= 1

        all_commented = True
        for i in range(start_block, end_block + 1):
            block = self.document().findBlockByNumber(i)
            text = block.text()
            if text.strip() and not text.lstrip().startswith('#'):
                all_commented = False
                break

        cursor.beginEditBlock()
        for i in range(start_block, end_block + 1):
            block = self.document().findBlockByNumber(i)
            cursor.setPosition(block.position())
            text = block.text()
            if all_commented:
                if text.lstrip().startswith('#'):
                    hash_pos = text.find('#')
                    num = 2 if len(text.lstrip()) > 1 and text.lstrip()[1] == ' ' else 1
                    cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, hash_pos)
                    cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, num)
                    cursor.removeSelectedText()
            else:
                if text.strip() and not text.lstrip().startswith('#'):
                    indent = len(text) - len(text.lstrip())
                    cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, indent)
                    cursor.insertText("# ")
        cursor.endEditBlock()

    def format_code(self):
        try:
            old = self.toPlainText()
            if not old.strip(): return
            new = black.format_str(old, mode=black.FileMode())
            if old != new:
                v_val = self.verticalScrollBar().value()
                self.setPlainText(new)
                self.verticalScrollBar().setValue(v_val)
                self.setup_font()
        except: pass

    def trigger_completion(self):
        """异步触发代码补全：通过后台线程执行 Jedi 分析"""
        user_code = self.toPlainText()
        cursor = self.textCursor()
        line = cursor.blockNumber()
        col = cursor.columnNumber()
        self._jedi_worker.request_completion(user_code, line, col)

    def _on_completion_ready(self, comps):
        """后台线程补全结果回调"""
        if not comps:
            self.completer.hide()
            return
        self.completer.update_completions(comps)
        crect = self.cursorRect()
        popup_x = crect.left() + self.line_number_area.width()
        popup_y = crect.bottom() + 2
        self.completer.move(popup_x, popup_y)

    def insert_completion(self, index=None):
        if not index: index = self.completer.currentIndex()
        if index.data():
            cursor = self.textCursor()
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)
            cursor.insertText(index.data())
        self.completer.hide()

    def update_line_number_area_width(self, _):
        digits = len(str(max(1, self.document().blockCount())))
        width = 20 + self.space_width * max(2, digits)
        self.setViewportMargins(width, 0, 0, 0)
        self.line_number_area.setFixedWidth(width)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.line_number_area.setGeometry(0, 0, self.line_number_area.width(), self.viewport().height())

    # --- QSS属性接口 ---
    @Property(QColor)
    def lineNumberBg(self): return self._line_number_bg
    @lineNumberBg.setter
    def lineNumberBg(self, c): self._line_number_bg = QColor(c); self.line_number_area.update()
    @Property(QColor)
    def lineNumberText(self): return self._line_number_text
    @lineNumberText.setter
    def lineNumberText(self, c): self._line_number_text = QColor(c); self.line_number_area.update()
    @Property(QColor)
    def lineNumberBorder(self): return self._line_number_border
    @lineNumberBorder.setter
    def lineNumberBorder(self, c): self._line_number_border = QColor(c); self.line_number_area.update()
    @Property(QColor)
    def currentLineColor(self): return self._current_line_color
    @currentLineColor.setter
    def currentLineColor(self, c): self._current_line_color = QColor(c); self.viewport().update()
    @Property(QColor)
    def selectionBackground(self): return self.palette().color(QPalette.ColorRole.Highlight)
    @selectionBackground.setter
    def selectionBackground(self, c): 
        p = self.palette(); p.setColor(QPalette.ColorRole.Highlight, QColor(c)); self.setPalette(p)
    @Property(QColor)
    def selectionColor(self): return self.palette().color(QPalette.ColorRole.HighlightedText)
    @selectionColor.setter
    def selectionColor(self, c): 
        p = self.palette()
        p.setBrush(QPalette.ColorRole.HighlightedText, Qt.BrushStyle.NoBrush)
        self.setPalette(p)
    @Property(QColor)
    def indentGuideColor(self): return self._indent_guide_color
    @indentGuideColor.setter
    def indentGuideColor(self, c): self._indent_guide_color = QColor(c); self.viewport().update()
    @Property(QColor)
    def indentErrorColor(self): return self._indent_error_color
    @indentErrorColor.setter
    def indentErrorColor(self, c): self._indent_error_color = QColor(c); self.viewport().update()

# --- 行号区域 (保留原有逻辑) ---
class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        self.setMouseTracking(True)
        self.error_icon = QIcon(":/icons/error_1.svg")
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self.update_blink)
        self.blink_alpha = 255
        self.blink_dir = -1

    def update_blink(self):
        self.blink_alpha += self.blink_dir * 10
        if self.blink_alpha <= 100: self.blink_dir = 1
        if self.blink_alpha >= 255: self.blink_dir = -1
        self.update()

    def set_blink_active(self, active):
        if active and not self.blink_timer.isActive():
            self.blink_timer.start(50)
        elif not active and self.blink_timer.isActive():
            self.blink_timer.stop()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.editor._line_number_bg)

        layout = self.editor.document().documentLayout()
        val = self.editor.verticalScrollBar().value()
        block = self.editor.document().begin()

        while block.isValid():
            top = round(layout.blockBoundingRect(block).top()) - val
            if top > event.rect().bottom(): break

            if top + self.editor.fixed_line_height >= event.rect().top():
                line_num = block.blockNumber()
                line_rect = QRect(0, top, self.width(), self.editor.fixed_line_height)

                if line_num in self.editor.error_lines:
                    # 错误行背景闪烁
                    flash_color = QColor("#ff5555")
                    flash_color.setAlpha(int(self.blink_alpha * 0.2)) 
                    painter.fillRect(line_rect, flash_color)

                    # 绘制错误图标/提示
                    icon_size = int(self.editor.fixed_line_height * 0.6)
                    icon_rect = QRect(
                        4, 
                        top + (self.editor.fixed_line_height - icon_size) // 2, 
                        icon_size, 
                        icon_size
                    )
                    if not self.error_icon.isNull():
                        self.error_icon.paint(painter, icon_rect)
                    else:
                        painter.setPen(QColor("#ff5555"))
                        painter.drawText(icon_rect, Qt.AlignCenter, "!")

                # 绘制行号文字
                text_color = self.editor._line_number_text
                if line_num in self.editor.error_lines:
                    text_color = QColor("#ff5555")
                painter.setPen(text_color)
                painter.drawText(
                    0, top, self.width() - 8, self.editor.fixed_line_height, 
                    Qt.AlignRight | Qt.AlignVCenter, str(line_num + 1)
                )
            block = block.next()

    def mouseMoveEvent(self, event):
        pos = event.pos()
        layout = self.editor.document().documentLayout()
        scroll_y = self.editor.verticalScrollBar().value()
        
        block = self.editor.document().begin()
        while block.isValid():
            rect = layout.blockBoundingRect(block)
            top = rect.top() - scroll_y
            bottom = top + rect.height()

            if top <= pos.y() <= bottom:
                line_num = block.blockNumber()
                if line_num in self.editor.error_lines:
                    error_msg = self.editor.error_lines[line_num]
                    local_tip_point = QPoint(self.width() + 2, event.pos().y() - 40)
                    global_tip_pos = self.mapToGlobal(local_tip_point)
                    QToolTip.showText(
                        global_tip_pos, 
                        f"<div style='min-width: 150px;'><b>⚠️ 错误:</b><br>{error_msg}</div>", 
                        self
                    )
                    return 
                else:
                    break
            if top > pos.y(): break
            block = block.next()
        
        QToolTip.hideText()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):
        QToolTip.hideText()
        super().leaveEvent(event)