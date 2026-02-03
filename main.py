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
    
    # 🚀 拦截并手动执行
    if os.environ.get("IS_CHILD_PROCESS") == "TRUE":
        # 🚀 1. 路径补丁：确保能找到打包后的库
        if hasattr(sys, '_MEIPASS'):
            if sys._MEIPASS not in sys.path:
                sys.path.insert(0, sys._MEIPASS)

        # 🚀 2. 核心补丁：伪造 arcade 版本号，防止它去磁盘读那个“变文件夹”的 VERSION 文件
        try:
            import types
            mock_ver = types.ModuleType("arcade.version")
            mock_ver.VERSION = "2.6.17" # 手动定义版本字符串
            sys.modules["arcade.version"] = mock_ver
            print("DEBUG: 已成功注入伪造的 Arcade 版本号")
        except Exception as e:
            print(f"DEBUG: 注入版本号失败: {e}")


        if len(sys.argv) > 1:
            script_to_run = sys.argv[-1]
            if os.path.exists(script_to_run):
                # 🚀 确保子进程的 sys.path 包含打包后的库路径
                if hasattr(sys, '_MEIPASS'):
                    # 将打包根目录加入路径，这样才能找到内置的 arcade
                    if sys._MEIPASS not in sys.path:
                        sys.path.insert(0, sys._MEIPASS)
                
                # 修正工作目录，防止脚本读取相对路径资源失败
                os.chdir(os.path.dirname(os.path.abspath(script_to_run)))
                
                sys.argv = [script_to_run]
                with open(script_to_run, "r", encoding="utf-8") as f:
                    code = f.read()
                
                # 运行环境准备
                global_vars = {
                    "__name__": "__main__",
                    "__file__": script_to_run,
                    "__builtins__": __builtins__
                }
                
                exec(code, global_vars)
        sys.exit(0) 
    else:
        run_app()