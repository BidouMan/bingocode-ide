import sys
import os
from PySide6.QtWidgets import QApplication, QGraphicsView, QGraphicsScene
from PySide6.QtCore import QTimer

# 添加项目根目录到Python路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

print("开始测试...")

try:
    from modules.render_manager import RenderManager
    print("✅ 成功导入RenderManager")
except Exception as e:
    print(f"❌ 导入RenderManager失败: {e}")
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
    
    print("测试渲染管理器直接调用create_sprite方法...")
    
    # 直接调用create_sprite方法
    sprite_id = "test_hero"
    image_path = "assets/sprites/hero/hero_000.png"
    
    print(f"图片路径: {image_path}")
    print(f"绝对路径: {os.path.abspath(image_path)}")
    print(f"图片是否存在: {os.path.exists(os.path.abspath(image_path))}")
    
    data = {
        "image": image_path,
        "x": 320,
        "y": 240,
        "angle": 0,
        "scale": 1.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
        "type": "image"
    }
    
    try:
        print("调用create_sprite方法...")
        render_manager.create_sprite(sprite_id, data)
        print("✅ 成功创建精灵")
    except Exception as e:
        print(f"❌ 创建精灵失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 显示视图
    print("显示视图...")
    view.show()
    
    # 启动事件循环
    print("启动事件循环...")
    app.exec()

if __name__ == "__main__":
    main()
