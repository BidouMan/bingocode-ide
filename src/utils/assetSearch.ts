import type { MapResourceItem } from '../stores/mapResourceLib'

/** 全角字符转半角：学生用中文输入法时常打出全角空格/字母 */
function toHalfWidth(input: string): string {
  return input
    .replace(/[\uFF01-\uFF5E]/g, ch => String.fromCharCode(ch.charCodeAt(0) - 0xfee0))
    .replace(/\u3000/g, ' ')
}

/** 归一化：小写 + 半角 + 下划线与连字符视作空格 */
function normalize(input: string): string {
  return toHalfWidth(input).toLowerCase().replace(/[_\-]+/g, ' ').replace(/\s+/g, ' ').trim()
}

/** 空格分词（AND 语义：每个词都要命中） */
export function splitQuery(query: string): string[] {
  const normalized = normalize(query)
  if (!normalized) return []
  return normalized.split(' ').filter(Boolean)
}

const LETTERS_ONLY = /^[a-z]+$/

/** 单个词在条目上的得分；0 表示未命中 */
function scoreToken(item: MapResourceItem, token: string): number {
  const name = normalize(item.name)
  const fileName = normalize(item.file.replace(/[.][^.]+$/, ''))
  const group = normalize(item.group)
  const tags = item.tags.map(normalize)

  if (name === token) return 100
  if (fileName === token) return 95
  if (name.startsWith(token)) return 90
  if (fileName.startsWith(token)) return 82
  if (name.includes(token)) return 78
  if (tags.some(t => t === token)) return 72
  if (tags.some(t => t.includes(token))) return 66
  if (group.includes(token)) return 55

  // 拼音匹配只接受纯字母输入，且至少两个字符，避免单字母命中一大片
  if (LETTERS_ONLY.test(token) && token.length >= 2) {
    if (item.py === token) return 60
    if (item.py.startsWith(token)) return 58
    if (item.pyi === token) return 56
    if (item.pyi.startsWith(token)) return 52
    if (item.py.includes(token)) return 50
    if (item.pyi.includes(token)) return 45
  }

  if (fileName.includes(token)) return 40
  return 0
}

/**
 * 检索 + 排序：所有词都命中才算命中，得分累加；
 * 同分按名称排序，保证结果稳定可预期。
 */
export function searchItems(list: MapResourceItem[], query: string): MapResourceItem[] {
  const tokens = splitQuery(query)
  if (tokens.length === 0) return list

  const scored: Array<{ item: MapResourceItem; score: number }> = []
  for (const item of list) {
    let total = 0
    let matched = true
    for (const token of tokens) {
      const s = scoreToken(item, token)
      if (s === 0) {
        matched = false
        break
      }
      total += s
    }
    if (matched) scored.push({ item, score: total })
  }

  scored.sort(
    (a, b) => b.score - a.score || a.item.name.localeCompare(b.item.name, 'zh-CN', { numeric: true }),
  )
  return scored.map(s => s.item)
}
