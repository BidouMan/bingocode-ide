将QSS文件也分成全局和多个模组来写
- base.qss: 存放全局变量、基础字体、所有按钮的通用圆角等。
- sidebar.qss: 专门写侧边栏的深色背景、导航按钮的特殊样式。
- editor.qss: 专门写代码编辑区的背景、滚动条样式。
- menu.qss: 专门写你刚做好的下拉菜单样式。

---
在 Python 中合并加载：
```py
def get_combined_style(theme_folder):
    files = ['base.qss', 'sidebar.qss', 'menu.qss']
    style_content = ""
    for f_name in files:
        with open(f"styles/{theme_folder}/{f_name}", "r", encoding="utf-8") as f:
            style_content += f.read() + "\n"
    return style_content

# 使用时
app.setStyleSheet(get_combined_style("dark"))
```

```css
* {
    outline: none; /* 全局去掉焦点虚线 */
}
```
#### 按键绑定切换主题
发送信号
```py
from PySide6.QtCore import Signal, QObject

class NavigationManager:
    # 定义一个信号，传递想切换的主题名称
    theme_requested = Signal(str) 

    def __init__(self, ui_handle):
        self.ui = ui_handle
        # 绑定按钮
        self.ui.btn_theme_toggle.clicked.connect(self.emit_theme_change)

    def emit_theme_change(self):
        # 假设我们点一下切到 light
        self.theme_requested.emit("light")
```
main接受信号后切换主题
```py
class MyIDE(QMainWindow):
    def __init__(self):
        # ... 初始化 UI ...
        self.nav_logic = NavigationManager(self.ui)
        
        # 在这里“接线”：当 nav_logic 发出请求时，执行换肤函数
        self.nav_logic.theme_requested.connect(self.change_app_theme)

    def change_app_theme(self, theme_name):
        style_data = load_stylesheet(f"styles/{theme_name}.qss")
        # 拿到全局 app 实例并修改
        QApplication.instance().setStyleSheet(style_data)
```

```
样式名称,风格类型,视觉特征,推荐场景
one-dark,深色/柔和,著名的 Atom 风格，冷色调，护眼效果极佳,首选，适合长时间编程
nord,深色/北欧,极简的蓝灰色调，色彩优雅且克制,追求桌面美学和一致性
gruvbox-dark,深色/复古,带有黄色调的泥土色，复古胶片感，饱和度舒适,喜欢怀旧、温暖视觉感的开发者
solarized-dark,深色/高对比,基于精准色温设计的青绿色背景，极具辨识度,对色彩准确度和对比度有特殊要求
monokai,深色/高彩,经典的黑色背景 + 霓虹色，Sublime Text 默认色,喜欢高对比度、一眼看清关键字
github-dark,深色/现代,模仿 GitHub 网页端的深色模式，灰度层次分明,习惯 GitHub 网页阅读体验
pastie,浅色/清新,经典的 Ruby 社区风格，背景纯净，色彩明快,制作课件、文档截图，或者白天办公
arduino,混色/特殊,模仿 Arduino IDE 的蓝绿调，非常简洁,适合简单的脚本编写

pip freeze > requirements.txt
pip install -r requirements.txt