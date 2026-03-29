import os
from PySide6.QtCore import Qt, QStandardPaths, QTimer, QProcess
from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QTabBar,
    QSizePolicy,
    QApplication,
    QVBoxLayout,
)


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
from models.sprite_model import SpriteDataModel
from modules.sprite_editor_manager import SpriteEditorManager


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
        self.project_manager = ProjectManager()  # 这个必须要第一个实例化

        # 注入角色编辑器管理器
        self.sprite_editor = SpriteEditorManager(self.ui)

        self.file_manager = FileManager(self.window)
        self.console_manager = ConsoleManager(self.ui.splitter, self.ui.console_output)
        self.menu_manager = MenuManager(main_window)
        self.render_manager = RenderManager(self.ui.game_view, app_controller=self)
        self.screen_manager = ScreenManager(self)
        self.tabbar_manager = TabbarManager(self.ui.tab_frame)
        self.editor_manager = EditorManager(
            self.ui.code_stacked, self.tabbar_manager, self.project_manager
        )
        self.script_runner = ScriptRunner(self)
        self.res_manager = ResourceManager(self.ui, self.window, self)

        # 4. 绑定信号 (保持原有业务连接)
        self.setup_connections()

    def setup_connections(self):
        """绑定业务信号，完全保留文件和编辑器逻辑"""
        # 主页全局按钮-
        self.ui.btn_file.clicked.connect(
            lambda: self.menu_manager.show_popup_menu(self.ui.btn_file)
        )
        # self.ui.btn_save.clicked.connect(self.handle_save_project)

        # 编辑器页面切换按钮
        self.ui.btn_code_editor.clicked.connect(
            lambda: self.ui.editor_stacked.setCurrentIndex(0)
        )
        self.ui.btn_sprite_editor.clicked.connect(self.handle_switch_to_sprite_editor)

        # 菜单栏按钮_>文件管理
        self.menu_manager.open_file_signal.connect(self.handle_open_project)
        self.menu_manager.save_file_signal.connect(self.handle_save_project)
        self.menu_manager.save_as_signal.connect(self.handle_save_as)
        self.menu_manager.new_file_signal.connect(self.handle_new_project)
        self.menu_manager.close_file_signal.connect(self.handle_new_project)

        # 运行程序按钮
        self.ui.btn_run.clicked.connect(self.handle_run_script)
        if hasattr(self.ui, "btn_stop"):
            self.ui.btn_stop.clicked.connect(self.script_runner.stop_script)

        # 运行console控制台
        self.console_manager.process_started.connect(
            lambda: self.script_runner.set_run_btn_visual(True)
        )
        self.console_manager.process_finished.connect(
            lambda: self.script_runner.set_run_btn_visual(False)
        )

        # 切换全屏和编辑模式
        self.ui.btn_full_screen.clicked.connect(self.screen_manager.enter_fullscreen)
        self.ui.fullscreen_btn_unfull.clicked.connect(
            self.screen_manager.exit_fullscreen
        )

        # 代码编辑标签页功能
        self.tabbar_manager.tab_changed.connect(self.editor_manager.switch_to_page)
        self.ui.btn_add_tab.clicked.connect(self.editor_manager.create_untitled_file)

        # 将捕获的JSON指令喂给render_manager
        self.console_manager.instruction_received.connect(
            self.render_manager.handle_instruction
        )

        self.ui.game_view.setFocusPolicy(Qt.StrongFocus)  # 确保游戏区域能拿焦点
        self.ui.game_view.keyPressEvent = self._handle_qt_key_press
        self.ui.game_view.keyReleaseEvent = self._handle_qt_key_release

        self.res_manager.bind_switch_page()

        # 2. 绑定资源导入信号：导入即同步模型数据 (不切页面)
        self.res_manager.sig_sprite_imported.connect(self.sprite_editor.load_sprite)

        # 3. 绑定资源双击信号：双击即加载并切到编辑页面
        self.res_manager.sig_sprite_selected.connect(self._open_and_switch_to_editor)

    def _open_and_switch_to_editor(self, path):
        print(f"🛎️ [AppController] 收到编辑请求，目标路径: {path}")

        # 1. 切换页面 (确保这里的 index 是正确的)
        # 这里的 index 1 通常对应你 UI 里的编辑器页面
        self.ui.editor_stacked.setCurrentIndex(1)

        # 2. 通知编辑器加载数据
        self.sprite_editor.load_sprite(path)

    def handle_new_project(self):
        """新建项目：重置并初始化运行目标"""
        self.project_manager.new_project()
        self.editor_manager._clear_initial_state()

        path = self.project_manager.main_script_path
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        self.editor_manager.create_new_tab(path, content, auto_activate=True)

        # 🚀 显式初始化运行目标，防止第一次运行没反应
        self.project_manager.set_run_target(path)

    def handle_open_project(self):
        """打开项目：加载目录下所有脚本"""
        target_dir = QFileDialog.getExistingDirectory(self.window, "选择工程目录")
        if not target_dir:
            return

        # 1. 切换根目录（现在它不会因为没 main.py 而返回 False 了）
        success, _ = self.project_manager.open_project(target_dir)

        if success:
            self.editor_manager._clear_initial_state()
            self.res_manager.refresh_code_list()
            self.res_manager.refresh_sprite_grid()
            # 2. 获取目录下所有 py 文件
            all_files = [
                f
                for f in os.listdir(target_dir)
                if f.endswith(".py") and not f.startswith(".")
            ]

            if not all_files:
                # 如果是空项目，自动帮学生建一个，免得界面空荡荡
                self.handle_new_project()
                return

            # 3. 排序并加载
            all_files.sort(key=lambda x: (x != "main.py", x.lower()))

            for file_name in all_files:
                file_path = os.path.join(target_dir, file_name)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    self.editor_manager.create_new_tab(
                        file_path, content, auto_activate=False
                    )
                except:
                    pass

            # 4. 默认激活第一个找到的脚本
            if self.tabbar_manager.tab_bar.count() > 0:
                self.tabbar_manager.tab_bar.setCurrentIndex(0)
                self.editor_manager.switch_to_page(0)
                self.tabbar_manager.active_index = 0

        else:
            QMessageBox.warning(self.window, "打开失败", "无法访问该目录。")

    def handle_save_project(self):
        """点击保存按钮：保存当前项目所有改动"""
        pm = self.project_manager
        em = self.editor_manager

        # 1. 检查是否是从未保存过的“纯临时”项目
        # 如果路径里包含系统的 Temp 目录，说明用户还没给项目起名
        if "/T/" in pm.project_root or "Temp" in pm.project_root:
            self.handle_save_as()  # 引导去另存为
            return

        # 2. 如果已经是正式项目（比如在桌面），执行全量保存
        # 🚀 这一步会把所有新建的 untitled_x.py 都存进项目文件夹
        if em.save_all_opened_files():
            # print("✨ 项目所有文件已成功同步到磁盘")
            pass
        else:
            QMessageBox.warning(
                self.window, "保存提醒", "部分新标签页保存失败，请检查权限。"
            )

    def handle_save_as(self):
        """另存为：强制弹出起名窗口，并完整搬迁项目（包含所有标签页）"""
        pm = self.project_manager
        em = self.editor_manager

        # 1. 基础检查：如果没有打开的编辑器，则无需保存
        editor = em.get_current_editor()
        if not editor:
            return

        # 2. 弹出『起名』对话框
        full_path, _ = QFileDialog.getSaveFileName(
            self.window,
            "另存为新项目 (请输入项目名称)",
            os.path.expanduser("~/Desktop"),
            "Bingo Project (*.bingo)",
        )

        if not full_path:
            return

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
                if hasattr(widget, "file_path"):
                    old_name = os.path.basename(widget.file_path)
                    widget.file_path = os.path.join(pm.project_root, old_name)
                    # 标记为非临时文件，因为已经落户了
                    widget.is_temp = False

            QMessageBox.information(
                self.window,
                "保存成功",
                f"项目已完整另存为至：\n{os.path.basename(target_project_dir)}",
            )

    def handle_run_script(self):
        """运行脚本：完全动态捕获"""
        if hasattr(self, "render_manager"):
            self.render_manager.reset_session()
        # 1. 运行前全量保存（确保所有标签页的改动都进硬盘了）
        self.handle_save_project()
        self.res_manager.refresh_code_list()
        self.ui.game_view.setFocus()
        # 2. 获取当前的动态入口
        run_path = self.project_manager.get_run_target()

        if run_path and os.path.exists(run_path):
            self.script_runner.run_script(run_path)
        else:
            # 自动补救：如果没设目标，强制设为 main.py 再试一次
            fallback = os.path.join(self.project_manager.project_root, "main.py")
            if os.path.exists(fallback):
                self.project_manager.set_run_target(fallback)
                self.script_runner.run_script(fallback)
            else:
                QMessageBox.warning(
                    self.window,
                    "运行失败",
                    "找不到可运行的 Python 脚本，请确认标签页是否打开。",
                )

    def handle_exit_cleanup(self):
        """
        最后的物理清理与强制静默保存
        """
        print("🚀 执行最后的物理清理...")

        # 1. 【强制保存】不管三七二十一，尝试把所有打开的编辑器内容写回文件
        # 这一步能解决你说的“改了代码没提示但再打开没保存”的问题
        if hasattr(self, "editor_manager") and self.editor_manager:
            try:
                print("📝 正在执行静默代码保存...")
                self.editor_manager.save_all_opened_files()
            except Exception as e:
                print(f"❌ 静默保存失败: {e}")

        # 2. 【停止引擎】防止 Python 进程残留
        if hasattr(self, "script_runner") and self.script_runner:
            try:
                self.script_runner.stop_script(is_exiting=True)
                self.script_runner.cleanup_temp_files()
            except:
                pass

        # 3. 【释放 UI 资源】停止角色编辑器的定时器
        manager = getattr(self, "sprite_editor_manager", None)
        if not manager:
            manager = getattr(self, "sprite_editor", None)

        if manager:
            try:
                manager.cleanup()  # 停止定时器
                if hasattr(manager, "canvas") and manager.canvas:
                    manager.canvas.setScene(None)
            except:
                pass

        print("🏁 程序已安全关闭。")

    def open_file_in_editor(self, file_path):
        """统一的打开文件入口"""
        self.editor_manager.logic_open_file(file_path)

    def _handle_qt_key_press(self, event):
        if event.isAutoRepeat():
            return
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
                process.write(full_msg.encode("utf-8"))
                # 必须 flush，否则数据只在内存里
                process.waitForBytesWritten(5)
            except Exception as e:
                pass

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

    def handle_switch_to_sprite_editor(self):
        """切换到角色编辑页面，自动加载最后选择的或默认的角色"""
        # 切换页面
        self.ui.editor_stacked.setCurrentIndex(1)

        # 获取最后选择的角色路径
        last_path = self.res_manager.last_selected_sprite_path

        if last_path and os.path.exists(last_path):
            # 如果有最后选择的角色，加载它
            self.sprite_editor.load_sprite(last_path)
        else:
            # 如果没有选择过角色，加载最后一个角色
            project_root = self.project_manager.project_root
            if project_root:
                sprites_dir = os.path.join(project_root, "assets", "sprites")
                if os.path.exists(sprites_dir):
                    # 获取所有角色文件夹
                    sprite_folders = [
                        d
                        for d in os.listdir(sprites_dir)
                        if not d.startswith(".")
                        and os.path.isdir(os.path.join(sprites_dir, d))
                    ]
                    if sprite_folders:
                        # 加载最后一个角色
                        sprite_folders.sort()
                        last_sprite = sprite_folders[-1]
                        sprite_path = os.path.join(sprites_dir, last_sprite)
                        self.sprite_editor.load_sprite(sprite_path)
                        # 更新最后选择的路径
                        self.res_manager.last_selected_sprite_path = sprite_path

    def request_exit(self):
        """
        退出前的决策逻辑
        """
        project_root = self.project_manager.project_root.lower()

        # 1. 环境判定
        import tempfile

        temp_dir = tempfile.gettempdir().lower()
        is_temp = not project_root or temp_dir in project_root or "temp" in project_root

        # 2. 状态判定 (直接读取 ProjectManager 的标记)
        code_dirty = getattr(self.project_manager, "_code_dirty", False)
        res_dirty = getattr(self.project_manager, "_resource_dirty", False)

        # 调试打印，你可以在控制台看到到底是哪个变量触发的
        print(
            f"🔍 退出检查: is_temp={is_temp}, code_dirty={code_dirty}, res_dirty={res_dirty}"
        )

        # 🚀 重新梳理逻辑：
        # 只要代码脏了 (code_dirty) -> 必须弹窗
        # 或者 (是临时项目 且 资源脏了) -> 必须弹窗

        should_prompt = False
        if code_dirty:
            should_prompt = True
        elif is_temp and res_dirty:
            should_prompt = True

        if should_prompt:
            msg_box = QMessageBox(self.window)
            msg_box.setWindowTitle("Bingo IDE")
            msg_box.setText("要保存对项目的更改吗？")
            msg_box.setInformativeText(
                "如果不保存，您的代码改动（或临时项目中的资源）将会丢失。"
            )

            save_btn = msg_box.addButton("保存项目", QMessageBox.AcceptRole)
            discard_btn = msg_box.addButton("不保存退出", QMessageBox.DestructiveRole)
            cancel_btn = msg_box.addButton("取消", QMessageBox.RejectRole)

            msg_box.setDefaultButton(save_btn)
            msg_box.exec()

            clicked = msg_box.clickedButton()
            if clicked == save_btn:
                # 如果用户选保存，保存后重置脏标记
                success = self.handle_save_project()
                if success:
                    self.project_manager.reset_dirty()
                return success
            elif clicked == discard_btn:
                return True
            else:
                return False

        return True  # 干净的正式项目，直接退出 # 既不是临时项目也没改动，直接退出 # 已经是正式项目且无代码改动，允许直接退出 # 没有改动，直接走 # 没有未保存内容，静默退出
