/**
 * 帮助文档打开工具
 * 文档站部署在远程服务器（kadahub.cn 的 /help/ 子目录）上，客户端只打开网址：
 * 这样文档更新与客户端版本完全解耦，不需要发版。
 */

import { open } from '@tauri-apps/plugin-shell'

// 文档站地址（服务器或路径变了只改这一行）
const HELP_DOCS_URL = 'http://kadahub.cn/help/'

// 开发模式下打开本地文档热重载服务（pnpm docs:dev）
const DEV_DOCS_URL = 'http://localhost:4322/'

/**
 * 在系统默认浏览器中打开帮助文档
 */
export async function openHelpDocs(): Promise<void> {
  const url = import.meta.env.DEV ? DEV_DOCS_URL : HELP_DOCS_URL
  await open(url)
}
