import sys
import os
import traceback
import logging

# 设置日志级别
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    logging.info("Starting program...")
    
    # 尝试导入所有必要的模块
    logging.info("Importing modules...")
    
    # 先导入基础模块
    logging.info("Importing sys, os, etc...")
    
    # 导入自定义模块
    logging.info("Importing modules.app_controller...")
    from modules.app_controller import AppController
    
    logging.info("Importing ui.main_window_ui...")
    from ui.main_window_ui import Ui_Form
    
    logging.info("All modules imported successfully")
    
    # 尝试创建应用程序
    logging.info("Creating QApplication...")
    from PySide6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    logging.info("QApplication created successfully")
    
    # 尝试创建主窗口
    logging.info("Creating BingoIDE window...")
    class BingoIDE(QWidget):
        def __init__(self):
            super().__init__()
            self.ui = Ui_Form()
            self.ui.setupUi(self)
            self.controller = AppController(self)
    
    window = BingoIDE()
    logging.info("BingoIDE window created successfully")
    
    # 尝试显示窗口
    logging.info("Showing window...")
    window.show()
    
    # 尝试运行应用程序
    logging.info("Running application...")
    sys.exit(app.exec())
    
except Exception as e:
    logging.error(f"Error occurred: {e}")
    logging.error("Full traceback:")
    traceback.print_exc()
    sys.exit(1)
