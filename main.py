import sys
import os
from PySide6.QtCore import QLoggingCategory
from PySide6.QtWidgets import QApplication, QWidget, QLayout, QSizePolicy

# --- 1. 路径适配函数 (必须放在最前面) ---
def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# 将 assets 目录添加到 Python 的搜索路径中
sys.path.append(get_resource_path('assets'))
import assets.resources_rc

# 导入转换出来的 UI 类和逻辑模块
from ui.main_window_ui import Ui_Form
from modules.app_controller import AppController

class BingoIDE(QWidget):
    def __init__(self):
        super().__init__()
        
        # 组装 UI
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        
        # 启动 AppController
        self.work = AppController(self)

        # 布局约束设置
        if self.layout():
            self.layout().setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
            
        self.ui.tab_frame.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

# --- 2. 独立的样式加载函数 ---
def load_stylesheet(file_name):
    """通用的样式加载函数"""
    # 🚀 使用 get_resource_path 包装路径
    qss_path = get_resource_path(file_name)
    try:
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                content = f.read()
                print(f"加载样式成功: {qss_path}")
                return content
        else:
            print(f"未找到样式文件: {qss_path}")
    except Exception as e:
        print(f"加载样式表出错: {e}")
    return ""

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 屏蔽调试信息
    QLoggingCategory.setFilterRules("qt.qpa.fonts.debug=false")
    
    # --- 3. 正确加载皮肤样式 ---
    # 统一使用 get_resource_path 包装
    style_data = load_stylesheet(os.path.join('assets', 'qss', 'dark_style.qss'))
    if style_data:
        app.setStyleSheet(style_data) 
    
    window = BingoIDE()
    window.show()
    
    sys.exit(app.exec())