import os
from PySide6.QtCore import QObject, Qt, QTimer, QRectF, QSize, QEvent
from PySide6.QtGui import QPixmap, QPainter, QAction, QCursor, QBrush, QColor, QIcon
from PySide6.QtWidgets import (
    QTreeWidgetItem,
    QLineEdit,
    QHBoxLayout,
    QWidget,
    QSpinBox,
    QLabel,
    QMenu,
    QInputDialog,
    QGraphicsScene,
    QPushButton,
    QListWidgetItem,
    QAbstractItemView,
    QListView,
)
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
        self.timer.timeout.connect(self._update_animation_frame)
        self.current_anim_config = None
        self.current_frame_index = 0
        self.is_playing = False

        # 4. UI 组件引用 (注意：不要再给 self.canvas 赋值了！)
        self.fps_list = self.ui.sprite_fps_list
        self.preview = self.ui.animate_preview
        self.anim_list = self.ui.animate_list
        self.ui.fps_slider.setRange(1, 60)

        # 禁用滚动条
        self.fps_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.fps_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # 禁用水平滚动
        self.fps_list.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.fps_list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.fps_list.setMovement(QListView.Static)

        # 彻底阻止水平滚动
        self.fps_list.viewport().setMouseTracking(True)
        self.fps_list.viewport().installEventFilter(self)

        # 移除分支图标和缩进，让选中区域覆盖整行
        self.anim_list.setRootIsDecorated(False)
        self.anim_list.setIndentation(0)

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
        self.fps_list.customContextMenuRequested.connect(
            self._show_costume_context_menu
        )
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
        if not self.model:
            return

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
            "loop": True,
        }

        # 3. 更新模型并保存
        self.model.animations[new_name] = new_config
        self.model.save()  # 确保你的 model 有 save 方法将 self.animations 写回 config.json

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
        self.anim_list.setColumnCount(1)
        self.anim_list.setColumnWidth(0, 220)

        # 🚀 开启右键菜单策略
        self.anim_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.anim_list.customContextMenuRequested.connect(self._show_anim_context_menu)

        self.anim_list.blockSignals(True)
        self.anim_list.clear()
        if not self.model:
            return

        for name, config in self.model.animations.items():
            item = QTreeWidgetItem(self.anim_list)
            # 🚀 存储一份原始名字到 UserRole，方便重命名时对比
            item.setData(0, Qt.ItemDataRole.UserRole, name)
            # 🚀 设置第一列（名字）可以编辑
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)

            # 创建单一容器来管理所有组件
            container_widget = QWidget()
            container_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            container_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            container_widget.setStyleSheet("background: transparent; border: none;")

            # 使用水平布局排列所有组件
            container_layout = QHBoxLayout(container_widget)
            container_layout.setContentsMargins(20, 0, 8, 0)
            container_layout.setSpacing(4)

            # 创建动画名称标签
            name_label = QLabel(name)
            name_label.setStyleSheet("color: white;")

            # 添加弹簧（拉伸空间）
            from PySide6.QtWidgets import QSpacerItem, QSizePolicy

            spacer = QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum)

            # 创建起始帧输入框
            start_input = QSpinBox()
            start_input.setRange(1, 999)
            start_input.setValue(config.get("start", 1))
            start_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            start_input.setFixedWidth(35)
            start_input.setStyleSheet(
                "background: rgba(0,0,0,120); color: white; border-radius: 2px;"
            )
            start_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # 创建连接线标签
            line_label = QLabel("-")
            line_label.setStyleSheet("color: #9ca0a4;")

            # 创建结束帧输入框
            end_input = QSpinBox()
            end_input.setRange(1, 999)
            end_input.setValue(config.get("end", 1))
            end_input.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
            end_input.setFixedWidth(35)
            end_input.setStyleSheet(
                "background: rgba(0,0,0,120); color: white; border-radius: 2px;"
            )
            end_input.setAlignment(Qt.AlignmentFlag.AlignCenter)

            # 添加循环按钮
            loop_icon_path = os.path.join("assets", "icons", "anim_loop.svg")
            loop_off_icon_path = os.path.join("assets", "icons", "anim_loop_off.svg")
            loop_icon = QIcon(loop_icon_path)
            loop_off_icon = QIcon(loop_off_icon_path)
            is_loop = config.get("loop", True)

            loop_button = QPushButton()
            loop_button.setFixedSize(24, 24)
            loop_button.setFlat(True)
            loop_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            loop_button.setStyleSheet("padding: 0; border: none; margin: 0;")
            loop_button.setContentsMargins(0, 0, 0, 0)

            if is_loop:
                loop_button.setIcon(loop_icon)
                loop_button.setIconSize(QSize(14, 14))
            else:
                loop_button.setIcon(loop_off_icon)
                loop_button.setIconSize(QSize(14, 14))

            # 连接循环按钮点击事件
            loop_button.clicked.connect(
                lambda checked, n=name, btn=loop_button: self._on_loop_toggled(n, btn)
            )

            # 添加所有组件到布局
            container_layout.addWidget(name_label)
            container_layout.addItem(spacer)
            container_layout.addWidget(start_input)
            container_layout.addWidget(line_label)
            container_layout.addWidget(end_input)
            container_layout.addWidget(loop_button)

            # 设置容器为item的widget
            self.anim_list.addTopLevelItem(item)
            self.anim_list.setItemWidget(item, 0, container_widget)

            # 绑定数值改变
            start_input.valueChanged.connect(
                lambda val, n=name: self._on_anim_data_changed(n, "start", val)
            )
            end_input.valueChanged.connect(
                lambda val, n=name: self._on_anim_data_changed(n, "end", val)
            )

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
        if not item:
            return

        anim_name = item.text(0)
        menu = QMenu(self.anim_list)

        # 只保留删除动作
        delete_action = QAction("删除动作", menu)
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
        if not self.model or anim_name not in self.model.animations:
            return

        # 1. 停止播放
        if (
            self.is_playing
            and self.current_anim_config == self.model.animations[anim_name]
        ):
            self.stop_animation()

        # 2. 彻底从字典移除
        print(f"🗑️ [DEBUG] 准备从字典删除: {anim_name}")
        self.model.animations.pop(anim_name)

        # 3. 立即保存到磁盘
        self.model.save()

        # 4. 刷新 UI
        self._update_animation_list()
        print(
            f"🗑️ [DEBUG] 准备删除: {anim_name}, 剩余动作: {list(self.model.animations.keys())}"
        )

    def load_sprite(self, project_path):
        """由 AppController 调用"""
        if self.current_project_path == project_path:
            return

        self.stop_animation()  # 切换角色前先停止旧动画
        self.current_project_path = project_path
        self.model = SpriteDataModel(project_path)
        self.model.data_changed.connect(self.refresh_all_ui)
        self.refresh_all_ui("ALL")

    def _on_animation_item_clicked(self, item, column):
        # 从UserRole获取动画名称
        anim_name = item.data(0, Qt.ItemDataRole.UserRole)
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
            list_item = self.fps_list.item(i - 1)  # 这里减 1 确保对齐 Row 0
            if list_item:
                list_item.setSelected(True)

        # 滚动到起始帧（同样是 start_idx - 1）
        first_item = self.fps_list.item(start_idx - 1)
        if first_item:
            self.fps_list.scrollToItem(
                first_item, self.fps_list.ScrollHint.PositionAtTop
            )

        self.fps_list.setSelectionMode(self.fps_list.SelectionMode.SingleSelection)
        self.fps_list.blockSignals(False)

        # 同步 Slider 位置
        fps = self.current_anim_config.get("fps", 10)
        self.ui.fps_slider.blockSignals(
            True
        )  # 阻塞信号，防止触发上面的 _on_fps_slider_changed 导致重复保存
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
        # 更新播放按钮状态为选中
        self.ui.btn_preview_play.setChecked(True)

    def stop_animation(self):
        """停止播放"""
        self.timer.stop()
        self.is_playing = False
        # 更新播放按钮状态为未选中
        self.ui.btn_preview_play.setChecked(False)
        # 不要清除current_anim_config，以便再次播放

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

        # 2. 移除序列帧列表同步功能，保持列表位置不变

        # 3. 递增帧号
        self.current_frame_index += 1

        # 4. 边界检查
        if self.current_frame_index > end:
            if loop:
                self.current_frame_index = start
            else:
                self.stop_animation()

    # --- UI 刷新逻辑 ---

    def refresh_all_ui(self, change_type, detail=None):
        if change_type in ["ALL", "COSTUME"]:
            self._update_fps_list()
        if change_type in ["ALL", "ANIMATION"]:
            self._update_animation_list()

    def _update_fps_list(self):
        self.fps_list.blockSignals(True)
        self.fps_list.clear()

        try:
            from PySide6.QtWidgets import QVBoxLayout, QSizePolicy

            for i, filename in enumerate(self.model.costumes):
                # 创建卡片widget
                card_widget = QWidget()
                # 设置卡片为正方形，参考resource_manager.py中的实现
                card_widget.setFixedSize(78, 78)
                card_widget.setStyleSheet("""
                    QWidget {
                        background-color: #1e1e1e;
                        border: 1px solid #2d2d2d;
                        border-radius: 4px;
                        margin: 0;
                        padding: 0;
                    }
                    QWidget:hover {
                        background-color: #3e4451;
                        border: 1px solid #4a4f58;
                    }
                """)
                card_layout = QVBoxLayout(card_widget)
                card_layout.setContentsMargins(4, 4, 4, 4)
                card_layout.setSpacing(4)
                card_layout.setAlignment(Qt.AlignCenter)

                # 创建缩略图标签
                thumbnail_label = QLabel()
                thumbnail_label.setAlignment(Qt.AlignCenter)
                thumbnail_label.setSizePolicy(
                    QSizePolicy.Expanding, QSizePolicy.Expanding
                )
                thumbnail_label.setStyleSheet("background: transparent; border: none;")

                # 尝试加载图片作为缩略图
                costume_path = self.model.get_costume_path(i + 1)
                if costume_path:
                    pixmap = QPixmap(costume_path)
                    if not pixmap.isNull():
                        # 缩放到正方形大小，使用fast模式
                        scaled_pixmap = pixmap.scaled(
                            60, 60, Qt.KeepAspectRatioByExpanding, Qt.FastTransformation
                        )
                        thumbnail_label.setPixmap(scaled_pixmap)

                # 创建帧数标签
                frame_label = QLabel(f"帧 {i + 1}")
                frame_label.setAlignment(Qt.AlignCenter)
                frame_label.setStyleSheet(
                    "color: #abb2bf; font-size: 10px; background: transparent; border: none;"
                )

                # 添加到布局
                card_layout.addWidget(thumbnail_label)
                card_layout.addWidget(frame_label)

                # 创建列表项并设置widget
                item = QListWidgetItem()
                # 设置QListWidgetItem为正方形，与卡片大小一致
                item.setSizeHint(QSize(80, 80))
                item.setTextAlignment(Qt.AlignCenter)
                self.fps_list.addItem(item)
                self.fps_list.setItemWidget(item, card_widget)
        except Exception as e:
            # 如果卡片创建失败，回退到文本显示
            for i, filename in enumerate(self.model.costumes):
                self.fps_list.addItem(f"{i + 1}: {filename}")

        self.fps_list.blockSignals(False)
        if self.fps_list.count() > 0:
            self.fps_list.setCurrentRow(0)

    def _on_costume_selection_changed(self, row):
        # 如果是多选模式，row 可能只是最后一次点击的那一行
        if row < 0 or not self.model:
            return

        # 重置所有卡片的样式
        for i in range(self.fps_list.count()):
            item = self.fps_list.item(i)
            if item:
                widget = self.fps_list.itemWidget(item)
                if widget:
                    widget.setStyleSheet("""
                        QWidget {
                            background-color: #1e1e1e;
                            border: 1px solid #2d2d2d;
                            border-radius: 4px;
                            margin: 0;
                            padding: 0;
                        }
                        QWidget:hover {
                            background-color: #3e4451;
                            border: 1px solid #4a4f58;
                        }
                    """)

        # 设置选中卡片的样式
        current_item = self.fps_list.currentItem()
        if current_item:
            current_widget = self.fps_list.itemWidget(current_item)
            if current_widget:
                current_widget.setStyleSheet("""
                    QWidget {
                        background-color: #1e1e1e;
                        border: 2px solid rgb(91, 199, 114);
                        border-radius: 4px;
                        margin: 0;
                        padding: 0;
                    }
                    QWidget:hover {
                        background-color: #3e4451;
                        border: 2px solid rgb(91, 199, 114);
                    }
                """)

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
        if view_w <= 0:
            view_w = 800
        if view_h <= 0:
            view_h = 600

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
        if source_pix.isNull():
            return

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
                Qt.TransformationMode.FastTransformation,
            )

        # 居中计算，向上偏移
        x = (final_view_size.width() - target_pix.width()) // 2
        # 向上移动10像素
        y = (final_view_size.height() - target_pix.height()) // 2 - 10

        painter.drawPixmap(x, y, target_pix)
        painter.end()

        # 4. 显示
        self.preview.setPixmap(full_canvas)

    def _show_costume_context_menu(self, pos):
        """造型列表右键：物理删除"""
        row = self.fps_list.currentRow()
        if row < 0:
            return

        menu = QMenu(self.fps_list)
        del_action = QAction(f"删除造型: {row + 1}", menu)
        del_action.triggered.connect(lambda: self.delete_costume_physically(row + 1))
        menu.addAction(del_action)
        menu.exec(QCursor.pos())

    def delete_costume_physically(self, target_idx):
        """彻底删除某一帧并修正所有动画索引"""
        if not self.model:
            return

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
        self.refresh_all_ui("ALL")  # 刷新全部 UI 以确保索引同步
        new_row = min(target_idx - 1, self.fps_list.count() - 1)
        self.fps_list.setCurrentRow(new_row)

    def _on_fps_slider_changed(self, value):
        """当 FPS 滑动条数值改变时触发"""
        if not self.model or not self.current_anim_config:
            return

        # 直接更新当前动画配置的FPS值
        # 不依赖于选中的动画项，避免动画名称为空的问题
        if self.current_anim_config:
            # 更新当前运行配置
            self.current_anim_config["fps"] = value
            
            # 更新模型数据中的对应动画
            if self.anim_list.currentItem():
                anim_name = self.anim_list.currentItem().text(0)
                if anim_name and anim_name in self.model.animations:
                    self.model.animations[anim_name]["fps"] = value

            # 关键：如果正在播放，实时调整计时器间隔
            if self.is_playing:
                interval = int(1000 / max(value, 1))
                self.timer.setInterval(interval)

            # 保存模型
            self.model.save()

    def _on_loop_toggled(self, anim_name, button):
        """处理循环状态切换"""
        if not self.model or anim_name not in self.model.animations:
            return

        # 切换循环状态
        current_loop = self.model.animations[anim_name].get("loop", True)
        new_loop = not current_loop

        # 更新模型数据
        self.model.animations[anim_name]["loop"] = new_loop

        # 更新当前运行配置
        if (
            self.current_anim_config
            and self.current_anim_config == self.model.animations[anim_name]
        ):
            self.current_anim_config["loop"] = new_loop

        # 更新UI显示
        loop_icon_path = os.path.join("assets", "icons", "anim_loop.svg")
        loop_off_icon_path = os.path.join("assets", "icons", "anim_loop_off.svg")
        loop_icon = QIcon(loop_icon_path)
        loop_off_icon = QIcon(loop_off_icon_path)

        if new_loop:
            button.setIcon(loop_icon)
            button.setIconSize(QSize(16, 16))
        else:
            button.setIcon(loop_off_icon)
            button.setIconSize(QSize(16, 16))

        # 保存到磁盘
        self.model.save()
        print(f"🔄 [DEBUG] 动画 {anim_name} 的循环状态已切换为: {new_loop}")

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
            # 重新开始播放时，将帧索引重置到起始帧
            start = self.current_anim_config.get("start", 1)
            self.current_frame_index = start
            # 更新预览显示第一帧
            img_path = self.model.get_costume_path(self.current_frame_index)
            if img_path:
                self.update_preview_static(img_path)
            # 启动计时器
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
        loop = self.current_anim_config.get("loop", True)

        # 索引循环逻辑
        if self.current_frame_index >= end:
            if loop:
                self.current_frame_index = start
            else:
                # 非循环模式下保持在最后一帧
                self.current_frame_index = end
                # 停止动画并更新按钮状态
                self.stop_animation()
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
        loop = self.current_anim_config.get("loop", True)

        if self.current_frame_index <= start:
            if loop:
                self.current_frame_index = end
            else:
                # 非循环模式下保持在第一帧
                self.current_frame_index = start
        else:
            self.current_frame_index -= 1

        self._sync_animation_frame()

    def _sync_animation_frame(self):
        """同步帧，并确保索引完全匹配 (1-based to 0-based)"""
        self.ui.sprite_fps_list.blockSignals(True)

        # 获取对应的 List Item
        # 🚀 修正点：current_frame_index(1~N) -> item(index-1)
        target_row = self.current_frame_index - 1
        item = self.ui.sprite_fps_list.item(target_row)

        if item:
            # 直接设置当前行，不再区分sender
            self.ui.sprite_fps_list.setCurrentRow(target_row)
            # 移除滚动功能，保持列表位置不变

        self.ui.sprite_fps_list.blockSignals(False)

    def toggle_preview_scale(self):
        """手动切换缩放状态"""
        # 1. 状态取反
        self.is_original_size = not self.is_original_size

        # 2. 打印 Debug 信息，确保点击生效
        state_str = "原始尺寸" if self.is_original_size else "适配尺寸"
        print(f"🔘 [DEBUG] 缩放按钮点击! 当前模式: {state_str}")

        # 3. 强制触发当前帧重绘
        if self.model and hasattr(self, "current_frame_index"):
            img_path = self.model.get_costume_path(self.current_frame_index)
            if img_path:
                self.update_preview_static(img_path)

    def eventFilter(self, obj, event):
        """事件过滤器：阻止水平滚动但允许选择"""
        try:
            if obj == self.fps_list.viewport():
                if event.type() == QEvent.MouseMove:
                    if event.buttons() & Qt.LeftButton:
                        # 检测是否在进行水平拖拽
                        if hasattr(self, "_last_mouse_pos"):
                            delta_x = abs(event.pos().x() - self._last_mouse_pos.x())
                            delta_y = abs(event.pos().y() - self._last_mouse_pos.y())
                            # 如果水平移动大于垂直移动，阻止水平滚动
                            if delta_x > delta_y and delta_x > 5:
                                return True
                elif event.type() == QEvent.MouseButtonPress:
                    # 记录点击位置
                    self._last_mouse_pos = event.pos()
        except RuntimeError:
            pass
        return super().eventFilter(obj, event)

    def cleanup(self):
        """安全释放资源，防止退出时析构冲突"""
        try:
            # 1. 停止计时器（防止销毁过程中触发刷新）
            if hasattr(self, "timer") and self.timer.isActive():
                self.timer.stop()
                self.timer.blockSignals(True)  # 彻底切断信号

            # 2. 清空场景
            if hasattr(self, "canvas_scene") and self.canvas_scene:
                self.canvas_scene.clear()
                # 解绑场景，防止 QGraphicsView 销毁时去访问已失效的 Python 场景对象
                if hasattr(self, "canvas"):
                    self.canvas.setScene(None)

            # 3. 解除对 UI 的引用，帮助 GC
            self.ui = None
            self.model = None
            print("✅ [DEBUG] SpriteEditorManager 清理完成")
        except Exception as e:
            print(f"❌ [DEBUG] 清理报错: {e}")
