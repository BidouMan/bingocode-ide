# -*- coding: utf-8 -*-
"""坐标系转换：用户空间（对外）↔ 世界空间（对内）。

世界空间：原点在舞台左上角，x 向右、y 向下。
          —— 与 PixiJS 渲染完全一致，碰撞、渲染、地图数据、存档全用它。
用户空间：原点在舞台左下角，x 向右、y 向上，角度逆时针为正。
          —— 只出现在学生可见的 API 上，符合数学课本直觉。

约定：
  1. 整个项目里只有本模块允许出现 y / 角度 / 垂直速度的取反符号；
  2. 世界坐标不得直接出现在对学生的公开接口上（公开接口一律走本模块）；
  3. 引擎内部逻辑（碰撞/渲染/物理）一律直接用 _x/_y/_angle/_vy，不经过本模块。
  4. 绝对坐标用 to_*_x / to_*_y；增量与速度用 to_*_dx / to_*_dy（增量不带原点平移）。
"""

STAGE_W = 640
STAGE_H = 480

# 用户坐标原点在舞台中的世界坐标（舞台左下角）
USER_ORIGIN_X = 0.0
USER_ORIGIN_Y = float(STAGE_H)


# ---------- 绝对坐标 ----------

def to_world_x(x_user):
    """用户 x → 世界 x"""
    return x_user + USER_ORIGIN_X


def to_world_y(y_user):
    """用户 y → 世界 y（y 向上翻成 y 向下）"""
    return USER_ORIGIN_Y - y_user


def to_user_x(x_world):
    """世界 x → 用户 x"""
    return x_world - USER_ORIGIN_X


def to_user_y(y_world):
    """世界 y → 用户 y（y 向下翻成 y 向上）"""
    return USER_ORIGIN_Y - y_world


# ---------- 增量 / 速度 ----------

def to_world_dx(dx_user):
    """用户水平增量 → 世界水平增量（当前为恒等，不含原点平移）"""
    return dx_user


def to_world_dy(dy_user):
    """用户垂直增量 / 垂直速度 → 世界垂直增量（取反：向上变向下）"""
    return -dy_user


def to_user_dx(dx_world):
    """世界水平增量 → 用户水平增量（当前为恒等）"""
    return dx_world


def to_user_dy(dy_world):
    """世界垂直增量 / 垂直速度（向下为正）→ 用户垂直增量（向上为正）"""
    return -dy_world


# ---------- 角度 ----------

def to_world_angle(angle_user):
    """用户角度（逆时针为正）→ 世界角度（顺时针为正）"""
    return -angle_user


def to_user_angle(angle_world):
    """世界角度（顺时针为正）→ 用户角度（逆时针为正）"""
    return -angle_world
