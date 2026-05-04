import os
import shutil  # 🚀 用于文件拷贝
from PySide6.QtWidgets import QWidget,QFileDialog
from PySide6.QtCore import Qt, QEvent, QPropertyAnimation, QEasingCurve, QRect
from ui.upload_menu_ui import Ui_upload_menu 
from ui.map_upload_ui import Ui_upload_menu as Ui_map_upload_menu


class UploadMenuManager(QWidget):
    def __init__(self, parent_widget):
        super().__init__(parent_widget)
        self.ui = Ui_upload_menu()
        self.ui.setupUi(self)

        # 🚀 外部回调接口：由 ResourceManager 在初始化时绑定
        self.on_import_finished = None
        self.on_create_map = None
        self.on_open_lib = None
        
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
        parent_widget.installEventFilter(self)

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
        try:
            # 🚀 修正为主按钮 btn_upload1
            if hasattr(self, 'ui') and self.ui and obj == self.ui.btn_upload and event.type() == QEvent.Type.Enter:
                self.anim_menu(True)
            # 当鼠标离开整个 UploadMenuManager 区域时收回
            elif obj == self and event.type() == QEvent.Type.Leave:
                self.anim_menu(False)
            
            if event.type() == QEvent.Type.Resize:
                self.auto_layout()
        except RuntimeError:
            # 对象已销毁，忽略事件
            pass
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
        elif action_name == "创建地图":
            if self.on_create_map:
                self.on_create_map()
        elif action_name == "选择库文件":
            if self.on_open_lib:
                self.on_open_lib()
        self.anim_menu(False)


    def import_assets(self):
        """弹出文件对话框：增加 .bgs 支持"""
        # 🚀 修改：增加 .bgs 过滤器
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择角色资源", "", 
            "Bingo 角色包 (*.bgs);;图片序列帧 (*.png *.jpg *.jpeg *.bmp);;所有文件 (*)"
        )
        
        if files:
            # 🚀 修复焦点丢失问题：强制主窗口重新获取焦点
            self.activateWindow()
            self.raise_()
            
            # 如果选中的是 .bgs 文件，我们单独处理
            if len(files) == 1 and files[0].lower().endswith('.bgs'):
                # 触发 .bgs 专属回调（复用接口，但传特殊标志）
                if self.on_import_finished:
                    self.on_import_finished(None, files, is_bgs=True)
            else:
                # 原有的序列帧处理逻辑
                import os
                sprite_name = os.path.basename(os.path.dirname(files[0]))
                if not sprite_name: sprite_name = "new_sprite"
                
                if self.on_import_finished:
                    self.on_import_finished(sprite_name, files, is_bgs=False)


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

    def destroy(self):
        """销毁UploadMenuManager，移除所有事件过滤器"""
        try:
            # 移除按钮的事件过滤器
            if hasattr(self, 'ui') and self.ui:
                for btn in [self.ui.btn_import, self.ui.btn_paint, self.ui.btn_open, self.ui.btn_upload]:
                    try:
                        btn.removeEventFilter(self)
                    except:
                        pass
            
            # 移除自身的事件过滤器
            self.removeEventFilter(self)
            
            # 移除父窗口的事件过滤器
            parent = self.parentWidget()
            if parent:
                parent.removeEventFilter(self)
                
            print("✅ [UploadMenuManager] 事件过滤器已移除")
        except Exception as e:
            print(f"❌ [UploadMenuManager] 移除事件过滤器失败: {e}")


class MapUploadMenuManager(QWidget):
    def __init__(self, parent_widget):
        super().__init__(parent_widget)
        self.ui = Ui_map_upload_menu()
        self.ui.setupUi(self)

        # 🚀 外部回调接口：由 ResourceManager 在初始化时绑定
        self.on_import_finished = None
        self.on_create_map = None
        
        # 1. 基础属性
        self.setFixedSize(50, 226)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # 🚀 2. 容器设置：不要设置鼠标穿透属性，否则子按钮无法响应
        self.menu_container = QWidget(self)
        self.menu_container.setGeometry(0, 0, 50, 226)
        
        self.ui.menu_frame.setParent(self.menu_container)
        self.menu_container.setObjectName("upload_menu_mask_container")

        # 3. 核心参数
        self.target_h = 120 
        self.anchor_y = 201 
        
        # 给子按钮安装过滤器
        for btn in [self.ui.btn_import, self.ui.btn_creat, self.ui.btn_open]:
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
        parent_widget.installEventFilter(self)

        # 绑定按键功能
        self.setup_connections()
        self.auto_layout()


    def setup_connections(self):
        # 🚀 绑定按钮点击事件
        self.ui.btn_import.clicked.connect(lambda: self.on_button_clicked("从文件导入"))
        self.ui.btn_creat.clicked.connect(lambda: self.on_button_clicked("创建地图"))
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
        try:
            # 🚀 修正为主按钮 btn_upload1
            if hasattr(self, 'ui') and self.ui and obj == self.ui.btn_upload and event.type() == QEvent.Type.Enter:
                self.anim_menu(True)
            # 当鼠标离开整个 UploadMenuManager 区域时收回
            elif obj == self and event.type() == QEvent.Type.Leave:
                self.anim_menu(False)
            
            if event.type() == QEvent.Type.Resize:
                self.auto_layout()
        except RuntimeError:
            # 对象已销毁，忽略事件
            pass
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
        elif action_name == "创建地图":
            if self.on_create_map:
                self.on_create_map()
        elif action_name == "选择库文件":
            if self.on_open_lib:
                self.on_open_lib()
        self.anim_menu(False)


    def import_assets(self):
        """弹出文件对话框：支持地图资源"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择地图资源", "",
            "地图文件 (*.json);;所有文件 (*)"
        )

        if files:
            self.activateWindow()
            self.raise_()
            
            # 处理地图文件导入
            import os
            map_name = os.path.splitext(os.path.basename(files[0]))[0]
            if not map_name: map_name = "new_map"
            
            if self.on_import_finished:
                self.on_import_finished(map_name, files, is_bgs=False)


    def process_imports(self, file_paths, map_name):
        """核心：将资源拷贝到当前打开的工程目录下"""
        try:
            if hasattr(self, 'on_import_finished') and self.on_import_finished:
                if self.on_import_finished:
                    self.on_import_finished(map_name, file_paths)
                    
        except Exception as e:
            print(f"❌ 导入失败: {e}")

    def destroy(self):
        """销毁MapUploadMenuManager，移除所有事件过滤器"""
        try:
            # 移除按钮的事件过滤器
            if hasattr(self, 'ui') and self.ui:
                for btn in [self.ui.btn_import, self.ui.btn_creat, self.ui.btn_open, self.ui.btn_upload]:
                    try:
                        btn.removeEventFilter(self)
                    except:
                        pass
            
            # 移除自身的事件过滤器
            self.removeEventFilter(self)
            
            # 移除父窗口的事件过滤器
            parent = self.parentWidget()
            if parent:
                parent.removeEventFilter(self)
                
            print("✅ [MapUploadMenuManager] 事件过滤器已移除")
        except Exception as e:
            print(f"❌ [MapUploadMenuManager] 移除事件过滤器失败: {e}")
