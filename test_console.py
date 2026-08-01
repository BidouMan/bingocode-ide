import sys
import os

# 测试1: 检查 stdout 是否可写
print("=== 测试1: stdout 可写性 ===", flush=True)
print(f"stdout encoding: {sys.stdout.encoding}", flush=True)
print(f"stdout isatty: {sys.stdout.isatty()}", flush=True)

# 测试2: input() 提示符
print("=== 测试2: input() 测试 ===", flush=True)
try:
    name = input('输入名字:')
    print(f'你好!{name}', flush=True)
except EOFError:
    print("EOFError: stdin 已关闭", flush=True)
except Exception as e:
    print(f"错误: {e}", flush=True)

# 测试3: 环境变量
print("=== 测试3: 环境变量 ===", flush=True)
print(f"TERM: {os.environ.get('TERM', '未设置')}", flush=True)
print(f"PYTHONUNBUFFERED: {os.environ.get('PYTHONUNBUFFERED', '未设置')}", flush=True)
