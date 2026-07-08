from bingo_engine import *

hero = Sprite("洛克人")

while True:
    if key_down('a'):
        hero.move(-5)
    if key_down('d'):
        hero.move(5)
    if key_down('w'):
        hero.jump(10)
