from bingo_engine import *


b = Sprite('hero.png')


b.set_rotation_mode('left_right')
b.angle = 180
def loop():

    
    if key_down('a'):
        print(11)
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



run()
