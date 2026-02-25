from bingo_engine import *

show_fps(True)
b = Sprite('hero.png')
b.set_size(30)

b.set_rotation_mode('left_right')
b.angle = 0
print(11)

a = Sprite('hero.png')
a.set_size(40)
a.x = 500
a.y = 320
a.add_to_group('enemy')

def loop():
        
    
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

    if b.touch_group('enemy'):
        print('hit')
        a.delete()
run()
