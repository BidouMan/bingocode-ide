import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from modules.bingo_engine import load_map

def main():
    print("测试相机移动和视口裁剪效果...")
    
    # 用户的测试项目工程目录
    project_dir = "/Users/amixc/Desktop/IDEtest/Test/"
    
    print(f"切换到工程目录: {project_dir}")
    
    # 切换到用户的工程目录
    os.chdir(project_dir)
    
    print(f"当前工作目录: {os.getcwd()}")
    
    # 测试地图加载
    result = load_map('地图1')
    
    print(f"地图加载结果: {result}")

if __name__ == "__main__":
    main()
