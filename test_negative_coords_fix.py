# 测试脚本：验证摄像机跟随到负坐标位置
show_fps(True)

# 创建角色
player = Sprite('rockman')
player.set_rotation_mode('left_right')
player.scale = 100
player.play('待机')

# 设置角色初始位置（在地图中间）
player.x = 300
player.y = 100

# 加载地图
load_map('地图2')

# 开启重力
set_gravity(True)

# 设置摄像机跟随角色
follow(player)

# 游戏循环
def loop():
    # 处理角色移动
    if key_down('a'):
        player.set_angle(180)
        player.move(7)
        player.play('跑步')
    if key_down('d'):
        player.set_angle(0)
        player.move(7)
        player.play('跑步')
    if key_down('w'):
        player.jump(12)
    else:
        player.cut_jump()     # 松键截断跳跃
        player.play('待机')

# 运行游戏
run()