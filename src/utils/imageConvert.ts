// SVG 栅格化工具：引擎（Pillow）不支持 SVG，角色帧图必须在导入时一次性转为 PNG，
// 转换后全链路（编辑器/缩略图/引擎运行）都是普通 PNG，运行时零额外开销

interface SvgSize {
  width: number
  height: number
}

// 从 SVG 源码提取固有尺寸：width/height 属性优先，否则取 viewBox
function extractSvgSize(svgText: string): SvgSize {
  const wMatch = svgText.match(/width\s*=\s*["']\s*([\d.]+)/i)
  const hMatch = svgText.match(/height\s*=\s*["']\s*([\d.]+)/i)
  if (wMatch && hMatch) {
    const width = parseFloat(wMatch[1])
    const height = parseFloat(hMatch[1])
    if (width > 0 && height > 0) return { width, height }
  }
  const vb = svgText.match(/viewBox\s*=\s*["']\s*-?[\d.]+[\s,]+-?[\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)/i)
  if (vb) {
    const width = parseFloat(vb[1])
    const height = parseFloat(vb[2])
    if (width > 0 && height > 0) return { width, height }
  }
  return { width: 64, height: 64 }
}

export async function svgToPngBlob(svgBlob: Blob): Promise<Blob> {
  const svgText = await svgBlob.text()
  const { width, height } = extractSvgSize(svgText)

  const svgUrl = URL.createObjectURL(svgBlob)
  try {
    const img = new Image()
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve()
      img.onerror = () => reject(new Error('SVG 解码失败'))
      img.src = svgUrl
    })
    const canvas = document.createElement('canvas')
    canvas.width = Math.max(1, Math.round(width))
    canvas.height = Math.max(1, Math.round(height))
    const ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Canvas 2D 上下文不可用')
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
    return await new Promise<Blob>((resolve, reject) => {
      canvas.toBlob(b => (b ? resolve(b) : reject(new Error('PNG 导出失败'))), 'image/png')
    })
  } finally {
    URL.revokeObjectURL(svgUrl)
  }
}
