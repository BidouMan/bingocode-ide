import os,shutil
from PySide6.QtCore import QObject, Qt, QSize,QEvent,QRect
from PySide6.QtWidgets import (QListWidgetItem, QStyle, QMessageBox,QFrame,QVBoxLayout,
                               QWidget,QHBoxLayout,QLabel,QPushButton,QListWidget,QStyledItemDelegate,
                               QApplication,QScrollArea,QGridLayout)
from PySide6.QtGui import QIcon, QFont, QFontDatabase, QCursor, QPixmap,QColor,QPainter,QPen
from modules.upload_menu_manager import UploadMenuManager


size = 76
w= 318

class SpriteDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        name = index.data(Qt.ItemDataRole.DisplayRole)
        icon_path = index.data(Qt.ItemDataRole.UserRole)
        
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 🚀 这里的 rect 宽度现在是 77
        rect = option.rect
        
        # 卡片视觉大小设为 70x70，这样每两个卡片之间会有 7px 的间距
        card_w, card_h = 70, 70
        
        # 绝对居中计算：(77 - 70) / 2 = 3.5px
        card_rect = QRect(
            int(rect.left() + (rect.width() - card_w) / 2),
            int(rect.top() + (rect.height() - card_h) / 2),
            card_w,
            card_h
        )

        # --- 绘制背景 ---
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setBrush(QColor(60, 60, 60))
            painter.setPen(QPen(QColor(255, 85, 85), 2))
        else:
            painter.setBrush(QColor(45, 45, 45))
            painter.setPen(Qt.PenStyle.NoPen)
        
        painter.drawRoundedRect(card_rect, 6, 6)

        # --- 绘制图标 (蓝块) ---
        icon_size = 40
        icon_rect = QRect(
            int(card_rect.center().x() - icon_size / 2),
            card_rect.top() + 8,
            icon_size,
            icon_size
        )
        painter.setBrush(QColor(74, 144, 226))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(icon_rect, 6, 6)

        # --- 绘制文字 ---
        painter.setPen(QColor(230, 230, 230))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        text_rect = QRect(card_rect.left(), card_rect.bottom() - 18, card_w, 15)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, name)

        painter.restore()

    def sizeHint(self, option, index):
        # 必须和 GridSize 保持一致
        return QSize(size, size)

class SpriteItemWidget(QWidget):
    def __init__(self, name, font, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 🚀 设为 78，紧贴格子边界
        self.setFixedSize(78, 78)
        
        layout = QVBoxLayout(self)
        # 左右边距设为 0，让内容在 78px 内部绝对居中
        layout.setContentsMargins(0, 5, 0, 5) 
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # 蓝色方块
        self.box = QFrame()
        self.box.setFixedSize(48, 48) # 稍微大一点更协调
        self.box.setStyleSheet("background-color: #4a90e2; border-radius: 6px;")
        
        # 名字
        self.label = QLabel(name)
        self.label.setFont(QFont(font.family(), 8))
        self.label.setFixedWidth(74)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: white;")

        layout.addWidget(self.box, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.label, 0, Qt.AlignmentFlag.AlignCenter)

class CodeItemWidget(QWidget):
    def __init__(self, file_name, icon, font, delete_callback,rename_callback, double_click_callback, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.file_name = file_name
        self.double_click_callback = double_click_callback
        self.rename_callback = rename_callback
        self.current_selected_card = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 15, 0)
        layout.setSpacing(12)

        # 1. 图标
        self.icon_label = QLabel()
        self.icon_label.setPixmap(icon.pixmap(20, 20))
        self.icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # 2. 文件名
        self.name_label = QLabel(file_name)
        self.name_label.setFont(font)
        self.name_label.setStyleSheet("color: #E0E0E0; background: transparent;")
        self.name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)



        # 🚀 3. 按钮容器 (用于存放重命名和删除按钮)
        self.btn_container = QWidget()
        self.btn_layout = QHBoxLayout(self.btn_container)
        self.btn_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_layout.setSpacing(8) # 两个按钮之间的间距

        # --- 重命名按钮 ---
        self.rename_btn = QPushButton()
        rename_icon = QIcon(":/icons/icon--edit.svg") # 确保你有这个图标
        self.rename_btn.setIcon(rename_icon if not rename_icon.isNull() else self.style().standardIcon(QStyle.SP_DialogResetButton))
        self.rename_btn.setFixedSize(26, 26)
        self.rename_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # self.rename_btn.setToolTip("重命名")
        self.rename_btn.setStyleSheet("""
            QPushButton { border: none; background: transparent; border-radius: 4px; }
            QPushButton:hover { background-color: rgba(255, 255, 255, 0.1); }
        """)
        

        # 3. 删除按钮
        self.delete_btn = QPushButton()
        delete_icon_path = ":/icons/icon--delete.svg"
        
        # 🚀 修改变量名为 delete_icon，避免覆盖构造函数参数中的 icon
        delete_icon = QIcon(delete_icon_path)
        
        # 资源系统判定：使用 isNull() 替代 os.path.exists()
        if not delete_icon.isNull():
            self.delete_btn.setIcon(delete_icon)
            self.delete_btn.setIconSize(QSize(18, 18))
        else:
            # 兜底逻辑：如果 QRC 资源未加载成功，显示红色文本
            self.delete_btn.setText("×")
            self.delete_btn.setStyleSheet("color: #FF4D4D; font-weight: bold; border: none;")

        self.delete_btn.setFixedSize(26, 26)
        self.delete_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        # 🚀 优化样式：增加悬停反馈
        self.delete_btn.setStyleSheet("""
            QPushButton { border: none; background: transparent; border-radius: 4px; }
            QPushButton:hover { background-color: rgba(255, 77, 77, 0.2); }
        """)
        
        # self.delete_btn.setVisible(False)
        self.delete_btn.clicked.connect(lambda: delete_callback(self.file_name))
        self.rename_btn.clicked.connect(lambda: rename_callback(self.file_name))

        # 将按钮加入容器
        self.btn_layout.addWidget(self.rename_btn)
        self.btn_layout.addWidget(self.delete_btn)
        
        # 默认隐藏整个按钮容器
        self.btn_container.setVisible(False)

        # 重新编排主布局
        layout.addWidget(self.icon_label)
        layout.addWidget(self.name_label, 1)
        layout.addWidget(self.btn_container) # 添加容器而不是单个按钮

    def set_active(self, active):
        """同步显示状态"""
        if self.btn_container.isVisible() != active:
            self.btn_container.setVisible(active)
            if active:
                self.btn_container.raise_()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_click_callback(self.file_name)
            # 🚀 阻止事件传递，防止 ListWidget 误判
            event.accept()
    
    def start_rename(self):
        """进入原位重命名模式"""
        from PySide6.QtWidgets import QLineEdit
        
        # 创建一个临时输入框，覆盖在 name_label 上
        self.edit = QLineEdit(self)
        self.edit.setText(self.file_name)
        # 这里的布局计算要匹配你的 UI 样式
        self.edit.setGeometry(self.name_label.geometry()) 
        self.edit.setFont(self.name_label.font())
        self.edit.setStyleSheet("""
            QLineEdit { 
                background: #2D2D2D; 
                color: white; 
                border: 1px solid #555; 
                border-radius: 6px;
            }
        """)
        
        self.name_label.hide()
        self.edit.show()
        self.edit.setFocus()
        self.edit.selectAll()

        # 绑定提交逻辑
        def finish():
            new_name = self.edit.text().strip()
            if new_name and new_name != self.file_name:
                # 触发真正的物理重命名逻辑
                self.rename_callback(self.file_name, new_name)
            
            self.edit.deleteLater()
            self.name_label.show()

        self.edit.returnPressed.connect(finish)
        self.edit.editingFinished.connect(finish)

class ResourceManager(QObject):
    def __init__(self, main_ui, parent_window, app_controller):
        super().__init__()
        self.ui = main_ui
        self.window = parent_window
        self.app_controller = app_controller
        self.custom_font_family = self.load_custom_font()

        # 修正映射：btn_outline_bg 文字是“代码”
        self.nav_map = {
            self.ui.btn_outline_code: self.ui.page_code,      
            self.ui.btn_outline_sprite: self.ui.page_sprite, 
            self.ui.btn_outline_bg: self.ui.page_map,     
            self.ui.btn_outline_sound: self.ui.page_sound   
        }

        self.setup_list_styles()       
        # 绑定信号
        self.ui.list_code.installEventFilter(self)
        self.bind_switch_page()
        self.app_controller.editor_manager.file_renamed_on_disk.connect(self.refresh_code_list)
        
        # 初始显示
        self.ui.list_code.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.ui.outline_stracked.setCurrentWidget(self.ui.page_code)
        self.refresh_code_list()
        self.sprite_upload_menu = UploadMenuManager(self.ui.page_sprite)
        self.sprite_upload_menu.on_import_finished = self.handle_sprite_import_success

        self.setup_sprite_grid_mode()
        # for i in range(8):
        #     self.add_sprite_test_item(f"测试角色_{i}", "")
        

    def setup_list_styles(self):
        lw = self.ui.list_code
        if not lw: return
        lw.itemSelectionChanged.connect(self.sync_delete_icons)
        lw.setStyleSheet("""
            /* 1. 基础容器：彻底去边框和虚线框 */
            QListWidget { 
                border: none; 
                background: transparent; 
                outline: none; 
            }
            
            /* 2. 列表项：保持你的圆角和边距逻辑 */
            QListWidget::item { 
                background: transparent; 
                border-radius: 8px; 
                margin: 2px 5px; 
            }
            
            /* 3. 选中状态：统一激活和非激活的颜色基础，防止抠图感 */
            QListWidget::item:selected { 
                background-color: #3D3D3D; 
            }
            
            /* 4. 视觉欺骗：失去焦点时强制透明 */
            QListWidget::item:selected:!active { 
                background-color: transparent; 
            }

            /* 5. 内部组件：确保背景不冲突 */
            QListWidget QWidget { 
                background: transparent; 
                border: none; 
            }
            
            /* 6. 按钮默认状态：完全收缩 (保持你原始的 0px 逻辑) */
            QListWidget QPushButton {
                background-color: transparent;
                border: none;
                width: 0px;
                min-width: 0px;
                max-width: 0px;
                qproperty-flat: true;
            }

            /* 7. 按钮显影：列表激活且选中时恢复宽度 */
            QListWidget:active ::item:selected QPushButton {
                width: 24px;
                min-width: 24px;
                max-width: 24px;
            }
        """)

      
        style = self.ui.list_code.styleSheet()
        self.ui.list_sprite.setStyleSheet(style)
        self.ui.list_sprite.setSpacing(2) # 增加项之间的间距

    def bind_switch_page(self):
        """绑定导航按钮"""
        for btn in self.nav_map.keys():
            btn.clicked.connect(lambda checked=False, b=btn: self.switch_page(b))

    def switch_page(self, btn):
        """切换页面逻辑"""
        target_page = self.nav_map.get(btn)
        if target_page:
            self.ui.outline_stracked.setCurrentWidget(target_page)
            if target_page == self.ui.page_code:
                self.refresh_code_list()

    def refresh_code_list(self):
        if not hasattr(self.ui, 'list_code'): return
        self.ui.list_code.clear()
        
        project_root = self.app_controller.project_manager.project_root
        if not project_root or not os.path.exists(project_root): return

        try:
            files = [f for f in os.listdir(project_root) if f.endswith('.py') and not f.startswith('.')]
            files.sort(key=lambda x: (x != "main.py", x.lower()))
            
            for file_name in files:
                self._add_code_item(file_name)
            
            self.sync_delete_icons()
        except Exception as e:
            print(f"刷新失败: {e}")

    def _add_code_item(self, name):
        item = QListWidgetItem(self.ui.list_code)
        item.setData(Qt.ItemDataRole.UserRole, name)
        item.setSizeHint(QSize(0, 45))
        
        # 🚀 关键修改：获取文件的完整绝对路径
        project_root = self.app_controller.project_manager.project_root
        full_path = os.path.join(project_root, name)

        icon_path = ":/icons/python_file_1.svg"
        icon = QIcon(icon_path) 
        if icon.isNull():
            icon = self.window.style().standardIcon(QStyle.SP_FileIcon)

        widget = CodeItemWidget(
            name, icon, QFont(self.custom_font_family, 14),
            self.handle_delete_file,
            self.handle_rename_file,
            # 🚀 传给回调函数的应该是 full_path 而不是 name
            lambda _: self.app_controller.open_file_in_editor(full_path) 
        )
        self.ui.list_code.setItemWidget(item, widget)

    @staticmethod
    def load_custom_font():
        """加载 assets/font 下的鸿蒙字体"""
        res_path = ":/font/HarmonyOS_Sans_SC_Regular.ttf"
        font_id = QFontDatabase.addApplicationFont(res_path)

        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                return families[0]

        # 🚀 放在这里作为终极兜底，无论哪一步失败都会返回 Arial
        return "Arial"




    def handle_delete_file(self, file_name):
        """处理删除逻辑"""
        project_root = self.app_controller.project_manager.project_root
        full_path = os.path.join(project_root, file_name)

        # 1. 弹出确认对话框
        reply = QMessageBox.question(
            self.window, 
            '确认删除', 
            f"你确定要永久删除文件 '{file_name}' 吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # 2. 物理删除文件
                if os.path.exists(full_path):
                    os.remove(full_path)
                
                # 3. 🚀 关键逻辑：如果该文件在编辑器里开着，得通知 EditorManager 关闭它
                self.close_editor_if_open(full_path)
                
                # 4. 刷新列表
                self.refresh_code_list()
                
            except Exception as e:
                QMessageBox.critical(self.window, "错误", f"删除失败: {e}")

    def close_editor_if_open(self, file_path):
        """检查编辑器是否打开了该文件，如果是则关闭对应的 Tab"""
        em = self.app_controller.editor_manager
        # 规范化路径用于对比
        target_path = os.path.normpath(file_path)
        
        for i in range(em.stacked.count()):
            editor = em.stacked.widget(i)
            if hasattr(editor, 'file_path') and os.path.normpath(editor.file_path) == target_path:
                # 调用你 editor_manager 里现成的 close_tab 方法
                em.close_tab(i)
                break
    
    def sync_delete_icons(self):
        """同步所有按钮的显示状态"""
        lw = self.ui.list_code
        for i in range(lw.count()):
            item = lw.item(i)
            widget = lw.itemWidget(item)
            if widget:
                # 只有被选中的项才显示删除按钮
                widget.set_active(item.isSelected())

    
    def eventFilter(self, watched, event):
        # 1. 代码列表逻辑
        if watched == self.ui.list_code:
            if event.type() == QEvent.Type.FocusOut:
                if self.ui.list_code.selectedItems():
                    self.ui.list_code.clearSelection()

        # 2. 角色卡片逻辑
        if event.type() == QEvent.Type.FocusOut:
            if watched.objectName() == "spriteCard":
                new_focus = QApplication.focusWidget()
                
                # 🚀 优化判定：只要新焦点不是卡片本身，就清空
                # 这样即使点到 list_code、代码区或背景，都能触发清空
                if not new_focus or new_focus.objectName() != "spriteCard":
                    self.clear_all_selections()
        
        return super().eventFilter(watched, event)

    def clear_list_selection(self):
        """供外部调用：清空列表选中并隐藏删除按钮"""
        self.ui.list_code.clearSelection()
        self.sync_delete_icons()
    
    def handle_rename_file(self, old_name, new_name=None):
        """处理重命名"""
        # 情况 A：如果没传 new_name，说明是刚点下按钮，开启编辑框
        if new_name is None:
            lw = self.ui.list_code
            for i in range(lw.count()):
                item = lw.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == old_name:
                    widget = lw.itemWidget(item)
                    if widget:
                        widget.start_rename() # 开启原位编辑
                    break
            return

        # 情况 B：拿到了新名字，执行物理重命名
        if not new_name.endswith('.py'):
            new_name += '.py'

        project_root = self.app_controller.project_manager.project_root
        old_path = os.path.join(project_root, old_name)
        new_path = os.path.join(project_root, new_name)

        if os.path.exists(new_path):
            return # 实际开发中建议加个提示：文件名已存在

        try:
            # 1. 物理改名
            os.rename(old_path, new_path)
            
            # 2. 同步编辑器中的 Tab 状态
            em = self.app_controller.editor_manager
            for i in range(em.stacked.count()):
                editor = em.stacked.widget(i)
                if hasattr(editor, 'file_path') and os.path.normpath(editor.file_path) == os.path.normpath(old_path):
                    editor.file_path = new_path
                    # 更新 Tab 的文字显示
                    display_name = os.path.splitext(new_name)[0]
                    em.tabs.setTabText(i, display_name)
                    break
            
            # 3. 刷新列表
            self.refresh_code_list()
            
        except Exception as e:
            print(f"列表重命名失败: {e}")
    
    def handle_sprite_import_success(self, sprite_name, file_paths):
        """第一步：只负责拷贝和触发刷新"""
        import shutil
        project_root = self.app_controller.project_manager.project_root
        if not project_root: return

        # 确定目标路径
        target_dir = os.path.join(project_root, "assets", "sprites", sprite_name)
        
        # 防止同名覆盖
        counter = 1
        base_target = target_dir
        while os.path.exists(target_dir):
            target_dir = f"{base_target}_{counter}"
            sprite_name = f"{sprite_name}_{counter}"
            counter += 1
            
        os.makedirs(target_dir, exist_ok=True)
        for f in file_paths:
            shutil.copy2(f, target_dir)
            
        # 拷贝完直接刷新界面
        self.refresh_sprite_grid()

    def setup_sprite_grid_mode(self):
        # 1. 找到存放列表的容器 (verticalLayout_15)
        container_layout = self.ui.verticalLayout_15
        
        # 2. 清除掉旧的 list_sprite (如果有的话)
        if hasattr(self.ui, 'list_sprite'):
            self.ui.list_sprite.deleteLater()

        # 3. 创建一个新的滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("SpriteScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("background: transparent;")

        # 🚀 关键修改：允许点击获取焦点，并安装过滤器
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.scroll_area.installEventFilter(self)


        # 4. 创建内部容器和网格布局
        self.grid_container = QWidget()
        self.grid_container.setStyleSheet("background: transparent;")
        self.grid_container.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.sprite_grid_layout = QGridLayout(self.grid_container)
        


        # 🚀 重点：设置间距和边距
        self.sprite_grid_layout.setContentsMargins(4, 6, 4, 6) # 这里的边距可以自由控制了
        self.sprite_grid_layout.setSpacing(0)
        self.sprite_grid_layout.setVerticalSpacing(5)

    
        for i in range(4):
            self.sprite_grid_layout.setColumnStretch(i,1)


        self.sprite_grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        
        # self.grid_container.mousePressEvent = lambda event: self.clear_all_selections()
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.scroll_area.installEventFilter(self)

        self.scroll_area.setWidget(self.grid_container)
        container_layout.addWidget(self.scroll_area)

        
        
        

    def add_sprite_card(self, name, index, icon_path=None):
        # 创建卡片
        card = QWidget()
        card.setFixedSize(74, 74) 
        card.setObjectName("spriteCard")
        
        # 🚀 必须设置焦点策略，否则无法触发 FocusOut 事件
        card.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        
        # 注册事件过滤器（用于监控它的失去焦点动作）
        card.installEventFilter(self)

        card.setStyleSheet("""
            #spriteCard {
                background-color: #2D2D2D;
                border-radius: 8px;
                border: 2px solid transparent;
            }
            #spriteCard:hover {
                background-color: #3D3D3D;
            }
            #spriteCard[selected="true"] {
                background-color: #3D3D3D;
                border: 2px solid #5bc772;
            }
        """)
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # 图标部分
        icon_label = QLabel()
        icon_label.setFixedSize(40, 40)
        if icon_path and os.path.exists(icon_path):
            pix = QPixmap(icon_path)
            if not pix.isNull():
                # 🚀 核心方案：模仿像素风格渲染
                # 1. 检查原始尺寸，如果是极小图（比如 32x32 或 16x16）
                if pix.width() < 100: 
                    # 使用 FastTransformation (即邻近采样)，这样像素点边缘会非常锐利
                    # 先放大一倍提高采样密度，再由容器进行物理显示
                    target_pix = pix.scaled(
                        80, 80, 
                        Qt.AspectRatioMode.KeepAspectRatio, 
                        Qt.TransformationMode.FastTransformation # 👈 像素风格的关键：不进行平滑
                    )
                else:
                    # 对于普通高清大图，依然保持平滑缩放，防止锯齿太难看
                    target_pix = pix.scaled(
                        80, 80, 
                        Qt.AspectRatioMode.KeepAspectRatio, 
                        Qt.TransformationMode.SmoothTransformation
                    )
                
                icon_label.setPixmap(target_pix)
                # 🚀 配合这个属性，让 80 缩回 40 时保持锐利
                icon_label.setScaledContents(True)
        else:
            icon_label.setStyleSheet("background-color: #4A90E2; border-radius: 4px;")

        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignCenter)

        # 名字部分
        name_label = QLabel(name)
        # 🚀 核心修改：使用已加载的自定义字体家族
        # self.custom_font_family 是你在 __init__ 中获取的字体名称
        if hasattr(self, 'custom_font_family'):
            name_label.setFont(QFont(self.custom_font_family, 12)) 
        else:
            name_label.setStyleSheet("font-size: 12px;") # 兜底策略

        # 更新样式表：移除重复的 font-size 设置，确保背景透明
        name_label.setStyleSheet("color: #E0E0E0; background: transparent;")
        layout.addWidget(name_label, 0, Qt.AlignmentFlag.AlignCenter)

        # 网格布局定位
        row, col = index // 4, index % 4
        self.sprite_grid_layout.addWidget(card, row, col, Qt.AlignmentFlag.AlignCenter)

        # 🚀 点击事件：高亮 + 拿焦点
        card.mousePressEvent = lambda event: self.handle_card_click(card, event)
        card.setProperty("selected", "false")
        
        return card
    
    def refresh_sprite_grid(self):
        """核心：保持布局不动，只换数据源"""
        # 🚀 关键修复：清空布局前，务必重置当前选中，防止变量指向已被销毁的卡片
        self.current_selected_card = None

        # 清空
        while self.sprite_grid_layout.count():
            child = self.sprite_grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # 获取路径
        project_root = self.app_controller.project_manager.project_root
        if not project_root: return
        
        sprites_dir = os.path.join(project_root, "assets", "sprites")
        if not os.path.exists(sprites_dir):
            os.makedirs(sprites_dir, exist_ok=True)
            return

        # 扫描文件夹
        items = os.listdir(sprites_dir)
        sprite_folders = [d for d in items if not d.startswith('.') and os.path.isdir(os.path.join(sprites_dir, d))]
        sprite_folders.sort()

        # 遍历渲染
        for i, folder_name in enumerate(sprite_folders):
            # 🚀 增加：寻找该角色文件夹下的第一张图
            folder_path = os.path.join(sprites_dir, folder_name)
            img_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.webp')
            thumb_path = None
            
            try:
                # 获取文件夹内所有文件，过滤出图片并排个序
                files = [f for f in os.listdir(folder_path) if f.lower().endswith(img_exts)]
                if files:
                    files.sort()
                    thumb_path = os.path.join(folder_path, files[0])
            except:
                pass

            # 🚀 关键：依然使用 add_sprite_card，只是多传了 thumb_path
            self.add_sprite_card(folder_name, i, thumb_path)
    
    
    
    def handle_card_click(self, card, event):
        """处理卡片点击：设置焦点并切换高亮"""
        event.accept()
        card.setFocus() # 🚀 让卡片抓住焦点
        
        # 取消旧的
        if hasattr(self, 'current_selected_card') and self.current_selected_card:
            try:
                self.current_selected_card.setProperty("selected", "false")
                self.current_selected_card.style().unpolish(self.current_selected_card)
                self.current_selected_card.style().polish(self.current_selected_card)
            except RuntimeError: pass

        # 选中新的
        self.current_selected_card = card
        card.setProperty("selected", "true")
        card.style().unpolish(card)
        card.style().polish(card)

    def clear_all_selections(self):
        """清除高亮状态"""
        if hasattr(self, 'current_selected_card') and self.current_selected_card:
            try:
                self.current_selected_card.setProperty("selected", "false")
                self.current_selected_card.style().unpolish(self.current_selected_card)
                self.current_selected_card.style().polish(self.current_selected_card)
            except RuntimeError: pass
            self.current_selected_card = None