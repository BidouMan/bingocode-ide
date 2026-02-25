from bingo_engine import *

show_fps(True)

set_background('森林.png')
b = Sprite('hero.png')
b.set_size(30)

b.set_rotation_mode('left_right')
b.angle = 0
b.layer = 2
print(b.layer)

a = Sprite('hero.png')
a.set_rotation_mode('left_right')
a.set_size(40)
a.x = 500
a.y = 320
a.add_to_group('enemy')
a.layer = 1
print(a.layer)

def loop():
    a.look_at(b)    
    a.move(2)
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
    
    dis = a.distance_to(b)
    print(dis)
#     if b.touch_group('enemy'):
#         print('hit')
#         a.delete()
#     if b.is_out_side():
#         print('out')
    
run()
