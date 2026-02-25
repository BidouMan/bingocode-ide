from bingo_engine import *

show_fps(True)
b = Sprite('hero.png')
b.set_size(30)

b.set_rotation_mode('left_right')
b.angle = 0
print(11)

a = Sprite('hero.png')
a.set_size(40)

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

    if b.is_touching(a):
        print('hit')

run()
