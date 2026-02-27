from PySide6.QtCore import QObject, Qt,QSize
from PySide6.QtWidgets import QListWidgetItem, QFileDialog 
from PySide6.QtGui import QIcon,QPixmap,QPainter
import os


from modules.upload_menu_manager import UploadMenuManager

class ResourceManager(QObject):
    def __init__(self, main_ui, parent_window):
        super().__init__()
        self.ui = main_ui
        self.window = parent_window
        
        # 1. 映射表：将按钮对象与对应的页面对象关联
        self.nav_map = {
            self.ui.btn_outline_code: self.ui.page_1,
            self.ui.btn_outline_sprite: self.ui.page_2,
            self.ui.btn_outline_bg: self.ui.page_3,
            self.ui.btn_outline_sound: self.ui.page_4
        }

        self.upload_menu = UploadMenuManager(self.ui.sprite_page_frame)
        
        # 初始化界面
        self.ui.outline_stracked.setCurrentWidget(self.ui.page_1)

    
    def bind_switch_page(self):
        """核心优雅点：循环绑定所有导航按钮"""
        for btn in self.nav_map.keys():
            # 使用 btn=btn 捕获当前循环的变量，避免闭包陷阱
            btn.clicked.connect(lambda checked=False, b=btn: self.switch_page(b))

    def switch_page(self, btn):
        """执行切换逻辑"""
        target_page = self.nav_map.get(btn)
        if target_page:
            self.ui.outline_stracked.setCurrentWidget(target_page)
            print(f"ResourceManager: 切换至 {target_page.objectName()}")
        
        if target_page == self.ui.page_2:
                self.upload_menu.auto_layout()
                self.upload_menu.show()
    

    def add_resource_to_list(self, file_path):
        file_name = os.path.basename(file_path)
        
        # --- 1. 定义标准尺寸 ---
        standard_size = 100  # 每个图标底板的大小
        
        # --- 2. 创建一个透明的底板 ---
        # 这就像是在一张透明的画布上作画
        canvas = QPixmap(standard_size, standard_size)
        canvas.fill(Qt.transparent) # 填充透明色
        
        # --- 3. 加载并缩放原图 ---
        raw_pixmap = QPixmap(file_path)
        # 保持比例缩放，确保图片不会被拉伸变形
        scaled_pixmap = raw_pixmap.scaled(
            standard_size, standard_size, 
            Qt.KeepAspectRatio, 
            Qt.SmoothTransformation
        )
        
        # --- 4. 使用 QPainter 将缩放后的图画在底板中心 ---
        painter = QPainter(canvas)
        # 计算居中坐标： (画布宽 - 图片宽) / 2
        x = (standard_size - scaled_pixmap.width()) // 2
        y = (standard_size - scaled_pixmap.height()) // 2
        painter.drawPixmap(x, y, scaled_pixmap)
        painter.end() # 结束绘画
        
        # --- 5. 生成 Item ---
        item = QListWidgetItem(file_name)
        item.setIcon(QIcon(canvas)) # 关键：使用的是那个带透明底板的 canvas
        item.setTextAlignment(Qt.AlignCenter)
        
        self.ui.list_sprite.addItem(item)
    
    def import_sprite_dialog(self):
        """逻辑：弹出对话框并处理导入"""
        file_path, _ = QFileDialog.getOpenFileName(
            self.window,
            "选择角色图片",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        
        if file_path:
            self.add_resource_to_list(file_path)
    
    # modules/resource_manager.py

def setup_list_style(self):
    list_widget = self.ui.list_sprite
    
    # 网格大小要比图标底板大一些，留给文字空间
    # 宽度 120 (留 10 左右边距), 高度 140 (留 40 给文字)
    list_widget.setGridSize(QSize(120, 140))
    
    # 必须匹配上面代码里的 standard_size
    list_widget.setIconSize(QSize(100, 100))
    
    list_widget.setSpacing(10)
    list_widget.setViewMode(list_widget.ViewMode.IconMode)
    list_widget.setResizeMode(list_widget.ResizeMode.Adjust)
    list_widget.setMovement(list_widget.Movement.Static)