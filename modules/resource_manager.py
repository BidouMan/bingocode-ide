import os
from PySide6.QtCore import QObject, Qt, QSize
from PySide6.QtWidgets import (QListWidgetItem, QStyle,QMenu, QMessageBox,
                               QWidget,QHBoxLayout,QLabel,QPushButton)
from PySide6.QtGui import QIcon,QFont,QFontDatabase,QCursor
from PySide6.QtSvg import QSvgRenderer

from assets import resources_rc

class CodeItemWidget(QWidget):
    def __init__(self, file_name, icon, font, delete_callback, double_click_callback, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground) 
        self.file_name = file_name
        self.double_click_callback = double_click_callback

        layout = QHBoxLayout(self)
        layout.setContentsMargins(15, 0, 15, 0)
        layout.setSpacing(12)

        # 1. 图标
        self.icon_label = QLabel()
        self.icon_label.setPixmap(icon.pixmap(20, 20))
        self.icon_label.setAttribute(Qt.WA_TransparentForMouseEvents)

        # 2. 文件名
        self.name_label = QLabel(file_name)
        self.name_label.setFont(font)
        self.name_label.setStyleSheet("color: #E0E0E0; background: transparent;")
        self.name_label.setAttribute(Qt.WA_TransparentForMouseEvents)

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
        self.delete_btn.setCursor(QCursor(Qt.PointingHandCursor))
        # 🚀 优化样式：增加悬停反馈
        self.delete_btn.setStyleSheet("""
            QPushButton { border: none; background: transparent; border-radius: 4px; }
            QPushButton:hover { background-color: rgba(255, 77, 77, 0.2); }
        """)
        
        self.delete_btn.setVisible(False)
        self.delete_btn.clicked.connect(lambda: delete_callback(self.file_name))

        layout.addWidget(self.icon_label)
        layout.addWidget(self.name_label, 1)
        layout.addWidget(self.delete_btn)

    def set_active(self, active):
        """同步显示状态"""
        if self.delete_btn.isVisible() != active:
            self.delete_btn.setVisible(active)
            if active:
                self.delete_btn.raise_()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.double_click_callback(self.file_name)

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
        self.bind_switch_page()
        
        # 初始显示
        self.ui.outline_stracked.setCurrentWidget(self.ui.page_code)
        self.refresh_code_list()

        

    def setup_list_styles(self):
        lw = self.ui.list_code
        if not lw: return
        lw.itemSelectionChanged.connect(self.sync_delete_icons)
        lw.setStyleSheet("""
            QListWidget { border: none; background: transparent; outline: none; }
            QListWidget::item { background: transparent; border-radius: 8px; margin: 2px 5px; }
            QListWidget::item:selected { background-color: #4A4A4A; }
            QListWidget QWidget { background: transparent; border: none; }
        """)

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
        # 🚀 存储数据到 Role 中，避免 Text 渲染导致的重叠
        item.setData(Qt.UserRole, name) 
        item.setSizeHint(QSize(0, 45))
        
        
        icon_path = ":/icons/python_file_1.svg"
        icon = QIcon(icon_path) 
        if icon.isNull():
            # 如果加载失败（资源路径错误或未编译），使用系统默认的图标
            icon = self.window.style().standardIcon(QStyle.SP_FileIcon)

        widget = CodeItemWidget(
            name, icon, QFont(self.custom_font_family, 14),
            self.handle_delete_file,
            self.app_controller.open_file_in_editor
        )
        self.ui.list_code.setItemWidget(item, widget)
    
    def load_custom_font(self):
        """加载 assets/font 下的鸿蒙字体"""
        # 获取字体文件的绝对路径        
        res_path = ":/font/HarmonyOS_Sans_SC_Regular.ttf"
        font_id = QFontDatabase.addApplicationFont(res_path)

        # 3. 判断是否加载成功
        # addApplicationFont 失败会返回 -1
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families:
                return families[0]
        
        # 4. 如果加载失败，打印调试信息并回退
        print(f"警告: 无法从资源加载字体 {res_path}，已回退到 Arial")
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
            QMessageBox.Yes | QMessageBox.No, 
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # 2. 物理删除文件
                if os.path.exists(full_path):
                    os.remove(full_path)
                
                # 3. 🚀 关键逻辑：如果该文件在编辑器里开着，得通知 EditorManager 关闭它
                self.close_editor_if_open(full_path)
                
                # 4. 刷新列表
                self.refresh_code_list()
                print(f"成功删除文件: {full_path}")
                
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
        lw.viewport().update()