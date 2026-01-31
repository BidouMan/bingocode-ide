import sys, os
import jedi
import black
import re
from PySide6.QtWidgets import (QTextEdit, QWidget, QListView,QToolTip)
from PySide6.QtGui import (QColor, QFont, QSyntaxHighlighter, QTextCharFormat, 
                           QPainter, QStandardItemModel, 
                           QStandardItem, QKeyEvent, QTextCursor, QTextBlockFormat,QPalette,
                           QFontDatabase, QPen,QIcon)
from PySide6.QtCore import Qt, QRect, Property,QTimer,QPoint
# from PySide6.QtSvg import QSvgRenderer  # 🚀 必须导入这个
# from PySide6.QtCore import QDirIterator


# 全局变量
RAINBOW_COLORS = ["#ffd700", "#da70d6", "#179fff", "#ff5d5d", "#41e1a4"]



# --- 语法高亮逻辑 (保留原始逻辑) ---
class PygmentsHighlighter(QSyntaxHighlighter):
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
        # 🚀 优化点 1：使用正则直接匹配括号，跳过普通字符
        # 这个正则会一次性找出所有括号及其位置
        bracket_pattern = re.compile(r"[\(\)\[\]\{\}]")
        
        for match in bracket_pattern.finditer(text):
            char = match.group()
            index = match.start()
            
            if char in "([{":
                color = QColor(RAINBOW_COLORS[level % len(RAINBOW_COLORS)])
                fmt = QTextCharFormat()
                fmt.setForeground(color)
                fmt.setFontWeight(QFont.Bold)
                self.setFormat(index, 1, fmt)
                level += 1
            else:
                level = max(0, level - 1)
                color = QColor(RAINBOW_COLORS[level % len(RAINBOW_COLORS)])
                fmt = QTextCharFormat()
                fmt.setForeground(color)
                fmt.setFontWeight(QFont.Bold)
                self.setFormat(index, 1, fmt)
        
        self.setCurrentBlockState(level)

# --- 内嵌补全框 ---
class CompleterWidget(QListView):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_editor = parent

        # --- QSS 属性变量 (设置默认值) ---
        self._list_bg_color = QColor("#2c313a")
        self._list_text_color = QColor("#abb2bf")
        self._item_selected_bg = QColor("#3e4451")
        self._item_selected_text = QColor("#ffffff")
        self._border_color = QColor("#4b5263")

        # 基础设置 (去重)
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
        """安全地更新样式表，避免死循环"""
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
        # 只有当新旧样式不同时才应用，双重保险
        if self.styleSheet() != style:
            self.setStyleSheet(style)
    

    def refresh_font(self):
        f = QFont()
        # 同步编辑器字体族
        f.setFamilies([self.parent_editor.font_family, self.parent_editor.zh_font_family])
        # 补全字号略小于编辑器字号
        new_size = max(9, self.parent_editor.current_font_size - 2)
        f.setPointSize(new_size)
        self.setFont(f)
        
        # 🚀 动态同步补全窗口的宽高
        self.setFixedWidth(self.parent_editor.current_font_size * 18)
        self.setFixedHeight(self.parent_editor.current_font_size * 10)

        # 🚀 动态计算 Item 内边距，防止字号变大后文字重叠
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
        """保留：支持在补全框上滚动鼠标来切换选项"""
        if self.model.rowCount() == 0: return
        row = self.currentIndex().row()
        if event.angleDelta().y() > 0:
            new_row = max(0, row - 1)
        else:
            new_row = min(self.model.rowCount() - 1, row + 1)
        self.setCurrentIndex(self.model.index(new_row, 0))
        event.accept()
    
    def move_selection(self, direction):
        """处理上下键切换：direction 为 -1 (上) 或 1 (下)"""
        if self.model.rowCount() == 0: return
        
        current_row = self.currentIndex().row()
        new_row = current_row + direction
        
        # 循环滚动逻辑
        if new_row < 0: 
            new_row = self.model.rowCount() - 1
        elif new_row >= self.model.rowCount():
            new_row = 0
            
        self.setCurrentIndex(self.model.index(new_row, 0))

    # --- QSS 接口属性 ---
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

# --- 核心编辑器类 ---
class QCodeEditor(QTextEdit):
    def __init__(self, language='python'):
        super().__init__()
        # 1. 属性初始化 (对接 QSS)
        self._line_number_bg = QColor("#23272e")
        self._line_number_text = QColor("#4b5263")
        self._line_number_border = QColor("#181a1f")
        self._current_line_color = QColor("#2c313a")

        self.last_hover_block = -1
        self.file_path = ""
        self.current_font_size = 18
        self.fixed_line_height = 20
        self.error_lines ={}
        self.space_width = self.fontMetrics().horizontalAdvance(' ')
        self.indent_guide_width = self.space_width * 4

        self.setAcceptRichText(False)
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled)
        
        
        self.load_custom_font()
        self.highlighter = PygmentsHighlighter(self.document())
        self.completer = CompleterWidget(self)
        self.completer.clicked.connect(self.insert_completion)
        
        self.line_number_area = LineNumberArea(self)
        self.document().blockCountChanged.connect(self.update_line_number_area_width)
        self.document().documentLayout().update.connect(lambda: self.line_number_area.update())
        self.verticalScrollBar().valueChanged.connect(lambda: self.line_number_area.update())
        
        # 初始化一个防抖定时器->检查变量用 防止每次输入都检查
        self.analyze_timer = QTimer(self)
        self.analyze_timer.setSingleShot(True) # 只触发一次
        self.analyze_timer.timeout.connect(self.update_indent_errors)
        
        # 🚀 替换 ExtraSelection：直接绘制 viewport 背景，解决抖动
        self.cursorPositionChanged.connect(self.viewport().update)
        # self.cursorPositionChanged.connect(self.update_indent_errors)
        self.textChanged.connect(self.request_analyze)
        
        self.setup_font()
        self.update_font_metrics_cache()    # 更新缓存的度量值
        self.update_line_number_area_width(0)

    def request_analyze(self):
        # 每次输入都会重置 500ms 倒计时
        # 只有当用户停止打字 0.5 秒后，才会执行沉重的 Jedi 分析
        self.analyze_timer.start(200)


    def update_indent_errors(self):
        self.error_lines.clear()
        
        # 检查缩进
        self._check_indentation()

        # 检查变量名
        self._check_varname()
            
        # 刷新显示
        self.line_number_area.update()
        self.viewport().update()

    def _check_varname(self):
        code = self.toPlainText()
        if not code.strip(): return
        
        try:
            import keyword
            py_keywords = keyword.kwlist
            script = jedi.Script(code)
            
            # 🚀 方案 1 核心：获取当前光标所在的行号
            current_line = self.textCursor().blockNumber()

            # 仅扫描可见区域以确保性能
            first_v = self.cursorForPosition(QPoint(0, 0)).blockNumber()
            last_v = self.cursorForPosition(QPoint(0, self.viewport().height())).blockNumber()

            identifiers = re.finditer(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', code)
            
            for match in identifiers:
                name = match.group()
                if name in py_keywords or name == 'self': continue

                start_pos = match.start()
                block = self.document().findBlock(start_pos)
                line_num = block.blockNumber()

                # 🚀 关键过滤：
                # 1. 不在可见范围的不查
                # 2. 当前光标所在的行绝对不查 (等用户离开这一行再说)
                # 3. 已经有缩进错误的行不查
                if not (first_v <= line_num <= last_v) or \
                   line_num == current_line or \
                   line_num in self.error_lines:
                    continue

                # 上下文过滤：排除 for i in 和 a = 
                raw_line_text = block.text()
                after_text = raw_line_text[match.end() - block.position():].lstrip()
                if after_text.startswith('in ') or after_text.startswith('='):
                    continue

                line = line_num + 1
                column = start_pos - block.position()
                
                defs = script.goto(line, column)
                if not defs:
                    self.error_lines[line_num] = f"名称 '{name}' 未定义"
                    
        except Exception:
            pass
            
    def _check_indentation(self):
        block = self.document().begin()        
        last_valid_indent = 0
        last_valid_text = ""
        # 🚀 核心：深度堆栈，记录未闭合的括号
        parens_stack = [] 

        while block.isValid():
            raw_text = block.text()
            stripped_text = raw_text.strip()
            line_num = block.blockNumber()

            if not stripped_text:
                block = block.next()
                continue
                
            current_indent = len(raw_text.replace('\t', '    ')) - len(raw_text.lstrip())
            
            # 1. 基础 4 倍数检查 (处于多行括号内时，通常允许非 4 倍数缩进，这里可以放宽)
            if not parens_stack and current_indent % 4 != 0:
                self.error_lines[line_num] = f"缩进错误: {current_indent} 个空格"

            # 2. 智能逻辑检查
            if last_valid_text:
                # 检查是否是由于上一行有冒号引起的缩进增加
                is_after_colon = last_valid_text.endswith(':')
                
                # 🚀 修复点：如果在括号内，或者上一行有反斜杠 \，或者是冒号后，缩进增加是合法的
                if current_indent > last_valid_indent:
                    if not (is_after_colon or parens_stack or last_valid_text.endswith('\\')):
                        self.error_lines[line_num] = "不合理的缩进"
                
                # 冒号后强制缩进
                if is_after_colon and current_indent <= last_valid_indent:
                    self.error_lines[line_num] = "冒号后需要缩进"

            # 🚀 3. 更新括号堆栈 (解决你提到的所有括号/多行字符串报错)
            # 简单扫描当前行增加或减少了多少括号深度
            for char in raw_text:
                if char in "([{":
                    parens_stack.append(char)
                elif char in ")]}":
                    if parens_stack: parens_stack.pop()

            # 更新状态供下行使用
            last_valid_indent = current_indent
            last_valid_text = stripped_text
            block = block.next()


    def paintEvent(self, event):
        painter = QPainter(self.viewport())
        
        if not self.textCursor().hasSelection():
        # 🚀 方案核心：利用 cursorRect 获取 Layout 引擎计算后的精确物理坐标
            crect = self.cursorRect()
            
            # 物理扩容：向上偏 1px，总高度加 2px
            # 这 2 个像素的冗余量足以覆盖 Win/Mac 下所有缩放产生的舍入误差
            draw_rect = QRect(
                0, 
                crect.top() - 1, 
                self.viewport().width(), 
                crect.height() + 2
            )
            
            painter.fillRect(draw_rect, self._current_line_color)

        self.draw_indent_guides(painter)
        self.draw_indent_errors(painter)
        # painter.end()
        
        # 绘制文字
        super().paintEvent(event)

    def update_font_metrics_cache(self):
        """专门负责更新缓存的度量值，在初始化和缩放时调用"""
        metrics = self.fontMetrics()
        # 1. 单个空格宽度
        self.space_width = metrics.horizontalAdvance(' ')
        # 2. 4个空格宽度 (用于 draw_indent_guides)
        self.indent_guide_width = self.space_width * 4
        # 3. 记录逻辑行高，给 LineNumberArea 和绘制背景使用
        # +2 是你代码中原有的微调值
        self.fixed_line_height = metrics.lineSpacing() + 2

        

    def draw_indent_errors(self, painter):
        error_color = getattr(self, '_indent_error_color', QColor(255, 0, 0, 40))
        layout = self.document().documentLayout()
        scroll_y = self.verticalScrollBar().value()
        viewport_h = self.viewport().height()

        # 直接遍历存储好的错误行号
        for line_num, msg in self.error_lines.items():
            block = self.document().findBlockByNumber(line_num)
            if not block.isValid(): continue
            
            rect = layout.blockBoundingRect(block)
            top = rect.top() - scroll_y
            
            # 性能优化：只画可视区域内的
            if top > viewport_h: continue
            if top + rect.height() < 0: continue
            
            painter.fillRect(QRect(0, int(top), self.viewport().width(), int(rect.height())), error_color)

    def draw_indent_guides(self, painter):
        color = getattr(self, '_indent_guide_color', QColor("#3b4048"))
        painter.setPen(QPen(color, 1, Qt.PenStyle.SolidLine))
        
        # 🚀 直接使用预计算的变量，速度极快
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
                    # 🚀 这里的计算也变快了
                    indent_levels = (len(text) - len(stripped_text)) // 4
                    last_indent_levels = indent_levels
                
                for i in range(indent_levels):
                    x = offset_x + (i * indent_width)
                    if indent_levels > 0:
                        painter.drawLine(x, top, x, bottom)
            
            block = block.next()

    def setup_font(self):
        font = QFont()
        # 🚀 严格顺序：英文在前，中文在后
        font.setFamilies([self.font_family, self.zh_font_family, "Consolas"])
        font.setPointSize(self.current_font_size)
        font.setFixedPitch(True)
        # 强制开启抗锯齿，这在 Mac Retina 屏上非常重要
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        self.setFont(font)
        
        metrics = self.fontMetrics()
        # 记录逻辑行高，给 LineNumberArea 使用
        # self.fixed_line_height = metrics.lineSpacing() + 2
        
        # 设置文档属性
        self.document().setDefaultFont(font)
        self.document().setDocumentMargin(0)

    def load_custom_font(self):
        # 1. 获取绝对路径，为打包做准备
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        asset_path = os.path.join(base_dir, "assets", "font")
        
        # 2. 🚀 跨平台默认回退方案
        if sys.platform == "darwin":      # macOS
            self.font_family = "Menlo"    # Mac 默认等宽
            self.zh_font_family = "PingFang SC"
        elif sys.platform == "win32":     # Windows (包含32/64位)
            self.font_family = "Consolas" # Win 默认等宽
            self.zh_font_family = "Microsoft YaHei"
        else:                             # Linux/其他
            self.font_family = "Monospace"
            self.zh_font_family = "sans-serif"

        # 3. 尝试加载你的专属打包字体
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
                    print(f"成功激活内置字体: {f_name} -> {family}")
            else:
                print(f"注意: 未找到内置字体 {f_name}，已切换至系统默认回退方案")

    # --- 缩放逻辑 (修复行号同步) ---
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
        """点击缩放或 Ctrl+滚轮时触发"""
        self.setup_font()
        self.update_font_metrics_cache() # 🚀 必须同步更新缓存
        self.completer.refresh_font()
        self.line_number_area.setFont(self.font())
        self.update_line_number_area_width(0)
        self.line_number_area.update()

    # --- 快捷键与业务逻辑 ---
    def keyPressEvent(self, event: QKeyEvent):
        key, mods = event.key(), event.modifiers()
        char = event.text()
        
        # 1. 补全框可见时的拦截逻辑
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

        # 2. 快捷键逻辑 (Command/Control)
        if mods & Qt.ControlModifier:
            # 缩放：放大 (Ctrl/Cmd + Plus 或 Ctrl/Cmd + Equal)
            if key in (Qt.Key_Plus, Qt.Key_Equal):
                self.current_font_size = min(72, self.current_font_size + 2)
                self.refresh_all_components()
                return
            
            # 缩放：缩小 (Ctrl/Cmd + Minus)
            if key == Qt.Key_Minus:
                self.current_font_size = max(6, self.current_font_size - 2)
                self.refresh_all_components()
                return

            # 缩放：恢复默认 (Ctrl/Cmd + 0)
            if key == Qt.Key_0:
                self.current_font_size = 18
                self.refresh_all_components()
                return

            # 注释逻辑
            if key == Qt.Key_Slash:
                self.toggle_comment()
                return
            
            # 代码格式化 (Shift + Ctrl + F)
            if key == Qt.Key_F and (mods & Qt.ShiftModifier):
                self.format_code()
                return

        # 3. 自动补全括号和引号
        bracket_pairs = {'(': ')', '[': ']', '{': '}', '"': '"', "'": "'"}
        if char in bracket_pairs:
            cursor = self.textCursor()
            if cursor.hasSelection():
                cursor.insertText(f"{char}{cursor.selectedText()}{bracket_pairs[char]}")
                return
            else:
                self.insertPlainText(char + bracket_pairs[char])
                cursor = self.textCursor()
                cursor.movePosition(QTextCursor.Left, QTextCursor.MoveAnchor, 1)
                self.setTextCursor(cursor)
                return

        # 4. 智能退格
        if key == Qt.Key_Backspace:
            cursor = self.textCursor()
            if not cursor.hasSelection():
                line_text = cursor.block().text()[:cursor.columnNumber()]
                if line_text and line_text.isspace() and len(line_text) % 4 == 0:
                    cursor.beginEditBlock()
                    for _ in range(4): cursor.deletePreviousChar()
                    cursor.endEditBlock()
                    return

        # 5. 换行逻辑
        if key in (Qt.Key_Return, Qt.Key_Enter):
            line = self.textCursor().block().text()
            indent = len(line) - len(line.lstrip())
            if line.strip().endswith(':'): 
                indent += 4
            super().keyPressEvent(event)
            self.insertPlainText(" " * indent)
            return

        # 6. 默认输入处理
        super().keyPressEvent(event)
        
        # 7. 触发补全提示
        if char.isalnum() or char == ".":
            self.trigger_completion()

    # --- 其余保留的功能 (注释、格式化等) ---
    def toggle_comment(self):
        cursor = self.textCursor()
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        cursor.setPosition(start); start_block = cursor.blockNumber()
        cursor.setPosition(end, QTextCursor.KeepAnchor); end_block = cursor.blockNumber()
        if cursor.columnNumber() == 0 and cursor.hasSelection(): end_block -= 1
        
        cursor.beginEditBlock()
        for i in range(start_block, end_block + 1):
            block = self.document().findBlockByNumber(i)
            cursor.setPosition(block.position())
            text = block.text()
            if text.lstrip().startswith('#'):
                hash_pos = text.find('#')
                num = 2 if len(text.lstrip()) > 1 and text.lstrip()[1] == ' ' else 1
                cursor.movePosition(QTextCursor.Right, QTextCursor.MoveAnchor, hash_pos)
                cursor.movePosition(QTextCursor.Right, QTextCursor.KeepAnchor, num)
                cursor.removeSelectedText()
            else: cursor.insertText("# ")
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
        try:
            script = jedi.Script(self.toPlainText())
            comps = script.complete(self.textCursor().blockNumber() + 1, self.textCursor().columnNumber())
            if comps:
                self.completer.update_completions(comps[:15])
                crect = self.cursorRect()
                # 🚀 改进：让垂直偏移随行高动态变化 (大约是行高的 1/10)
                vertical_offset = max(2, self.fixed_line_height // 10)
                self.completer.move(
                    crect.left() + self.line_number_area.width(), 
                    crect.bottom() + vertical_offset
                )
            else:
                self.completer.hide()
        except:
            self.completer.hide()

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

    # --- QSS 接口 ---
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
    def indentGuideColor(self): return self._indent_guide_color if hasattr(self, '_indent_guide_color') else QColor("#3b4048")
    @indentGuideColor.setter
    def indentGuideColor(self, c): self._indent_guide_color = QColor(c); self.viewport().update()

    @Property(QColor)
    def indentErrorColor(self): return getattr(self, '_indent_error_color', QColor(255, 0, 0, 50))
    @indentErrorColor.setter
    def indentErrorColor(self, c): self._indent_error_color = QColor(c); self.viewport().update()
    


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor
        # 开启鼠标追踪，否则 mouseMoveEvent 只有在按下鼠标时才触发
        self.setMouseTracking(True)
        
        self.error_icon = QIcon(":/icons/error.svg")

        self.blink_timer = QTimer(self)
        # ✅ 修正连接：指向下面定义的 update_blink
        self.blink_timer.timeout.connect(self.update_blink) 
        self.blink_timer.start(50) # 提高刷新率让呼吸感更顺滑
        self.blink_alpha = 255
        self.blink_dir = -1


    def update_blink(self):
        # 顺滑的呼吸灯逻辑
        self.blink_alpha += self.blink_dir * 10
        if self.blink_alpha <= 100: self.blink_dir = 1
        if self.blink_alpha >= 255: self.blink_dir = -1
        self.update() # 触发重绘

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
                    # 🚀 背景闪烁逻辑
                    flash_color = QColor("#ff5555")
                    flash_color.setAlpha(int(self.blink_alpha * 0.2)) 
                    painter.fillRect(line_rect, flash_color)

                    # 🚀 绘制图标逻辑
                    icon_size = int(self.editor.fixed_line_height * 0.6)
                    # 图标放在左侧，留 4 像素边距
                    icon_rect = QRect(4, top + (self.editor.fixed_line_height - icon_size) // 2, 
                                     icon_size, icon_size)
                    
                    if not self.error_icon.isNull():
                        self.error_icon.paint(painter, icon_rect)
                    else:
                        # 兜底绘制
                        painter.setPen(QColor("#ff5555"))
                        painter.drawText(icon_rect, Qt.AlignCenter, "!")

                # --- 绘制行号文字 ---
                text_color = self.editor._line_number_text
                if line_num in self.editor.error_lines:
                    text_color = QColor("#ff5555")
                
                painter.setPen(text_color)
                # 右侧留 8 像素间距，确保不和右边框贴太近
                painter.drawText(0, top, self.width() - 8, self.editor.fixed_line_height, 
                                 Qt.AlignRight | Qt.AlignVCenter, str(line_num + 1))
            
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
                if hasattr(self.editor, 'error_lines') and line_num in self.editor.error_lines:
                    error_msg = self.editor.error_lines[line_num]
                    
                    # 🚀 纵向优化：
                    # 使用 event.pos().y() (鼠标当前高度) 而不是 top (行顶部)
                    # 然后减去 10 到 15 像素，强行把 Tip 往上提
                    local_tip_point = QPoint(self.width() + 2, event.pos().y() - 40)
                    
                    global_tip_pos = self.mapToGlobal(local_tip_point)
                    
                    QToolTip.showText(global_tip_pos, 
                                      f"<div style='min-width: 150px;'><b>❌ 错误:</b><br>{error_msg}</div>", 
                                      self)
                    return 
                else:
                    break
            
            if top > pos.y(): break
            block = block.next()
        
        QToolTip.hideText()
        super().mouseMoveEvent(event)


    def leaveEvent(self, event):
        # 鼠标离开行号区，强制关闭提示
        QToolTip.hideText()
        super().leaveEvent(event)