
hero =  Sprite("喷火龙")
enemy = Sprite("女忍者")
# enemy.set_x(400)
# enemy.set_y(240)
# enemy.hp = 3
# enemy.add_to_group("enemies")

def damage(bullet, other):
    other.hp -= 1
    bullet.delete()
    # print(f"敌人血量: {other.hp}")
    if other.hp <= 0:
        other.delete()
        print("敌人被击败！")

def loop():
    if key_down('right'):
        hero.add_x(3)
        hero.set_angle(0)
    if key_down('left'):
        hero.add_x(-3)
        hero.set_angle(180)
    if key_down('up'):
        hero.add_y(-3)
        hero.set_angle(270)
    if key_down('down'):
        hero.add_y(3)
        hero.set_angle(90)

    if key_down('space') and wait(0.2):
        bullet = Sprite('林克')
        bullet.goto(hero.x, hero.y)
        bullet.set_angle(hero.angle)
        bullet.set_speed(8)
        bullet.add_to_group("bullets")
        bullet.on_hit("enemies", damage)

run()
