print("Hello World")
import sys
print(f"Python version: {sys.version}")
print(f"sys.path: {sys.path}")

try:
    from modules.bingo_engine import Sprite
    print("Successfully imported Sprite")
except Exception as e:
    print(f"Error importing Sprite: {e}")
    import traceback
    traceback.print_exc()
