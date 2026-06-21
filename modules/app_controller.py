import os
from PySide6.QtCore import Qt, QStandardPaths, QTimer, QProcess, QSize
from PySide6.QtGui import QColor, QKeySequence, QIcon
from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QDialog,
    QHBoxLayout,
    QTabBar,
    QSizePolicy,
    QApplication,
    QVBoxLayout,
    QComboBox,
    QWidget,
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
from modules.map_editor.map_editor_manager import MapEditorManager
from modules.map_lib_manager import MapLibManager
from modules.sprite_lib_manager import SpriteLibManager
from modules.map_res_lib_manager import MapResLibManager
from modules.sound_lib_manager import SoundLibManager
from modules.help_panel_manager import HelpPanelManager


class MapSelectorComboBox(QComboBox):
    def showPopup(self):
        self.setMaxVisibleItems(max(self.count(), 1))
        super().showPopup()
        popup = self.view().parent()
        if popup is None:
            return
        for child in popup.findChildren(QWidget):
            cls = child.metaObject().className()
            if "Scroller" in cls or "ToolButton" in cls:
                child.hide()
        btn_pos = self.mapToGlobal(self.rect().bottomLeft())
        popup.move(btn_pos)
        popup.setFixedWidth(self.width())


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

        # 注入地图编辑器管理器
        self.map_editor = MapEditorManager()
        # 设置项目管理器
        self.map_editor.project_manager = self.project_manager
        # 初始化地图编辑器的资源列表视图，确保默认页面时上传按钮能工作
        self.map_editor.set_res_list_view(self.ui.res_list_view)

        # 初始化地图编辑器的图层列表视图
        # 使用现有的editor_map_layer_list控件
        self.map_editor.set_editor_map_layer_list(self.ui.editor_map_layer_list)

        self.file_manager = FileManager(self.window)
        self.console_manager = ConsoleManager(self.ui.splitter, self.ui.console_output)
        self.menu_manager = MenuManager(main_window)
        from modules.title_bar_manager import TitleBarManager
        self.title_bar_manager = TitleBarManager(self.window, self.ui, self.menu_manager)
        self.render_manager = RenderManager(self.ui.game_view, app_controller=self)
        self.screen_manager = ScreenManager(self)
        self.tabbar_manager = TabbarManager(self.ui.tab_frame)
        self.editor_manager = EditorManager(
            self.ui.code_stacked, self.tabbar_manager, self.project_manager, mode="game"
        )
        self.script_runner = ScriptRunner(self)
        self.res_manager = ResourceManager(self.ui, self.window, self)

        self.map_lib_manager = MapLibManager(self.ui, self)
        self.sprite_lib_manager = SpriteLibManager(self.ui, self)
        self.map_res_lib_manager = MapResLibManager(self.ui, self)
        self.sound_lib_manager = SoundLibManager(self.ui, self)

        from modules.file_tree_manager import FileTreeManager
        self.file_tree_manager = FileTreeManager(self.project_manager)

        self.ide_tabbar_manager = TabbarManager(self.ui.ide_tab_frame)
        self.ide_editor_manager = EditorManager(
            self.ui.ide_code_stacked, self.ide_tabbar_manager, self.project_manager, mode="ide"
        )

        # 帮助面板管理器
        self.help_panel_manager = HelpPanelManager(self.ui)
        from modules.console_manager import ConsoleManager as CM
        self.ide_console_manager = CM(
            self.ui.ide_splitter, self.ui.ide_console,
            container=self.ui.ide_console_container
        )

        self.ui.ide_console_clear.clicked.connect(self.ui.ide_console.clear)
        self.ui.ide_console_close.clicked.connect(
            lambda: self.ide_console_manager.anim_console(show=False)
        )

        self._upgrade_map_selector()

        # 4. 绑定信号 (保持原有业务连接)
        self.setup_connections()

        from PySide6.QtCore import QSettings
        _settings = QSettings("BingoCode", "BingoIDE")
        if not _settings.value("mode/is_game_mode", False, type=bool):
            self.ui.editor_stacked.setCurrentIndex(3)
            if self.ide_editor_manager.tabs.count() > 0:
                self.ide_editor_manager.switch_to_page(0)

        # 自动切换到地图编辑器页面（调试用）
        # self.handle_switch_to_map_editor()

    def _upgrade_map_selector(self):
        old = self.ui.btn_editor_map_selectmap
        parent = old.parent()
        layout = old.parent().layout()
        idx = layout.indexOf(old)
        old.hide()
        new_combo = MapSelectorComboBox(parent)
        new_combo.setObjectName(old.objectName())
        new_combo.setMinimumSize(old.minimumSize())
        new_combo.setEditable(False)
        layout.insertWidget(idx, new_combo)
        layout.removeWidget(old)
        old.deleteLater()
        self.ui.btn_editor_map_selectmap = new_combo

    def setup_connections(self):
        """绑定业务信号，完全保留文件和编辑器逻辑"""
        # 主页全局按钮-
        self.ui.btn_file.clicked.connect(
            lambda: self.menu_manager.show_popup_menu(self.ui.btn_file)
        )
        # self.ui.btn_save.clicked.connect(self.handle_save_project)

        # 编辑器页面切换按钮
        self.ui.btn_code_editor.clicked.connect(self.handle_switch_to_code_editor)
        self.ui.btn_sprite_editor.clicked.connect(self.handle_switch_to_sprite_editor)
        self.ui.btn_map_editor.clicked.connect(self.handle_switch_to_map_editor)

        # 地图编辑器上传按钮
        self.ui.btn_res_list_upload.clicked.connect(
            self.map_editor.handle_resource_upload
        )

        # 地图编辑器删除/清空资源按钮
        self.ui.btn_res_list_del.clicked.connect(
            self.map_editor.delete_selected_resource
        )
        self.ui.btn_res_list_clear.clicked.connect(
            self.map_editor.clear_current_layer_resources
        )

        # 碰撞编辑器工具按钮
        self.ui.btn_res_col_add.toggled.connect(
            lambda checked: (
                self.map_editor.collision_manager.set_collision_tool("add")
                if checked
                else None
            )
        )
        self.ui.btn_res_col_del.toggled.connect(
            lambda checked: (
                self.map_editor.collision_manager.set_collision_tool("delete")
                if checked
                else None
            )
        )
        self.ui.btn_res_col_move.toggled.connect(
            lambda checked: (
                self.map_editor.collision_manager.set_collision_tool("move")
                if checked
                else None
            )
        )
        self.ui.btn_res_col_reset.clicked.connect(
            self.map_editor.collision_manager.reset_collision_shape
        )

        # 地图编辑器网格显示/隐藏按钮
        self.ui.btn_editor_map_gird.toggled.connect(
            self.map_editor.toggle_grid_visibility
        )

        # 地图编辑器导出/导入按钮
        self.ui.btn_editor_map_export.clicked.connect(
            self.map_editor.map_exporter.export_map
        )
        self.ui.btn_editor_map_import.clicked.connect(self.open_map_lib)
        self.ui.btn_res_list_open.clicked.connect(self.open_map_res_lib)

        # 绑定地图编辑器工具按钮
        self.map_editor.setup_tool_buttons(self.ui)

        # 菜单栏按钮_>文件管理
        self.menu_manager.open_file_signal.connect(self.handle_open_project)
        self.menu_manager.save_file_signal.connect(self.handle_save_project)
        self.menu_manager.save_as_signal.connect(self.handle_save_as)
        self.menu_manager.new_file_signal.connect(self.handle_new_project)
        self.menu_manager.close_file_signal.connect(self.handle_close_project)

        # 运行程序按钮
        self.ui.btn_run.clicked.connect(self.handle_run_script)
        if hasattr(self.ui, "btn_stop"):
            self.ui.btn_stop.clicked.connect(self.script_runner.stop_script)
        if hasattr(self.ui, "fullscreen_btn_run"):
            self.ui.fullscreen_btn_run.clicked.connect(self.handle_run_script)
        if hasattr(self.ui, "fullscreen_btn_stop"):
            self.ui.fullscreen_btn_stop.clicked.connect(self.script_runner.stop_script)

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
        # 4. 绑定地图双击信号：双击即加载并切到地图编辑页面
        self.res_manager.sig_map_selected.connect(self._open_and_switch_to_map_editor)

        # 5. 绑定地图重命名信号：地图重命名后刷新地图列表
        self.map_editor.map_renamed.connect(self.res_manager.refresh_map_list)
        self.map_editor.map_imported.connect(self.res_manager.refresh_map_list)

        # 5.1 绑定代码文件变更信号：新建/保存文件后刷新代码列表
        self.editor_manager.file_created_on_disk.connect(self.res_manager.refresh_code_list)
        self.editor_manager.file_renamed_on_disk.connect(self.res_manager.refresh_code_list)
        self.ide_editor_manager.file_created_on_disk.connect(self.res_manager.refresh_code_list)
        self.ide_editor_manager.file_renamed_on_disk.connect(self.res_manager.refresh_code_list)

        # 6. 地图选择下拉框
        self.ui.btn_editor_map_selectmap.setEditable(False)
        self.ui.btn_editor_map_selectmap.currentIndexChanged.connect(
            self._on_map_selector_changed
        )
        self.map_editor.map_renamed.connect(self._refresh_map_selector)
        self.map_editor.map_imported.connect(self._refresh_map_selector)
        self.map_editor.map_loaded.connect(self._sync_map_selector)
        self.res_manager.sig_map_created.connect(self._on_map_created)
        self._refresh_map_selector()

        # 7. 地图编辑器新建地图按钮
        self.ui.btn_editor_map_new.clicked.connect(self._on_btn_new_map)

        # 8. 地图库导入信号
        self.map_lib_manager.sig_map_imported.connect(self._on_map_lib_imported)

        # 9. 角色库导入信号
        self.sprite_lib_manager.sig_sprite_imported.connect(
            self._on_sprite_lib_imported
        )

        # 10. 声音库导入信号
        self.sound_lib_manager.sig_sound_imported.connect(self._on_sound_lib_imported)

        # 11. 模式切换（代码模式 / 游戏模式）
        self.ui.btn_mode_switch.toggled.connect(self._on_mode_switch)

        # 12. IDE 新建标签页
        self.ui.ide_btn_add_tab.clicked.connect(self.ide_editor_manager.create_untitled_file)

        # 12.1 设置 IDE 按钮图标（缓存路径，性能优先）
        self._ide_icons_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "icons")
        self._ide_icon_play = QIcon(os.path.join(self._ide_icons_dir, "btn_preview_play.svg"))
        self._ide_icon_pause = QIcon(os.path.join(self._ide_icons_dir, "btn_preview_pause.svg"))
        self._ide_icon_undo = QIcon(os.path.join(self._ide_icons_dir, "undo.svg"))
        self._ide_icon_redo = QIcon(os.path.join(self._ide_icons_dir, "redo.svg"))
        self.ui.ide_btn_undo.setIcon(self._ide_icon_undo)
        self.ui.ide_btn_redo.setIcon(self._ide_icon_redo)
        self.ui.ide_btn_run.setIcon(self._ide_icon_play)

        # 12.2 帮助面板按钮
        self.ui.btn_help.clicked.connect(self.help_panel_manager.toggle)

        # 14. IDE 标签切换
        self.ide_tabbar_manager.tab_changed.connect(self.ide_editor_manager.switch_to_page)

        # 15. IDE 运行/停止
        self.ui.ide_btn_run.clicked.connect(self.ide_handle_run)

        # 16. IDE 撤销/重做
        self.ui.ide_btn_undo.clicked.connect(self._ide_undo)
        self.ui.ide_btn_redo.clicked.connect(self._ide_redo)

        # 17. IDE 控制台指令
        self.ide_console_manager.instruction_received.connect(
            self.render_manager.handle_instruction
        )

        # 18. IDE 运行状态切换
        self.ide_console_manager.process_started.connect(self._ide_set_running)
        self.ide_console_manager.process_finished.connect(self._ide_set_stopped)

    def _open_and_switch_to_editor(self, path):
        if hasattr(self, "map_editor") and self.map_editor:
            try:
                if (
                    hasattr(self.map_editor, "current_map_path")
                    and self.map_editor.current_map_path
                ):
                    self.map_editor.save_map()
                    self.res_manager.refresh_map_list()
            except Exception as e:
                pass

        # 2. 切换页面 (确保这里的 index 是正确的)
        # 这里的 index 1 通常对应你 UI 里的编辑器页面
        self.ui.editor_stacked.setCurrentIndex(1)

        # 3. 通知编辑器加载数据
        self.sprite_editor.load_sprite(path)

    def _open_and_switch_to_map_editor(self, path):
        if hasattr(self, "map_editor") and self.map_editor:
            try:
                if (
                    hasattr(self.map_editor, "current_map_path")
                    and self.map_editor.current_map_path
                ):
                    self.map_editor.save_map()
                    self.res_manager.refresh_map_list()
            except Exception as e:
                pass

        # 2. 切换到地图编辑页面
        self.ui.editor_stacked.setCurrentIndex(2)

        # 3. 初始化地图编辑器的画布
        try:
            if hasattr(self.ui, "editor_map_canvas") and self.ui.editor_map_canvas:
                try:
                    self.ui.editor_map_canvas.parentWidget()
                except RuntimeError:
                    self.ui.editor_map_canvas = None
                if self.ui.editor_map_canvas:
                    self.map_editor.set_canvas_widget(self.ui.editor_map_canvas)
        except Exception:
            pass

        try:
            if hasattr(self.ui, "res_list_view") and self.ui.res_list_view:
                self.map_editor.set_res_list_view(self.ui.res_list_view)
        except Exception:
            pass

        try:
            if hasattr(self.ui, "col_editor_view") and self.ui.col_editor_view:
                self.map_editor.initialize_collision_editor(self.ui.col_editor_view)
        except Exception:
            pass

        # 4. 加载地图文件
        self.map_editor.load_map_from_path(path)

    def _refresh_map_selector(self):
        self.ui.btn_editor_map_selectmap.blockSignals(True)
        current_text = self.ui.btn_editor_map_selectmap.currentText()
        self.ui.btn_editor_map_selectmap.clear()

        project_root = self.project_manager.project_root
        if project_root:
            maps_dir = os.path.join(project_root, "assets", "maps")
            if os.path.exists(maps_dir):
                map_folders = [
                    d
                    for d in os.listdir(maps_dir)
                    if not d.startswith(".")
                    and os.path.isdir(os.path.join(maps_dir, d))
                ]
                map_folders.sort(
                    key=lambda d: os.path.getmtime(os.path.join(maps_dir, d))
                )
                for folder in map_folders:
                    info_path = os.path.join(maps_dir, folder, f"{folder}.info")
                    json_path = os.path.join(maps_dir, folder, f"{folder}.json")
                    if os.path.exists(info_path) or os.path.exists(json_path):
                        self.ui.btn_editor_map_selectmap.addItem(folder)

        if self.ui.btn_editor_map_selectmap.count() == 0:
            self.ui.btn_editor_map_selectmap.addItem("空")

        idx = self.ui.btn_editor_map_selectmap.findText(current_text)
        if idx >= 0:
            self.ui.btn_editor_map_selectmap.setCurrentIndex(idx)
        self.ui.btn_editor_map_selectmap.blockSignals(False)

    def _sync_map_selector(self, map_path):
        if not map_path:
            return
        map_name = os.path.splitext(os.path.basename(map_path))[0]
        idx = self.ui.btn_editor_map_selectmap.findText(map_name)
        if idx >= 0:
            self.ui.btn_editor_map_selectmap.blockSignals(True)
            self.ui.btn_editor_map_selectmap.setCurrentIndex(idx)
            self.ui.btn_editor_map_selectmap.blockSignals(False)

    def _on_map_selector_changed(self, index):
        if index < 0:
            return
        map_name = self.ui.btn_editor_map_selectmap.itemText(index)
        if map_name == "空":
            return

        project_root = self.project_manager.project_root
        if not project_root:
            return

        maps_dir = os.path.join(project_root, "assets", "maps")
        info_path = os.path.join(maps_dir, map_name, f"{map_name}.info")
        json_path = os.path.join(maps_dir, map_name, f"{map_name}.json")

        map_path = None
        if os.path.exists(info_path):
            map_path = info_path
        elif os.path.exists(json_path):
            map_path = json_path

        if map_path:
            self._open_and_switch_to_map_editor(map_path)

    def _on_map_created(self, map_path):
        self._refresh_map_selector()
        if map_path and os.path.exists(map_path):
            self._open_and_switch_to_map_editor(map_path)

    def _on_btn_new_map(self):
        self.res_manager.handle_create_map()

    def open_map_lib(self):
        self.map_lib_manager.load_map_lib()
        self.ui.change_page.setCurrentIndex(2)

    def open_sprite_lib(self):
        self.sprite_lib_manager.load_sprite_lib()
        self.ui.change_page.setCurrentIndex(3)

    def open_map_res_lib(self):
        self.map_res_lib_manager.load_map_res_lib()
        self.ui.change_page.setCurrentIndex(4)

    def open_sound_lib(self):
        self.sound_lib_manager.load_sound_lib()
        self.ui.change_page.setCurrentIndex(5)

    def _on_map_lib_imported(self, map_path):
        self.res_manager.refresh_map_list()
        self._refresh_map_selector()
        if map_path and os.path.exists(map_path):
            map_name = os.path.splitext(os.path.basename(map_path))[0]
            idx = self.ui.btn_editor_map_selectmap.findText(map_name)
            if idx >= 0:
                self.ui.btn_editor_map_selectmap.blockSignals(True)
                self.ui.btn_editor_map_selectmap.setCurrentIndex(idx)
                self.ui.btn_editor_map_selectmap.blockSignals(False)

    def _on_sprite_lib_imported(self, sprite_path):
        self.res_manager.refresh_sprite_grid()

    def _on_sound_lib_imported(self, sound_path):
        self.res_manager.refresh_sound_grid()

    def _on_mode_switch(self, checked):
        if checked:
            self.ui.editor_stacked.setCurrentIndex(0)
            if self.editor_manager.tabs.count() > 0:
                idx = self.editor_manager.tabs.currentIndex()
                if idx >= 0:
                    self.editor_manager.switch_to_page(idx)
        else:
            self.ui.editor_stacked.setCurrentIndex(3)
            if self.ide_editor_manager.tabs.count() > 0:
                idx = self.ide_editor_manager.tabs.currentIndex()
                if idx >= 0:
                    self.ide_editor_manager.switch_to_page(idx)

    def ide_handle_run(self):
        if self.ui.ide_btn_run.isChecked():
            self.render_manager.reset_session()
            self.handle_save_project()
            run_path = self.project_manager.get_run_target()
            if run_path and os.path.exists(run_path):
                self.ide_console_manager.run_file(run_path)
            else:
                fallback = os.path.join(self.project_manager.project_root, "main.py")
                if os.path.exists(fallback):
                    self.project_manager.set_run_target(fallback)
                    self.ide_console_manager.run_file(fallback)
        else:
            self.ide_console_manager.process.kill()

    def _ide_undo(self):
        editor = self.ide_editor_manager.get_current_editor()
        if editor:
            editor.undo()

    def _ide_redo(self):
        editor = self.ide_editor_manager.get_current_editor()
        if editor:
            editor.redo()

    def _ide_set_running(self):
        self.ui.ide_btn_run.setChecked(True)
        self.ui.ide_btn_run.setIcon(self._ide_icon_pause)
        self.ui.ide_btn_run.setStyleSheet(
            "QPushButton{background-color:rgb(55,120,200);border:none;border-radius:4px;}"
        )

    def _ide_set_stopped(self):
        self.ui.ide_btn_run.setChecked(False)
        self.ui.ide_btn_run.setIcon(self._ide_icon_play)
        self.ui.ide_btn_run.setStyleSheet(
            "QPushButton{background-color:rgb(40,43,52);border:none;border-radius:4px;}"
            "QPushButton:hover{background-color:rgb(62,66,79);}"
        )

    def handle_close_project(self):
        self.project_manager.new_project()
        self.editor_manager._clear_initial_state()
        self.res_manager.refresh_code_list()
        self.res_manager.refresh_sprite_grid()
        self.res_manager.refresh_map_list()
        self.res_manager.refresh_sound_grid()
        self._refresh_map_selector()

    def handle_new_project(self):
        """新建项目：重置并初始化运行目标"""
        self.project_manager.new_project()
        self.editor_manager._clear_initial_state()
        self.title_bar_manager.set_title("BingoCode")

        path = self.project_manager.main_script_path
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        self.editor_manager.create_new_tab(path, content, auto_activate=True)

        # 🚀 显式初始化运行目标，防止第一次运行没反应
        self.project_manager.set_run_target(path)

    def handle_open_project(self):
        """打开项目：代码模式打开.py文件，游戏模式打开.bingo/文件夹"""
        if hasattr(self, "menu_manager") and self.menu_manager.isVisible():
            self.menu_manager.hide_popup_menu()

        is_code_mode = not self.ui.btn_mode_switch.isChecked()

        if is_code_mode:
            file_path, _ = QFileDialog.getOpenFileName(
                self.window,
                "打开文件",
                self.project_manager.last_save_dir,
                "Python Files (*.py)",
            )
            if not file_path:
                return
            self.project_manager.last_save_dir = os.path.dirname(file_path)
            self.ui.editor_stacked.setCurrentIndex(3)
            self.ide_editor_manager.logic_open_file(file_path)
        else:
            file_path, _ = QFileDialog.getOpenFileName(
                self.window,
                "打开项目",
                self.project_manager.last_save_dir,
                "Bingo Project (*.bingo);;所有文件 (*)",
            )
            if not file_path:
                return
            self.project_manager.last_save_dir = os.path.dirname(file_path)

            from PySide6.QtCore import QTimer
            QTimer.singleShot(100, lambda: (
                self.window.activateWindow(),
                self.window.raise_(),
                self.window.setFocus(),
            ))

            if file_path.endswith('.bingo'):
                success, _ = self.project_manager.unpack_from_bingo(file_path)
                if success:
                    self.project_manager.bingo_path = file_path
            else:
                success, _ = self.project_manager.open_project(file_path)
                if success:
                    self.project_manager.bingo_path = None

        if is_code_mode:
            return

        if success:
            self.editor_manager._clear_initial_state()
            self.res_manager.refresh_code_list()
            self.res_manager.refresh_sprite_grid()
            self.res_manager.refresh_map_list()
            self.res_manager.refresh_sound_grid()
            self._refresh_map_selector()
            project_name = os.path.splitext(os.path.basename(file_path))[0] if file_path.endswith('.bingo') else os.path.basename(file_path)
            self.title_bar_manager.set_title(f"BingoCode - {project_name}")

            all_files = [
                f
                for f in os.listdir(self.project_manager.project_root)
                if f.endswith(".py") and not f.startswith(".")
            ]

            if not all_files:
                self.handle_new_project()
                return

            all_files.sort(
                key=lambda x: os.path.getmtime(os.path.join(self.project_manager.project_root, x)),
                reverse=True,
            )

            if all_files:
                fp = os.path.join(self.project_manager.project_root, all_files[0])
                try:
                    with open(fp, "r", encoding="utf-8") as f:
                        content = f.read()
                    self.editor_manager.create_new_tab(
                        fp, content, auto_activate=True
                    )
                except:
                    pass

            if self.tabbar_manager.tab_bar.count() > 0:
                self.tabbar_manager.tab_bar.setCurrentIndex(0)
                self.editor_manager.switch_to_page(0)
                self.tabbar_manager.active_index = 0

        else:
            QMessageBox.warning(self.window, "打开失败", "无法访问该文件。")

    def handle_save_project(self):
        """保存：代码模式保存当前文件，游戏模式保存整个项目"""
        pm = self.project_manager

        is_code_mode = not self.ui.btn_mode_switch.isChecked()

        if is_code_mode:
            em = self.ide_editor_manager
            editor = em.get_current_editor()
            if editor:
                em.request_save_file(self.window)
            return

        em = self.editor_manager
        if pm.bingo_path:
            em.save_all_opened_files()
            pm.pack_to_bingo(pm.bingo_path)
            return

        self.handle_save_as()

    def handle_save_as(self):
        """另存为：代码模式保存当前文件，游戏模式打包为 .bingo"""
        pm = self.project_manager

        if hasattr(self, "menu_manager") and self.menu_manager.isVisible():
            self.menu_manager.hide_popup_menu()

        is_code_mode = not self.ui.btn_mode_switch.isChecked()

        if is_code_mode:
            em = self.ide_editor_manager
            editor = em.get_current_editor()
            if not editor:
                return
            new_path, _ = QFileDialog.getSaveFileName(
                self.window,
                "另存为",
                pm.last_save_dir,
                "Python Files (*.py)",
            )
            if not new_path:
                return
            if not new_path.endswith('.py'):
                new_path += '.py'
            pm.last_save_dir = os.path.dirname(new_path)
            try:
                with open(new_path, "w", encoding="utf-8") as f:
                    f.write(editor.toPlainText())
                editor.file_path = new_path
                editor.is_temp = False
                idx = em.tabs.currentIndex()
                em.tabs.setTabText(idx, os.path.splitext(os.path.basename(new_path))[0])
                em._set_tab_modified(editor, False)
            except Exception as e:
                QMessageBox.warning(self.window, "保存失败", str(e))
            return

        full_path, _ = QFileDialog.getSaveFileName(
            self.window,
            "保存项目",
            pm.last_save_dir,
            "Bingo Project (*.bingo)",
        )

        if not full_path:
            return
        if not full_path.endswith('.bingo'):
            full_path += '.bingo'
        pm.last_save_dir = os.path.dirname(full_path)

        from PySide6.QtCore import QTimer
        QTimer.singleShot(100, lambda: (
            self.window.activateWindow(),
            self.window.raise_(),
            self.window.setFocus(),
        ))

        em = self.editor_manager
        em.save_all_opened_files()

        if pm.pack_to_bingo(full_path):
            pm.bingo_path = full_path
            self.title_bar_manager.set_title(f"BingoCode - {os.path.splitext(os.path.basename(full_path))[0]}")

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
        if hasattr(self, "editor_manager") and self.editor_manager:
            try:
                self.editor_manager.save_all_opened_files()
            except Exception as e:
                pass

        if hasattr(self, "map_editor") and self.map_editor:
            try:
                if (
                    hasattr(self.map_editor, "current_map_path")
                    and self.map_editor.current_map_path
                ):
                    self.map_editor.save_map()
            except Exception as e:
                pass

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

        # 4. 【销毁渲染管理器】移除事件过滤器，防止程序关闭时崩溃
        if hasattr(self, "render_manager") and self.render_manager:
            try:
                self.render_manager.destroy()
            except Exception as e:
                pass

        if hasattr(self, "res_manager") and self.res_manager:
            try:
                self.res_manager.destroy()
            except Exception as e:
                pass

        if hasattr(self, "map_editor") and self.map_editor:
            try:
                self.map_editor.destroy()
            except Exception as e:
                pass

        if hasattr(self, "res_manager") and self.res_manager:
            if (
                hasattr(self.res_manager, "upload_menu")
                and self.res_manager.upload_menu
            ):
                try:
                    self.res_manager.upload_menu.destroy()
                except Exception as e:
                    pass
            if (
                hasattr(self.res_manager, "map_upload_menu")
                and self.res_manager.map_upload_menu
            ):
                try:
                    self.res_manager.map_upload_menu.destroy()
                except Exception as e:
                    pass
            if (
                hasattr(self.res_manager, "sound_upload_menu")
                and self.res_manager.sound_upload_menu
            ):
                try:
                    self.res_manager.sound_upload_menu.destroy()
                except Exception as e:
                    pass

        # 5. 【清理事件过滤器】移除所有Python事件过滤器，防止PySide6关闭崩溃
        if hasattr(self, "menu_manager") and self.menu_manager:
            try:
                self.menu_manager.hide_popup_menu()
            except Exception:
                pass

        if hasattr(self, "sound_lib_manager") and self.sound_lib_manager:
            try:
                slm = self.sound_lib_manager
                if hasattr(slm, "ui") and slm.ui and hasattr(slm.ui, "listWidget_2"):
                    slm.ui.listWidget_2.viewport().removeEventFilter(slm)
            except Exception:
                pass

        if hasattr(self, "sprite_editor_manager") and self.sprite_editor_manager:
            try:
                sem = self.sprite_editor_manager
                if hasattr(sem, "fps_list") and sem.fps_list:
                    sem.fps_list.viewport().removeEventFilter(sem)
            except Exception:
                pass

        # 6. 主动销毁主窗口的 widget 树，防止 Py_FinalizeEx 阶段
        #    destroyQCoreApplication() 重新遍历 C++ 对象时触发已死的 Python eventFilter
        if hasattr(self, "window") and self.window:
            try:
                self.window.hide()
                from PySide6.QtWidgets import QApplication
                QApplication.processEvents()
                self.window.deleteLater()
                QApplication.processEvents()
            except Exception:
                pass

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
        if process and process.state() == QProcess.Running:
            try:
                full_msg = f"{msg}\n"
                process.write(full_msg.encode("utf-8"))
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

    def _save_current_map_if_editing(self):
        try:
            if not hasattr(self, "map_editor") or not self.map_editor:
                return
            if (
                hasattr(self.map_editor, "current_map_path")
                and self.map_editor.current_map_path
            ):
                self.map_editor.save_map()
                self.res_manager.refresh_map_list()
        except Exception:
            pass

    def handle_switch_to_code_editor(self):
        self._save_current_map_if_editing()
        if self.ui.btn_mode_switch.isChecked():
            self.ui.editor_stacked.setCurrentIndex(0)
        else:
            self.ui.editor_stacked.setCurrentIndex(3)
            if self.ide_editor_manager.tabs.count() > 0:
                idx = self.ide_editor_manager.tabs.currentIndex()
                if idx >= 0:
                    self.ide_editor_manager.switch_to_page(idx)

    def handle_switch_to_sprite_editor(self):
        self._save_current_map_if_editing()
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

    def handle_switch_to_map_editor(self):
        self.ui.editor_stacked.setCurrentIndex(2)

        if not hasattr(self, "map_editor"):
            return

        try:
            if hasattr(self.ui, "editor_map_canvas") and self.ui.editor_map_canvas:
                try:
                    self.ui.editor_map_canvas.parentWidget()
                except RuntimeError:
                    self.ui.editor_map_canvas = None
                if self.ui.editor_map_canvas:
                    self.map_editor.set_canvas_widget(self.ui.editor_map_canvas)
        except Exception:
            pass

        try:
            if hasattr(self.ui, "res_list_view") and self.ui.res_list_view:
                self.map_editor.set_res_list_view(self.ui.res_list_view)
        except Exception:
            pass

        try:
            if hasattr(self.ui, "col_editor_view") and self.ui.col_editor_view:
                self.map_editor.initialize_collision_editor(self.ui.col_editor_view)
        except Exception:
            pass

        self._load_current_or_last_map()

    def _load_current_or_last_map(self):
        self._refresh_map_selector()

        selector = self.ui.btn_editor_map_selectmap
        if (
            selector.count() == 0
            or selector.itemText(0) == "空"
            and selector.count() == 1
        ):
            return

        current_idx = selector.currentIndex()
        if current_idx < 0 or selector.itemText(current_idx) == "空":
            last_idx = selector.count() - 1
            if last_idx >= 0 and selector.itemText(last_idx) != "空":
                selector.blockSignals(True)
                selector.setCurrentIndex(last_idx)
                selector.blockSignals(False)
                current_idx = last_idx

        map_name = selector.itemText(current_idx)
        if not map_name or map_name == "空":
            return

        project_root = self.project_manager.project_root
        if not project_root:
            return

        maps_dir = os.path.join(project_root, "assets", "maps")
        info_path = os.path.join(maps_dir, map_name, f"{map_name}.info")
        json_path = os.path.join(maps_dir, map_name, f"{map_name}.json")

        map_path = None
        if os.path.exists(info_path):
            map_path = info_path
        elif os.path.exists(json_path):
            map_path = json_path

        if map_path:
            if (
                hasattr(self.map_editor, "current_map_path")
                and self.map_editor.current_map_path == map_path
            ):
                return
            self.map_editor.load_map_from_path(map_path)
            self._sync_map_selector(map_path)

    def request_exit(self):
        """
        退出前的决策逻辑
        """
        project_root = self.project_manager.project_root.lower()

        # 1. 环境判定
        import tempfile

        temp_dir = tempfile.gettempdir().lower()
        is_temp = not project_root or temp_dir in project_root or "temp" in project_root

        code_dirty = getattr(self.project_manager, "_code_dirty", False)
        res_dirty = getattr(self.project_manager, "_resource_dirty", False)

        # 🚀 重新梳理逻辑：
        # 只要代码脏了 (code_dirty) -> 必须弹窗
        # 或者 (是临时项目 且 资源脏了) -> 必须弹窗

        should_prompt = False
        if code_dirty:
            should_prompt = True
        elif is_temp and res_dirty:
            should_prompt = True

        if should_prompt:
            from PySide6.QtWidgets import QLabel, QPushButton

            dialog = QDialog(self.window)
            dialog.setWindowTitle("Bingo IDE")
            dialog.setFixedSize(320, 120)
            dialog.setStyleSheet("""
                QDialog {
                    background-color: rgb(34, 37, 43);
                }
                QLabel {
                    color: white;
                    font-size: 13px;
                    qproperty-alignment: AlignCenter;
                }
                QPushButton {
                    background-color: rgb(61, 64, 72);
                    color: white;
                    border: 1px solid rgb(55, 59, 68);
                    border-radius: 3px;
                    padding: 3px 8px;
                    min-width: 50px;
                    min-height: 17px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: rgb(80, 83, 92);
                }
                QPushButton:pressed {
                    background-color: rgb(95, 45, 39);
                }
            """)

            layout = QVBoxLayout(dialog)
            layout.setAlignment(Qt.AlignCenter)
            layout.setSpacing(30)

            label = QLabel("是否保存更改？")
            layout.addWidget(label)

            btn_layout = QHBoxLayout()
            btn_layout.setAlignment(Qt.AlignCenter)
            btn_layout.setSpacing(20)

            cancel_btn = QPushButton("取消")
            discard_btn = QPushButton("不保存")
            save_btn = QPushButton("保存")

            cancel_btn.clicked.connect(dialog.reject)
            discard_btn.clicked.connect(lambda: dialog.done(2))
            save_btn.clicked.connect(dialog.accept)

            btn_layout.addWidget(cancel_btn)
            btn_layout.addWidget(discard_btn)
            btn_layout.addWidget(save_btn)
            layout.addLayout(btn_layout)

            dialog.exec()

            result = dialog.result()
            if result == QDialog.Accepted:
                success = self.handle_save_project()
                if success:
                    self.project_manager.reset_dirty()
                return True
            elif result == 2:
                return True
            else:
                return False

        return True  # 干净的正式项目，直接退出 # 既不是临时项目也没改动，直接退出 # 已经是正式项目且无代码改动，允许直接退出 # 没有改动，直接走 # 没有未保存内容，静默退出
