import os, shutil
import zipfile
import json
from PySide6.QtCore import QObject, Qt, QSize, QEvent, QRect, QTimer, Signal
from PySide6.QtWidgets import (
    QListWidgetItem,
    QStyle,
    QMessageBox,
    QFrame,
    QVBoxLayout,
    QWidget,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QStyledItemDelegate,
    QApplication,
    QScrollArea,
    QGridLayout,
)
from PySide6.QtGui import (
    QIcon,
    QFont,
    QFontDatabase,
    QCursor,
    QPixmap,
    QColor,
    QPainter,
    QPen,
)
from modules.upload_menu_manager import UploadMenuManager, MapUploadMenuManager


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
            card_h,
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
            icon_size,
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
        return QSize(76, 76)


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
        self.box.setFixedSize(48, 48)  # 稍微大一点更协调
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
    def __init__(
        self,
        file_name,
        icon,
        font,
        delete_callback,
        rename_callback,
        double_click_callback,
        parent=None,
    ):
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
        self.btn_layout.setSpacing(8)  # 两个按钮之间的间距

        # --- 重命名按钮 ---
        self.rename_btn = QPushButton()
        rename_icon = QIcon(":/icons/icon--edit.svg")  # 确保你有这个图标
        self.rename_btn.setIcon(
            rename_icon
            if not rename_icon.isNull()
            else self.style().standardIcon(QStyle.SP_DialogResetButton)
        )
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
            self.delete_btn.setStyleSheet(
                "color: #FF4D4D; font-weight: bold; border: none;"
            )

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
        layout.addWidget(self.btn_container)  # 添加容器而不是单个按钮

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
    sig_sprite_selected = Signal(str)  # 双击卡片时：发送文件夹绝对路径
    sig_sprite_imported = Signal(str)  # 导入成功时：发送文件夹绝对路径
    sig_map_selected = Signal(str)  # 双击地图卡片时：发送地图文件绝对路径

    def __init__(self, main_ui, parent_window, app_controller):
        super().__init__()
        self.ui = main_ui
        self.window = parent_window
        self.app_controller = app_controller
        self.custom_font_family = self.load_custom_font()

        # 1. 🚀 必须最先准备好网格容器（创建 self.sprite_grid_layout）
        # 这一步相当于 list_code 在 UI 文件里就已经存在了一样
        self.setup_sprite_grid_mode()

        # 2. 基础映射（保持不变）
        self.nav_map = {
            self.ui.btn_outline_code: self.ui.page_code,
            self.ui.btn_outline_sprite: self.ui.page_sprite,
            self.ui.btn_outline_bg: self.ui.page_map,
            self.ui.btn_outline_sound: self.ui.page_sound,
        }

        self.setup_list_styles()

        # 图片缓存，避免重复加载相同的图片
        self._pixmap_cache = {}

        # 3. 信号绑定
        self.ui.list_code.installEventFilter(self)
        self.bind_switch_page()

        # 监听磁盘重命名
        self.app_controller.editor_manager.file_renamed_on_disk.connect(
            self.refresh_code_list
        )

        # 记录最后选择的角色路径
        self.last_selected_sprite_path = None

        # 4. 🚀 初始显示：像刷新代码列表一样，直接刷新角色网格
        self.ui.list_code.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.ui.outline_stracked.setCurrentWidget(self.ui.page_sprite)

        self.refresh_code_list()  # 刷新代码列表
        self.refresh_sprite_grid()  # 💡 现在刷新就不会报错了，因为 layout 已经准备好了
        self.refresh_map_list()  # 刷新地图列表

        # 5. 上传菜单管理
        self.sprite_upload_menu = UploadMenuManager(self.ui.page_sprite)
        self.sprite_upload_menu.on_import_finished = self.handle_sprite_import_success

        # 地图上传菜单管理
        self.map_upload_menu = MapUploadMenuManager(self.ui.page_map)
        self.map_upload_menu.on_import_finished = self.handle_map_import_success
        self.map_upload_menu.on_create_map = self.handle_create_map

    def setup_list_styles(self):
        lw = self.ui.list_code
        if not lw:
            return
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
        self.ui.list_sprite.setSpacing(2)  # 增加项之间的间距

        # 设置地图列表为网格布局
        self.setup_map_grid_mode()

    def bind_switch_page(self):
        """绑定导航按钮"""
        for btn in self.nav_map.keys():
            btn.clicked.connect(lambda checked=False, b=btn: self.switch_page(b))

    def switch_page(self, btn):
        """切换页面逻辑"""
        target_page = self.nav_map.get(btn)
        if target_page:
            self.ui.outline_stracked.setCurrentWidget(target_page)

            # 🚀 谁的页面被打开，就刷新谁
            if target_page == self.ui.page_code:
                self.refresh_code_list()
            elif target_page == self.ui.page_sprite:
                self.refresh_sprite_grid()
            elif target_page == self.ui.page_map:
                self.refresh_map_list()

    def refresh_code_list(self):
        if not hasattr(self.ui, "list_code"):
            return
        self.ui.list_code.clear()

        project_root = self.app_controller.project_manager.project_root
        if not project_root or not os.path.exists(project_root):
            return

        try:
            files = [
                f
                for f in os.listdir(project_root)
                if f.endswith(".py") and not f.startswith(".")
            ]
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
            name,
            icon,
            QFont(self.custom_font_family, 14),
            self.handle_delete_file,
            self.handle_rename_file,
            # 🚀 传给回调函数的应该是 full_path 而不是 name
            lambda _: self.app_controller.open_file_in_editor(full_path),
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
            "确认删除",
            f"你确定要永久删除文件 '{file_name}' 吗？\n此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
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
            if (
                hasattr(editor, "file_path")
                and os.path.normpath(editor.file_path) == target_path
            ):
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
        try:
            # 1. 代码列表逻辑
            if hasattr(self, "ui") and self.ui and watched == self.ui.list_code:
                if event.type() == QEvent.Type.FocusOut:
                    if self.ui.list_code.selectedItems():
                        self.ui.list_code.clearSelection()

            # 2. 角色卡片逻辑
            if event.type() == QEvent.Type.FocusOut:
                if watched.objectName() == "spriteCard":
                    new_focus = QApplication.focusWidget()

                    # 如果点的是空白或者其他非卡片区域
                    if not new_focus or new_focus.objectName() != "spriteCard":
                        # 不排除任何卡片，全部隐藏
                        self.hide_all_delete_buttons()
                        self.clear_all_selections()
        except RuntimeError:
            # 对象已销毁，忽略事件
            pass

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
                        widget.start_rename()  # 开启原位编辑
                    break
            return

        # 情况 B：拿到了新名字，执行物理重命名
        if not new_name.endswith(".py"):
            new_name += ".py"

        project_root = self.app_controller.project_manager.project_root
        old_path = os.path.join(project_root, old_name)
        new_path = os.path.join(project_root, new_name)

        if os.path.exists(new_path):
            return  # 实际开发中建议加个提示：文件名已存在

        try:
            # 1. 物理改名
            os.rename(old_path, new_path)

            # 2. 同步编辑器中的 Tab 状态
            em = self.app_controller.editor_manager
            for i in range(em.stacked.count()):
                editor = em.stacked.widget(i)
                if hasattr(editor, "file_path") and os.path.normpath(
                    editor.file_path
                ) == os.path.normpath(old_path):
                    editor.file_path = new_path
                    # 更新 Tab 的文字显示
                    display_name = os.path.splitext(new_name)[0]
                    em.tabs.setTabText(i, display_name)
                    break

            # 3. 刷新列表
            self.refresh_code_list()

        except Exception as e:
            print(f"列表重命名失败: {e}")

    def handle_sprite_import_success(self, sprite_name, file_paths, is_bgs=False):
        """核心：处理资源导入，支持 .bgs 解压和 config.json 读取"""
        import shutil
        import zipfile  # 确保导入了 zipfile

        project_root = self.app_controller.project_manager.project_root
        if not project_root:
            return

        sprites_dir = os.path.join(project_root, "assets", "sprites")
        target_dir = ""

        if is_bgs:
            bgs_path = file_paths[0]
            try:
                with zipfile.ZipFile(bgs_path, "r") as zip_ref:
                    # 1. 先读取 config.json 获取真实名字
                    if "config.json" not in zip_ref.namelist():
                        print("❌ .bgs 文件缺少 config.json")
                        return

                    with zip_ref.open("config.json") as f:
                        config_data = json.load(f)
                        # 🚀 修复点：确保获取到名字
                        real_name = config_data.get("name", "new_sprite")

                    # 2. 确定目标目录（使用获取到的 real_name）
                    target_dir = self._get_safe_dir_name(sprites_dir, real_name)
                    os.makedirs(target_dir, exist_ok=True)

                    # 3. 解压所有内容
                    zip_ref.extractall(target_dir)
            except Exception as e:
                print(f"❌ 解压 .bgs 失败: {e}")
                return
        else:
            # 普通图片拷贝逻辑
            target_dir = self._get_safe_dir_name(sprites_dir, sprite_name)
            os.makedirs(target_dir, exist_ok=True)
            for f in file_paths:
                shutil.copy2(f, target_dir)

        # 🚀 后续逻辑：生成配置、发射信号、刷新网格
        if target_dir and os.path.exists(target_dir):
            self.init_sprite_config(target_dir)
            self.sig_sprite_imported.emit(target_dir)
            self.refresh_sprite_grid()

            # 告诉项目管理器：有新角色进来了，项目已经“脏”了，退出时记得提醒保存
            if hasattr(self.app_controller, "project_manager"):
                self.app_controller.project_manager.mark_resource_dirty()

    # 🚀 【新增函数】：用于生成基础 JSON
    def init_sprite_config(self, sprite_path):
        config_file = os.path.join(sprite_path, "config.json")
        if not os.path.exists(config_file):
            # 扫描图片文件
            img_exts = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
            images = sorted(
                [f for f in os.listdir(sprite_path) if f.lower().endswith(img_exts)]
            )

            default_data = {
                "name": os.path.basename(sprite_path),
                "costumes": images,  # 你的 Model 期待的是字符串列表
                "animations": {
                    "默认": {"start": 1, "end": len(images), "fps": 10, "loop": True}
                },
            }
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(default_data, f, indent=4, ensure_ascii=False)

    def _get_safe_dir_name(self, base_path, name):
        """内部工具：防止重名逻辑封装"""
        target = os.path.join(base_path, name)
        counter = 1
        base_name = name
        while os.path.exists(target):
            name = f"{base_name}_{counter}"
            target = os.path.join(base_path, name)
            counter += 1
        return target

    def setup_sprite_grid_mode(self):
        # 1. 找到存放列表的容器 (verticalLayout_15)
        container_layout = self.ui.verticalLayout_15

        # 2. 清除掉旧的 list_sprite (如果有的话)
        if hasattr(self.ui, "list_sprite"):
            self.ui.list_sprite.deleteLater()

        # 3. 创建一个新的滚动区域
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("SpriteScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
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
        self.sprite_grid_layout.setContentsMargins(
            4, 6, 4, 6
        )  # 这里的边距可以自由控制了
        self.sprite_grid_layout.setSpacing(0)
        self.sprite_grid_layout.setVerticalSpacing(5)

        for i in range(4):
            self.sprite_grid_layout.setColumnStretch(i, 1)

        self.sprite_grid_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        # self.grid_container.mousePressEvent = lambda event: self.clear_all_selections()
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.scroll_area.installEventFilter(self)

        self.scroll_area.setWidget(self.grid_container)
        container_layout.addWidget(self.scroll_area)

    def setup_map_grid_mode(self):
        # 1. 找到存放列表的容器 (verticalLayout_21)
        container_layout = self.ui.verticalLayout_21

        # 2. 清除掉旧的 list_map (如果有的话)
        if hasattr(self.ui, "list_map"):
            self.ui.list_map.deleteLater()

        # 3. 创建一个新的滚动区域
        self.map_scroll_area = QScrollArea()
        self.map_scroll_area.setObjectName("MapScrollArea")
        self.map_scroll_area.setWidgetResizable(True)
        self.map_scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.map_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.map_scroll_area.setStyleSheet("background: transparent;")

        # 关键修改：允许点击获取焦点，并安装过滤器
        self.map_scroll_area.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.map_scroll_area.installEventFilter(self)

        # 4. 创建内部容器和网格布局
        self.map_grid_container = QWidget()
        self.map_grid_container.setStyleSheet("background: transparent;")
        self.map_grid_container.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.map_grid_layout = QGridLayout(self.map_grid_container)

        # 重点：设置间距和边距
        self.map_grid_layout.setContentsMargins(4, 6, 4, 6)  # 这里的边距可以自由控制了
        self.map_grid_layout.setSpacing(0)
        self.map_grid_layout.setVerticalSpacing(5)

        for i in range(4):
            self.map_grid_layout.setColumnStretch(i, 1)

        self.map_grid_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft
        )

        self.map_scroll_area.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.map_scroll_area.installEventFilter(self)

        self.map_scroll_area.setWidget(self.map_grid_container)
        container_layout.addWidget(self.map_scroll_area)

    def add_sprite_card(self, name, index, icon_path=None):
        """核心入口：负责卡片的创建与网格定位"""
        from PySide6.QtCore import QTimer

        # 1. 创建基础容器
        card = QWidget()
        card.setFixedSize(74, 74)
        card.setObjectName("spriteCard")
        card.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        card.setProperty("selected", "false")
        card.installEventFilter(self)

        # 2. 调用内部构建逻辑
        self._build_card_ui(card, name, icon_path)
        self._build_card_delete_button(card, name)
        self._setup_card_interactions(card, name)

        # 3. 网格布局定位 (保持 4 列布局)
        row, col = index // 4, index % 4
        self.sprite_grid_layout.addWidget(card, row, col, Qt.AlignmentFlag.AlignCenter)

        return card

    def add_map_card(self, name, index, icon_path=None):
        """核心入口：负责地图卡片的创建与网格定位"""
        from PySide6.QtCore import QTimer

        # 1. 创建基础容器
        card = QWidget()
        card.setFixedSize(74, 74)
        card.setObjectName("mapCard")
        card.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        card.setProperty("selected", "false")
        card.installEventFilter(self)

        # 2. 调用内部构建逻辑
        self._build_map_card_ui(card, name, icon_path)
        self._build_card_delete_button(card, name)
        self._setup_card_interactions(card, name)

        # 3. 网格布局定位 (保持 4 列布局)
        row, col = index // 4, index % 4
        self.map_grid_layout.addWidget(card, row, col, Qt.AlignmentFlag.AlignCenter)

        return card

    def _build_card_ui(self, card, name, icon_path):
        """负责卡片的视觉样式、图标处理和文字"""
        card.setStyleSheet("""
            #spriteCard {
                background-color: #2D2D2D;
                border-radius: 8px;
                border: 2px solid transparent;
            }
            #spriteCard:hover { background-color: #3D3D3D; }
            #spriteCard[selected="true"] {
                background-color: #3D3D3D;
                border: 2px solid #5bc772;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # --- 图标处理 (像素风格缩放) ---
        icon_label = QLabel()
        icon_label.setFixedSize(40, 40)
        if icon_path and os.path.exists(icon_path):
            # 检查缓存中是否已有该图片
            if icon_path in self._pixmap_cache:
                target_pix = self._pixmap_cache[icon_path]
            else:
                pix = QPixmap(icon_path)
                if not pix.isNull():
                    mode = (
                        Qt.TransformationMode.FastTransformation
                        if pix.width() < 100
                        else Qt.TransformationMode.SmoothTransformation
                    )
                    target_pix = pix.scaled(
                        80, 80, Qt.AspectRatioMode.KeepAspectRatio, mode
                    )
                    # 缓存缩放后的图片
                    self._pixmap_cache[icon_path] = target_pix
                else:
                    target_pix = None

            if target_pix:
                icon_label.setPixmap(target_pix)
                icon_label.setScaledContents(True)
            else:
                icon_label.setStyleSheet(
                    "background-color: #4A90E2; border-radius: 4px;"
                )
        else:
            icon_label.setStyleSheet("background-color: #4A90E2; border-radius: 4px;")
        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignCenter)

        # --- 名字处理 (字体与颜色) ---
        name_label = QLabel(name)
        name_label.setObjectName("spriteNameLabel")
        if hasattr(self, "custom_font_family"):
            name_label.setFont(QFont(self.custom_font_family, 12))
        name_label.setStyleSheet("color: #E0E0E0; background: transparent;")
        layout.addWidget(name_label, 0, Qt.AlignmentFlag.AlignCenter)

        # 🚀 保持点击穿透
        icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def _build_map_card_ui(self, card, name, icon_path):
        """负责地图卡片的视觉样式、图标处理和文字"""
        card.setStyleSheet("""
            #mapCard {
                background-color: #2D2D2D;
                border-radius: 8px;
                border: 2px solid transparent;
            }
            #mapCard:hover { background-color: #3D3D3D; }
            #mapCard[selected="true"] {
                background-color: #3D3D3D;
                border: 2px solid #5bc772;
            }
        """)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # --- 图标处理 (像素风格缩放) ---
        icon_label = QLabel()
        icon_label.setFixedSize(40, 40)
        if icon_path and os.path.exists(icon_path):
            # 检查缓存中是否已有该图片
            if icon_path in self._pixmap_cache:
                target_pix = self._pixmap_cache[icon_path]
            else:
                pix = QPixmap(icon_path)
                if not pix.isNull():
                    mode = (
                        Qt.TransformationMode.FastTransformation
                        if pix.width() < 100
                        else Qt.TransformationMode.SmoothTransformation
                    )
                    target_pix = pix.scaled(
                        80, 80, Qt.AspectRatioMode.KeepAspectRatio, mode
                    )
                    # 缓存缩放后的图片
                    self._pixmap_cache[icon_path] = target_pix
                else:
                    target_pix = None

            if target_pix:
                icon_label.setPixmap(target_pix)
                icon_label.setScaledContents(True)
            else:
                # 地图用绿色方块
                icon_label.setStyleSheet(
                    "background-color: #5bc772; border-radius: 4px;"
                )
        else:
            # 地图用绿色方块
            icon_label.setStyleSheet("background-color: #5bc772; border-radius: 4px;")
        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignCenter)

        # --- 名字处理 (字体与颜色) ---
        name_label = QLabel(name)
        name_label.setObjectName("mapNameLabel")
        if hasattr(self, "custom_font_family"):
            name_label.setFont(QFont(self.custom_font_family, 12))
        name_label.setStyleSheet("color: #E0E0E0; background: transparent;")
        layout.addWidget(name_label, 0, Qt.AlignmentFlag.AlignCenter)

        # 🚀 保持点击穿透
        icon_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        name_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def _build_card_delete_button(self, card, name):
        """负责创建右上角的删除按钮"""
        del_btn = QPushButton(card)
        del_btn.setFixedSize(22, 22)
        del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        del_btn.setIcon(QIcon(":/icons/icon--delete.svg"))
        del_btn.setIconSize(QSize(16, 16))
        del_btn.move(50, 2)
        # 修正了之前的 border-radius 单位问题
        del_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff4d4f;
                border-radius: 11px; 
                border: 2px solid #2D2D2D;
            }
            QPushButton:hover { background-color: #ff7875; }
        """)
        del_btn.hide()
        # 🚀 绑定物理删除逻辑
        del_btn.clicked.connect(lambda: self.handle_sprite_delete(name))
        card.del_btn = del_btn

    def _setup_card_interactions(self, card, name):
        """负责长按计时、点击高亮、双击重命名"""
        from PySide6.QtCore import QTimer

        # 准备长按定时器
        card.long_press_timer = QTimer()
        card.long_press_timer.setSingleShot(True)
        card.long_press_timer.timeout.connect(lambda: self.show_delete_mode(card))

        # 整合 MousePress (长按计秒 + 点击高亮)
        def custom_mouse_press(event):
            if event.button() == Qt.MouseButton.LeftButton:
                card.long_press_timer.start(400)
            self.handle_card_click(card, event)

        def custom_mouse_release(event):
            if card.long_press_timer.isActive():
                card.long_press_timer.stop()

        card.mousePressEvent = custom_mouse_press
        card.mouseReleaseEvent = custom_mouse_release

        # card.mouseDoubleClickEvent = lambda event: self.start_sprite_rename(card, name)
        def on_double_click(event):
            project_root = self.app_controller.project_manager.project_root
            # 每个地图有独立文件夹，路径格式：maps/地图名称/地图名称.info（二进制格式）
            full_path = os.path.join(
                project_root, "assets", "maps", name, f"{name}.info"
            )
            # 🚀 发射选中信号，通知 AppController 切换页面并加载地图
            self.sig_map_selected.emit(full_path)

        card.mouseDoubleClickEvent = on_double_click

    def refresh_sprite_grid(self):
        """核心：保持布局不动，只换数据源"""
        self.current_selected_card = None  # 重置选中状态

        # 清空现有卡片
        while self.sprite_grid_layout.count():
            child = self.sprite_grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        # 获取并校验路径
        project_root = self.app_controller.project_manager.project_root
        if not project_root:
            return

        # 确保 assets/sprites 目录存在
        sprites_dir = os.path.join(project_root, "assets", "sprites")
        if not os.path.exists(sprites_dir):
            return

        try:
            sprite_folders = [
                d
                for d in os.listdir(sprites_dir)
                if not d.startswith(".") and os.path.isdir(os.path.join(sprites_dir, d))
            ]
            sprite_folders.sort()

            for i, folder_name in enumerate(sprite_folders):
                folder_path = os.path.join(sprites_dir, folder_name)
                thumb_path = None

                # 🚀 优先尝试从 config.json 获取缩略图
                config_path = os.path.join(folder_path, "config.json")
                if os.path.exists(config_path):
                    try:
                        with open(config_path, "r", encoding="utf-8") as f:
                            cfg = json.load(f)
                            # 获取第一张 costumes 的 file
                            if cfg.get("costumes"):
                                first_file = cfg["costumes"][0].get("file")
                                thumb_path = os.path.join(folder_path, first_file)
                    except:
                        pass

                # 兜底：如果没有 config.json 或读取失败，扫描第一张图
                if not thumb_path or not os.path.exists(thumb_path):
                    img_exts = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
                    files = sorted(
                        [
                            f
                            for f in os.listdir(folder_path)
                            if f.lower().endswith(img_exts)
                        ]
                    )
                    if files:
                        thumb_path = os.path.join(folder_path, files[0])

                self.add_sprite_card(folder_name, i, thumb_path)
        except Exception as e:
            print(f"角色网格刷新失败: {e}")

    def handle_card_click(self, card, event):
        """处理卡片点击：设置焦点并切换高亮"""
        event.accept()
        card.setFocus()  # 🚀 让卡片抓住焦点
        self.hide_all_delete_buttons(exclude_card=card)

        # 获取卡片名称
        name_label = card.findChild(QLabel, "spriteNameLabel")
        if name_label:
            sprite_name = name_label.text()
            project_root = self.app_controller.project_manager.project_root
            if project_root:
                # 记录最后选择的角色路径
                self.last_selected_sprite_path = os.path.join(
                    project_root, "assets", "sprites", sprite_name
                )

        # 取消旧的
        if hasattr(self, "current_selected_card") and self.current_selected_card:
            try:
                self.current_selected_card.setProperty("selected", "false")
                self.current_selected_card.style().unpolish(self.current_selected_card)
                self.current_selected_card.style().polish(self.current_selected_card)
            except RuntimeError:
                pass

        # 选中新的
        self.current_selected_card = card
        card.setProperty("selected", "true")
        card.style().unpolish(card)
        card.style().polish(card)

    def clear_all_selections(self):
        """清除高亮状态"""
        if hasattr(self, "current_selected_card") and self.current_selected_card:
            try:
                self.current_selected_card.setProperty("selected", "false")
                self.current_selected_card.style().unpolish(self.current_selected_card)
                self.current_selected_card.style().polish(self.current_selected_card)
            except RuntimeError:
                pass
            self.current_selected_card = None

    def start_sprite_rename(self, card, old_name):
        from PySide6.QtWidgets import QLineEdit

        name_label = card.findChild(QLabel, "spriteNameLabel")
        if not name_label:
            return

        # 🚀 核心逻辑 1：暂时禁用卡片的布局刷新
        # 这样在创建 edit 控件时，布局管理器不会去重新排列图标
        card.layout().setEnabled(False)

        # 🚀 核心逻辑 2：创建 edit，但不设置父对象为布局管理的对象
        # 我们手动指定它在 card 上的位置
        edit = QLineEdit(card)
        edit.setText(old_name)

        # 获取 Label 当前的准确位置
        geo = name_label.geometry()

        # 🚀 核心逻辑 3：绝对定位，且不让布局影响它
        # 保持高度和位置完全一致，左右可以稍微扩一点方便输入
        edit.setGeometry(geo.adjusted(-4, -2, 4, 2))

        edit.setFont(name_label.font())
        edit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        edit.setStyleSheet("""
            QLineEdit {
                background-color: #1A1A1A;
                color: white;
                border: 1px solid #5bc772;
                border-radius: 4px;
                padding-left: 4px;   /* 文字左右留白 */
                padding-right: 4px;
                padding-top: 1px;    /* 垂直方向微调 */
                padding-bottom: 1px;
                margin: 0px;
            }
        """)

        # 隐藏文字，显示输入框
        name_label.hide()
        edit.show()
        edit.setFocus()
        edit.selectAll()

        def finish_edit():
            if not edit.isVisible():
                return

            new_name = edit.text().strip()

            # 只有当名字真的变了，且不为空时才触发同步
            if new_name and new_name != old_name:
                # 🚀 接入磁盘同步
                self.handle_sprite_physical_rename(old_name, new_name)

            # 以下是原有的 UI 恢复逻辑
            edit.hide()
            edit.deleteLater()
            name_label.show()
            card.layout().setEnabled(True)
            card.update()

        # 信号绑定
        edit.editingFinished.connect(finish_edit)
        # 捕获回车，让它失去焦点触发 finish_edit
        edit.returnPressed.connect(edit.clearFocus)

    def handle_sprite_physical_rename(self, old_name, new_name):
        """物理重命名 assets/sprites 中的文件夹"""
        # 1. 获取项目根路径
        project_root = self.app_controller.project_manager.project_root
        if not project_root:
            return

        # 2. 构建旧路径和新路径
        sprites_dir = os.path.join(project_root, "assets", "sprites")
        old_path = os.path.join(sprites_dir, old_name)
        new_path = os.path.join(sprites_dir, new_name)

        # 3. 安全检查
        if not os.path.exists(old_path):
            return

        if os.path.exists(new_path):
            QMessageBox.warning(
                self.window, "重命名失败", f"角色名称 '{new_name}' 已存在。"
            )
            return

        # 4. 执行重命名
        try:
            os.rename(old_path, new_path)

            # 5. 🚀 关键：重命名后必须刷新整个网格，以确保内部数据一致
            # 如果不刷新，下次点击或再次改名时，逻辑引用的还是旧名字
            self.refresh_sprite_grid()

        except Exception as e:
            QMessageBox.critical(self.window, "错误", f"文件夹重命名失败: {e}")

    def show_delete_mode(self, card):
        """长按触发的效果"""
        if hasattr(card, "del_btn"):
            card.del_btn.show()
            # 这里的 card.update() 确保按钮能立刻显示
            card.update()

    def hide_all_delete_buttons(self, exclude_card=None):
        """隐藏所有删除按钮，支持排除特定卡片"""
        for i in range(self.sprite_grid_layout.count()):
            item = self.sprite_grid_layout.itemAt(i)
            if item:
                w = item.widget()
                # 🚀 如果 w 存在，且不是我们要排除的那张卡片
                if w and w != exclude_card and hasattr(w, "del_btn"):
                    w.del_btn.hide()

    def handle_sprite_delete(self, name):
        """物理删除 assets/sprites 中的文件夹"""
        # 1. 弹出二次确认弹窗
        reply = QMessageBox.question(
            self.window,
            "确认删除",
            f"确定要删除角色 '{name}' 吗？\n此操作将永久删除该文件夹及其所有素材，不可撤销！",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            project_root = self.app_controller.project_manager.project_root
            if not project_root:
                return

            # 构建路径
            target_path = os.path.join(project_root, "assets", "sprites", name)

            try:
                if os.path.exists(target_path):
                    import shutil

                    # 🚀 使用 shutil.rmtree 递归删除整个文件夹
                    shutil.rmtree(target_path)

                    # 🚀 刷新网格，让消失的角色在 UI 上也滚蛋
                    self.refresh_sprite_grid()
                else:
                    QMessageBox.warning(
                        self.window, "删除失败", "找不到该角色的文件夹。"
                    )
            except Exception as e:
                QMessageBox.critical(self.window, "错误", f"无法删除文件夹: {e}")

    def refresh_map_list(self):
        """刷新地图列表"""
        # 检查地图网格布局是否存在，如果不存在则重新创建
        if not hasattr(self, "map_grid_layout"):
            self.setup_map_grid_mode()

        # 清空现有卡片
        while self.map_grid_layout.count():
            child = self.map_grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        project_root = self.app_controller.project_manager.project_root
        if not project_root or not os.path.exists(project_root):
            return

        try:
            maps_dir = os.path.join(project_root, "assets", "maps")
            if os.path.exists(maps_dir):
                # 扫描所有子文件夹，每个地图有独立文件夹
                map_folders = [
                    d
                    for d in os.listdir(maps_dir)
                    if not d.startswith(".")
                    and os.path.isdir(os.path.join(maps_dir, d))
                ]
                map_folders.sort()

                for i, folder_name in enumerate(map_folders):
                    # 每个地图文件夹内有对应的文件（支持二进制和JSON格式）
                    # 先检查二进制文件（.info文件作为入口）
                    info_file_path = os.path.join(
                        maps_dir, folder_name, f"{folder_name}.info"
                    )
                    map_file_path = info_file_path

                    # 如果二进制文件不存在，尝试JSON文件（兼容旧版本）
                    if not os.path.exists(map_file_path):
                        map_file_path = os.path.join(
                            maps_dir, folder_name, f"{folder_name}.json"
                        )
                    if os.path.exists(map_file_path):
                        self.add_map_card(folder_name, i)

        except Exception as e:
            print(f"刷新地图列表失败: {e}")

    def handle_map_import_success(self, map_name, file_paths, is_bgs=False):
        """处理地图导入成功的回调"""
        self.refresh_map_list()

    def handle_create_map(self):
        """处理创建地图的回调"""
        # 获取当前地图数量，生成默认名字
        map_count = self.map_grid_layout.count()
        map_name = f"地图{map_count + 1}"

        # 保存地图数据到文件 - 每个地图一个独立文件夹
        project_root = self.app_controller.project_manager.project_root
        if project_root:
            maps_dir = os.path.join(project_root, "assets", "maps")
            map_folder = os.path.join(maps_dir, map_name)
            tilesets_dir = os.path.join(map_folder, "tilesets")

            # 创建必要的目录结构 - 每个地图有独立文件夹
            os.makedirs(map_folder, exist_ok=True)
            os.makedirs(tilesets_dir, exist_ok=True)
            # 创建地图文件路径 - 使用二进制格式（.info作为入口文件）
            map_file_path = os.path.join(map_folder, f"{map_name}.info")

            # 创建新的空地图模型来保存新地图数据
            from models.map_model import MapDataModel

            new_map_model = MapDataModel()
            # 设置地图名称
            new_map_model.set_map_name(map_name)
            save_result = new_map_model.save(map_file_path)
            print(f"DEBUG: 新地图已保存到: {map_file_path}, 结果: {save_result}")

        # 创建地图卡片
        self.add_map_card(map_name, map_count)

    def destroy(self):
        """销毁ResourceManager，移除所有事件过滤器"""
        try:
            # 移除代码列表的事件过滤器
            if hasattr(self, 'ui') and self.ui and hasattr(self.ui, 'list_code'):
                try:
                    self.ui.list_code.removeEventFilter(self)
                except:
                    pass
            
            # 移除精灵滚动区域的事件过滤器
            if hasattr(self, 'scroll_area'):
                try:
                    self.scroll_area.removeEventFilter(self)
                except:
                    pass
            
            # 移除地图滚动区域的事件过滤器
            if hasattr(self, 'map_scroll_area'):
                try:
                    self.map_scroll_area.removeEventFilter(self)
                except:
                    pass
            
            # 移除所有卡片的事件过滤器
            if hasattr(self, 'sprite_grid_layout'):
                for i in range(self.sprite_grid_layout.count()):
                    item = self.sprite_grid_layout.itemAt(i)
                    if item and item.widget():
                        try:
                            item.widget().removeEventFilter(self)
                        except:
                            pass
            
            if hasattr(self, 'map_grid_layout'):
                for i in range(self.map_grid_layout.count()):
                    item = self.map_grid_layout.itemAt(i)
                    if item and item.widget():
                        try:
                            item.widget().removeEventFilter(self)
                        except:
                            pass
            
            print("✅ [ResourceManager] 事件过滤器已移除")
        except Exception as e:
            print(f"❌ [ResourceManager] 移除事件过滤器失败: {e}")
