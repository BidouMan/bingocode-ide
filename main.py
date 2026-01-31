import sys
import os
from PySide6.QtCore import QLoggingCategory

# 将 assets 目录添加到 Python 的搜索路径中
sys.path.append(os.path.join(os.path.dirname(__file__), 'assets'))
import assets.resources_rc

# 导入要的qt组件
from PySide6.QtWidgets import QApplication,QWidget,QLayout,QSizePolicy
# 导入转换出来的UI类
from ui.main_window_ui import Ui_Form


# 导入写好的逻辑模块
from modules.app_controller import AppController



class BingoIDE(QWidget):
    def __init__(self):
        super().__init__()
        
        # 组装 UI
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        
        # 启动AppController 开始全部模组上班工作
        self.work = AppController(self)

        # 这一行是“银弹”：它告诉窗口，你的大小只听用户的，不听子控件的
        # 获取窗口的主布局，然后设置约束
        if self.layout():
            self.layout().setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
            

        # 或者是更强力的：禁止布局根据内容自动调整窗口大小
        self.ui.tab_frame.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        # 注意：SetFixedSize 会让窗口完全不能拉伸。
        # 我们通常保持默认，但要确保子控件不申请空间。

    
    
def load_stylesheet(file_path):
    if not os.path.exists(file_path):
        print(f'警告:找不到QSS文件:{file_path}')
        return ''
    with open(file_path,'r',encoding='utf-8') as f:
        print(f'加载成功:{file_path}')
        return f.read()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # 屏蔽字体搜索相关的调试信息
    QLoggingCategory.setFilterRules("qt.qpa.fonts.debug=false")
    
    # 加载皮肤样式 
    style_data = load_stylesheet('assets/qss/dark_style.qss')
    app.setStyleSheet(style_data) 
    
    window = BingoIDE()
    window.show()
    
    sys.exit(app.exec())

    