from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QSizePolicy

class ScreenManager:
    def __init__(self, app_controller):
        self.ctrl = app_controller
        self.ui = app_controller.ui
        # 严格遵守 640x480 黄金比例
        self.stage_width = 640
        self.stage_height = 480

    def enter_fullscreen(self):
        """进入全屏预览"""
        self.ui.change_page.setCurrentIndex(1)
        
        if self.ui.fullscreen_view_frame.layout():
            layout = self.ui.fullscreen_view_frame.layout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.ui.game_view)
        
        # 🚀 重点：解除编辑模式的小尺寸锁定
        self.ui.game_view.setMinimumSize(0, 0)
        self.ui.game_view.setMaximumSize(16777215, 16777215)
        self.ui.game_view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # 立即计算一次 4:3 比例
        self.apply_ratio_constraint()
        
        # 通知渲染经理对齐场景
        QTimer.singleShot(100, self.ctrl.render_manager.apply_fit)

    def exit_fullscreen(self):
        """退出全屏返回编辑"""
        self.ui.change_page.setCurrentIndex(0)
        
        if self.ui.edit_stage_container.layout():
            self.ui.edit_stage_container.layout().addWidget(self.ui.game_view)
        
        # 🚀 重点：还原编辑模式固定尺寸
        self.ui.game_view.setFixedSize(320, 240)
        
        QTimer.singleShot(50, self.ctrl.render_manager.apply_fit)

    def apply_ratio_constraint(self):
        """锁定比例的核心算法 (断路器逻辑)"""
        # 只有在全屏页才需要计算
        if self.ui.change_page.currentIndex() != 1:
            return

        # 获取当前窗口的实时尺寸
        # 注意：这里直接问 window 要尺寸是最准的
        full_w = self.ctrl.window.width()
        full_h = self.ctrl.window.height()
        
        tool_h = self.ui.fullscreen_tool_bar.height()
        if tool_h <= 0: tool_h = 30 # 容错
        
        available_w = full_w - 40 
        available_h = full_h - tool_h - 20 

        # 计算 4:3 目标尺寸
        target_h = available_h
        target_w = int(target_h * (4 / 3))

        if target_w > available_w:
            target_w = available_w
            target_h = int(target_w * (3 / 4))

        # 限制包装器，防止撑大主窗口
        self.ui.central_stage_wrapper.setMaximumSize(full_w, target_h + tool_h + 20)
        # 强制设置显示区域为 4:3
        self.ui.fullscreen_view_frame.setFixedSize(target_w, target_h)