/**
 * 绘制编辑器文字工具字体（HarmonyOS Sans SC，支持中文）。
 * 文件由 Vite publicDir（engine/assets）以 /fonts/ 静态服务。
 * 已子集化为 WOFF2（GB2312 常用字集，约 0.9M，原 TTF 7.8M）：
 * 生僻字自动回退到系统字体（PingFang SC / Microsoft YaHei），不影响使用。
 * 默认用 Medium 字重：Regular 在画布 40px 下偏细、可读性差。
 */
export const PAINT_FONT_FAMILY = 'HarmonyOS Sans SC'
export const PAINT_FONT_MEDIUM_URL = '/fonts/HarmonyOS_Sans_SC_Medium.woff2'

/** 默认字号（对齐 Scratch text-tool） */
export const PAINT_TEXT_SIZE = 40
/** 行高比例：leading/fontSize（Scratch 实验值 46.15/40 ≈ 1.154） */
export const PAINT_TEXT_LEADING_RATIO = 46.15 / 40

let fontPromise: Promise<void> | null = null

/** 幂等加载绘制字体（Medium；失败降级系统字体，不阻断文字工具） */
export function ensurePaintFont(): Promise<void> {
  if (fontPromise) return fontPromise
  fontPromise = (async () => {
    try {
      const face = new FontFace(PAINT_FONT_FAMILY, `url(${PAINT_FONT_MEDIUM_URL})`, {
        weight: '500',
      })
      await face.load()
      document.fonts.add(face)
    } catch (e) {
      console.error('[Paint] 加载绘制字体失败:', e)
    }
  })()
  return fontPromise
}
