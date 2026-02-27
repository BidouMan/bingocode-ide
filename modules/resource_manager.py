from PySide6.QtCore import QObject

class ResourceManager(QObject):
    def __init__(self, main_ui):
        super().__init__()
        self.ui = main_ui
        
        # 1. 映射表：将按钮对象与对应的页面对象关联
        self.nav_map = {
            self.ui.btn_outline_code: self.ui.page_1,
            self.ui.btn_outline_sprite: self.ui.page_2,
            self.ui.btn_outline_bg: self.ui.page_3,
            self.ui.btn_outline_sound: self.ui.page_4
        }
        
        # 初始化界面
        self.ui.outline_stracked.setCurrentWidget(self.ui.page_1)

    def bind_switch_page(self):
        """核心优雅点：循环绑定所有导航按钮"""
        for btn in self.nav_map.keys():
            # 使用 btn=btn 捕获当前循环的变量，避免闭包陷阱
            btn.clicked.connect(lambda checked=False, b=btn: self.switch_page(b))

    def switch_page(self, btn):
        """执行切换逻辑"""
        target_page = self.nav_map.get(btn)
        if target_page:
            self.ui.outline_stracked.setCurrentWidget(target_page)
            print(f"ResourceManager: 切换至 {target_page.objectName()}")