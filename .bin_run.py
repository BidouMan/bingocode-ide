from bingo_engine import *

show_fps(True)
b = Sprite('hero.png')


b.set_rotation_mode('left_right')
b.angle = 180
print(11)
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



run()
