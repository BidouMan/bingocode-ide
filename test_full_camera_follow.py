import sys
import os
import threading
import subprocess
from PySide6.QtWidgets import QApplication, QGraphicsView
from PySide6.QtCore import Qt, QTimer

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入模块
from modules.render_manager import RenderManager

def test_full_camera_follow():
    """测试完整的摄像机跟随功能"""
    print("测试完整摄像机跟随功能...")
    
    # 创建Qt应用
    app = QApplication(sys.argv)
    
    # 创建图形视图
    view = QGraphicsView()
    view.setFixedSize(640, 480)
    view.setWindowTitle("摄像机跟随测试")
    
    # 初始化渲染管理器
    render_manager = RenderManager(view)
    
    # 创建一个临时脚本文件来测试摄像机跟随
    temp_script = os.path.join(project_root, ".temp_camera_test.py")
    with open(temp_script, "w", encoding="utf-8") as f:
        f.write("""
import sys
import os
import time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modules.bingo_engine import Sprite, follow, load_map

# 加载地图
load_map('地图1')

# 创建精灵
player = Sprite('洛克人')

# 设置摄像机跟随精灵
follow(player)

# 移动精灵，测试摄像机跟随
positions = [
    (400, 300),
    (500, 200),
    (200, 400),
    (320, 240)
]

for i, (x, y) in enumerate(positions):
    print(f"移动到位置 {i+1}: ({x}, {y})")
    player._x = x
    player._y = y
    player._update_transform()
    time.sleep(1)

print("摄像机跟随测试完成！")
""")
    
    # 启动引擎进程
    print("\n启动引擎进程...")
    engine_process = subprocess.Popen(
        [sys.executable, temp_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    # 读取引擎输出的线程
    def read_engine_output():
        while True:
            line = engine_process.stdout.readline()
            if not line:
                break
            line = line.strip()
            if line:
                try:
                    # 处理渲染指令
                    render_manager.handle_instruction(line)
                except Exception as e:
                    print(f"处理指令失败: {e}")
    
    # 启动输出读取线程
    output_thread = threading.Thread(target=read_engine_output)
    output_thread.daemon = True
    output_thread.start()
    
    # 显示窗口
    view.show()
    
    # 运行Qt事件循环
    sys.exit(app.exec())

if __name__ == "__main__":
    test_full_camera_follow()
