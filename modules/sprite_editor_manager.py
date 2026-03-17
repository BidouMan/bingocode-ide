import os
import json
from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QGraphicsScene, QTreeWidgetItem
from models.sprite_model import SpriteDataModel

class SpriteEditorManager(QObject):
    def __init__(self, ui_form):
        super().__init__()
        print("🔍 [DEBUG] SpriteEditorManager: 正在初始化...")
        self.ui = ui_form
        self.model = None
        self.current_project_path = ""

        # UI 组件引用
        self.fps_list = self.ui.sprite_fps_list
        self.canvas = self.ui.sprite_canvas       # QGraphicsView
        self.preview = self.ui.animate_preview     # QLabel
        self.anim_list = self.ui.animate_list      # QTreeWidget

        # 初始化画布场景
        self.canvas_scene = QGraphicsScene()
        self.canvas.setScene(self.canvas_scene)

        # 信号绑定
        self._setup_connections()
        print("🔍 [DEBUG] SpriteEditorManager: 初始化完成，信号已绑定")

    def _setup_connections(self):
        """绑定 UI 原始信号"""
        # 点击左侧列表项切换
        self.fps_list.currentRowChanged.connect(self._on_costume_selection_changed)

    def load_sprite(self, project_path):
        """
        核心入口：由 AppController 触发
        """
        print(f"🚀 [DEBUG] SpriteEditorManager: 收到加载请求 -> {project_path}")
        
        if not project_path or not os.path.exists(project_path):
            print(f"❌ [DEBUG] SpriteEditorManager: 路径无效或不存在: {project_path}")
            return

        self.current_project_path = project_path
        
        try:
            # 实例化模型
            self.model = SpriteDataModel(project_path)
            print(f"📊 [DEBUG] Model 数据: 造型={len(self.model.costumes)}个, 动画={len(self.model.animations)}个")
            
            # 绑定模型变更信号
            self.model.data_changed.connect(self.refresh_all_ui)
            
            # 强制刷新全界面
            self.refresh_all_ui("ALL")
            
        except Exception as e:
            print(f"❌ [DEBUG] SpriteEditorManager: 加载模型崩溃: {e}")
            import traceback
            traceback.print_exc()

    def refresh_all_ui(self, change_type, detail=None):
        """根据模型信号，分发刷新任务"""
        print(f"🔄 [DEBUG] SpriteEditorManager: 刷新 UI (Type: {change_type})")
        
        if change_type in ["ALL", "COSTUME"]:
            self._update_fps_list()
        
        if change_type in ["ALL", "ANIMATION"]:
            self._update_animation_list()

    def _update_fps_list(self):
        """刷新左侧造型列表"""
        print("📝 [DEBUG] SpriteEditorManager: 正在填充造型列表...")
        self.fps_list.blockSignals(True)
        self.fps_list.clear()
        
        for i, filename in enumerate(self.model.costumes):
            # 1-Base 显示：1: walk.png
            self.fps_list.addItem(f"{i + 1}: {filename}")
            
        self.fps_list.blockSignals(False)
        print(f"✅ [DEBUG] SpriteEditorManager: 列表填充完毕 (项数: {self.fps_list.count()})")

        # 自动选中第一项
        if self.fps_list.count() > 0:
            self.fps_list.setCurrentRow(0)
            self._on_costume_selection_changed(0)

    def _update_animation_list(self):
        """刷新右下角动作列表"""
        print("🌳 [DEBUG] SpriteEditorManager: 正在刷新动作树...")
        self.anim_list.clear()
        if not self.model: return
        
        for name, config in self.model.animations.items():
            item = QTreeWidgetItem(self.anim_list)
            item.setText(0, name)
            item.setText(1, f"{config.get('start', 1)}-{config.get('end', 1)}")
        print("✅ [DEBUG] SpriteEditorManager: 动作树刷新完毕")

    def _on_costume_selection_changed(self, row):
        """列表点选联动"""
        if row < 0 or not self.model:
            return
            
        print(f"🖱️ [DEBUG] SpriteEditorManager: 选中行 {row}")
        
        # 转换 1-Base 获取路径
        img_path = self.model.get_costume_path(row + 1)
        
        if img_path and os.path.exists(img_path):
            self.display_on_canvas(img_path)
            self.update_preview_static(img_path)
        else:
            print(f"⚠️ [DEBUG] SpriteEditorManager: 找不到图片文件: {img_path}")

    def display_on_canvas(self, path):
        """中间画布显示"""
        pix = QPixmap(path)
        if pix.isNull():
            print(f"❌ [DEBUG] SpriteEditorManager: QPixmap 无法加载: {path}")
            return
            
        self.canvas_scene.clear()
        # 🚀 关键：创建 PixmapItem 并获取它
        pix_item = self.canvas_scene.addPixmap(pix)
        
        # 🚀 设置场景边界为图片大小，并重置 View 的视图
        self.canvas_scene.setSceneRect(pix.rect())
        self.canvas.centerOn(pix_item) 
        
        print(f"🎨 [DEBUG] 画布已更新，图片尺寸: {pix.width()}x{pix.height()}")

    def update_preview_static(self, path):
        """右上角预览窗显示"""
        pix = QPixmap(path)
        if not pix.isNull():
            # 缩放以适应 QLabel 大小
            scaled_pix = pix.scaled(
                self.preview.size(), 
                Qt.AspectRatioMode.KeepAspectRatio, 
                Qt.TransformationMode.SmoothTransformation
            )
            self.preview.setPixmap(scaled_pix)
            self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)