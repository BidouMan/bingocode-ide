import sys
import os
import traceback

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    print("Testing Sprite import...")
    from modules.bingo_engine import Sprite
    print("✓ Successfully imported Sprite")
    
    print("Testing Sprite initialization...")
    # 创建一个简单的Sprite实例（需要提供一个文件名）
    sprite = Sprite("test")
    print("✓ Successfully created Sprite instance")
    
    print("All tests passed!")
    
except Exception as e:
    print(f"✗ Error: {e}")
    traceback.print_exc()
