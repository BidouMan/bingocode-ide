import os
from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QGraphicsScene, QTreeWidgetItem
from models.sprite_model import SpriteDataModel

class SpriteEditorManager(QObject):
    def __init__(self, ui_form):
        super().__init__()
        self.ui = ui_form
        self.model = None
        self.current_project_path = ""

        # 1. 动画引擎核心变量
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_animation_frame)
        self.current_anim_config = None
        self.current_frame_index = 0  # 这里的 index 是 1-Base 的真实帧号
        self.is_playing = False

        # UI 组件引用
        self.fps_list = self.ui.sprite_fps_list
        self.canvas = self.ui.sprite_canvas
        self.preview = self.ui.animate_preview
        self.anim_list = self.ui.animate_list

        # 画布初始化
        self.canvas_scene = QGraphicsScene()
        self.canvas.setScene(self.canvas_scene)

        self._setup_connections()

    def _setup_connections(self):
        # 造型列表点击 -> 切换显示
        self.fps_list.currentRowChanged.connect(self._on_costume_selection_changed)
        # 动作列表点击 -> 切换动画序列
        self.anim_list.itemClicked.connect(self._on_animation_item_clicked)

    def load_sprite(self, project_path):
        """由 AppController 调用"""
        if self.current_project_path == project_path: return
        
        self.stop_animation() # 切换角色前先停止旧动画
        self.current_project_path = project_path
        self.model = SpriteDataModel(project_path)
        self.model.data_changed.connect(self.refresh_all_ui)
        self.refresh_all_ui("ALL")

    def _on_animation_item_clicked(self, item, column):
        """当用户点击右下角动作树中的某一项时触发"""
        anim_name = item.text(0)
        if not self.model or anim_name not in self.model.animations:
            return
        
        print(f"🎬 [DEBUG] 切换动画序列: {anim_name}")
        self.play_animation(anim_name)

    # --- 动画引擎方法 ---

    def play_animation(self, anim_name):
        """开始播放指定的动画序列"""
        if not self.model or anim_name not in self.model.animations:
            return
        
        self.current_anim_config = self.model.animations[anim_name]
        self.current_frame_index = self.current_anim_config.get("start", 1)
        
        # 计算间隔：ms = 1000 / fps
        fps = self.current_anim_config.get("fps", 10)
        interval = int(1000 / max(fps, 1))
        
        self.timer.start(interval)
        self.is_playing = True
        print(f"▶️ [DEBUG] 动画开始: {anim_name} (FPS: {fps}, Range: {self.current_anim_config['start']}-{self.current_anim_config['end']})")

    def stop_animation(self):
        """停止播放"""
        self.timer.stop()
        self.is_playing = False
        self.current_anim_config = None

    def _update_animation_frame(self):
        """计时器触发：更新预览窗帧位"""
        if not self.current_anim_config:
            return

        start = self.current_anim_config.get("start", 1)
        end = self.current_anim_config.get("end", 1)
        loop = self.current_anim_config.get("loop", True)

        # 1. 获取当前帧路径并渲染到预览窗
        img_path = self.model.get_costume_path(self.current_frame_index)
        if img_path:
            self.update_preview_static(img_path)

        # 2. 递增帧号
        self.current_frame_index += 1

        # 3. 边界检查
        if self.current_frame_index > end:
            if loop:
                self.current_frame_index = start
            else:
                self.stop_animation()
                print("⏹️ [DEBUG] 动画播放完毕(不循环)")

    # --- UI 刷新逻辑 ---

    def refresh_all_ui(self, change_type, detail=None):
        if change_type in ["ALL", "COSTUME"]:
            self._update_fps_list()
        if change_type in ["ALL", "ANIMATION"]:
            self._update_animation_list()

    def _update_fps_list(self):
        self.fps_list.blockSignals(True)
        self.fps_list.clear()
        for i, filename in enumerate(self.model.costumes):
            self.fps_list.addItem(f"{i + 1}: {filename}")
        self.fps_list.blockSignals(False)
        if self.fps_list.count() > 0:
            self.fps_list.setCurrentRow(0)

    def _update_animation_list(self):
        self.anim_list.clear()
        if not self.model: return
        for name, config in self.model.animations.items():
            item = QTreeWidgetItem(self.anim_list)
            item.setText(0, name)
            item.setText(1, f"{config.get('start', 1)}-{config.get('end', 1)}")
        
        # 默认选中第一个动作并播放
        if self.anim_list.topLevelItemCount() > 0:
            first_item = self.anim_list.topLevelItem(0)
            self.anim_list.setCurrentItem(first_item)
            self._on_animation_item_clicked(first_item, 0)

    def _on_costume_selection_changed(self, row):
        if row < 0 or not self.model: return
        img_path = self.model.get_costume_path(row + 1)
        if img_path:
            self.display_on_canvas(img_path)
            # 只有在没播放动画时，点击左侧列表才更新预览窗
            if not self.is_playing:
                self.update_preview_static(img_path)

    def display_on_canvas(self, path):
        pix = QPixmap(path)
        if pix.isNull(): return
        self.canvas_scene.clear()
        item = self.canvas_scene.addPixmap(pix)
        self.canvas_scene.setSceneRect(pix.rect())
        self.canvas.centerOn(item)

    def update_preview_static(self, path):
        pix = QPixmap(path)
        if not pix.isNull():
            # 缩放以适应预览窗大小
            scaled_pix = pix.scaled(
                self.preview.size(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            self.preview.setPixmap(scaled_pix)
            self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)