import os
from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtGui import QPixmap,QPainter,QAction, QCursor
from PySide6.QtWidgets import (QTreeWidgetItem, QLineEdit, QHBoxLayout, QWidget, 
                             QSpinBox, QLabel, QMenu, QInputDialog,QGraphicsScene)
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

        self.anim_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.anim_list.customContextMenuRequested.connect(self._show_anim_context_menu)
        
        # 🚀 只有在这里连接一次 itemChanged
        self.anim_list.itemChanged.connect(self._on_anim_renamed)

        # 按键绑定
        self.ui.btn_preview_add.clicked.connect(self.add_new_animation)

    def add_new_animation(self):
        """添加新动画片段，处理重名逻辑"""
        if not self.model: return

        # 1. 生成不重复的名字
        base_name = "动画"
        new_name = base_name
        counter = 1
        while new_name in self.model.animations:
            new_name = f"{base_name}_{counter}"
            counter += 1

        # 2. 准备默认配置 (假设默认包含所有帧)
        total_frames = len(self.model.costumes)
        new_config = {
            "start": 1,
            "end": total_frames if total_frames > 0 else 1,
            "fps": 10,
            "loop": True
        }

        # 3. 更新模型并保存
        self.model.animations[new_name] = new_config
        self.model.save() # 确保你的 model 有 save 方法将 self.animations 写回 config.json
        
        # 4. 刷新 UI
        self._update_animation_list()
        print(f"➕ [DEBUG] 已添加新动画: {new_name}")

    

    def _on_anim_data_changed(self, anim_name, key, value):
        """当用户修改输入框数值时同步到模型"""
        if self.model and anim_name in self.model.animations:
            self.model.animations[anim_name][key] = value
            self.model.save()
            
            # 🚀 重点：如果正在预览的就是这个动画，实时修改当前引擎的配置
            if self.is_playing and self.current_anim_config:
                # 这里检查名字是否匹配（如果你的 model.animations 是有序的）
                # 或者简单的直接更新当前配置引用
                self.current_anim_config[key] = value 
                print(f"🔄 [DEBUG] 动画 {anim_name} 的 {key} 已实时变为 {value}")



    def _update_animation_list(self):
        """刷新动作树，支持双击原地编辑名字"""
        print("🌳 [DEBUG] SpriteEditorManager: 刷新动作树(原地编辑模式)...")
        
        self.anim_list.setColumnCount(2)
        self.anim_list.setColumnWidth(0, 110)
        self.anim_list.setColumnWidth(1, 90)
        
        # 🚀 开启右键菜单策略
        self.anim_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        # try: self.anim_list.customContextMenuRequested.disconnect()
        # except: pass
        self.anim_list.customContextMenuRequested.connect(self._show_anim_context_menu)

        # 🚀 监听编辑完成信号 (防止重复连接)
        # try: self.anim_list.itemChanged.disconnect()
        # except: pass
        # self.anim_list.itemChanged.connect(self._on_anim_renamed)

        self.anim_list.blockSignals(True)
        self.anim_list.clear()
        if not self.model: return

        for name, config in self.model.animations.items():
            item = QTreeWidgetItem(self.anim_list)
            item.setText(0, name) 
            # 🚀 存储一份原始名字到 UserRole，方便重命名时对比
            item.setData(0, Qt.ItemDataRole.UserRole, name)
            # 🚀 设置第一列（名字）可以编辑
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            
            # 注入输入框容器 (保持透明和 NoFocus 解决高亮断层)
            edit_widget = QWidget()
            edit_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            edit_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            edit_widget.setStyleSheet("background: transparent; border: none;")
            
            layout = QHBoxLayout(edit_widget)
            layout.setContentsMargins(5, 0, 5, 0)
            layout.setSpacing(2)

            start_input = QSpinBox()
            start_input.setRange(1, 999)
            start_input.setValue(config.get("start", 1))
            start_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            start_input.setFixedWidth(35)
            start_input.setStyleSheet("background: rgba(0,0,0,50); color: white; border-radius: 2px;")
            
            line_label = QLabel("-")
            
            end_input = QSpinBox()
            end_input.setRange(1, 999)
            end_input.setValue(config.get("end", 1))
            end_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            end_input.setFixedWidth(35)
            end_input.setStyleSheet(start_input.styleSheet())

            layout.addWidget(start_input)
            layout.addWidget(line_label)
            layout.addWidget(end_input)
            
            self.anim_list.addTopLevelItem(item)
            self.anim_list.setItemWidget(item, 1, edit_widget)

            # 绑定数值改变
            start_input.valueChanged.connect(lambda val, n=name: self._on_anim_data_changed(n, "start", val))
            end_input.valueChanged.connect(lambda val, n=name: self._on_anim_data_changed(n, "end", val))

        self.anim_list.blockSignals(False)
        self.anim_list.doItemsLayout()

    def _show_anim_context_menu(self, pos):
        """弹出右键菜单 - 仅保留删除"""
        item = self.anim_list.itemAt(pos)
        if not item: return
        
        anim_name = item.text(0)
        menu = QMenu(self.anim_list)
        
        # 只保留删除动作
        delete_action = QAction("🗑️ 删除动作", menu)
        delete_action.triggered.connect(lambda: self.delete_animation(anim_name))
        
        menu.addAction(delete_action)
        menu.exec(QCursor.pos())

    def _on_anim_renamed(self, item, column):
        """原地编辑名字完成后的回调 - 修复死循环"""
        if column != 0 or not self.model: 
            return

        new_name = item.text(0).strip()
        
        # 获取旧名字 (我们利用 DataRole 来精准定位，不再用遍历对比)
        # 在 _update_animation_list 里我们会设置这个 UserRole
        old_name = item.data(0, Qt.ItemDataRole.UserRole)
        
        if not old_name or new_name == old_name:
            return

        # 🚀 重点：校验冲突并阻止死循环
        if not new_name or new_name in self.model.animations:
            print(f"⚠️ [DEBUG] 名称冲突或非法: {new_name}")
            # 暂时切断信号，防止 setText 导致递归
            self.anim_list.blockSignals(True)
            item.setText(0, old_name)
            self.anim_list.blockSignals(False)
            return

        # 同步 Model
        config = self.model.animations.pop(old_name)
        self.model.animations[new_name] = config
        
        # 🚀 关键修复：先保存，再阻塞信号刷新 UI
        self.model.save()
        
        self.anim_list.blockSignals(True)
        self._update_animation_list()
        self.anim_list.blockSignals(False)
        print(f"📝 [DEBUG] 重命名成功: {old_name} -> {new_name}")

    

    

    

    def delete_animation(self, anim_name):
        if not self.model or anim_name not in self.model.animations: return

        # 1. 停止播放
        if self.is_playing and self.current_anim_config == self.model.animations[anim_name]:
            self.stop_animation()

        # 2. 彻底从字典移除
        print(f"🗑️ [DEBUG] 准备从字典删除: {anim_name}")
        self.model.animations.pop(anim_name)
        
        # 3. 立即保存到磁盘
        self.model.save()
        
        # 4. 刷新 UI
        self._update_animation_list()
        print(f"🗑️ [DEBUG] 准备删除: {anim_name}, 剩余动作: {list(self.model.animations.keys())}")

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
        
        # 🚀 这里的重点：QGraphicsView 本身也有缩放控制
        # 如果你之后要在画布上实现鼠标滚轮缩放像素，这种设置是必须的
        item = self.canvas_scene.addPixmap(pix)
        
        # 关键设置：如果以后对 View 进行 scale()，确保它是像素化的
        self.canvas.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.canvas.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        
        self.canvas_scene.setSceneRect(pix.rect())
        self.canvas.centerOn(item)
        print(f"🎨 [DEBUG] 画布已更新(像素模式)")

    def update_preview_static(self, path):
        pix = QPixmap(path)
        if not pix.isNull():
            # 缩放以适应预览窗大小
            scaled_pix = pix.scaled(
                self.preview.size(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.FastTransformation
            )
            self.preview.setPixmap(scaled_pix)
            self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)