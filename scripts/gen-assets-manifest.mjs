#!/usr/bin/env node
/**
 * 生成内置素材清单 engine/assets/manifest.json。
 *
 * 为什么需要：Windows 的 NSIS 是覆盖安装，只覆盖同名文件，发布包里删掉的素材
 * 会一直留在安装目录，被素材库扫描出来。有了清单，正式包只认「本版本实际打包」
 * 的文件，残留的旧素材既不会显示，也会被后台清理掉。
 *
 * 由 tauri.conf.json 的 beforeBuildCommand 调用（打包前生成）；dev 模式不生成也不用。
 */
import { readdir, writeFile } from 'node:fs/promises'
import { join, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = fileURLToPath(new URL('../engine/assets', import.meta.url))
const MANIFEST_NAME = 'manifest.json'
const SKIP_NAMES = new Set(['__pycache__'])

const files = []

async function walk(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    // 隐藏文件（.DS_Store 等）和清单自身不进清单
    if (entry.name.startsWith('.') || SKIP_NAMES.has(entry.name)) continue
    if (entry.name === MANIFEST_NAME && dir === root) continue
    const full = join(dir, entry.name)
    if (entry.isDirectory()) {
      await walk(full)
      continue
    }
    files.push(relative(root, full).split(sep).join('/'))
  }
}

await walk(root)
files.sort()

const manifest = {
  version: 1,
  files,
}
await writeFile(join(root, MANIFEST_NAME), `${JSON.stringify(manifest)}\n`, 'utf8')
console.log(`[assets] 已生成 manifest.json：${files.length} 个文件`)
