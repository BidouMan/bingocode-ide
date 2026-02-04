import sys
import os
import multiprocessing  # 🚀 必须导入

# --- 1. 路径适配函数 ---
def get_resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

# --- 2. 独立的样式加载函数 ---
def load_stylesheet(file_name):
    qss_path = get_resource_path(file_name)
    try:
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                content = f.read()
                return content
    except Exception as e:
        print(f"加载样式表出错: {e}")
    return ""

# 🚀 重点：将业务逻辑导入放在函数或条件判断内，防止子进程预加载
def run_app():
    from PySide6.QtCore import QLoggingCategory
    from PySide6.QtWidgets import QApplication, QWidget, QLayout, QSizePolicy
    
    # 将 assets 目录添加到搜索路径
    sys.path.append(get_resource_path('assets'))
    import assets.resources_rc

    from ui.main_window_ui import Ui_Form
    from modules.app_controller import AppController

    class BingoIDE(QWidget):
        def __init__(self):
            super().__init__()
            self.ui = Ui_Form()
            self.ui.setupUi(self)
            self.controller = AppController(self)
            if self.layout():
                self.layout().setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
            self.ui.tab_frame.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

        def closeEvent(self, event):
            self.controller.cleanup_before_exit()
            event.accept()

    app = QApplication(sys.argv)
    QLoggingCategory.setFilterRules("qt.qpa.fonts.debug=false")
    
    style_data = load_stylesheet(os.path.join('assets', 'qss', 'dark_style.qss'))
    if style_data:
        app.setStyleSheet(style_data) 
    
    window = BingoIDE()
    window.show()
    sys.exit(app.exec())

# 🚀 核心入口保护
# 🚀 核心入口保护升级版
if __name__ == "__main__":
    multiprocessing.freeze_support()
    
    if os.environ.get("IS_CHILD_PROCESS") == "TRUE":
        # 🚀 1. 路径补丁
        if hasattr(sys, '_MEIPASS'):
            if sys._MEIPASS not in sys.path:
                sys.path.insert(0, sys._MEIPASS)
            # 也要把 modules/internal_lib 加入，防止找不到 arcade_shell
            lib_path = os.path.join(sys._MEIPASS, "modules", "internal_lib")
            if lib_path not in sys.path:
                sys.path.insert(0, lib_path)

        # 🚀 2. 伪造版本号 (解决 VERSION 报错)
        try:
            import types
            m = types.ModuleType("arcade.version")
            m.VERSION = "2.6.17"
            sys.modules["arcade.version"] = m
        except: pass

        # 🚀 3. 运行脚本
        if len(sys.argv) > 1:
            script_to_run = sys.argv[-1]
            if os.path.exists(script_to_run):
                os.chdir(os.path.dirname(os.path.abspath(script_to_run)))
                with open(script_to_run, "r", encoding="utf-8") as f:
                    code = f.read()
                sys.argv = [script_to_run]
                exec(code, {"__name__": "__main__", "__file__": script_to_run})
        sys.exit(0) 
    else:
        run_app()