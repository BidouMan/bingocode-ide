/**
 * 坐标系转换：用户空间（对外）↔ 世界空间（对内）
 *
 * 世界空间：原点在舞台左上角，x 向右、y 向下（与 PixiJS 渲染一致）。
 *          地图数据、碰撞体、图层位置、渲染全部用它。
 * 用户空间：原点在地图左下角，x 向右、y 向上，角度逆时针为正。
 *          只出现在学生会看到的数字上（坐标读数、属性面板、教学图）。
 *
 * 约定：整个前端只有本文件允许出现 y / 角度取反的符号。
 * 后端对应实现：engine/models/coords.py
 */

export const STAGE_W = 640
export const STAGE_H = 480

/** 用户坐标原点在世界空间中的位置（y 原点跟随地图高度，地图底部 = y 0） */
export const USER_ORIGIN_X = 0
export let USER_ORIGIN_Y: number = STAGE_H

/** 更新用户坐标 y 原点（地图加载/改尺寸时传地图像素高度） */
export function setUserOriginY(worldY: number): void {
  USER_ORIGIN_Y = worldY
}

/** 世界 x → 用户 x */
export function toUserX(xWorld: number): number {
  return xWorld - USER_ORIGIN_X
}

/** 用户 x → 世界 x */
export function toWorldX(xUser: number): number {
  return xUser + USER_ORIGIN_X
}

/** 世界 y → 用户 y（y 向下翻成 y 向上） */
export function toUserY(yWorld: number): number {
  return USER_ORIGIN_Y - yWorld
}

/** 用户 y → 世界 y（y 向上翻成 y 向下） */
export function toWorldY(yUser: number): number {
  return USER_ORIGIN_Y - yUser
}

/** 世界角度（顺时针为正）→ 用户角度（逆时针为正） */
export function toUserAngle(angleWorld: number): number {
  return -angleWorld
}

/** 用户角度（逆时针为正）→ 世界角度（顺时针为正） */
export function toWorldAngle(angleUser: number): number {
  return -angleUser
}

/** 世界 y 增量 → 用户 y 增量（位移只翻符号，和原点在哪无关） */
export function toUserDeltaY(dyWorld: number): number {
  return -dyWorld
}

/** 用户 y 增量 → 世界 y 增量（位移只翻符号，和原点在哪无关） */
export function toWorldDeltaY(dyUser: number): number {
  return -dyUser
}
