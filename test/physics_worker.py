import time
import json
import sys
import arcade

def run_physics():
    # 1. 初始化
    player = arcade.SpriteCircle(15, arcade.color.BLUE)
    player.center_x = 50   # 从左边开始
    player.center_y = 350
    player.change_x = 3    # 🚀 给一个向右的初始速度
    
    walls = arcade.SpriteList()
    # 地板
    ground = arcade.SpriteSolidColor(400, 20, arcade.color.GREEN)
    ground.center_x = 200
    ground.center_y = 50
    walls.append(ground)
    
    physics_engine = arcade.PhysicsEnginePlatformer(player, walls, gravity_constant=0.5)
    
    try:
        while True:
            physics_engine.update()
            
            # 🚀 简单的边界反弹逻辑
            if player.left < 0 or player.right > 400:
                player.change_x *= -1
            
            # 如果掉在地板上不动了，给它一个随机的弹力（可选，模拟交互）
            if player.center_y < 70 and abs(player.change_y) < 0.1:
                player.change_y = 12 # 🚀 落地自动弹起
            
            pos_data = {
                "x": round(player.center_x, 2),
                "y": round(player.center_y, 2)
            }
            
            sys.stdout.write(f"DATA:{json.dumps(pos_data)}\n")
            sys.stdout.flush()
            
            time.sleep(1/60)
    except Exception as e:
        sys.exit(1)

if __name__ == "__main__":
    run_physics()