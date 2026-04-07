import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, '/Volumes/WorkStation/MyWork/CodeStation/MyIDE')

from modules.bingo_engine import Sprite

def main():
    print("测试Sprite类图片路径解析...")
    
    # 创建一个角色
    player = Sprite("hero")
    
    print(f"角色ID: {player.id}")
    print(f"图片路径: {player.image}")
    print(f"图片路径是否存在: {os.path.exists(player.image)}")
    print(f"绝对路径: {os.path.abspath(player.image)}")
    print(f"绝对路径是否存在: {os.path.exists(os.path.abspath(player.image))}")
    
    # 检查图片是否能被PIL打开
    try:
        from PIL import Image
        img = Image.open(player.image)
        print(f"图片尺寸: {img.size}")
        print(f"图片格式: {img.format}")
        print("✅ 图片可以正常打开")
    except Exception as e:
        print(f"❌ 图片打开失败: {e}")

if __name__ == "__main__":
    main()
