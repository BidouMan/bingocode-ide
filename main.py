import sys
import os
import multiprocessing
from PySide6.QtWidgets import QApplication, QWidget, QLayout, QSizePolicy
from PySide6.QtCore import QLoggingCategory

# --- 1. 路径修复核心逻辑 ---
# 获取当前 main.py 所在的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))

# 让系统能直接识别 modules 文件夹下的库
modules_path = os.path.join(current_dir, "modules")
if modules_path not in sys.path:
    sys.path.insert(0, modules_path)

# 🚀 关键：解决 resources_rc 在 assets 目录下的导入问题
assets_path = os.path.join(current_dir, "assets")
if assets_path not in sys.path:
    sys.path.insert(0, assets_path)

# 🚀 关键：保持 ui 目录在搜索路径中，方便 UI 文件加载
ui_path = os.path.join(current_dir, "ui")
if ui_path not in sys.path:
    sys.path.insert(0, ui_path)

# 🚀 添加 models 目录到搜索路径，方便模型文件加载
models_path = os.path.join(current_dir, "models")
if models_path not in sys.path:
    sys.path.insert(0, models_path)

# --- 2. 导入自定义模块 (必须在路径修复之后) ---
from modules.app_controller import AppController
from ui.main_window_ui import Ui_Form


# --- 3. 资源加载助手 ---
def get_resource_path(relative_path):
    """处理开发环境与 PyInstaller 打包后的路径差异"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(current_dir, relative_path)


def load_stylesheet(file_name):
    """加载 QSS 样式表"""
    qss_path = get_resource_path(file_name)
    try:
        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                return f.read()
    except Exception as e:
        print(f"加载样式表出错: {e}")
    return ""


# --- 4. 主窗口包装类 ---
class BingoIDE(QWidget):
    def __init__(self):
        super().__init__()
        self.ui = Ui_Form()
        self.ui.setupUi(self)

        # 初始化控制器（它会自动对接 StageManager）
        self.controller = AppController(self)

        # UI 基础约束设置
        if self.layout():
            self.layout().setSizeConstraint(QLayout.SizeConstraint.SetDefaultConstraint)
        self.ui.tab_frame.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 只需要这一行，把缩放逻辑“外包”给经理
        if hasattr(self, "controller"):
            self.controller.screen_manager.apply_ratio_constraint()

    def closeEvent(self, event):
        if hasattr(self, "controller"):
            if self.controller.request_exit():
                self.controller.handle_exit_cleanup()
                # 彻底切断引用
                del self.controller
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


# --- 5. 程序启动入口 ---
if __name__ == "__main__":
    # 适配多进程打包
    multiprocessing.freeze_support()
    # 🚀 在创建 QApplication 之前，设置不恢复窗口状态

    app = QApplication(sys.argv)

    # 屏蔽 Qt 内部不必要的字体警告
    QLoggingCategory.setFilterRules(
        "*.debug=false\nqt.qpa.fonts=false\n*.warning=false"
    )
    # 加载暗色皮肤
    style_data = load_stylesheet(os.path.join("assets", "qss", "dark_style.qss"))
    # 加载 sprite editor 样式
    sprite_style_data = load_stylesheet(
        os.path.join("assets", "qss", "sprite_editor_style.qss")
    )
    if style_data:
        app.setStyleSheet(style_data + sprite_style_data)

    # 显示窗口
    window = BingoIDE()
    window.show()

    sys.exit(app.exec())
