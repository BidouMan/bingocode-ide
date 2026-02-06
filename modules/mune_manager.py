from PySide6.QtCore import Signal
from modules.popup_manager import PopupManager
from ui.file_menu_ui import Ui_Form # 假设你导出的 UI 类名

class MenuManager(PopupManager):
    # 定义信号->这里只负责自己的任务 发信号 至于谁收信号做什么不用管
    new_file_signal = Signal()
    open_file_signal = Signal()
    save_file_signal = Signal()
    save_as_signal = Signal()
    close_file_signal = Signal()
    exit_project_signal = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Form()
        self.ui.setupUi(self)
        
        # 绑定按键
        self.ui.btn_new.clicked.connect(self.emit_new_file_signal)
        self.ui.btn_open.clicked.connect(self.emit_open_signal)
        self.ui.btn_save.clicked.connect(self.emit_save_signal)
        self.ui.btn_save_as.clicked.connect(self.emit_save_as_signal)
        self.ui.btn_close.clicked.connect(self.emit_close_file_signal)
        self.ui.btn_exit.clicked.connect(self.emit_exit_project_signal)

    def emit_new_file_signal(self):
        self.new_file_signal.emit()
        self.close()
        # print('发送信号:新建文件')

    def emit_open_signal(self):
        self.open_file_signal.emit()
        self.close() # 点击后菜单应消失
        # print("发送信号:打开文件")  
    
    def emit_save_signal(self):
        self.save_file_signal.emit()
        self.close() # 点击后菜单应消失
        # print('发送信号:保存文件')
    
    def emit_save_as_signal(self):
        self.save_as_signal.emit()
        self.close()
        # print('发送信号:另存为')
    
    def emit_close_file_signal(self):
        self.close_file_signal.emit()
        self.close()
        print('发送信号:关闭文件')
    
    def emit_exit_project_signal(self):
        self.exit_project_signal.emit()
        self.close()
        print('发送信号:退出项目')
    
    
