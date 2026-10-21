/**
 * 角色缩略图归一化：裁到非透明内容框 → 等比缩放后**居中铺进固定尺寸的缩略图画布**。
 *
 * 为什么这么做：缩略图此前直接 contain 整幅画布图，画布留白因素材而异——实测内置素材
 * 内容只占画布 21%~93%（bullets_1 帧内容 14×8 藏在 68×24 画布里、props 内容 61×52 在
 * 108×108 里、cannon 内容 210×304 在 500×500 里），于是列表里有的盛满格子、有的小到
 * 看不清。现在每张缩略图都是 THUMB_SIZE² 的透明画布、内容按最长边缩放到 THUMB_CONTENT_RATIO，
 * 所以无论原素材多大，列表里视觉大小完全一致。
 *
 * 小素材（≤SMALL_ART_MAX_SIDE）放大时必须用**最近邻**：否则缩略图本身就被双线性插值糊掉了，
 * 后面再挂 image-rendering: pixelated 也救不回来（糊在像素里）。
 */
import { loadImage } from '../composables/useSpriteData'
import { contentBBox } from './bsfPacker'
import { SMALL_ART_MAX_SIDE } from './renderMode'

/** 缩略图画布边长（正方形）：所有素材共用，保证列表里视觉大小一致 */
const THUMB_SIZE = 160
/**
 * 内容最长边占缩略图的比例（含呼吸边）。
 * 0.43 是「铺满」方案（≈0.86）的一半——列表里铺满格子看着太大太挤。
 */
const THUMB_CONTENT_RATIO = 0.43

export async function normalizeSpriteThumb(src: string): Promise<string> {
  const img = await loadImage(src)
  const w = img.naturalWidth || img.width
  const h = img.naturalHeight || img.height
  if (!w || !h) return src

  try {
    // 先缩到 THUMB_SIZE 以内再找内容框：500px 素材不必全尺寸扫像素（160² 扫描量，视觉无损）
    const scanScale = Math.min(1, THUMB_SIZE / Math.max(w, h))
    const sw = Math.max(1, Math.round(w * scanScale))
    const sh = Math.max(1, Math.round(h * scanScale))
    const scan = document.createElement('canvas')
    scan.width = sw
    scan.height = sh
    scan.getContext('2d')!.drawImage(img, 0, 0, sw, sh)
    // 整幅全透明时没有内容框可用，退回整幅缩放
    const box = contentBBox(scan) ?? { x: 0, y: 0, w: sw, h: sh }

    // 内容按最长边铺进内部区，居中画进固定画布
    const inner = Math.round(THUMB_SIZE * THUMB_CONTENT_RATIO)
    const drawScale = Math.min(inner / box.w, inner / box.h)
    const dw = Math.max(1, Math.round(box.w * drawScale))
    const dh = Math.max(1, Math.round(box.h * drawScale))
    const out = document.createElement('canvas')
    out.width = THUMB_SIZE
    out.height = THUMB_SIZE
    const ctx = out.getContext('2d')!
    // 小素材（像素画）放大走最近邻，否则缩略图自己就被抹糊了
    const contentMax = Math.max(box.w, box.h) / scanScale
    ctx.imageSmoothingEnabled = contentMax > SMALL_ART_MAX_SIDE
    ctx.drawImage(
      scan,
      box.x, box.y, box.w, box.h,
      Math.round((THUMB_SIZE - dw) / 2), Math.round((THUMB_SIZE - dh) / 2), dw, dh,
    )

    return out.toDataURL('image/png')
  } catch (e) {
    // 解码/画布异常（异常编码、超大尺寸等）：退回原图，别让列表整块空掉
    console.warn('[spriteThumb] 缩略图归一化失败，使用原图:', e)
    return src
  }
}
