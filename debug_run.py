import sys
import traceback

try:
    print("Starting program...")
    exec(open('main.py').read())
except Exception as e:
    print(f"Error: {e}")
    traceback.print_exc()
