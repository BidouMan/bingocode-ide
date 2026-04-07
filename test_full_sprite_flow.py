import sys
import os
import io
import json
from PySide6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene
from PySide6.QtCore import QTimer

# 添加项目根目录到Python路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

print("开始完整流程测试...")

# 先导入bingo_engine和render_manager
try:
    from modules.bingo_engine import Sprite
    print("✅ 成功导入Sprite类")
except Exception as e:
    print(f"❌ 导入Sprite类失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    from modules.render_manager import RenderManager
    print("✅ 成功导入RenderManager类")
except Exception as e:
    print(f"❌ 导入RenderManager类失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

def main():
    print("创建QApplication...")
    app = QApplication([])
    
    print("创建场景和视图...")
    # 创建场景和视图
    scene = QGraphicsScene()
    view = QGraphicsView(scene)
    view.setFixedSize(640, 480)
    
    print("初始化渲染管理器...")
    # 初始化渲染管理器
    render_manager = RenderManager(view, app_controller=None)
    
    print("测试Sprite类和渲染管理器的完整流程...")
    
    # 重定向stdout到缓冲区
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    
    try:
        print("创建Sprite对象...")
        # 创建一个角色
        player = Sprite("hero")
        player.set_xy(320, 240)
        
        # 获取输出
        output = sys.stdout.getvalue()
        print("捕获的输出:")
        print(output)
        
        # 处理输出中的JSON指令
        lines = output.split('\n')
        json_lines = []
        for line in lines:
            line = line.strip()
            if line.startswith('{"type":') and line.endswith('}'):
                json_lines.append(line)
        
        print(f"找到 {len(json_lines)} 条JSON指令")
        for i, line in enumerate(json_lines):
            print(f"处理第 {i+1} 条指令: {line[:100]}...")
            try:
                render_manager.handle_instruction(line)
                print(f"✅ 成功处理指令 {i+1}")
            except Exception as e:
                print(f"❌ 处理指令 {i+1} 失败: {e}")
                import traceback
                traceback.print_exc()
        
        # 显示视图
        print("显示视图...")
        view.show()
        
        # 启动事件循环
        print("启动事件循环...")
        app.exec()
        
    finally:
        sys.stdout = old_stdout

if __name__ == "__main__":
    main()
