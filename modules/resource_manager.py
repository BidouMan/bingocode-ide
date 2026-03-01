import os
from PySide6.QtCore import QObject, Qt, QSize
from PySide6.QtWidgets import QListWidgetItem, QStyle
from PySide6.QtGui import QIcon,QFont,QFontDatabase
from PySide6.QtSvg import QSvgRenderer

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
        self.bind_switch_page()
        
        # 初始显示
        self.ui.outline_stracked.setCurrentWidget(self.ui.page_code)
        self.refresh_code_list()

    def setup_list_styles(self):
        """精修：打造传统的单列纵向 Outline 列表"""
        lw = self.ui.list_code
        if not lw: return

        # 🚀 关键：切回 ListMode (确保单列自上而下)
        lw.setViewMode(lw.ViewMode.ListMode) 
        lw.setFlow(lw.Flow.TopToBottom)
        lw.setMovement(lw.Movement.Static)
        
        # 🚀 调整 1：图标稍微加大，从 18 增加到 22
        lw.setIconSize(QSize(20, 20))  
        lw.setSpacing(4)               # 行与行之间留出一点点缝隙
        lw.setWordWrap(False)
        
        # 🚀 调整 2：通过 QSS 设置更大的字体和内边距
        # 使用普通的字符串拼接，避免三引号引起的高亮问题
        style = (
            "QListWidget { "
            "   border: none; "
            "   background: transparent; "
            "   outline: none; "
            "   padding: 5px; "
            "}"
            "QListWidget::item { "
            "   padding: 8px 12px; "        # 🚀 增加上下内边距，让点击区域更宽阔
            "   border-radius: 6px; "
            "   color: #E0E0E0; "
         
            "}"
            "QListWidget::item:hover { "
            "   background-color: #3F3F3F; "
            "}"
            "QListWidget::item:selected { "
            "   background-color: #4A4A4A; "
            "   color: #FFFFFF; "
            "   font-weight: bold; "        # 选中后加粗，视觉更突出
            "}"
        )
        lw.setStyleSheet(style)
        lw.setStyleSheet(style)

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
        """扫描物理目录并填充代码列表"""
        self.ui.list_code.clear()
        
        # 获取路径 (注意适配你 ProjectManager 里的属性名)
        project_path = self.app_controller.project_manager.project_root
        
        if not project_path or not os.path.exists(project_path):
            return

        try:
            # 过滤 py 文件并排序
            files = [f for f in os.listdir(project_path) if f.endswith('.py') and not f.startswith('.')]
            files.sort(key=lambda x: (x != "main.py", x.lower()))
            
            for file_name in files:
                self._add_code_item(file_name)
        except Exception as e:
            print(f"刷新列表失败: {e}")

    def _add_code_item(self, name):
        """添加传统的行式条目"""
        item = QListWidgetItem(name)
        
        # 1. 🚀 获取 SVG 图标路径
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        icon_path = os.path.join(base_dir, "assets", "icons", "python_file_1.svg")

        # 2. 🚀 使用 QIcon 加载 SVG
        # Qt 会自动识别 .svg 后缀并进行矢量渲染
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
        else:
            icon = self.window.style().standardIcon(QStyle.SP_FileIcon)

        item.setIcon(icon)

        # 3. 🚀 关键：除了 QSS，直接给 Item 对象设置字体 (这是最强效的)
        font = QFont(self.custom_font_family)
        font.setPointSize(16) # 🚀 直接设置字体大小为 18pt (相当于 24px 左右)
        font.setWeight(QFont.Medium)
        item.setFont(font)
        
        # icon = self.window.style().standardIcon(QStyle.SP_FileIcon)
        # item.setIcon(icon)
        
        # 4. 🚀 必须给足高度！如果字体 24px，高度至少要 60px 才协调
        item.setSizeHint(QSize(0, 32))         
        self.ui.list_code.addItem(item)
    
    def load_custom_font(self):
        """加载 assets/font 下的鸿蒙字体"""
        # 获取字体文件的绝对路径
        base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        font_path = os.path.join(base_path, "assets", "font", "HarmonyOS_Sans_SC_Regular.ttf") # 🚀 确认你的文件名
        
        if os.path.exists(font_path):
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                family_name = QFontDatabase.applicationFontFamilies(font_id)[0]
                return family_name
        return "Arial" # 如果加载失败，回退到 Arial