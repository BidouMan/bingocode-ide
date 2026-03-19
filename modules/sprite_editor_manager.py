import os
from PySide6.QtCore import QObject, Qt, QTimer,QRectF
from PySide6.QtGui import QPixmap,QPainter,QAction, QCursor,QBrush,QColor,QIcon
from PySide6.QtWidgets import (QTreeWidgetItem, QLineEdit, QHBoxLayout, QWidget, 
                             QSpinBox, QLabel, QMenu, QInputDialog,QGraphicsScene)
from models.sprite_model import SpriteDataModel
from modules.checkerboard_manager import checker_manager
from modules.canvas_manager import SmartCanvas

class SpriteEditorManager(QObject):
    def __init__(self, ui_form):
        super().__init__()
        self.ui = ui_form
        self.model = None
        self.current_project_path = ""
        self.current_bg_index = 0
        self.is_original_size = False


        # 1. 🚀 替换画布控件 (只做一次，不要覆盖)
        from modules.canvas_manager import SmartCanvas
        parent_widget = self.ui.sprite_canvas.parentWidget()
        parent_layout = parent_widget.layout()
        
        self.canvas = SmartCanvas(parent_widget)
        parent_layout.replaceWidget(self.ui.sprite_canvas, self.canvas)
        self.ui.sprite_canvas.hide()
        self.ui.sprite_canvas.deleteLater()
        
        # 2. 绑定场景 (指向我们的新 self.canvas)
        self.canvas_scene = QGraphicsScene()
        self.canvas.setScene(self.canvas_scene)

        # 3. 动画引擎核心变量
        self.timer = QTimer()
        # self.timer.timeout.disconnect() # 先断开所有可能的连接防止重复
        self.timer.timeout.connect(self.play_next_frame)
        self.current_anim_config = None
        self.current_frame_index = 0
        self.is_playing = False

        # 4. UI 组件引用 (注意：不要再给 self.canvas 赋值了！)
        self.fps_list = self.ui.sprite_fps_list
        self.preview = self.ui.animate_preview
        self.anim_list = self.ui.animate_list
        self.ui.fps_slider.setRange(1, 60)

        self._setup_connections()

    def _setup_connections(self):
        # 造型列表点击 -> 切换显示
        self.fps_list.currentRowChanged.connect(self._on_costume_selection_changed)
        # 动作列表点击 -> 切换动画序列
        self.anim_list.itemClicked.connect(self._on_animation_item_clicked)

        # 动画管理器(删除+重命名)
        self.anim_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.anim_list.customContextMenuRequested.connect(self._show_anim_context_menu)
        self.anim_list.itemChanged.connect(self._on_anim_renamed)

        # 开启造型列表右键
        self.fps_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.fps_list.customContextMenuRequested.connect(self._show_costume_context_menu)
        self.fps_list.setSelectionMode(self.fps_list.SelectionMode.ExtendedSelection)
        # 造型列表点击 -> 切换显示
        self.fps_list.currentRowChanged.connect(self._on_costume_selection_changed)
        # 动作列表点击 -> 切换动画序列
        self.anim_list.itemClicked.connect(self._on_animation_item_clicked)

        # 按键绑定
        self.ui.fps_slider.valueChanged.connect(self._on_fps_slider_changed)
        self.ui.btn_preview_play.clicked.connect(self.toggle_play)
        self.ui.btn_preview_prev.clicked.connect(self.play_prev_frame)
        self.ui.btn_preview_next.clicked.connect(self.play_next_frame)
        self.ui.btn_preview_scale.clicked.connect(self.toggle_preview_scale)
        self.ui.btn_preview_add.clicked.connect(self.add_new_animation)
        self.ui.btn_preview_change_bg.clicked.connect(self.toggle_preview_background)


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
        self.anim_list.setColumnCount(2)
        self.anim_list.setColumnWidth(0, 110)
        self.anim_list.setColumnWidth(1, 90)
        
        # 🚀 开启右键菜单策略
        self.anim_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.anim_list.customContextMenuRequested.connect(self._show_anim_context_menu)

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

        # ✨ 就是这行：列表倒完数据后，立即点一下第一个
        if self.anim_list.topLevelItemCount() > 0:
            # 只有在“当前没有选中项”时才自动选第一个（这解决了你担心的重复触发问题）
            if not self.anim_list.currentItem():
                first_item = self.anim_list.topLevelItem(0)
                self.anim_list.setCurrentItem(first_item)
                # 主动调用点击函数，把整套预览逻辑带起来
                self._on_animation_item_clicked(first_item, 0)

                self.ui.btn_preview_play.setChecked(True)
                self.is_playing = True

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
        anim_name = item.text(0)
        if not self.model or anim_name not in self.model.animations:
            return
        
        # 1. 播放动画
        self.play_animation(anim_name)

        # 2. 🚀 联动高亮（临时开启多选）
        config = self.model.animations[anim_name]
        start_idx = config.get("start", 1) 
        end_idx = config.get("end", 1) 
        
        self.fps_list.blockSignals(True)
        self.fps_list.setSelectionMode(self.fps_list.SelectionMode.MultiSelection)
        self.fps_list.clearSelection()
        
        # 🚀 修正点：i 是 1~N，那么 Row 索引必须是 i-1
        for i in range(start_idx, end_idx + 1):
            list_item = self.fps_list.item(i - 1) # 这里减 1 确保对齐 Row 0
            if list_item:
                list_item.setSelected(True)
        
        # 滚动到起始帧（同样是 start_idx - 1）
        first_item = self.fps_list.item(start_idx - 1)
        if first_item:
            self.fps_list.scrollToItem(first_item, self.fps_list.ScrollHint.PositionAtTop)
        
        self.fps_list.setSelectionMode(self.fps_list.SelectionMode.SingleSelection)
        self.fps_list.blockSignals(False)

        # 同步 Slider 位置
        fps = self.current_anim_config.get("fps", 10)
        self.ui.fps_slider.blockSignals(True) # 阻塞信号，防止触发上面的 _on_fps_slider_changed 导致重复保存
        self.ui.fps_slider.setValue(fps)
        self.ui.fps_slider.blockSignals(False)

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
        # 如果是多选模式，row 可能只是最后一次点击的那一行
        if row < 0 or not self.model: return
        
        # 获取当前真正被点击（焦点所在）的那一张图
        img_path = self.model.get_costume_path(row + 1)
        if img_path:
            self.display_on_canvas(img_path)
            if not self.is_playing:
                self.update_preview_static(img_path)

    def display_on_canvas(self, path):
        pix = QPixmap(path)
        if pix.isNull(): 
            self.canvas_scene.clear()
            # 清空场景时，重置 zoom_level 和 SceneRect 
            self.canvas._zoom_level = 1.0
            self.canvas.setSceneRect(QRectF()) 
            return
        
        # 1. 清理并添加新图
        self.canvas_scene.clear()
        item = self.canvas_scene.addPixmap(pix)
        
        # 2. 彻底重置所有变换（非常重要）
        # 这样可以确保 scale 计算是从 1.0 开始的干净状态
        self.canvas.resetTransform()
        
        # 3. 计算自适应缩放系数
        # 这里建议使用 viewport() 的实时尺寸
        view_w = self.canvas.viewport().width()
        view_h = self.canvas.viewport().height()
        
        # 如果刚启动程序窗口还没显示，可能会得到 0，做个保底
        if view_w <= 0: view_w = 800
        if view_h <= 0: view_h = 600

        sc_width = view_w / pix.width()
        sc_height = view_h / pix.height()
        
        # 取最小比例并留出 30% 空隙 (0.7)
        initial_scale = min(sc_width, sc_height) * 0.7
        
        # 限制自动缩放范围：不小于1倍，不大于15倍
        initial_scale = max(1.0, min(initial_scale, 15.0))
        
        # 4. 应用缩放并同步变量
        self.canvas.scale(initial_scale, initial_scale)
        self.canvas._zoom_level = initial_scale 

        # 5. 🚀 关键：顺序逻辑
        # 必须先执行 update_scene_range 扩展可滑动的“轨道”
        # 然后再执行 centerOn 才能确保图片能被定位到轨道中心
        self.canvas.update_scene_range() 
        self.canvas.centerOn(item)

    def update_preview_static(self, path):
        source_pix = QPixmap(path)
        if source_pix.isNull(): return

        # 1. 画布准备
        final_view_size = self.preview.size()
        full_canvas = QPixmap(final_view_size)
        painter = QPainter(full_canvas)
        
        # 2. 背景绘制 (保持你原有的逻辑)
        if self.current_bg_index == 0:
            full_canvas.fill(QColor("#2b2b2b"))
        elif self.current_bg_index == 1:
            full_canvas.fill(QColor("#ffffff"))
        elif self.current_bg_index == 2:
            brush = checker_manager.get_brush(theme="light")
            painter.fillRect(full_canvas.rect(), brush)

        # 🚀 3. 绘制角色 (使用我们手动的变量)
        if self.is_original_size:
            # 模式：原始尺寸 (1:1)
            target_pix = source_pix
        else:
            # 模式：适配尺寸 (拉伸)
            target_pix = source_pix.scaled(
                final_view_size, 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.FastTransformation
            )
        
        # 居中计算
        x = (final_view_size.width() - target_pix.width()) // 2
        y = (final_view_size.height() - target_pix.height()) // 2
        
        painter.drawPixmap(x, y, target_pix)
        painter.end()

        # 4. 显示
        self.preview.setPixmap(full_canvas)
        


    def _show_costume_context_menu(self, pos):
        """造型列表右键：物理删除"""
        row = self.fps_list.currentRow()
        if row < 0: return
        
        menu = QMenu(self.fps_list)
        del_action = QAction(f"🗑️ 彻底删除造型: {row + 1}", menu)
        del_action.triggered.connect(lambda: self.delete_costume_physically(row + 1))
        menu.addAction(del_action)
        menu.exec(QCursor.pos())

    def delete_costume_physically(self, target_idx):
        """彻底删除某一帧并修正所有动画索引"""
        if not self.model: return

        removed_frame = self.model.costumes.pop(target_idx - 1)
        
        # 3. 🚀 核心：修正所有动画片段的索引
        anims_to_delete = []
        for name, config in self.model.animations.items():
            start = config.get("start", 1)
            end = config.get("end", 1)

            # 情况 A: 动作在被删除帧之后 -> 整体前移
            if start > target_idx:
                config["start"] -= 1
                config["end"] -= 1
            
            # 情况 B: 被删除帧在动作范围内
            elif start <= target_idx <= end:
                # 如果动作只有这一帧且被删了 -> 标记动作待删除
                if start == end:
                    anims_to_delete.append(name)
                else:
                    # 范围缩小
                    config["end"] -= 1
                    # 特殊情况：如果删的是 start 帧，start 不变（因为后面的补上来了），只需减 end
                    # 但需要确保 end 依然 >= start
            
            # 情况 C: 动作在被删除帧之前 -> 不受影响

        # 清理失效动作
        for name in anims_to_delete:
            del self.model.animations[name]

        # 4. 保存模型并刷新 UI
        self.model.save()
        self.refresh_all_ui("ALL") # 刷新全部 UI 以确保索引同步
        new_row = min(target_idx - 1, self.fps_list.count() - 1)
        self.fps_list.setCurrentRow(new_row)
    
    def _on_fps_slider_changed(self, value):
        """当 FPS 滑动条数值改变时触发"""
        if not self.model or not self.current_anim_config:
            return

        # 1. 获取当前选中的动画名字
        current_item = self.anim_list.currentItem()
        if not current_item:
            return
        
        anim_name = current_item.text(0)
        
        # 2. 更新模型数据
        self.model.animations[anim_name]["fps"] = value
        # 实时更新当前运行配置，这样播放器能立刻感知
        self.current_anim_config["fps"] = value
        
        # 3. 🚀 关键：如果正在播放，实时调整计时器间隔
        if self.is_playing:
            interval = int(1000 / max(value, 1))
            self.timer.setInterval(interval) 
            
        # 4. 打印调试信息（可选：如果你界面上有个 Label 显示数字更好）
        # self.ui.fps_label.setText(f"{value} FPS")
        print(f"⚡ [DEBUG] FPS 实时调整为: {value}")
        
        # 5. 延迟保存（或者在停止滑动后保存，防止频繁写磁盘）
        self.model.save()
    
    from PySide6.QtGui import QPixmap, QPainter, QColor

    def toggle_preview_background(self):
        """切换预览窗口的背景模式"""
        self.current_bg_index = (self.current_bg_index + 1) % 3
        
        # 强制刷新当前帧，让新背景立刻生效
        # 获取当前正在显示的这一帧路径
        current_row = self.fps_list.currentRow()
        img_path = self.model.get_costume_path(current_row + 1)
        if img_path:
            self.update_preview_static(img_path)

    

    def toggle_play(self):
        if not self.current_anim_config:
            self.ui.btn_preview_play.setChecked(False)
            return

        # 完全信任 UI 按钮的状态
        self.is_playing = self.ui.btn_preview_play.isChecked()
        
        if self.is_playing:
            fps = self.current_anim_config.get("fps", 10)
            self.timer.start(int(1000 / max(fps, 1)))
        else:
            self.timer.stop()


    def play_next_frame(self):
        """播放下一帧"""
        # 🚀 逻辑修正：如果是手动点击“下一帧”按钮触发的
        if self.sender() == self.ui.btn_preview_next:
            if self.is_playing:
                # 强制取消按钮的选中状态（这会自动触发图标变回播放箭头）
                self.ui.btn_preview_play.setChecked(False)
                # 手动调用一次，确保 timer 停止，is_playing 变 False
                self.toggle_play() 

        if not self.model or not self.current_anim_config:
            return
            
        start = self.current_anim_config.get("start", 1)
        end = self.current_anim_config.get("end", 1)
        
        # 索引循环逻辑
        if self.current_frame_index >= end:
            self.current_frame_index = start
        else:
            self.current_frame_index += 1
            
        # 执行渲染
        self._sync_animation_frame()

    def play_prev_frame(self):
        """播放上一帧"""
        # 🚀 逻辑修正：手动点击“上一帧”时
        if self.sender() == self.ui.btn_preview_prev:
            if self.is_playing:
                self.ui.btn_preview_play.setChecked(False)
                self.toggle_play()

        if not self.model or not self.current_anim_config:
            return
            
        start = self.current_anim_config.get("start", 1)
        end = self.current_anim_config.get("end", 1)
            
        if self.current_frame_index <= start:
            self.current_frame_index = end
        else:
            self.current_frame_index -= 1
        
        self._sync_animation_frame()
    
    def _sync_animation_frame(self):
        """同步帧，并确保索引完全匹配 (1-based to 0-based)"""
        img_path = self.model.get_costume_path(self.current_frame_index)
        if img_path:
            self.update_preview_static(img_path)
            
            self.ui.sprite_fps_list.blockSignals(True)
            
            # 获取对应的 List Item
            # 🚀 修正点：current_frame_index(1~N) -> item(index-1)
            target_row = self.current_frame_index - 1
            item = self.ui.sprite_fps_list.item(target_row)
            
            if item:
                if self.sender() == self.timer:
                    # 自动播放时：仅滚动，不改变选中蓝底
                    self.ui.sprite_fps_list.scrollToItem(item, self.ui.sprite_fps_list.ScrollHint.EnsureVisible)
                else:
                    # 手动点击（Prev/Next）时：强行选中该行
                    self.ui.sprite_fps_list.setCurrentRow(target_row)
                    
            self.ui.sprite_fps_list.blockSignals(False)


    def toggle_preview_scale(self):
        """手动切换缩放状态"""
        # 1. 状态取反
        self.is_original_size = not self.is_original_size
        
        # 2. 打印 Debug 信息，确保点击生效
        state_str = "原始尺寸" if self.is_original_size else "适配尺寸"
        print(f"🔘 [DEBUG] 缩放按钮点击! 当前模式: {state_str}")

        # 3. 强制触发当前帧重绘
        if self.model and hasattr(self, 'current_frame_index'):
            img_path = self.model.get_costume_path(self.current_frame_index)
            if img_path:
                self.update_preview_static(img_path)
    
    def cleanup(self):
        """安全释放资源，防止退出时析构冲突"""
        try:
            # 1. 停止计时器（防止销毁过程中触发刷新）
            if hasattr(self, 'timer') and self.timer.isActive():
                self.timer.stop()
                self.timer.blockSignals(True) # 彻底切断信号
            
            # 2. 清空场景
            if hasattr(self, 'canvas_scene') and self.canvas_scene:
                self.canvas_scene.clear()
                # 解绑场景，防止 QGraphicsView 销毁时去访问已失效的 Python 场景对象
                if hasattr(self, 'canvas'):
                    self.canvas.setScene(None)

            # 3. 解除对 UI 的引用，帮助 GC
            self.ui = None
            self.model = None
            print("✅ [DEBUG] SpriteEditorManager 清理完成")
        except Exception as e:
            print(f"❌ [DEBUG] 清理报错: {e}")
    