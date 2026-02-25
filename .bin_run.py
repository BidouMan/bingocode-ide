from bingo_engine import *

show_fps(True)
b = Sprite('hero.png')
b.set_size(30)

b.set_rotation_mode('left_right')
b.angle = 45
print(11)
def loop():
    b.move(5)
    b.edge_bounce()
    
#     if key_down('a'):
#         
#         b.angle = 180
#         b.move(5)
#     elif key_down('d'):
#         b.angle = 0
#         b.move(5)
#     elif key_down('w'):
#         b.angle = 270
#         b.move(5)
#     elif key_down('s'):
#         b.angle = 90
#         b.move(5)



run()
