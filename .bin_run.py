from bingo_engine import *

show_fps(True)

# set_background('森林.png')
b = Sprite('hero.png')
b.set_scale(30)

b.set_rotation_mode('left_right')
b.angle = 0
b.layer = 2
# print(b.layer)

a = Sprite('hero.png')
a.set_rotation_mode('left_right')
a.set_scale(40)
a.x = 500
a.y = 320
a.add_to_group('enemy')
a.layer = 1
# print(a.layer)

def loop():
#     b.say('hello 我是金三胖!')
    
    if mouse_down():
        print(11)
#     else:
#         print(22)
    
#     a.move(2)
#     a.edge_bounce()
    
    a.look_at(b)
    a.move(5)
    
    if a.is_touch(mouse):
        print('碰到鼠标了')
    
    if key_down('a'):
        
        b.angle = 180
        b.move(5)
    elif key_down('d'):
        b.angle = 0
        b.move(5)
    elif key_down('w'):
        b.angle = 270
        b.move(5)
    elif key_down('s'):
        b.angle = 90
        b.move(5)
    
    if key_down('1'):
        b.add_scale(10)
    if key_down('2'):
        b.add_scale(-10)
    
    dis = a.distance_to(b)
#     print(dis)
#     if b.touch_group('enemy'):
#         print('hit')
#         a.delete()
#     if b.is_out_side():
#         print('out')
    
run()
