    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 只有在 Page 1 (全屏页) 时才实时重算
        if hasattr(self, 'ui') and self.ui.change_page.currentIndex() == 1:
            if hasattr(self, 'controller'):
                # 此时窗口尺寸已经改变，ref_container.width() 拿到的将是新值
                self.controller.adjust_fullscreen_layout()