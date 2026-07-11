<script setup lang="ts">
import { ref, computed, nextTick } from 'vue'
import iconRightArrow from '../../assets/icons/right_arrow.svg'
import iconDownArrow from '../../assets/icons/down_arrow.svg'

defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: [] }>()

const expandedCards = ref<Record<string, boolean>>({})
const activeCategory = ref(0)
const searchQuery = ref('')

function toggleCard(ci: number, fi: number) {
  const key = `${ci}-${fi}`
  expandedCards.value[key] = !expandedCards.value[key]
}

function scrollToCategory(index: number) {
  activeCategory.value = index
  nextTick(() => {
    document.getElementById(`help-cat-${index}`)?.scrollIntoView()
  })
}

const categories = [
  // ════════ 精灵 ════════
  {
    name: '精灵',
    color: '#59C759',
    funcs: [
      { label: 'Sprite 创建角色', code: 'hero = Sprite("洛克人")', desc: '创建一个角色并让它出现在画面上。括号里写角色资源的名字。角色一开始出现在画面正中间。', badgeType: 'module' },
      { label: 'delete 删除角色', code: 'hero.delete()', desc: '把这个角色从画面上彻底删掉。删掉之后就不能再用了，如果还想用就重新创建一个。', badgeType: 'object' },
      { label: 'x 角色的左右位置', code: 'hero.x = 100\nprint(hero.x)', desc: '角色在画面上的左右位置。左边是 0，右边是 640。可以直接赋值改位置，也可以读取当前值。', badgeType: 'property' },
      { label: 'y 角色的上下位置', code: 'hero.y = 200\nprint(hero.y)', desc: '角色在画面上的上下位置。上面是 0，下面是 480。', badgeType: 'property' },
      { label: 'scale 角色的大小', code: 'hero.scale = 200\nprint(hero.scale)', desc: '角色的大小，用百分比表示。100 是正常大小，200 是两倍大，50 是一半大。', badgeType: 'property' },
      { label: 'angle 角色的朝向', code: 'hero.angle = 90\nprint(hero.angle)', desc: '角色面朝的方向。0 = 朝右，90 = 朝下，180 = 朝左，270 = 朝上。', badgeType: 'property' },
      { label: 'layer 角色的层级', code: 'hero.layer = 10', desc: '角色在画面上的前后顺序。数字越大越在前面，数字越小越在后面。默认是 1000。', badgeType: 'property' },
      { label: 'on_ground 是否在地面', code: 'if hero.on_ground:\n    hero.jump()', desc: '角色是不是踩在地上。站在地上是 True，悬在空中是 False。可以用 if 来判断能不能跳。', badgeType: 'property' },
      { label: 'vy 垂直速度', code: 'print(hero.vy)', desc: '角色在上下方向的速度。往上飞时是负数，往下落时是正数，静止时是 0。', badgeType: 'property' },
    ],
  },
  // ════════ 运动 ════════
  {
    name: '运动',
    color: '#4C97FF',
    funcs: [
      { label: 'goto 传送到某个位置', code: 'hero.goto(100, 200)', desc: '让角色瞬间传送到画面的某个位置。x 是左右方向（0~640），y 是上下方向（0~480）。', badgeType: 'object' },
      { label: 'move 朝前走', code: 'hero.move(5)', desc: '让角色朝着它面朝的方向走几步。比如 move(5) 就往前走 5 步。走的时候会自动避开墙壁。', badgeType: 'object' },
      { label: 'jump 跳起来', code: 'if hero.on_ground:\n    hero.jump(12)', desc: '让角色跳起来！数字越大跳得越高，默认是 10。jump 只是施加向上的力，需要自己用 on_ground 判断是否在地面。', badgeType: 'object' },
      { label: 'cut_jump 提前落地', code: 'if key_pressed("space") and hero.on_ground:\n    hero.jump(10)\nif key_up("space"):\n    hero.cut_jump()', desc: '松手的时候调用，角色会提前下落。按住跳键跳得高，松手就落下来，这样你就能控制跳多高。', badgeType: 'object' },
      { label: 'drop_through 穿过跳板', code: 'hero.drop_through()', desc: '让角色穿过脚下的跳板掉下去。站在跳板上时按向下键就能穿过去。', badgeType: 'object' },
      { label: 'add_x 向右走', code: 'hero.add_x(5)', desc: '让角色向右走几步。写负数就向左走，比如 add_x(-5) 向左走 5 步。', badgeType: 'object' },
      { label: 'add_y 向下走', code: 'hero.add_y(5)', desc: '让角色向下走几步。写负数就向上走。', badgeType: 'object' },
      { label: 'set_x 直接改横坐标', code: 'hero.set_x(300)', desc: '直接设置角色在左右方向的位置，会自动检测碰撞。', badgeType: 'object' },
      { label: 'set_y 直接改纵坐标', code: 'hero.set_y(200)', desc: '直接设置角色在上下方向的位置，会自动检测碰撞。', badgeType: 'object' },
      { label: 'set_angle 改变朝向', code: 'hero.set_angle(180)', desc: '改变角色面朝的方向。0 = 朝右，90 = 朝下，180 = 朝左，270 = 朝上。', badgeType: 'object' },
      { label: 'look_at 看向目标', code: 'hero.look_at(mouse)', desc: '让角色自动转头看向另一个角色或者鼠标。比如 player.look_at(mouse) 会让角色一直看着鼠标。', badgeType: 'object' },
      { label: 'set_speed 持续移动', code: 'hero.set_speed(3)', desc: '设置角色的持续移动速度。之后角色会自动一直朝当前方向走。写 0 就停下来。', badgeType: 'object' },
      { label: 'edge_bounce 碰边反弹', code: 'hero.edge_bounce()', desc: '角色碰到画面边缘会自动弹回来，就像弹力球撞墙一样。', badgeType: 'object' },
      { label: 'goto_rand 传送到随机位置', code: 'hero.goto_rand()', desc: '让角色随机传送到画面上的某个位置。', badgeType: 'object' },
    ],
  },
  // ════════ 外观 ════════
  {
    name: '外观',
    color: '#9966FF',
    funcs: [
      { label: 'show 显示', code: 'hero.show()', desc: '让角色显示出来。', badgeType: 'object' },
      { label: 'hide 隐藏', code: 'hero.hide()', desc: '把角色藏起来。藏起来不代表删除了，还可以再 show 出来。', badgeType: 'object' },
      { label: 'say 说话', code: 'hero.say("你好！")\nhero.say("得分！", 2)', desc: '让角色头顶出现一个对话气泡。不写时间就一直显示，写上时间（秒）就到时间自动消失。', badgeType: 'object' },
      { label: 'set_scale 改变大小', code: 'hero.set_scale(150)', desc: '把角色变大或变小。100 是正常大小，200 是两倍大，50 是一半大。', badgeType: 'object' },
      { label: 'add_scale 加大/缩小', code: 'hero.add_scale(20)', desc: '在当前大小基础上变大或缩小。写正数变大，写负数变小。比如 add_scale(20) 就在当前基础上再大 20%。', badgeType: 'object' },
      { label: 'set_rotation_mode 旋转方式', code: 'hero.set_rotation_mode("left_right")', desc: '改变角色的旋转方式。"all" = 任意旋转（默认），"left_right" = 只左右翻转不旋转图片，"none" = 完全不旋转。', badgeType: 'object' },
      { label: 'play 播放动画', code: 'hero.play("walk")', desc: '让角色开始播放某个动画，比如走路、跑步、攻击等。需要角色资源里提前做好动画才行。', badgeType: 'object' },
    ],
  },
  // ════════ 侦测 ════════
  {
    name: '侦测',
    color: '#4CBFE6',
    funcs: [
      { label: 'is_touch 碰到了吗', code: 'hero.is_touch(enemy)\nhero.is_touch(mouse)\nhero.is_touch("地面")', desc: '检查角色有没有碰到某个东西。可以碰另一个角色、碰鼠标，或者碰有标签的地形。碰到了返回 True。', badgeType: 'object' },
      { label: 'is_touch_edge 碰到边框了吗', code: 'hero.is_touch_edge()', desc: '检查角色有没有碰到画面的边框（640×480）。只要有一边碰到就返回 True。', badgeType: 'object' },
      { label: 'is_out_side 完全出去了吗', code: 'hero.is_out_side()', desc: '检查角色是不是整个都跑到画面外面去了。只有一点点出去不算，要整个都出去才返回 True。', badgeType: 'object' },
      { label: 'distance_to 距离多远', code: 'hero.distance_to(enemy)\nhero.distance_to(mouse)', desc: '算出角色到另一个角色（或者鼠标）有多远。数字越大距离越远。', badgeType: 'object' },
      { label: 'touch_group 碰到组了吗', code: 'bullet.touch_group("enemies")', desc: '检查子弹有没有碰到"enemies"组里的任何一个角色。碰到了就返回那个角色，没碰到返回 None。', badgeType: 'object' },
      { label: 'is_on_floor 脚下有地面吗', code: 'hero.is_on_floor()', desc: '检查角色脚底下有没有带碰撞的地形。和 on_ground 类似，但更精准。', badgeType: 'object' },
      { label: 'key_down 按键按住了吗', code: 'key_down("space")\nkey_down("up")\nkey_down("a")', desc: '检查某个键是不是正在被按住。键名用小写英文字母，方向键写 "up" "down" "left" "right"。', badgeType: 'function' },
      { label: 'key_pressed 刚刚按下了吗', code: 'key_pressed("space")', desc: '只在按下那一瞬间返回 True。适合做"按一下就跳"这种事。', badgeType: 'function' },
      { label: 'mouse_down 鼠标按住了吗', code: 'mouse_down()', desc: '检查鼠标左键是不是正在被按住。按住的时候一直返回 True。', badgeType: 'function' },
      { label: 'mouse_pressed 刚刚点了吗', code: 'mouse_pressed()', desc: '只在鼠标点击那一瞬间返回 True。适合做"点一下就开枪"这种事。', badgeType: 'function' },
      { label: 'mouse.x 鼠标横坐标', code: 'print(mouse.x)', desc: '获取鼠标指针在画面上的左右位置。画面左边是 0，右边是 640。', badgeType: 'property' },
      { label: 'mouse.y 鼠标纵坐标', code: 'print(mouse.y)', desc: '获取鼠标指针在画面上的上下位置。画面上边是 0，下边是 480。', badgeType: 'property' },
    ],
  },
  // ════════ 控制 ════════
  {
    name: '控制',
    color: '#FFAB19',
    funcs: [
      { label: 'while True 主循环', code: 'while True:\n    if key_down("right"):\n        hero.move(3)', desc: '这是游戏的核心！用 while True 不断重复执行游戏逻辑，游戏就是这样"跑"起来的。', badgeType: 'function' },
      { label: 'pause 暂停游戏', code: 'pause()', desc: '把游戏暂停。所有角色都停下来不动了，但是程序还在跑，可以随时 resume。', badgeType: 'function' },
      { label: 'resume 继续游戏', code: 'resume()', desc: '让暂停的游戏重新动起来。', badgeType: 'function' },
      { label: 'is_paused 暂停了吗', code: 'if is_paused():\n    resume()', desc: '检查游戏是不是暂停了。暂停了返回 True，正在玩返回 False。', badgeType: 'function' },
      { label: 'stop 结束游戏', code: 'stop()', desc: '结束游戏。游戏画面停住，程序退出 run 循环。可以用在"游戏结束"或者"通关"的时候。', badgeType: 'function' },
      { label: 'on_hit 注册碰撞回调', code: 'bullet.on_hit("enemies",\n    lambda b, e: (b.delete(), e.delete()))', desc: '当角色碰到某个组里的成员时，自动执行你写的代码。比如子弹碰到敌人，两者都消失。', badgeType: 'object' },
      { label: 'add_to_group 加入组', code: 'enemy.add_to_group("enemies")', desc: '把角色归到某个组里，方便批量管理。比如把所有敌人都放到 "enemies" 组。', badgeType: 'object' },
      { label: 'broadcast 发广播', code: 'broadcast("开始游戏")', desc: '发一条广播消息，就像学校广播站喊话。所有"听到"这条消息的角色都会执行对应的行动。', badgeType: 'function' },
      { label: 'receive 接收广播', code: 'receive("开始游戏",\n    lambda: hero.show())', desc: '注册一个"广播接收器"。当收到指定的广播时，就执行你写好的那段代码。记得要在发广播之前注册好。', badgeType: 'function' },
    ],
  },
  // ════════ 声音 ════════
  {
    name: '声音',
    color: '#D65CD6',
    funcs: [
      { label: 'play_sound 播放音效', code: 'play_sound("jump")\nplay_sound("bgm", True)', desc: '播放一段音效。写上音效文件的名字（不用带后缀）。第二个参数写 True 就一直循环，比如背景音乐。', badgeType: 'function' },
      { label: 'stop_sound 停止音效', code: 'stop_sound("jump")\nstop_sound()', desc: '停掉正在播放的音效。写上名字就停那个，不写名字就全部停掉。', badgeType: 'function' },
    ],
  },
  // ════════ 地图 ════════
  {
    name: '地图',
    color: '#2ECC71',
    funcs: [
      { label: 'load_map 加载地图', code: 'load_map("我的地图")', desc: '把一张地图显示在画面上。地图需要先在左边的资源管理器里添加好，然后写上名字就行。', badgeType: 'function' },
      { label: 'follow 镜头跟随', code: 'follow(hero)', desc: '让摄像机（画面的"眼睛"）跟着某个角色移动。用了之后画面就会跟着角色走。', badgeType: 'function' },
    ],
  },
  // ════════ 运算 ════════
  {
    name: '运算',
    color: '#59C759',
    funcs: [
      { label: 'random_int 随机整数', code: 'random_int(1, 6)', desc: '随机生成一个整数（没有小数点的数）。random_int(1, 6) 就像掷骰子，可能返回 1~6 中的任意一个。', badgeType: 'function' },
      { label: 'random_float 随机小数', code: 'random_float(0, 1)', desc: '随机生成一个小数。random_float(0, 1) 会返回 0 到 1 之间的某个小数。', badgeType: 'function' },
    ],
  },
  // ════════ 工具 ════════
  {
    name: '工具',
    color: '#FF8C1A',
    funcs: [
      { label: 'draw_text 在画面上写字', code: 'draw_text(100, 50, "得分：", score)', desc: '在画面指定位置显示文字。所有参数会自动拼在一起。比如 draw_text(100, 50, "得分：", score) 就会在 (100, 50) 的位置显示"得分：XX"。', badgeType: 'function' },
      { label: 'shake 画面震动', code: 'shake(8, 0.5)', desc: '让画面抖一抖！第一个数字是强度（越大越厉害），第二个是秒数（抖多久）。可以用在角色被撞到的时候。', badgeType: 'function' },
      { label: 'show_fps 显示帧率', code: 'show_fps(True)', desc: '在画面上显示游戏运行速度（每秒画面刷新多少次）。True 显示，False 隐藏。用来检查游戏跑得流不流畅。', badgeType: 'function' },
      { label: 'show_collision 显示碰撞范围', code: 'show_collision(hero)', desc: '把角色的碰撞范围画出来（一个彩色框框），方便检查碰撞检测有没有弄对。', badgeType: 'function' },
      { label: 'Timer 创建计时器', code: 'clock = Timer(2)\nif clock.is_timeout():\n    print("时间到！")', desc: '创建一个计时器，每隔几秒提醒你一次。Timer(2) 就是每 2 秒提醒一次。第二个参数写 True（默认）一直重复，写 False 只提醒一次。', badgeType: 'module' },
      { label: 'is_timeout 时间到了吗', code: 'if clock.is_timeout():\n    print("时间到")', desc: '检查计时器的时间到了没。到了就返回 True。通常在 run() 里面用 if 来判断。', badgeType: 'object' },
      { label: 'wait 每隔几秒', code: 'if wait(1):\n    print("过了一秒")', desc: '每隔指定的时间返回一次 True。比如 wait(1) 每隔 1 秒返回 True，可以用它来做定时的事情。', badgeType: 'function' },
    ],
  },
]

function getBadgeColor(type?: string) {
  switch (type) {
    case 'module': return '#4C97FF'
    case 'object': return '#59C759'
    case 'property': return '#FF8C1A'
    case 'function': return '#9966FF'
    default: return '#9966FF'
  }
}

const filteredCategories = computed(() => {
  if (!searchQuery.value.trim()) return categories

  const query = searchQuery.value.toLowerCase()
  return categories
    .map(cat => ({
      ...cat,
      funcs: cat.funcs.filter(
        f =>
          f.label.toLowerCase().includes(query) ||
          f.desc.toLowerCase().includes(query) ||
          f.code.toLowerCase().includes(query)
      ),
    }))
    .filter(cat => cat.funcs.length > 0)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="help-slide">
      <div v-if="visible" class="help-overlay" @click.self="emit('close')">
        <div class="help-panel">
          <!-- 标题栏 -->
          <div class="help-header">
            <div class="help-title-row">
              <img src="../../assets/icons/help.svg" class="help-header-icon" />
              <span class="help-title">API 帮助文档</span>
            </div>
            <button class="help-close-btn" @click="emit('close')">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M1 1L13 13M13 1L1 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <!-- 搜索框 -->
          <div class="help-search">
            <div class="help-search-box">
              <svg class="help-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
              </svg>
              <input
                v-model="searchQuery"
                type="text"
                class="help-search-input"
                placeholder="搜索 API、函数、属性..."
              />
              <button v-if="searchQuery" class="help-search-clear" @click="searchQuery = ''">
                <svg width="12" height="12" viewBox="0 0 14 14" fill="none">
                  <path d="M1 1L13 13M13 1L1 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
              </button>
            </div>
          </div>

          <!-- 主体：左侧分类 + 右侧内容 -->
          <div class="help-body">
            <!-- 左侧分类栏 -->
            <div class="help-sidebar">
              <button
                v-for="(cat, ci) in filteredCategories"
                :key="ci"
                class="help-sidebar-btn"
                :class="{ 'help-sidebar-btn-active': activeCategory === ci }"
                :style="{
                  borderLeftColor: activeCategory === ci ? cat.color : 'transparent',
                }"
                @click="scrollToCategory(ci)"
              >
                <span class="help-sidebar-dot" :style="{ background: cat.color }"></span>
                <span class="help-sidebar-name" :style="{ color: activeCategory === ci ? cat.color : '' }">{{ cat.name }}</span>
              </button>
            </div>

            <!-- 右侧内容 -->
            <div class="help-content">
              <div
                v-for="(cat, ci) in filteredCategories"
                :key="ci"
                :id="`help-cat-${ci}`"
                class="help-category-section"
              >
                <div class="help-category-header">
                  <span class="help-category-name" :style="{ color: cat.color }">{{ cat.name }}</span>
                  <div class="help-category-line" :style="{ background: cat.color }"></div>
                </div>

                <div class="help-card-list">
                  <div
                    v-for="(func, fi) in cat.funcs"
                    :key="fi"
                    class="help-func-card"
                    :class="{ 'help-func-card-expanded': expandedCards[`${ci}-${fi}`] }"
                  >
                    <button class="help-func-header" @click="toggleCard(ci, fi)">
                      <img
                        :src="expandedCards[`${ci}-${fi}`] ? iconDownArrow : iconRightArrow"
                        class="help-arrow-icon"
                      />
                      <span class="help-func-dot" :style="{ background: getBadgeColor(func.badgeType) }"></span>
                      <span class="help-func-label">{{ func.label }}</span>
                    </button>
                    <div v-if="expandedCards[`${ci}-${fi}`]" class="help-func-body">
                      <div class="help-func-code">
                        <code>{{ func.code }}</code>
                      </div>
                      <div class="help-func-desc">{{ func.desc }}</div>
                    </div>
                  </div>
                </div>
              </div>

              <!-- 无搜索结果 -->
              <div v-if="filteredCategories.length === 0" class="help-empty">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5">
                  <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
                </svg>
                <span>没有找到匹配的内容</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.help-slide-enter-active,
.help-slide-leave-active { transition: opacity 0.25s ease; }
.help-slide-enter-active .help-panel,
.help-slide-leave-active .help-panel { transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.help-slide-enter-from,
.help-slide-leave-to { opacity: 0; }
.help-slide-enter-from .help-panel,
.help-slide-leave-to .help-panel { transform: translateX(100%); }

.help-overlay {
  position: fixed; inset: 0; z-index: 9000;
  display: flex; justify-content: flex-end;
  background: rgba(0, 0, 0, 0.3);
}

.help-panel {
  width: 340px; max-width: 90vw; height: 100%;
  display: flex; flex-direction: column;
  background: var(--bg-root);
  border-left: 1px solid var(--border);
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.4);
}

/* ── 标题栏 ── */
.help-header {
  display: flex; align-items: center; justify-content: space-between;
  height: 40px; min-height: 40px; padding: 0 16px;
  border-bottom: 1px solid var(--border);
}
.help-title-row { display: flex; align-items: center; gap: 8px; }
.help-header-icon { width: 20px; height: 20px; }
.help-title { font-size: 14px; font-weight: 600; color: white; }
.help-close-btn {
  display: flex; align-items: center; justify-content: center;
  width: 28px; height: 28px;
  background: transparent; border: none; border-radius: 4px;
  color: var(--text-secondary); cursor: pointer; transition: all 0.15s;
}
.help-close-btn:hover {   background: var(--bg-hover); color: white; }

/* ── 搜索框 ── */
.help-search {
  padding: 8px 12px; border-bottom: 1px solid var(--border);
}
.help-search-box {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px;
  background: var(--bg-hover);
  border-radius: 6px; border: 1px solid var(--border-light);
}
.help-search-icon { color: var(--text-muted); flex-shrink: 0; }
.help-search-input {
  flex: 1; background: transparent; border: none; outline: none;
  font-size: 13px; color: white;
}
.help-search-input::placeholder { color: var(--text-muted); }
.help-search-clear {
  display: flex; align-items: center; justify-content: center;
  width: 20px; height: 20px; padding: 0;
  background: transparent; border: none; border-radius: 3px;
  color: var(--text-muted); cursor: pointer; transition: all 0.15s;
}
.help-search-clear:hover { background: rgba(255,255,255,0.1); color: white; }

/* ── 主体布局 ── */
.help-body {
  flex: 1; min-height: 0; overflow: hidden;
  display: flex;
}

/* ── 左侧分类栏 ── */
.help-sidebar {
  width: 40px; min-width: 40px;
  display: flex; flex-direction: column;
  border-right: 1px solid var(--border);
  overflow-y: auto; padding: 0;
}
.help-sidebar::-webkit-scrollbar { display: none; }

.help-sidebar-btn {
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 4px;
  height: 50px; min-height: 50px;
  background: transparent;
  border: none; border-left: 3px solid transparent;
  cursor: pointer; transition: all 0.15s;
  padding: 0;
}
.help-sidebar-btn:hover { background: rgba(255, 255, 255, 0.04); }
.help-sidebar-btn-active { background: rgba(255, 255, 255, 0.06); }

.help-sidebar-dot {
  width: 10px; height: 10px; min-width: 10px; min-height: 10px;
  border-radius: 50%;
}
.help-sidebar-name {
  font-size: 11px; color: rgb(140, 140, 140);
  line-height: 1; white-space: nowrap;
}
.help-sidebar-btn-active .help-sidebar-name { font-weight: 600; }

/* ── 内容滚动区 ── */
.help-content {
  flex: 1; min-height: 0; overflow-y: auto; padding: 12px 16px 0;
}
.help-content::after {
  content: '';
  display: block;
  height: 50vh;
}
.help-content::-webkit-scrollbar { width: 6px; }
.help-content::-webkit-scrollbar-track { background: transparent; }
.help-content::-webkit-scrollbar-thumb { background: rgb(60, 63, 70); border-radius: 3px; }

/* ── 分类区块 ── */
.help-category-section { margin-bottom: 24px; }
.help-category-section:last-child { margin-bottom: 0; }
.help-category-header {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 10px; padding: 4px 0;
}
.help-category-name { font-size: 14px; font-weight: 700; white-space: nowrap; }
.help-category-line { flex: 1; height: 2px; border-radius: 1px; opacity: 0.3; }

/* ── 卡片列表 ── */
.help-card-list { display: flex; flex-direction: column; gap: 3px; }

.help-func-card {
  border-radius: 8px; border: 1px solid var(--border-light);
  background: transparent; overflow: hidden; transition: background 0.12s;
}
.help-func-card:hover { background: rgba(255, 255, 255, 0.04); }
.help-func-card-expanded { background: rgba(255, 255, 255, 0.06); }

.help-func-header {
  display: flex; align-items: center; gap: 8px;
  width: 100%; padding: 8px 12px;
  background: transparent; border: none;
  color: white; cursor: pointer; text-align: left;
}
.help-func-header:hover { background: rgba(255, 255, 255, 0.03); }

.help-arrow-icon { width: 14px; height: 14px; flex-shrink: 0; opacity: 0.5; }

.help-func-dot {
  width: 8px; height: 8px; min-width: 8px;
  border-radius: 50%; flex-shrink: 0;
}

.help-func-label {
  font-size: 13px; color: rgb(230, 230, 230);
  font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
}

/* ── 展开内容 ── */
.help-func-body { padding: 0 12px 10px 34px; }

.help-func-code {
  margin-bottom: 6px; padding: 6px 10px;
  background: rgb(28, 28, 32);
  border-radius: 6px; border: 1px solid var(--border-light);
  overflow-x: auto;
}
.help-func-code::-webkit-scrollbar { height: 4px; }
.help-func-code::-webkit-scrollbar-track { background: transparent; }
.help-func-code::-webkit-scrollbar-thumb { background: rgb(60, 63, 70); border-radius: 2px; }
.help-func-code code {
  font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
  font-size: 12px; color: rgb(156, 227, 170);
  white-space: pre; user-select: all;
}

.help-func-desc {
  font-size: 12.5px; line-height: 1.7;
  color: rgb(180, 180, 180);
}

/* ── 空状态 ── */
.help-empty {
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 12px; padding: 60px 20px;
  color: var(--text-muted); font-size: 13px;
}
</style>
