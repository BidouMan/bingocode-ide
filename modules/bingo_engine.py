import json
import sys
import time
import os
import random
import math
import threading
from PIL import Image


sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)

__all__ = ['Sprite', 'run','key_down','show_fps']
_PRESSED_KEYS = set()
_SHOW_FPS = False
_PERF_STATS = {"last_time": time.time(), "frame_count": 0}
_GROUPS = {}

class Sprite:
    def __init__(self, image_name):        
        # 使用内存地址作为唯一ID
        self.id = str(id(self))
        # 🚀 修正路径：确保与你 assets 文件夹名称一致
        self.image = os.path.join("assets", "images", image_name)
        self._x = 320  
        self._y = 240
        self._size = 100
        self._angle = 0
        self._rotation_style = "all"
        self._current_scale_x = 1.0
        self.hitbox_scale = 0.8 # 允许微调碰撞精度
        self._setup_hitbox()    # 创建hitbox
        self._groups = []
        self._visible = True
        self._is_deleted = False # 增加删除标记
        

        # 发送创建指令
        self._send_command("CREATE", {
            "image": self.image,
            "x": self._x,
            "y": self._y,
            "angle": self._angle,
            "scale_x": 1.0, # 初始镜像
            "type": "image"
        })

    # ---------- 运动模块 ----------
    def set_xy(self, x, y):
        """设置坐标"""
        self._x = x
        self._y = y
        self._update_transform()
    
    def set_x(self,x):
        self._x = x
        self._update_transform()

    def set_y(self,y):
        self._y = y
        self._update_transform()

    def add_x(self, delta_x):
        """将 x 坐标增加（或减少）一定数值"""
        self._x += delta_x
        self._update_transform()

    def add_y(self, delta_y):
        """将 y 坐标增加（或减少）一定数值"""
        self._y += delta_y
        self._update_transform()

    def move(self, distance):
        """朝着当前 angle 方向移动 distance 像素"""
        radians = math.radians(self._angle)
        self._x += distance * math.cos(radians)
        self._y += distance * math.sin(radians)
        self._update_transform() # 🚀 只发送一次指令，性能更高

    def goto_rand(self):
        '''移到随机位置'''
        self._x = random.randint(0,640)
        self._y = random.randint(0,480)
        self._update_transform()

    def set_angle(self, angle):
        """设置旋转角度"""
        self._angle = angle
        self._update_transform()
    
    def edge_bounce(self):
        """基于 Hitbox 的精准反弹"""
        STAGE_W, STAGE_H = 640, 480
        rect = self._get_hitbox_rect()
        hit = False

        # 左右判断
        if rect[2] > STAGE_W: # 右边出界
            self._x -= (rect[2] - STAGE_W) # 修正位置，消除穿墙感
            self._angle = 180 - self._angle
            hit = True
        elif rect[0] < 0:     # 左边出界
            self._x += (0 - rect[0])
            self._angle = 180 - self._angle
            hit = True

        # 上下判断
        if rect[3] > STAGE_H: # 下边出界
            self._y -= (rect[3] - STAGE_H)
            self._angle = -self._angle
            hit = True
        elif rect[1] < 0:     # 上边出界
            self._y += (0 - rect[1])
            self._angle = -self._angle
            hit = True

        if hit:
            self._angle %= 360
            self._update_transform()

    # ----------- 外观模块 ----------
    def set_size(self,value):
        self._size = value
        self._update_transform()

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

    def show(self):
        """显示角色"""
        if self._is_deleted: return # 已经删除的不能显示
        self._visible = True
        self._send_command("UPDATE", {"id": self.id, "visible": True})

    def hide(self):
        """隐藏角色（仅仅是看不见，物体还在内存里）"""
        self._visible = False
        self._send_command("UPDATE", {"id": self.id, "visible": False})

    # ---------- 侦测模块 ----------
    def is_touch(self, other):
        """判断是否碰到另一个 Sprite"""
        if not self._visible or not other._visible: 
            return False
        if self._is_deleted or other._is_deleted:
            return False
        if not isinstance(other, Sprite): 
            return False
        r1 = self._get_hitbox_rect()
        r2 = other._get_hitbox_rect()
        # AABB 碰撞公式：只要有一个维度不重叠，就没碰到
        return not (r1[2] < r2[0] or r1[0] > r2[2] or 
                    r1[3] < r2[1] or r1[1] > r2[3])

    def touch_group(self, group_name):
        """
        判断是否撞到了某个组里的任意成员。
        如果撞到了，返回那个成员；没撞到返回 None。
        """
        if group_name not in _GROUPS:
            return None
            
        for other in _GROUPS[group_name]:
            # 排除自己
            if other is self: continue
            # 这里的 is_touching 是我们之前写的 Pillow AABB 算法
            if self.is_touch(other):
                return other
        return None

    def add_to_group(self, group_name):
        """将角色归类，比如 'enemies', 'bullets'"""
        if group_name not in _GROUPS:
            _GROUPS[group_name] = []
        if self not in _GROUPS[group_name]:
            _GROUPS[group_name].append(self)
            self._groups.append(group_name)

    def delete(self):
        """彻底删除（视觉移除 + 物理移除 + 内存清理）"""
        self._is_deleted = True
        self._send_command("DELETE", {"id": self.id})
        # 从全局组里彻底踢出去
        if hasattr(self, '_groups'):
            for g in self._groups:
                if self in _GROUPS.get(g, []):
                    _GROUPS[g].remove(self)

    # ----------- 属性赋值 ----------
    @property
    def x(self):
        return self._x
    @x.setter
    def x(self,value):
        self.set_x(value)

    @property
    def y(self):
        return self._y
    @y.setter
    def y(self, value):
        self.set_y(value)

    @property
    def angle(self):
        return self._angle
    @angle.setter
    def angle(self,value):
        self.set_angle(value)

    @property
    def size(self):
        return self._size
    @size.setter
    def size(self,value):
        self.set_size(value)

    # ---------- 内部调用 ----------
    def _setup_hitbox(self):
        """扫描图片非透明区域，解决 64x64 容器内 32x32 角色问题"""
        try:
            with Image.open(self.image) as img:
                self._orig_w, self._orig_h = img.size
                # getbbox 会跳过透明区域，返回 (left, top, right, bottom)
                bbox = img.convert("RGBA").getbbox()
                if bbox:
                    l, t, r, b = bbox
                    self._content_w = r - l
                    self._content_h = b - t
                    # 计算视觉中心相对于图片中心点的偏移
                    self._visual_offset_x = (l + r) / 2.0 - self._orig_w / 2.0
                    self._visual_offset_y = (t + b) / 2.0 - self._orig_h / 2.0
                else:
                    self._content_w, self._content_h = self._orig_w, self._orig_h
                    self._visual_offset_x = self._visual_offset_y = 0
        except:
            self._orig_w = self._orig_h = 50
            self._content_w = self._content_h = 50
            self._visual_offset_x = self._visual_offset_y = 0

    def _get_hitbox_rect(self):
        """获取当前角色在舞台上的真实包围盒 [left, top, right, bottom]"""
        ratio = (self._size / 100.0) * self.hitbox_scale
        # 当前视觉中心 = 逻辑中心 + 偏移量 * 缩放
        cx = self._x + (self._visual_offset_x * (self._size / 100.0))
        cy = self._y + (self._visual_offset_y * (self._size / 100.0))
        
        hw, hh = (self._content_w * ratio) / 2.0, (self._content_h * ratio) / 2.0
        return [cx - hw, cy - hh, cx + hw, cy + hh]

    def _update_transform(self):
        """统一处理旋转、缩放和镜像逻辑"""
        display_angle = self._angle
        # 计算基础缩放比例（百分比转为小数）
        base_scale = self._size / 100.0
        
        # 默认情况下，Y轴只受 size 影响
        final_scale_y = base_scale
        # X轴受 size 和 镜像状态 共同影响
        final_scale_x = base_scale * self._current_scale_x
        
        if self._rotation_style == "left_right":
            norm_angle = self._angle % 360
            if 90 < norm_angle < 270:
                self._current_scale_x = -1.0
            elif (0 <= norm_angle < 90) or (270 < norm_angle <= 360):
                self._current_scale_x = 1.0
            
            # 重新计算镜像后的 X 缩放
            final_scale_x = base_scale * self._current_scale_x
            display_angle = 0
            
        elif self._rotation_style == "none":
            display_angle = 0
            final_scale_x = base_scale
            
        # 🚀 发送指令：确保携带 scale_y
        self._send_command("UPDATE", {
            "x": self._x,
            "y": self._y,
            "angle": display_angle,
            "scale_x": final_scale_x,
            "scale_y": final_scale_y 
        })

    # ----------- 超级核心 -----------
    def _send_command(self, cmd_type, data_dict):
        """核心:所有指令都是通过它发送出去并执行的"""
        packet = {
            "type": cmd_type,
            "id": self.id,
            "data": data_dict 
        }
        # 🚀 必须取消注释，且必须 flush=True 保证实时性
        print(json.dumps(packet), flush=True)

def _input_sync_listener():
    global _PRESSED_KEYS
    
    while True:
        try:
            # 🚀 确保是阻塞式读取
            line = sys.stdin.readline()
            if not line:
                time.sleep(0.01)
                continue
            
            clean_line = line.strip()
                       
            if clean_line.startswith("K_DOWN:"):
                key = clean_line.split(":", 1)[1]
                _PRESSED_KEYS.add(key)
            elif clean_line.startswith("K_UP:"):
                key = clean_line.split(":", 1)[1]
                _PRESSED_KEYS.discard(key)
        except:
            time.sleep(0.01)

# 确保线程启动 (代码末尾)
threading.Thread(target=_input_sync_listener, daemon=True).start()

def key_down(key):
    """供用户调用：if key_down('a')"""
    return str(key).lower() in _PRESSED_KEYS

def show_fps(visible=True):
    global _SHOW_FPS
    _SHOW_FPS = visible
    packet = {
        "type": "UI_COMMAND",
        "data": {"action": "show_fps", "value": visible}
    }
    # 🚀 使用 sys.stdout.write 配合 \n 更加底层稳健
    sys.stdout.write(json.dumps(packet) + "\n")
    sys.stdout.flush()

# ---------- 内部函数 ----------

def _send_fps_to_ide(fps):
    packet = {
        "type": "FPS_UPDATE",
        "data": {"fps": round(fps, 1)}
    }
    # 🚀 明确发送到标准输出
    print(json.dumps(packet), flush=True)


# bingo_engine.py

def run():
    global _PERF_STATS
    main_module = sys.modules['__main__']
    if not hasattr(main_module, 'loop'): return

    target_fps = 60
    frame_duration = 1.0 / target_fps
    _PERF_STATS["last_time"] = time.time()
    
    next_frame_time = time.time() # 🚀 记录下一帧应该开始的时间点

    while True:
        start_frame = time.time()
        
        # 执行用户逻辑
        main_module.loop()
        
        # FPS 统计
        _PERF_STATS["frame_count"] += 1
        now = time.time()
        duration = now - _PERF_STATS["last_time"]
        if duration >= 0.5:
            fps = _PERF_STATS["frame_count"] / duration
            if _SHOW_FPS:
                _send_fps_to_ide(fps)
            _PERF_STATS["frame_count"] = 0
            _PERF_STATS["last_time"] = now

        # 🚀 改进的帧率控制：追踪时间线而不是死等
        next_frame_time += frame_duration
        sleep_time = next_frame_time - time.time()
        
        if sleep_time > 0:
            time.sleep(sleep_time)
        else:
            # 如果逻辑太重导致掉帧了，重置时间线防止“加速追赶”
            next_frame_time = time.time()