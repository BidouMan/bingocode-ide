/**
 * 图块 GID 的翻转标志（Tiled 标准）
 *
 * 图块格子仍然只存一个数字（GID），翻转信息放在 GID 的高位：
 *   0x80000000 = 水平镜像（左右翻转）
 *   0x40000000 = 垂直镜像（上下翻转）
 *   低 29 位    = 基础 GID（firstgid + 图块序号）
 *
 * 这样翻转会跟着格子一起移动、复制、撤销，旧地图没有高位标记天然兼容。
 * 注意：不能用 JS 位运算（0x80000000 按位与会变成负数），统一用取模/除法。
 * 引擎 engine/map_runtime.py 的 _split_tile_gid 与此完全一致。
 */
export const TILE_FLIP_H = 0x80000000
export const TILE_FLIP_V = 0x40000000
/** 基础 GID 的上界（也是取模常数） */
const TILE_BASE_GID_MOD = 0x20000000

/** 去掉翻转标志，得到查图块集用的基础 GID */
export function tileBaseGid(gid: number): number {
  return gid % TILE_BASE_GID_MOD
}

/** 读取格子的翻转标志 */
export function tileFlipFlags(gid: number): { flipH: boolean; flipV: boolean } {
  return {
    flipH: (Math.floor(gid / TILE_FLIP_H) % 2) === 1,
    flipV: (Math.floor(gid / TILE_FLIP_V) % 2) === 1,
  }
}

/** 把翻转标志写进 GID（重复写同一标志不会叠加） */
export function withTileFlip(gid: number, flipH: boolean, flipV: boolean): number {
  const base = tileBaseGid(gid)
  return base + (flipH ? TILE_FLIP_H : 0) + (flipV ? TILE_FLIP_V : 0)
}
