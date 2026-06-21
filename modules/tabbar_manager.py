from PySide6.QtWidgets import QTabBar, QVBoxLayout, QSizePolicy
from PySide6.QtCore import QObject, Signal, Qt, QEvent


class _WheelTabBar(QTabBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._scroll_acc = 0
        self._scroll_threshold = 80

    def wheelEvent(self, event):
        self._scroll_acc += event.angleDelta().y()
        if abs(self._scroll_acc) >= self._scroll_threshold:
            if self._scroll_acc > 0:
                idx = max(0, self.currentIndex() - 1)
            else:
                idx = min(self.count() - 1, self.currentIndex() + 1)
            self.setCurrentIndex(idx)
            self._scroll_acc = 0
        event.accept()


class TabbarManager(QObject):
    tab_changed = Signal(int)

    def __init__(self, container):
        super().__init__()
        self.container = container 
        self.tab_bar = _WheelTabBar()
        self._last_active_index = -1
        self._init_tab_bar()

    def _init_tab_bar(self):
        # 🚀 还原原版配置
        self.tab_bar.setDocumentMode(True)
        self.tab_bar.setExpanding(True)
        self.tab_bar.setElideMode(Qt.TextElideMode.ElideRight)
        self.tab_bar.setObjectName("mainTabBar") # 保持 QSS 兼容
        
        # 🚀 还原布局逻辑：插入到 tab_frame 的最左侧
        self.container.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout = self.container.layout()
        if layout:
            layout.setContentsMargins(0, 0, 0, 0)
            layout.insertWidget(0, self.tab_bar) # 插入到加号按钮前面
            layout.setStretchFactor(self.tab_bar, 1)

        self.tab_bar.currentChanged.connect(self._internal_handle)

    def _internal_handle(self, index):
        self.update_tab_style(index)
        self.tab_changed.emit(index)

    def update_tab_style(self, current_index):
        if self._last_active_index != -1:
            self._set_btn_active(self._last_active_index, False)
        self._set_btn_active(current_index, True)
        self._last_active_index = current_index

    def _set_btn_active(self, index, is_active):
        if 0 <= index < self.tab_bar.count():
            # 原版 QSS 对应的是 RightSide 的关闭/状态按钮
            btn = self.tab_bar.tabButton(index, QTabBar.ButtonPosition.RightSide)
            if btn:
                btn.setProperty("active", "true" if is_active else "false")
                btn.style().unpolish(btn)
                btn.style().polish(btn)