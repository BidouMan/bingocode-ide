/**
 * 项目路径比较工具。
 * Windows 上 Tauri 可能返回反斜杠或带 `\\?\` 扩展前缀的路径，且路径大小写不敏感；
 * 直接字符串比较会漏判（例如文件浏览器选中的目录大小写与项目根不同）。
 */

const IS_WINDOWS =
  typeof navigator !== 'undefined' &&
  /Windows|Win32|Win64/i.test(navigator.userAgent || navigator.platform || '')

/** 统一分隔符、去掉 Windows 扩展前缀；Windows 下忽略大小写 */
export function normalizeComparePath(p: string): string {
  const s = p.replace(/\\/g, '/').replace(/^\/\/\?\//, '')
  return IS_WINDOWS ? s.toLowerCase() : s
}

/** 判断某个文件路径是否位于 `<项目根>/code/` 下 */
export function isProjectCodePath(path: string, projectRoot: string): boolean {
  if (!path || !projectRoot) return false
  const root = normalizeComparePath(projectRoot).replace(/\/+$/, '')
  return normalizeComparePath(path).startsWith(`${root}/code/`)
}

/** 两个路径是否指向同一个位置 */
export function samePath(a: string, b: string): boolean {
  if (!a || !b) return false
  return normalizeComparePath(a) === normalizeComparePath(b)
}

/** path 是否等于 parent 或位于 parent 目录下 */
export function isUnderPath(path: string, parent: string): boolean {
  if (!path || !parent) return false
  const base = normalizeComparePath(parent).replace(/\/+$/, '')
  const p = normalizeComparePath(path)
  return p === base || p.startsWith(`${base}/`)
}

/**
 * 取路径最后一段（文件名/目录名）。
 * 注意：不能直接用 split('/')——Windows 的对话框与 Tauri 会返回反斜杠路径，
 * 那样会拿到整条路径当文件名。
 */
export function baseName(p: string): string {
  if (!p) return ''
  const parts = p.replace(/\\/g, '/').replace(/\/+$/, '').split('/')
  return parts[parts.length - 1] || ''
}

/** 取路径所在目录 */
export function dirName(p: string): string {
  if (!p) return ''
  const normalized = p.replace(/\\/g, '/')
  const idx = normalized.lastIndexOf('/')
  if (idx <= 0) return ''
  return normalized.slice(0, idx)
}
