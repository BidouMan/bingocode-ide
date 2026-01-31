import sys, os
import jedi
import black
import re
from PySide6.QtWidgets import (QTextEdit, QWidget, QListView)
from PySide6.QtGui import (QColor, QFont, QSyntaxHighlighter, QTextCharFormat, 
                           QPainter, QStandardItemModel, 
                           QStandardItem, QKeyEvent, QTextCursor, QTextBlockFormat,QPalette,
                           QFontDatabase, QPen)
from PySide6.QtCore import Qt, QRect, Property

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
        
        
        
        # 🚀 替换 ExtraSelection：直接绘制 viewport 背景，解决抖动
        self.cursorPositionChanged.connect(self.viewport().update)
        
        self.setup_font()
        self.update_line_number_area_width(0)

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
        painter.end()
        
        # 绘制文字
        super().paintEvent(event)

    def mouseMoveEvent(self, event):
        # 获取鼠标位置对应的光标和行
        cursor = self.cursorForPosition(event.pos())
        block = cursor.block()
        block_number = block.blockNumber() # 获取行号数字

        # 🚀 优化 1：只有行号发生变化时才检测，防止 ToolTip 闪烁
        if block_number != self.last_hover_block:
            self.last_hover_block = block_number
            
            text = block.text()
            stripped = text.lstrip()
            leading_spaces = len(text) - len(stripped)
            
            if text.strip() and leading_spaces % 4 != 0:
                from PySide6.QtWidgets import QToolTip
                # 🚀 优化 2：使用简易 HTML 放大文字（即便没有 QSS 也会生效）
                error_msg = (
                        f"<b>⚠️ 缩进错误</b><br>"
                        f"当前缩进：{leading_spaces} 个空格<br>"
                        f"要求：必须是4个空格哦!"
                    )

                # 🚀 关键改进：调整显示位置
                pos = event.globalPos()
                # 向上偏移约 40-60 像素（根据你的字体大小调整）
                # 这样气泡会出现在鼠标箭头的上方，不会挡住后面的代码
                custom_pos = pos
                custom_pos.setY(pos.y() - 50)
                QToolTip.showText(event.globalPos(), error_msg, self)
            else:
                # 如果这一行没错，或者鼠标移到了正确行，隐藏之前的提示
                from PySide6.QtWidgets import QToolTip
                QToolTip.hideText()

        # 必须调用父类方法，否则会导致鼠标点击、拖拽失效
        super().mouseMoveEvent(event)


    def draw_indent_errors(self, painter):
        error_color = getattr(self, '_indent_error_color', QColor(255, 0, 0, 40))
        block = self.document().begin()
        layout = self.document().documentLayout()
        scroll_y = self.verticalScrollBar().value()

        while block.isValid():
            rect = layout.blockBoundingRect(block)
            top = rect.top() - scroll_y
            if top > self.viewport().height(): break
            
            if top + rect.height() >= 0:
                text = block.text()
                # 检查逻辑：
                # 1. 如果有缩进，是否是 4 的倍数
                leading_spaces = len(text) - len(text.lstrip())
                is_invalid = False
                
                if leading_spaces % 4 != 0:
                    is_invalid = True
                
                # 2. 检查上一行的关联（可选：如上一行没冒号但这一行增加了缩进）
                prev_block = block.previous()
                if prev_block.isValid():
                    prev_text = prev_block.text().strip()
                    prev_indent = len(prev_block.text()) - len(prev_block.text().lstrip())
                    if not prev_text.endswith(':') and leading_spaces > prev_indent:
                        is_invalid = True

                if is_invalid and text.strip(): # 仅对非空行报错
                    painter.fillRect(QRect(0, int(top), self.viewport().width(), int(rect.height())), error_color)
            
            block = block.next()

    def draw_indent_guides(self, painter):
        color = getattr(self, '_indent_guide_color', QColor("#3b4048"))
        painter.setPen(QPen(color, 1, Qt.PenStyle.SolidLine))
        
        metrics = self.fontMetrics()
        # 🚀 准确计算 4 个空格的宽度
        indent_width = metrics.horizontalAdvance(' ') * 4 
        # 🚀 这里的 offset 必须和文字的起始物理坐标完全一致
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
                    # 计算当前行共有多少个 4-空格 缩进
                    indent_levels = (len(text) - len(stripped_text)) // 4
                    last_indent_levels = indent_levels
                
                # 🚀 重点逻辑：
                # 假设这一行有 2 层缩进（8个空格），文字在第 8 格。
                # 我们应该在第 0 格画线，在第 4 格画线。
                # 这样线就永远在文字的左侧，且不会重叠。
                for i in range(indent_levels):
                    # x 计算公式：
                    # 当 i=0 时，线在最左侧偏移位 (offset_x)
                    # 当 i=1 时，线在第 4 个空格位
                    # ...以此类推
                    x = offset_x + (i * indent_width)
                    
                    # 只有当这一行有缩进时，我们才画线
                    # 如果你不想画最左边（第 0 级）那条线，这里可以加 if i > 0:
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
        self.fixed_line_height = metrics.lineSpacing() + 2
        
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
        self.setup_font()
        self.completer.refresh_font()
        # 🚀 修复点 1：同步行号字体并重新算宽
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
        width = 20 + self.fontMetrics().horizontalAdvance('9') * max(2, digits)
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

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.editor._line_number_bg)
        # painter.setPen(QPen(self.editor._line_number_border, 1))
        # painter.drawLine(self.width()-1, 0, self.width()-1, self.height())
        layout, val = self.editor.document().documentLayout(), self.editor.verticalScrollBar().value()
        block = self.editor.document().begin()

        while block.isValid():
            top = round(layout.blockBoundingRect(block).top()) - val
            if top > event.rect().bottom(): break
            if top + self.editor.fixed_line_height >= event.rect().top():
                painter.setPen(self.editor._line_number_text)
                painter.drawText(0, top, self.width()-10, self.editor.fixed_line_height, Qt.AlignRight | Qt.AlignVCenter, str(block.blockNumber()+1))
            block = block.next()