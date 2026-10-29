"""Sprite 主类：构造、公开 API（移动/跳/跟随/分组/朝向/显隐/属性）、
子模块 Mixin 组装。

什么时候来这里改：新增/修改给用户调用的角色方法、属性读写、Sprite 与引擎的粘合。
碰撞解算在 sprite_physics.py，素材/碰撞盒装载在 sprite_assets.py，动画/说话在 sprite_animation.py。"""
import json
import math
import os
import random
from models.coords import to_user_angle, to_user_dy, to_user_x, to_user_y, to_world_angle, to_world_dx, to_world_dy, to_world_x, to_world_y
from collision_geometry import _playable_bounds
from game_control import broadcast, receive, stop
from input_api import mouse
from markers import MapMarkerRef, _MarkerRef
from sprite_animation import SpriteAnimationMixin
from sprite_assets import SpriteAssetsMixin
from sprite_physics import SpritePhysicsMixin
import engine_state as st


class Sprite(SpritePhysicsMixin, SpriteAssetsMixin, SpriteAnimationMixin):
    """角色/精灵。物理碰撞、素材装载、动画实现分别拆到 sprite_*.py 的 Mixin 中。"""

    # 类属性：碰撞检测时间控制
    _last_collision_time = 0

    # 接触掩码位：分别表示「左侧 / 右侧 / 头顶 / 脚下」有阻挡
    _CONTACT_LEFT = 1
    _CONTACT_RIGHT = 2
    _CONTACT_UP = 4
    _CONTACT_DOWN = 8

    # 多边形/图像碰撞在 y 轴上可接受的推挤距离上限（像素）。
    # 超过这个距离说明角色是嵌进了墙体侧面，不是正常落地/撞头，应交给 x 轴处理；
    # 斜坡每帧的抬升只有几像素，远小于这个值，所以上坡不受影响。
    _MAX_CONTACT_SNAP = 12.0
    # 站在地面时能自动抬脚走上去的最大台阶高度（像素）
    _MAX_STEP_UP = 8.0
    # 多边形 MTV 的「主导轴」系数：只有 MTV 在该轴上的分量不小于另一轴 0.5 倍时，
    # 才认为这个轴是该面的真实朝向（0.5 ≈ 允许 63° 以内的斜坡）。
    _MTV_DOMINANT_RATIO = 0.5

    # depenetration：最多迭代次数 / 推出后额外留出的皮肤厚度
    _DEPEN_MAX_ITERATIONS = 4
    _DEPEN_SKIN = 0.01

    # 单步最大位移：超过就拆分，避免一步穿过薄墙（与 move() 的 16px 子步一致）
    _MAX_MOVE_STEP = 16.0

    # 前方阻挡探测距离（像素）：sweep_test 默认向前探这么远
    _BLOCK_PROBE = 2.0

    def __init__(self, filename):
        # 1. 基础属性初始化
        self.id = str(id(self))
        # 角色素材名（Sprite("角色1") 里的名字），供相机跟随按名字查找
        self.sprite_name = filename
        self._x = 320
        self._y = 240
        self._scale = 100
        self._angle = 0
        self._rotation_style = "all"
        self._current_scale_x = 1.0
        self.hitbox_scale = 1.0
        self._on_ground = False
        # 接触掩码（P4）：本帧 x/y 解算中碰到的方向，按位记录
        self._contacts = 0
        self._vy = 0
        self._prev_bottom_y = 0
        # 本步移动前的内容盒上沿：与 _prev_bottom_y 一起判断「从上方落地 / 从下方撞头」
        self._prev_top_y = 0
        self._jump_cut = False
        # smart_jump：active=正在由 smart_jump 控制的跳跃；called=本帧是否被调用过
        # 目标写法是 if key_down("w"): smart_jump()，按键松开后就不会再被调用，
        # 引擎据此判断松手并自动停止跳跃
        self._smart_jump_active = False
        self._smart_jump_called = False
        # 记录这次起跳对应的按键；松开该键时引擎自动停止跳跃
        self._smart_jump_key = None
        self._drop_through = False
        self._drop_through_timer = 0
        self._groups = []
        self._visible = True
        self._is_deleted = False
        self._layer = 0
        self._speed = 0
        # 本物理步学生代码执行前的 x：用于区分主动移动与斜面碰撞推挤下滑
        self._frame_start_x = 0.0
        self._on_hit_callbacks = []
        # 感应区进出回调：[(tag, callback)]；_sensor_active_tags 记录当前仍在区域内的标签，
        # 用于「只在从无到有 / 从有到无时各触发一次」
        self._sensor_enter_callbacks = []
        self._sensor_exit_callbacks = []
        self._sensor_active_tags = set()
        self._auto_destroy = False
        # 位置跟随目标（get_marker 挂点引用 / 另一个 Sprite）：None = 不跟随
        self._follow_ref = None
        # 跟随镜像继承（±1）：父翻面武器跟着翻（Godot 子节点语义）
        # 脱离跟随（unfollow）后保留最后一次取值，使挂件保持脱离瞬间的朝向
        self._follow_flip = 1.0
        # follow(target, flip=False) 可关闭镜像继承（如鼠标瞄准武器）
        self._follow_flip_on = True
        # 本帧实际显示的镜像倍率（含自身翻转与跟随继承），供挂点求值/链式跟随读取
        self._display_flip = 1.0

        # 3. 渲染预设缓存（必须在 early return 之前初始化，避免 deleted 精灵崩溃）
        self._cached_image = None
        self._cached_hitbox = None
        self._visual_offset_x = 0
        self._visual_offset_y = 0
        self._show_hitbox = st._SHOW_ALL_COLLISION

        # 🚀 2. 资源解析逻辑升级
        # 尝试寻找解压后的角色文件夹 (例如 assets/sprites/洛克人)
        self.sprite_dir = os.path.join("assets", "sprites", filename)

        # 注意：角色资源必须由用户在资源管理器中添加后才会存在于项目目录
        # 不再自动从引擎内置素材解压
        self._is_bsf = False
        # 禁用碰撞（编辑器「禁用碰撞」开关；仅 .bsf manifest 提供，缺省开启）
        self._collision_disabled = False
        # 受重力影响（编辑器「重力」开关 / 代码 sprite.gravity；缺省受重力）
        self._gravity = True
        self.config = self._load_sprite_config()
        # .bgs 的 config.json 直接携带 gravity 字段（.bsf 已在 normalize 时读取）
        if self.config and not self._is_bsf:
            self._gravity = bool(self.config.get("gravity", True))

        if self.config:
            # 如果是 BGS 角色包格式
            self.current_costume_index = 0

            if self._is_bsf:
                # .bsf：唯一贴图是 sheet.png，帧切换只改 UV 区域（frame_rect）
                # 初始帧 = manifest.defaultFrame（编辑器选中帧），缺省第一帧
                self.image = self._bsf_sheet
            # 检查 frames 或 costumes 字段
            elif "frames" in self.config:
                frames_list = self.config["frames"]
                # 默认渲染帧（编辑器选中帧持久化字段），无效/缺省回退第一帧
                df = self.config.get("defaultFrame")
                if isinstance(df, str) and df in frames_list:
                    self.current_costume_index = frames_list.index(df)
                elif isinstance(df, int) and 0 <= df < len(frames_list):
                    self.current_costume_index = df
                first_frame = frames_list[self.current_costume_index]
                self.image = os.path.join(self.sprite_dir, first_frame)
            elif "costumes" in self.config:
                first_frame = self.config["costumes"][0]["file"]
                self.image = os.path.join(self.sprite_dir, first_frame)
        else:
            self.image = self._resolve_path(filename, "sprites")
            self.sprite_dir = None
            self.config = None

        if not os.path.exists(self.image):
            print(f"[警告] 角色 '{filename}' 不存在，请先在资源管理器中添加")
            self._is_deleted = True
            stop()
            return

        # 4. 初始计算碰撞箱和图片信息
        self._setup_hitbox()

        # 5. 向 IDE 发送创建指令
        create_data = {
            # 关键：转为绝对路径确保 IDE 渲染器能跨目录找到文件
            "image": os.path.abspath(self.image),
            "x": self._x,
            "y": self._y,
            "angle": self._angle,
            "scale": self._scale / 100.0,
            "scale_x": 1.0,
            "scale_y": 1.0,
            "type": "image",
            "layer": self._layer,  # 默认 0：数字越大越靠前，学生设 1/2 即可盖住别人
            "vox": self._visual_offset_x,
            "voy": self._visual_offset_y,
            "raw_cw": self._content_w,
            "raw_ch": self._content_h,
        }

        # .bsf：CREATE 即携带首帧在 sheet 中的 UV 区域
        if self._is_bsf:
            create_data["frame_rect"] = self._bsf_frame_rect()

        # 添加精灵配置信息，用于动画播放
        if self.sprite_dir and self.config:
            create_data["sprite_dir"] = os.path.abspath(self.sprite_dir)
            create_data["config"] = self.config

        self._send_command("CREATE", create_data)

        # 将精灵添加到全局集合
        st._SPRITES[self.id] = self

        # 立即调用_setup_hitbox，确保内容尺寸已计算
        self._setup_hitbox()

        # 立即调用_get_hitbox_rect，确保碰撞盒信息已计算
        self._get_hitbox_rect()


    def goto(self, x, y=None):
        """移到指定坐标；也接受标记引用或另一个角色（注册点对齐）

        w.goto(320, 240)                   # 用户坐标：左下角原点，y 向上为正
        w.goto(player.get_marker())        # 对准角色的「标记」
        w.goto(enemy)
        """
        if y is None:
            pos = _resolve_target_xy(x)
            if pos is None:
                print("[警告] goto 参数无效：需要 (x, y)、标记或角色")
                return
            # 标记/角色解析出来的是世界坐标，直接写入，避免二次翻转
            self._set_xy_world(pos[0], pos[1])
            return
        self.set_xy(x, y)


    def get_marker(self, name="标记"):
        """获取标记引用（.bsf 角色在编辑器「标记」图层标注的锚点）

        返回值可直接给 goto()/follow() 用，也可读 .x/.y（用户坐标：左下角原点，y 向上）：
            w.goto(player.get_marker())        # 第一个标记「标记」
            w.follow(player.get_marker('标记2'))
        """
        if not getattr(self, "_is_bsf", False):
            print("[警告] 标记仅 .bsf 角色支持（先在角色编辑器「标记」图层添加）")
            return None
        if self._marker_world_xy(name) is None:
            known = sorted((getattr(self, "_bsf_markers", None) or {}).keys())
            hint = ("已有标记: " + ", ".join(known)) if known else "该角色还没有标记"
            print(f"[警告] 角色没有名为 '{name}' 的标记（{hint}）")
            return None
        return _MarkerRef(self, name)


    def follow(self, target, flip=True):
        """持续跟随目标的位置（每帧自动更新，只跟位置不跟朝向）

        target = get_marker() 返回的标记引用，或另一个 Sprite：
            w.follow(player.get_marker())
            w.follow(enemy)
        默认继承目标的左右镜像（父翻面武器跟着翻，Godot 子节点观感）；
        鼠标瞄准类武器可关：w.follow(m, flip=False)。
        朝向/缩放仍可独立控制（如 w.look_at(mouse) 瞄准）；
        目标被删除时自动停止跟随。w.unfollow() 手动解除（保留脱离时的朝向）。
        """
        if isinstance(target, (_MarkerRef, Sprite)):
            self._follow_ref = target
            self._follow_flip_on = bool(flip)
            self._follow_flip = 1.0  # 下一帧 _update_follows 重算
        else:
            print("[警告] follow 参数无效：需要标记或角色")


    def unfollow(self):
        """停止跟随（保留脱离瞬间的朝向，不恢复为正向）"""
        self._follow_ref = None


        # 故意不重置 _follow_flip：它保存着最后一次继承来的镜像，
        # 留着才能让挂件停在脱离时的朝向；再次 follow() 会重新初始化

    # ---------- 坐标（用户空间：原点在地图左下角，y 向上为正） ----------
    def set_xy(self, x, y):
        """设置坐标（用户坐标：地图左下角为 (0,0)，y 向上为正）"""
        self._set_xy_world(to_world_x(x), to_world_y(y))


    def _set_xy_world(self, x, y):
        """按世界坐标传送（不做任何转换）。

        传送不是「移动」，没有运动方向：
          - 先记录旧的上下沿，保留单向平台原有的落点判断
          - 写入目标坐标后先 depenetrate，再按最近边兜底解算
        """
        hitbox = self._get_hitbox_rect()
        if hitbox:
            self._prev_bottom_y = hitbox[3]
            self._prev_top_y = hitbox[1]
        self._x = x
        self._y = y
        if not self._collision_disabled and st._CURRENT_MAP:
            self._depenetrate()
            self._resolve_collision("x")
            self._resolve_collision("y")
        self._update_transform()


    def set_x(self, x):
        """设置 x 坐标（用户坐标：正数向右）"""
        target = to_world_x(x)
        self.move_and_slide(target - self._x, 0.0, axis_order="xy", resolve_y=False)
        self._update_transform()


    def set_y(self, y):
        """设置 y 坐标（用户坐标：正数向上）"""
        target = to_world_y(y)
        self.move_and_slide(0.0, target - self._y, axis_order="yx", resolve_x=False)
        self._update_transform()


    def add_x(self, delta_x):
        """将 x 坐标增加（或减少）一定数值（用户坐标：正数向右）"""
        dx = to_world_dx(delta_x)
        self.move_and_slide(dx, 0.0, axis_order="xy", resolve_y=False)
        self._update_transform()


    def add_y(self, delta_y):
        """将 y 坐标增加（或减少）一定数值（用户坐标：正数向上）"""
        dy = to_world_dy(delta_y)
        self.move_and_slide(0.0, dy, axis_order="yx", resolve_x=False)
        self._update_transform()


    def jump(self, power=10):
        """角色跳跃

        Args:
            power: 跳跃力度（默认10，越大跳得越高）
        """
        self._vy = -power
        self._on_ground = False
        self._jump_cut = False


    def stop_jump(self):
        """停止跳跃：角色正在上升时调用，停止继续上升并提前落下

        只在上升阶段生效（上升重力从 0.5 变为 2.8），自己不会让角色起跳；
        没有"松手"动作的场景（敌人 AI、撞天花板等）也能直接调用。
        """
        if self._vy < 0:
            self._jump_cut = True
        self._jump_buffered = False


    def cut_jump(self):
        """旧名字，保留兼容；等价于 stop_jump()"""
        self.stop_jump()


    def smart_jump(self, power=10):
        """大小跳：按下起跳，按住跳得高，松手就落下

        用法（必须写在 if key_down(...) 里面，每帧调用一次）：

            while True:
                if key_down("w"):
                    hero.smart_jump(12)

        引擎通过「本帧有没有被调用」判断按键状态：松开后这个函数不再被调用，
        引擎会自动帮你停止跳跃，所以不需要自己写 stop_jump。

        Args:
            power: 最大跳跃力度（默认 10，越大跳得越高）
        """
        self._smart_jump_called = True
        if not self._smart_jump_active and self._on_ground:
            # 刚按下且站在地面上：起跳
            self.jump(power)
            self._smart_jump_active = True
            # 记住本步刚按下的键：无论学生把 smart_jump 写在 if key_down 还是
            # if key_pressed 里，松手判断都按这个键的真实状态来，不会误截断
            newly = st._PRESSED_KEYS_FRAME - st._PRESSED_KEYS_PREV
            self._smart_jump_key = next(iter(newly), None)


    def drop_down(self):
        """从跳板掉下去：角色站在跳板上时调用，穿过脚下的跳板下落"""
        if self._on_ground:
            self._drop_through = True
            self._drop_through_timer = 10
            self._on_ground = False
            self._vy = 2


    def drop_through(self):
        """旧名字，保留兼容；等价于 drop_down()"""
        self.drop_down()


    def set_speed(self, speed):
        """设置持续速度，引擎每帧自动沿当前方向移动"""
        self._speed = speed


    def on_touch_group(self, group, callback=None):
        """碰到指定组的成员时自动处理（注册一次即可，引擎每帧自动检测）

        - 不传 callback：碰到后默认双方都删除
        - 传 callback：执行 callback(自己, 碰到的角色)；
          函数也可以只写 1 个参数（只接收自己）或不写参数
        - 同一个组重复注册会覆盖上一次：写在 while True 里也不会重复执行/越积越多
        """
        # 按组去重：重复注册只保留最后一次，避免每帧注册导致回调越积越多
        self._on_hit_callbacks = [
            item for item in self._on_hit_callbacks if item[0] != group
        ]
        self._on_hit_callbacks.append((group, callback))


    # 兼容旧项目代码，旧名不再出现在文档与补全中
    def on_hit(self, group, callback=None):
        return self.on_touch_group(group, callback)


    def on_sensor_enter(self, tag, callback):
        """进入某个感应形状时执行 callback（注册一次即可，引擎每帧自动检测）

        只有形状层里设成「感应」或「阻挡 + 感应」、并且填了同名标签的形状才会触发；
        同一个标签从无到有时只触发一次，站在里面不会每帧重复触发。

        回调函数参数可以不写、写 1 个或写 2 个：
            def 碰到水():               # 不接收信息
            def 碰到水(who):            # who = 进入的角色
            def 碰到水(who, tag):       # tag = 标签名

        同一个标签重复注册会覆盖上一次：写在 while True 里也不会重复执行/越积越多。
        """
        if not callable(callback):
            print("[提示] on_sensor_enter 需要传一个函数，例如：hero.on_sensor_enter(\"水\", 碰到水)")
            return
        # 按标签去重：重复注册只保留最后一次
        self._sensor_enter_callbacks = [
            item for item in self._sensor_enter_callbacks if item[0] != tag
        ]
        self._sensor_enter_callbacks.append((tag, callback))


    def on_sensor_exit(self, tag, callback):
        """离开某个感应形状时执行 callback（参数写法同 on_sensor_enter）

        同一个标签重复注册会覆盖上一次。
        """
        if not callable(callback):
            print("[提示] on_sensor_exit 需要传一个函数，例如：hero.on_sensor_exit(\"水\", 离开水)")
            return
        self._sensor_exit_callbacks = [
            item for item in self._sensor_exit_callbacks if item[0] != tag
        ]
        self._sensor_exit_callbacks.append((tag, callback))


    def broadcast(self, event_name):
        """发送广播（触发所有接收该事件的回调；单个回调出错不会中断游戏）"""
        broadcast(event_name)


    def receive(self, event_name):
        """这一帧有没有收到指定广播（广播是全局的，写在哪个角色上结果一样）"""
        return receive(event_name)


    def on_receive(self, event_name, callback=None):
        """防误用提示：on_receive 是注册用的全局函数，不是角色的方法"""
        if not getattr(self, "_receive_hint_shown", False):
            print("[提示] on_receive 是全局函数，不是角色的方法。注册写法：on_receive(\"事件名\", 函数)，写在循环外面；只想检查有没有收到广播，用 if 角色.receive(\"事件名\")")
            self._receive_hint_shown = True
        return None


    def move(self, distance):
        """朝着当前 angle 方向移动 distance 像素"""
        radians = math.radians(self._angle)

        # 计算移动分量
        dx = distance * math.cos(radians)
        dy = distance * math.sin(radians)

        # 大位移的拆步与碰撞全部交给唯一入口 move_and_slide
        self.move_and_slide(dx, dy, axis_order="xy")

        # 更新变换
        self._update_transform()


    def goto_rand(self):
        """移到地图内的随机位置"""
        bounds = _playable_bounds()
        self._set_xy_world(
            random.randint(int(bounds["left"]), int(bounds["right"])),
            random.randint(int(bounds["top"]), int(bounds["bottom"])),
        )


    def set_angle(self, angle):
        """设置旋转角度（用户坐标：逆时针为正，0=右 90=上 180=左 270=下）"""
        self._angle = to_world_angle(angle)
        self._update_transform()


    def look_at(self, target):
        """
        让当前角色看向另一个角色或鼠标 (自动旋转角度)
        """
        if self._is_deleted:
            return

        # 1. 🚀 获取目标位置 (mx, my)
        if target is mouse:
            tx, ty = st._MOUSE_STATE["x"], st._MOUSE_STATE["y"]
        elif isinstance(target, Sprite):
            if target._is_deleted:
                return
            # 用目标的位置点（轴心）而不是旋转后包围盒中心：
            # 对方也在旋转时，包围盒中心会绕着它的轴心摆动，瞄准点会跟着抖
            tx, ty = target._x, target._y
        else:
            # 如果不是 mouse 也不是 Sprite，不执行旋转
            return

        # 2. 🚀 以自身旋转轴心为射线起点
        # 非 .bsf 角色：轴心 = 内容重心 = 世界坐标 (x, y)，与旧实现（包围盒中心）完全等价
        # .bsf 角色：轴心 = manifest pivot，而 pivot 可能明显偏离内容重心。
        # 此时若仍用「包围盒中心」作起点，该中心会随 angle 绕轴心旋转，形成
        # angle → 中心 → angle 的自反馈，近目标处相邻两帧角度来回跳变
        # （看起来像两个不同朝向的角色），故起点固定为不随旋转变化的轴心。
        sx, sy = self._x, self._y

        # 3. 计算坐标差并求角度
        dx = tx - sx
        dy = ty - sy

        # 目标几乎和自己的轴心重合时，方向没有意义：鼠标/对方在原地轻微一动，
        # atan2 结果就在 0° 和 180° 之间乱跳，画面看起来像疯狂抖动。
        # 此时保持上一帧的朝向，不再重新瞄准。
        if dx * dx + dy * dy < 0.25:
            return

        # 使用 atan2 计算弧度，再转换为角度
        radians = math.atan2(dy, dx)
        angle = math.degrees(radians)

        # 4. 应用角度（atan2 在世界空间算出，已是世界角度，直接写入避免二次翻转）
        self._angle = angle % 360
        self._update_transform()


    def edge_bounce(self):
        """基于 Hitbox 的精准反弹，自动识别地图边界"""
        bounds = _playable_bounds()

        STAGE_LEFT = bounds["left"]
        STAGE_TOP = bounds["top"]
        STAGE_RIGHT = bounds["right"]
        STAGE_BOTTOM = bounds["bottom"]
        rect = self._get_hitbox_rect()
        if not rect:
            return
        hit = False
        # move() 内的 _resolve_collision 会把越界精灵钳制回边界内 0.05px，
        # 所以不能只判 overflow——还要判"贴边"；方向判断避免沿边缘滑动时误触发
        EPS = 0.5
        cos_a = math.cos(math.radians(self._angle))
        sin_a = math.sin(math.radians(self._angle))

        # 左右判断
        if rect[2] >= STAGE_RIGHT - EPS and cos_a > 0:
            self._x -= rect[2] - STAGE_RIGHT
            self._angle = 180 - self._angle
            hit = True
        elif rect[0] <= STAGE_LEFT + EPS and cos_a < 0:
            self._x += STAGE_LEFT - rect[0]
            self._angle = 180 - self._angle
            hit = True

        # 上下判断
        if rect[3] >= STAGE_BOTTOM - EPS and sin_a > 0:
            self._y -= rect[3] - STAGE_BOTTOM
            self._angle = -self._angle
            hit = True
        elif rect[1] <= STAGE_TOP + EPS and sin_a < 0:
            self._y += STAGE_TOP - rect[1]
            self._angle = -self._angle
            hit = True

        if hit:
            self._angle %= 360
            self._update_transform()


    # ----------- 外观模块 ----------
    def set_scale(self, value):
        self._scale = min(max(5.0, float(value)), 1000.0)
        self._update_transform()


    def add_scale(self, value):
        """
        在当前缩放比例的基础上增加 value (单位为百分比)
        例如：add_scale(10) 会让角色变大 10%
        """
        # 🚀 直接利用 property 逻辑，简单稳健
        self.scale += value


    def set_rotation_mode(self, style):
        """
        style:
        'all': 任意旋转 (默认)
        'left_right': 左右翻转 (角度不改变图片旋转，只决定水平镜像)
        'none': 不可旋转 (图片始终正向)
        """
        self._rotation_style = style
        # 立即触发一次更新以应用新样式
        self._update_transform()


    def _apply_visible(self, visible):
        """设置可见状态并同步帧缓冲：本帧已排队的更新若仍带旧状态，
        会在 hide()/show() 之后才刷出，把角色又画出来，这里一并改写"""
        self._visible = visible
        for update in st._FRAME_UPDATES:
            if update.get("id") == self.id:
                update["visible"] = visible
        self._send_command("UPDATE", {"id": self.id, "visible": visible})


    def show(self):
        """显示角色"""
        if self._is_deleted:
            return  # 已经删除的不能显示
        self._apply_visible(True)


    def hide(self):
        """隐藏角色（仅仅是看不见，物体还在内存里）"""
        self._apply_visible(False)


    # 兼容旧项目代码，旧名不再出现在文档与补全中
    def touch_group(self, group_name):
        return self.is_touch_group(group_name)


    def add_to_group(self, group_name):
        """将角色归类，比如 'enemies', 'bullets'"""
        if group_name not in st._GROUPS:
            st._GROUPS[group_name] = []
        if self not in st._GROUPS[group_name]:
            st._GROUPS[group_name].append(self)
            self._groups.append(group_name)


    def delete(self):
        """彻底删除（视觉移除 + 物理移除 + 内存清理）"""
        self._is_deleted = True
        self._send_command("DELETE", {"id": self.id})
        # 从全局组里彻底踢出去
        if hasattr(self, "_groups"):
            for g in self._groups:
                if self in st._GROUPS.get(g, []):
                    st._GROUPS[g].remove(self)
        # 从全局精灵集合中移除
        if self.id in st._SPRITES:
            del st._SPRITES[self.id]
        # 清理 say 计时器
        if self.id in st._SAY_TIMERS:
            del st._SAY_TIMERS[self.id]


    def distance_to(self, target):
        """
        计算当前角色到目标（Sprite 或 mouse）的像素距离

        用角色的位置点（.bgs = 内容重心，.bsf = 编辑器标注的轴心）来测距，
        与 goto()/look_at() 完全一致。不能用旋转后包围盒的中心：
        轴心标在脚底等位置时，包围盒中心会随旋转绕轴心摆动，
        角色明明已经站在鼠标上，距离却总是几十像素，导致判断失灵。
        """
        if self._is_deleted:
            return 999999

        # 🚀 1. 优先处理鼠标，因为它不是 Sprite 实例
        if target is mouse:
            dx = self._x - st._MOUSE_STATE["x"]
            dy = self._y - st._MOUSE_STATE["y"]
            return math.hypot(dx, dy)

        # 🚀 2. 处理其他 Sprite 角色
        if not isinstance(target, Sprite) or target._is_deleted:
            return 999999

        dx = self._x - target._x
        dy = self._y - target._y
        return math.hypot(dx, dy)


    # ----------- 属性赋值 ----------
    @property
    def x(self):
        """水平位置（用户坐标：正数向右）"""
        return to_user_x(self._x)


    @x.setter
    def x(self, value):
        self.set_x(value)


    @property
    def y(self):
        """垂直位置（用户坐标：正数向上）"""
        return to_user_y(self._y)


    @y.setter
    def y(self, value):
        self.set_y(value)


    @property
    def pos(self):
        """一次性获取角色坐标 (x, y)，可直接拆包：x, y = hero.pos（只读）"""
        return self.x, self.y


    @property
    def vy(self):
        """垂直速度（用户坐标：正数向上，负数向下）"""
        return to_user_dy(self._vy)


    @vy.setter
    def vy(self, value):
        self._vy = to_world_dy(value)


    @property
    def gravity(self):
        """是否受地图重力影响（默认 True）。设为 False 后不下坠，撞墙/落地等碰撞照常"""
        return self._gravity


    @gravity.setter
    def gravity(self, value):
        self._gravity = bool(value)


    @property
    def angle(self):
        """朝向角度（用户坐标：逆时针为正）"""
        return to_user_angle(self._angle)


    @angle.setter
    def angle(self, value):
        self.set_angle(value)


    @property
    def scale(self):
        return self._scale


    @scale.setter
    def scale(self, value):
        self.set_scale(value)


    @property
    def layer(self):
        return self._layer


    @layer.setter
    def layer(self, value):
        """学生可以手动设置层级，例如 hero.layer = 10"""
        self._layer = value
        self._send_command("UPDATE", {"id": self.id, "layer": value})


    # ----------- 超级核心 -----------
    def _send_command(self, cmd_type, data_dict):
        """核心:所有指令都是通过它发送出去并执行的"""
        packet = {"type": cmd_type, "id": self.id, "data": data_dict}
        # stdout 已经是行缓冲模式（buffering=1），print 自动带换行会刷缓冲
        print(json.dumps(packet))


def _resolve_target_xy(target):
    """把标记引用 / 地图标记 / Sprite 解析为世界坐标 (x, y)；无法解析返回 None"""
    if isinstance(target, _MarkerRef):
        return target._sprite._marker_world_xy(target.name)
    if isinstance(target, MapMarkerRef):
        # 地图标记本身保存的就是世界坐标
        return target.world_xy
    if isinstance(target, Sprite):
        if target._is_deleted:
            return None
        # 必须读世界坐标：target.x/y 是用户空间，会翻转 y
        return (target._x, target._y)
    return None
