# 测试脚本：验证重力和摄像机跟随修复（带调试信息）
show_fps(True)

# 创建角色
player = Sprite('rockman')
player.set_rotation_mode('left_right')
player.scale = 100
player.play('待机')

# 设置角色初始位置
player.x = 100
player.y = 100

print(f"[DEBUG] 精灵初始位置: ({player.x:.2f}, {player.y:.2f})")

#