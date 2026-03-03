import os
import shutil  # 🚀 用于文件拷贝
from PySide6.QtWidgets import QWidget,QFileDialog
from PySide6.QtCore import Qt, QEvent, QPropertyAnimation, QEasingCurve, QRect
from ui.upload_menu_ui import Ui_upload_menu 

class UploadMenuManager(QWidget):
    def __init__(self, list_sprite):
        super().__init__(list_sprite)
        self.ui = Ui_upload_menu()
        self.ui.setupUi(self)

        # 🚀 外部回调接口：由 ResourceManager 在初始化时绑定
        self.on_import_finished = None
        
        # 1. 基础属性
        self.setFixedSize(50, 226)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 🚀 2. 容器设置：不要设置鼠标穿透属性，否则子按钮无法响应
        self.menu_container = QWidget(self)
        self.menu_container.setGeometry(0, 0, 50, 226)
        # 移除这行：self.menu_container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        self.ui.menu_frame.setParent(self.menu_container)
        self.menu_container.setObjectName("upload_menu_mask_container")

        # 3. 核心参数
        self.target_h = 120 
        self.anchor_y = 201 
        
        # 给子按钮安装过滤器
        for btn in [self.ui.btn_import, self.ui.btn_paint, self.ui.btn_open]:
            btn.installEventFilter(self)

        self.ui.menu_frame.setGeometry(10, self.anchor_y, 30, 0)
        self.ui.menu_frame.setVisible(False)

        # 🚀 4. 修正主按钮名称 (btn_upload -> btn_upload1)
        self.ui.btn_upload.setParent(self)
        self.ui.btn_upload.setGeometry(0, 176, 50, 50)
        self.ui.btn_upload.raise_() 

        # 5. 应用遮罩
        from PySide6.QtGui import QRegion
        self.menu_container.setMask(QRegion(0, 0, 50, self.anchor_y))

        # 🚀 6. 事件监听：修正 btn_upload1
        self.anim = None
        self.ui.btn_upload.installEventFilter(self)
        self.installEventFilter(self)
        list_sprite.installEventFilter(self)

        # 绑定按键功能
        self.setup_connections()
        self.auto_layout()


    def setup_connections(self):
        # 🚀 绑定按钮点击事件
        self.ui.btn_import.clicked.connect(lambda: self.on_button_clicked("从文件导入"))
        self.ui.btn_paint.clicked.connect(lambda: self.on_button_clicked("打开画板"))
        self.ui.btn_open.clicked.connect(lambda: self.on_button_clicked("选择库文件"))


    def anim_menu(self, show=True):
        """形变动画逻辑"""
        if self.anim and self.anim.state() == QPropertyAnimation.State.Running:
            self.anim.stop()

        self.anim = QPropertyAnimation(self.ui.menu_frame, b"geometry")
        self.anim.setDuration(300)
        
        if show:
            self.ui.menu_frame.setVisible(True)
            # 向上伸展
            end_geo = QRect(10, self.anchor_y - self.target_h, 30, self.target_h)
        else:
            # 向下收缩
            end_geo = QRect(10, self.anchor_y, 30, 0)

        self.anim.setStartValue(self.ui.menu_frame.geometry())
        self.anim.setEndValue(end_geo)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        if not show:
            self.anim.finished.connect(lambda: self.ui.menu_frame.setVisible(False))
            
        self.anim.start()

    def eventFilter(self, obj, event):
    

        # 🚀 修正为主按钮 btn_upload1
        if obj == self.ui.btn_upload and event.type() == QEvent.Type.Enter:
            self.anim_menu(True)
        # 当鼠标离开整个 UploadMenuManager 区域时收回
        elif obj == self and event.type() == QEvent.Type.Leave:
            self.anim_menu(False)
        
        if event.type() == QEvent.Type.Resize:
            self.auto_layout()
        return super().eventFilter(obj, event)

    def auto_layout(self):
        parent = self.parentWidget()
        if not parent: return
        # 保持在父窗口右下角偏移
        self.move(parent.width() - 70 +15, parent.height() - 226 -5)
        self.raise_()

    
    def on_button_clicked(self, action_name):
        if action_name == "从文件导入":
            self.import_assets()
        self.anim_menu(False)

    def import_assets(self):
        """弹出文件对话框"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择角色序列帧图片", "", 
            "图片文件 (*.png *.jpg *.jpeg *.bmp);;所有文件 (*)"
        )
        
        if files:
            # 🚀 获取文件夹真实名称
            import os
            sprite_name = os.path.basename(os.path.dirname(files[0]))
            if not sprite_name: sprite_name = "new_sprite"
            
            # 触发回调
            if hasattr(self, 'on_import_finished') and self.on_import_finished:
                self.on_import_finished(sprite_name, files)

    def process_imports(self, file_paths, sprite_name):
        """核心：将资源拷贝到当前打开的工程目录下"""
        try:
            # 🚀 修正：不再从脚本位置推算，而是通过管家获取真实的工程根目录
            # 在 ResourceManager 初始化时，我们会确保这个路径是正确的
            if hasattr(self, 'on_import_finished') and self.on_import_finished:
                # 我们先进行物理拷贝。为了拿到 project_root，我们可以从 parent 向上找
                # 或者更稳健地，直接让 ResourceManager 处理路径逻辑
                
                # 暂时先通过 parent 链找到 ResourceManager 拥有的 project_root
                # 假设层级是：UploadMenuManager -> page_sprite -> outline_stacked -> main_ui -> ResourceManager
                # 但更优雅的做法是直接通过回调让 ResourceManager 返回路径
                
                # 这里我们先假设你已经按照下文修改了 ResourceManager，
                # 我们把“在哪里创建文件夹”的决定权交给管家。
                if self.on_import_finished:
                    self.on_import_finished(sprite_name, file_paths)
                    
        except Exception as e:
            print(f"❌ 导入失败: {e}")
