import sys
import os
from PySide6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene
from PySide6.QtCore import QTimer

# 添加项目根目录到Python路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from modules.render_manager import RenderManager
from modules.bingo_engine import load_map

def main():
    app = QApplication([])
    
    # 创建场景和视图
    scene = QGraphicsScene()
    view = QGraphicsView(scene)
    view.setFixedSize(640, 480)
    
    # 初始化渲染管理器
    render_manager = RenderManager(view, app_controller=None)
    
    print("测试地图加载功能...")
    
    # 调用load_map函数
    result = load_map('地图1')
    
    print(f"地图加载结果: {result}")
    
    # 显示视图
    view.show()
    
    # 启动事件循环
    app.exec()

if __name__ == "__main__":
    main()
