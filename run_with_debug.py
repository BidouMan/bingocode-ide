import sys
import traceback

try:
    print("开始运行程序...")
    import main
    print("程序运行完成")
except Exception as e:
    print(f"捕获到异常: {e}")
    print("异常堆栈:")
    traceback.print_exc()
    sys.exit(1)
