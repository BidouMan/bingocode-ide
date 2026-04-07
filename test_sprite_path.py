import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from modules.bingo_engine import Sprite

def main():
    print("测试Sprite类图片路径解析...")
    
    # 创建一个角色
    player = Sprite("角色1")
    
    print(f"角色ID: {player.id}")
    print(f"图片路径: {player.image}")
    print(f"图片路径是否存在: {os.path.exists(player.image)}")
    print(f"绝对路径: {os.path.abspath(player.image)}")
    print(f"绝对路径是否存在: {os.path.exists(os.path.abspath(player.image))}")
    
    # 检查assets/sprites目录
    sprites_dir = os.path.join("assets", "sprites")
    print(f"\n检查sprites目录: {sprites_dir}")
    print(f"目录是否存在: {os.path.exists(sprites_dir)}")
    
    if os.path.exists(sprites_dir):
        print("目录内容:")
        for item in os.listdir(sprites_dir):
            print(f"  - {item}")

if __name__ == "__main__":
    main()
