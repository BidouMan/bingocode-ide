import os
from PySide6.QtCore import Qt, QStandardPaths, QTimer,QProcess
from PySide6.QtGui import QColor,QKeySequence
from PySide6.QtWidgets import (QFileDialog, QMessageBox, QTabBar, QSizePolicy, QApplication, QVBoxLayout)





# 整合好的模组
from ui.main_window_ui import Ui_Form
from modules.mune_manager import MenuManager
from modules.console_manager import ConsoleManager
from modules.editor_manager import EditorManager
from modules.project_manager import ProjectManager
from modules.render_manager import RenderManager
from modules.screen_manager import ScreenManager
from modules.tabbar_manager import TabbarManager
from modules.file_manager import FileManager
from modules.script_runner import ScriptRunner
from modules.resource_manager import ResourceManager
from modules.upload_menu_manager import UploadMenuManager

class AppController:
    def __init__(self, main_window: Ui_Form):
        self.window = main_window
        self.ui: Ui_Form = main_window.ui
        self.last_active_index = -1
        self._is_adjusting = False
        
        # 🚀 1. 核心分辨率：统一使用 640x480 (自研引擎黄金比例)
        self.stage_width = 640   
        self.stage_height = 480  
        
        # 整理过的模块
        self.project_manager = ProjectManager()
        self.file_manager = FileManager(self.window)
        self.console_manager = ConsoleManager(self.ui.splitter, self.ui.console_output)        
        self.menu_manager = MenuManager(main_window)
        self.render_manager = RenderManager(self.ui.game_view,app_controller=self)
        self.screen_manager = ScreenManager(self)
        self.tabbar_manager = TabbarManager(self.ui.tab_frame)
        self.editor_manager = EditorManager(self.ui.code_stacked, self.tabbar_manager, self.project_manager)
        self.script_runner = ScriptRunner(self)
        self.res_manager = ResourceManager(self.ui,self.window)


       
     
        #4. 绑定信号 (保持原有业务连接)
        self.setup_connections()

        
    
    
     
    def setup_connections(self):
        """绑定业务信号，完全保留文件和编辑器逻辑"""
        # 主页全局按钮-
        self.ui.btn_file.clicked.connect(lambda: self.menu_manager.show_popup_menu(self.ui.btn_file))
        self.ui.btn_save.clicked.connect(self.handle_save_project)

    
        # 菜单栏按钮_>文件管理 
        self.menu_manager.open_file_signal.connect(self.handle_open_project)        
        self.menu_manager.save_file_signal.connect(self.handle_save_project)
        self.menu_manager.save_as_signal.connect(self.handle_save_as)
        self.menu_manager.new_file_signal.connect(self.handle_new_project)
        self.menu_manager.close_file_signal.connect(self.handle_new_project)


        # 运行程序按钮
        self.ui.btn_run.clicked.connect(self.script_runner.run_project)
        if hasattr(self.ui, 'btn_stop'):
            self.ui.btn_stop.clicked.connect(self.script_runner.stop_script)

        
        # 运行console控制台
        self.console_manager.process_started.connect(lambda: self.script_runner.set_run_btn_visual(True))
        self.console_manager.process_finished.connect(lambda: self.script_runner.set_run_btn_visual(False))


        # 切换全屏和编辑模式
        self.ui.btn_full_screen.clicked.connect(self.screen_manager.enter_fullscreen)
        self.ui.fullscreen_btn_unfull.clicked.connect(self.screen_manager.exit_fullscreen)


        # 代码编辑标签页功能
        self.tabbar_manager.tab_changed.connect(self.editor_manager.switch_to_page)
        self.ui.btn_add_tab.clicked.connect(self.editor_manager.create_untitled_file)


        # 将捕获的JSON指令喂给render_manager
        # self.console_manager.draw_signal.connect(self.render_manager.handle_instruction)
        self.console_manager.instruction_received.connect(self.render_manager.handle_instruction)


        self.ui.game_view.setFocusPolicy(Qt.StrongFocus) # 确保游戏区域能拿焦点
        self.ui.game_view.keyPressEvent = self._handle_qt_key_press
        self.ui.game_view.keyReleaseEvent = self._handle_qt_key_release
        
        self.res_manager.bind_switch_page()

        menu_ui = self.res_manager.upload_menu.ui
        menu_ui.btn_sprite.clicked.connect(self.res_manager.import_sprite_dialog)
        menu_ui.btn_bg.clicked.connect(lambda: print("点击了上传背景"))
        menu_ui.btn_sound.clicked.connect(lambda: print("点击了上传声音"))
    


    def handle_new_project(self):
        """新建项目：彻底清空并重新加载 main.py"""
        try:
            # 1. 重置后台数据
            self.project_manager.new_project()
            
            # 2. 彻底清理 UI（清空所有 Tab）
            self.editor_manager._clear_initial_state()
            
            # 3. 重置状态管理器索引
            self.tabbar_manager.active_index = -1 

            # 4. 获取刚创建的 main.py 内容
            with open(self.project_manager.main_script_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            # 5. 重建第一个标签
            # 这里的 auto_activate 必须为 True，它会触发 EditorManager 内部的 setCurrentIndex
            self.editor_manager.create_new_tab(
                file_path=self.project_manager.main_script_path,
                content=content,
                auto_activate=True
            )
            
            # 🚀 6. 【修复报错行】：使用 tabbar_manager 访问 tab_bar
            # 既然已经 auto_activate 了，其实只需要确保内部索引同步即可
            if self.tabbar_manager.tab_bar.count() > 0:
                self.tabbar_manager.tab_bar.setCurrentIndex(0)
                self.editor_manager.switch_to_page(0)
                self.tabbar_manager.active_index = 0
            
            print("🆕 新项目 UI 已重建，默认加载 main.py")
            
        except Exception as e:
            # 这里的报错会捕捉到具体哪行出了问题
            QMessageBox.critical(self.window, "错误", f"初始化新项目失败: {e}")
    def handle_open_project(self):
        """打开项目：排序加载并锁定第一个标签"""
        target_dir = QFileDialog.getExistingDirectory(self.window, "选择工程目录")
        if not target_dir: return

        # 1. 切换根目录
        success, _ = self.project_manager.open_project(target_dir)

        if success:
            # 2. 清理旧标签
            self.editor_manager._clear_initial_state()
            
            # 3. 排序：main.py 始终第一
            all_files = [f for f in os.listdir(target_dir) if f.endswith(".py")]
            all_files.sort(key=lambda x: (x != "main.py", x.lower()))
            
            # 4. 循环加载 (不自动抢焦点)
            for file_name in all_files:
                file_path = os.path.join(target_dir, file_name)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # 🚀 关键：传入 auto_activate=False，这样循环时界面不会乱闪乱跳
                    self.editor_manager.create_new_tab(
                        file_path=file_path, 
                        content=content, 
                        auto_activate=False
                    )
                except Exception as e:
                    print(f"读取失败 {file_name}: {e}")

            # 🚀 5. 循环结束，一次性强制对齐到第一个标签 (main.py)
            if self.ui.tab_frame.tab_bar.count() > 0:
                self.ui.tab_frame.tab_bar.setCurrentIndex(0) # 视觉：Tab 蓝条
                self.editor_manager.switch_to_page(0)        # 内容：代码页面
                self.tabbar_manager.active_index = 0         # 逻辑：内部记录
            
            print(f"📂 项目加载完毕，当前锁定：main.py")
        else:
            QMessageBox.warning(self.window, "打开失败", "未找到 main.py")
    

    def handle_save_project(self):
        """点击保存按钮：保存当前项目所有改动"""
        pm = self.project_manager
        em = self.editor_manager

        # 1. 检查是否是从未保存过的“纯临时”项目
        # 如果路径里包含系统的 Temp 目录，说明用户还没给项目起名
        if "/T/" in pm.project_root or "Temp" in pm.project_root:
            self.handle_save_as() # 引导去另存为
            return

        # 2. 如果已经是正式项目（比如在桌面），执行全量保存
        # 🚀 这一步会把所有新建的 untitled_x.py 都存进项目文件夹
        if em.save_all_opened_files():
            print("✨ 项目所有文件已成功同步到磁盘")
        else:
            QMessageBox.warning(self.window, "保存提醒", "部分新标签页保存失败，请检查权限。")
        
    def handle_save_as(self):
        """另存为：强制弹出起名窗口，并完整搬迁项目（包含所有标签页）"""
        pm = self.project_manager
        em = self.editor_manager
        
        # 1. 基础检查：如果没有打开的编辑器，则无需保存
        editor = em.get_current_editor()
        if not editor: return

        # 2. 弹出『起名』对话框
        full_path, _ = QFileDialog.getSaveFileName(
            self.window, 
            "另存为新项目 (请输入项目名称)", 
            os.path.expanduser("~/Desktop"), 
            "Bingo Project (*.bingo)"
        )
        
        if not full_path: return

        # 3. 解析目标路径：去掉 .bingo 后缀，作为项目文件夹
        target_project_dir = os.path.splitext(full_path)[0]

        # 🚀 4. 【核心改动】全量刷盘：
        # 在搬家前，让 EditorManager 把所有 Tab 里的内存代码写入当前的临时磁盘目录
        # 这样 shutil.copytree 才能抓取到这些新文件
        em.save_all_opened_files()

        # 5. 获取当前主编辑器的代码，用于 ProjectManager 的备用写入
        latest_code = editor.toPlainText()

        # 6. 下令给 ProjectManager 执行物理搬迁
        # 它会把整个临时文件夹（含 main.py 和所有已经写盘的 untitled_x.py）拷贝到新路径
        if pm.save_project_to(target_project_dir, latest_code):
            
            # 7. 搬家成功后，更新所有打开编辑器的关联路径
            # 这一步确保后续『静默保存』能写到新家，而不是旧的临时目录
            for i in range(em.stacked.count()):
                widget = em.stacked.widget(i)
                if hasattr(widget, 'file_path'):
                    old_name = os.path.basename(widget.file_path)
                    widget.file_path = os.path.join(pm.project_root, old_name)
                    # 标记为非临时文件，因为已经落户了
                    widget.is_temp = False

            QMessageBox.information(
                self.window, 
                "保存成功", 
                f"项目已完整另存为至：\n{os.path.basename(target_project_dir)}"
            )

        

    def _handle_qt_key_press(self, event):
        if event.isAutoRepeat(): return 
        key_name = self._map_qt_key(event.key())
        self._send_to_engine(f"K_DOWN:{key_name}")

    def _handle_qt_key_release(self, event):
        key_name = self._map_qt_key(event.key())
        self._send_to_engine(f"K_UP:{key_name}")

    def _send_to_engine(self, msg):
        """发送消息到子进程"""
        process = self.console_manager.process
        # 🚀 增加 check: 确保 process 存在且通道未关闭
        if process and process.state() == QProcess.Running:
            try:
                full_msg = f"{msg}\n"
                process.write(full_msg.encode('utf-8'))
                # 必须 flush，否则数据只在内存里
                process.waitForBytesWritten(5)
                print(f"✅ AppController: 消息 '{msg}' 已发送")
            except Exception as e:
                print(f"❌ AppController: 发送失败 {e}")
        else:
            print(f"⚠️ AppController: 进程未运行，无法发送 '{msg}'")

    def _map_qt_key(self, qt_key):
        """映射 Qt 键位到用户习惯的字符串"""
        mapping = {
        Qt.Key_Up: "up",
        Qt.Key_Down: "down",
        Qt.Key_Left: "left",
        Qt.Key_Right: "right",
        Qt.Key_Space: "space",
        Qt.Key_Return: "enter",
        Qt.Key_Enter: "enter",
        Qt.Key_Escape: "escape",
        Qt.Key_Shift: "shift",
        Qt.Key_Control: "ctrl",
    }
    
        if qt_key in mapping:
            return mapping[qt_key]

        # 2. 处理普通字符 (A-Z, 0-9 等)
        # QKeySequence 会把 Key_A 转成 "A"，我们统一转成小写 "a"
        key_str = QKeySequence(qt_key).toString().lower()
        
        return key_str