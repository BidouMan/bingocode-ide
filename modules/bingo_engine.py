import json
import sys
import time
import os
import random
import math
import threading
from PIL import Image
from PySide6.QtCore import QRectF
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', buffering=1)

_PRESSED_KEYS = set()
_SHOW_FPS = False
_PERF_STATS = {"last_time": time.time(), "frame_count": 0}
_GROUPS = {}
_MOUSE_STATE = {"down": False,"last_down": False,"x": 0, "y": 0}  # 用字典包装鼠标状态


class _MouseType:
    @property
    def x(self): return _MOUSE_STATE["x"]
    @property
    def y(self): return _MOUSE_STATE["y"]
    def __repr__(self): return "mouse"

mouse = _MouseType() # 🚀 定义全局变量 mouse

__all__ = ['Sprite', 'run','key_down','show_fps','set_background','mouse_down','mouse_pressed','mouse']


class Sprite:
    def __init__(self, filename):        
        # 使用内存地址作为唯一ID
        self.id = str(id(self))
        self.image = self._resolve_path(filename, "sprites")
        self._x = 320  
        self._y = 240
        self._scale = 100
        self._angle = 0
        self._rotation_style = "all"
        self._current_scale_x = 1.0
        self.hitbox_scale = 0.8 # 允许微调碰撞精度
        self._groups = []
        self._visible = True
        self._is_deleted = False # 增加删除标记
        self._layer = 0

        # 🚀 预设缓存变量
        self._cached_image = None
        self._cached_hitbox = None 
        self._visual_offset_x = 0
        self._visual_offset_y = 0
        
        # 初始计算一次
        self._setup_hitbox()

        # 发送创建指令
        self._send_command("CREATE", {
            # 🚀 关键：将相对路径转为绝对路径发给 IDE 渲染器
            "image": os.path.abspath(self.image), 
            "x": self._x,
            "y": self._y,
            "angle": self._angle,
            "scale_x": 1.0, 
            "type": "image",
            "vox": self._visual_offset_x,
            "voy": self._visual_offset_y,
            "raw_cw": self._content_w,
            "raw_ch": self._content_h
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
    
    def look_at(self, target):
        """
        让当前角色看向另一个角色或鼠标 (自动旋转角度)
        """
        if self._is_deleted: return

        # 1. 🚀 获取目标位置 (mx, my)
        if target is mouse:
            tx, ty = _MOUSE_STATE["x"], _MOUSE_STATE["y"]
        elif isinstance(target, Sprite):
            if target._is_deleted: return
            # 获取目标的视觉中心
            t_rect = target._get_hitbox_rect()
            tx, ty = (t_rect[0] + t_rect[2]) / 2.0, (t_rect[1] + t_rect[3]) / 2.0
        else:
            # 如果不是 mouse 也不是 Sprite，不执行旋转
            return

        # 2. 🚀 获取自身的视觉中心
        # 必须从视觉中心发出射线，指向才不会歪
        s_rect = self._get_hitbox_rect()
        sx, sy = (s_rect[0] + s_rect[2]) / 2.0, (s_rect[1] + s_rect[3]) / 2.0

        # 3. 计算坐标差并求角度
        dx = tx - sx
        dy = ty - sy

        # 使用 atan2 计算弧度，再转换为角度
        radians = math.atan2(dy, dx)
        angle = math.degrees(radians)

        # 4. 应用角度
        self.set_angle(angle % 360)

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
    def set_scale(self,value):
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

    def show(self):
        """显示角色"""
        if self._is_deleted: return # 已经删除的不能显示
        self._visible = True
        self._send_command("UPDATE", {"id": self.id, "visible": True})

    def hide(self):
        """隐藏角色（仅仅是看不见，物体还在内存里）"""
        self._visible = False
        self._send_command("UPDATE", {"id": self.id, "visible": False})

    def say(self, text):
        """
        让角色说话。由于设定是永久显示，新话会替换旧话。
        """
        # 确保 text 是字符串
        self._send_command("SAY", {"text": str(text)})

    # ---------- 侦测模块 ----------
    def is_touch_edge(self):
        """
        精准边界检测：判定角色的实际视觉边缘是否越过了 640*480 的舞台
        """
        # 1. 获取缩放和偏移后的真实包围盒 [left, top, right, bottom]
        rect = self._get_hitbox_rect()
        
        # 2. 舞台固定尺寸
        STAGE_W = 640
        STAGE_H = 480
        
        # 3. 只要任何一边超出了舞台，就返回 True
        if (rect[0] < 0 or         # 左边出界
            rect[2] > STAGE_W or   # 右边出界
            rect[1] < 0 or         # 上边出界
            rect[3] > STAGE_H):    # 下边出界
            return True
            
        return False
    
    def is_out_side(self):
        """
        完全出界检测：只有当角色整体（所有像素）都离开舞台时才返回 True
        舞台尺寸固定为 640 * 480
        """
        # 获取当前精准包围盒 [left, top, right, bottom]
        rect = self._get_hitbox_rect()
        
        STAGE_W = 640
        STAGE_H = 480
        
        # 逻辑判断：
        # rect[2] < 0: 右边缘比舞台左边还要小（在左侧完全出界）
        # rect[0] > STAGE_W: 左边缘比舞台右边还要大（在右侧完全出界）
        # rect[3] < 0: 下边缘比舞台顶边还要小（在上方完全出界）
        # rect[1] > STAGE_H: 上边缘比舞台底边还要大（在下方完全出界）
        if (rect[2] < 0 or 
            rect[0] > STAGE_W or 
            rect[3] < 0 or 
            rect[1] > STAGE_H):
            return True
            
        return False

    def is_touch(self, target):
        """判断是否碰到另一个 Sprite 或鼠标"""
        if self._is_deleted or not self._visible: 
            return False

        # 🚀 1. 统一获取当前的精准包围盒 [left, top, right, bottom]
        # 这个方法已经包含了 _visual_offset 和 scale 的所有校准
        r1 = self._get_hitbox_rect()
        if not r1: return False

        if target is mouse:
            mx, my = _MOUSE_STATE["x"], _MOUSE_STATE["y"]
            
            # 🚀 2. 判定鼠标点 (mx, my) 是否在内容矩形 r1 内
            # r1[0]=左, r1[1]=上, r1[2]=右, r1[3]=下
            return (r1[0] <= mx <= r1[2] and 
                    r1[1] <= my <= r1[3])

        # 🚀 3. 原有的 Sprite 间碰撞逻辑
        if target is None or not hasattr(target, '_visible') or not target._visible:
            return False

        if not isinstance(target, Sprite): 
            return False
            
        r2 = target._get_hitbox_rect()
        if not r2: return False
                
        # AABB 碰撞公式保持不变
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

    def distance_to(self, target):
        """
        计算当前角色视觉中心点到目标（Sprite 或 mouse）的距离
        """
        if self._is_deleted: return 999999

        # 🚀 1. 优先处理鼠标，因为它不是 Sprite 实例
        if target is mouse:
            # 使用精准的视觉中心点
            rect = self._get_hitbox_rect()
            cx, cy = (rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0
            dx = cx - _MOUSE_STATE["x"]
            dy = cy - _MOUSE_STATE["y"]
            return math.sqrt(dx*dx + dy*dy)

        # 🚀 2. 处理其他 Sprite 角色
        if not isinstance(target, Sprite) or target._is_deleted:
            return 999999

        # 为了保持精准，建议角色间测距也使用视觉中心
        r1 = self._get_hitbox_rect()
        r2 = target._get_hitbox_rect()
        
        cx1, cy1 = (r1[0] + r1[2]) / 2.0, (r1[1] + r1[3]) / 2.0
        cx2, cy2 = (r2[0] + r2[2]) / 2.0, (r2[1] + r2[3]) / 2.0
        
        dx = cx1 - cx2
        dy = cy1 - cy2
        return math.sqrt(dx**2 + dy**2)
    
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
    def scale(self):
        return self._scale
    @scale.setter
    def scale(self,value):
        self.set_scale(value)

    @property
    def layer(self):
        return self._layer
    @layer.setter
    def layer(self, value):
        """学生可以手动设置层级，例如 hero.layer = 10"""
        self._layer = value
        self._send_command("UPDATE", {"id": self.id, "layer": value})

    # ---------- 内部调用 ----------
    def _resolve_path(self, filename, category):
        """通用路径解析：工程根目录优先，其次是 assets/分类/ """
        if os.path.exists(filename):
            return filename
        
        # 预留支持：assets/sprites/ 或 assets/sounds/ 等
        guessed_path = os.path.join("assets", category, filename)
        if os.path.exists(guessed_path):
            return guessed_path
            
        return filename # 实在找不到就返回原名，让错误显现出来
    def _setup_hitbox(self):
        """通用型高性能采样：支持任何尺寸图片，自动定位内容重心"""
        from PySide6.QtCore import QRectF

        if (hasattr(self, '_content_w') and self._cached_image == self.image):
            return self._cached_hitbox

        try:
            with Image.open(self.image) as img:
                self._orig_w, self._orig_h = img.size
                # 转换为 RGBA 确保 getbbox 能正常工作
                bbox = img.convert("RGBA").getbbox()
                
                if bbox:
                    l, t, r, b = bbox
                    self._content_w = r - l
                    self._content_h = b - t
                    
                    # 🚀 算法核心：计算内容的中心点相对于图片物理中心的偏移
                    # 例如：128x128的图，内容在左上角，offset会是负值
                    self._visual_offset_x = (l + r) / 2.0 - self._orig_w / 2.0
                    self._visual_offset_y = (t + b) / 2.0 - self._orig_h / 2.0
                else:
                    # 全透明或无内容图
                    self._content_w, self._content_h = self._orig_w, self._orig_h
                    self._visual_offset_x = self._visual_offset_y = 0
                    
                self._cached_hitbox = QRectF(0, 0, self._content_w, self._content_h)
                self._cached_image = self.image
        except:
            # 兜底：防止路径错误导致崩溃
            self._content_w = self._content_h = 50
            self._visual_offset_x = self._visual_offset_y = 0
            self._cached_hitbox = QRectF(0, 0, 50, 50)
            self._cached_image = self.image

        return self._cached_hitbox

    def _get_hitbox_rect(self):
        """获取当前角色在舞台上的真实内容包围盒 [left, top, right, bottom]"""
        self._setup_hitbox() # 确保内容宽高和偏移量已算出
        
        # 1. 基础缩放比 (例如 1.0)
        base_scale = self._scale / 100.0
        
        # 2. 🚀 计算视觉中心 (考虑镜像对偏移的影响)
        # 如果图片翻转了，偏移量也要跟着翻转
        cx = self._x + (self._visual_offset_x * base_scale * self._current_scale_x)
        cy = self._y + (self._visual_offset_y * base_scale)
        
        # 3. 计算内容的大小 (必须使用 abs 保证宽高为正数)
        # 使用 self.hitbox_scale 允许微调，如果你觉得太严了，可以把 self.hitbox_scale 设为 1.0
        ratio = base_scale * self.hitbox_scale
        hw = (self._content_w * ratio) / 2.0
        hh = (self._content_h * ratio) / 2.0
    
        return [cx - hw, cy - hh, cx + hw, cy + hh]

    def _update_transform(self):
        """统一处理旋转、缩放和镜像逻辑"""
        display_angle = self._angle
        # 计算基础缩放比例（百分比转为小数）
        base_scale = self._scale / 100.0
        
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
            "scale_y": final_scale_y,
            "vox": self._visual_offset_x,
            "voy": self._visual_offset_y,
            "cw": self._content_w,
            "ch": self._content_h
            
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
    global _PRESSED_KEYS, _MOUSE_STATE
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

                # 🚀 新增鼠标事件处理
            elif clean_line.startswith("M_DOWN:"):
                old_value = _MOUSE_STATE["down"]
                _MOUSE_STATE["down"] = True
                
            elif clean_line.startswith("M_UP:"):
                old_value = _MOUSE_STATE["down"]
                _MOUSE_STATE["down"] = False
            
            elif clean_line.startswith("M_MOVE:"):        
                # 解析 M_MOVE:320.5,240.0
                pos_str = clean_line.split(":", 1)[1]
                mx_s, my_s = pos_str.split(",")
                _MOUSE_STATE["x"] = float(mx_s)
                _MOUSE_STATE["y"] = float(my_s)
        except:
            time.sleep(0.01)

# 确保线程启动 (代码末尾)
threading.Thread(target=_input_sync_listener, daemon=True).start()


def mouse_down():
    """判断鼠标是否按下"""
    # 🚀 不需要 global 声明，因为只读取不赋值
    return _MOUSE_STATE["down"]

def mouse_pressed():
    """单次检测：只有在按下的那一帧返回 True"""
    # 如果当前按下，且上一帧没按，说明是刚刚按下的
    return _MOUSE_STATE["down"] and not _MOUSE_STATE["last_down"]

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

def set_background(image_name):
    """
    设置舞台背景图
    """
    image_path = os.path.join("assets", "images", image_name)
    # 背景图使用固定的 ID，确保重复调用时是“替换”而不是“叠加”
    packet = {
        "type": "CREATE",
        "id": "STAGE_BACKGROUND", 
        "data": {
            "image": image_path,
            "x": 320,  # 自动居中
            "y": 240,
            "angle": 0,
            "scale_x": 1.0,
            "scale_y": 1.0,
            "z_value": -1000, # 🚀 核心：给一个极小的层级，确保在最底层
            "type": "background"
        }
    }
    print(json.dumps(packet), flush=True)

    
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
    global _PERF_STATS,_MOUSE_STATE
    _MOUSE_STATE["down"] = False
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
        
        # 每一帧结束时，记录当前状态供下一帧对比(鼠标持续按下还是单次按下)
        _MOUSE_STATE["last_down"] = _MOUSE_STATE["down"]


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