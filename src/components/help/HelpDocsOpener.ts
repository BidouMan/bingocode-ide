/**
 * 帮助文档打开工具
 * 用于在系统浏览器中打开本地 HTML 帮助文档
 */

import { invoke } from '@tauri-apps/api/core'

/**
 * 打开帮助文档
 * 在系统默认浏览器中打开本地 HTML 文档
 */
export async function openHelpDocs(): Promise<void> {
  // 获取项目根目录
  const projectRoot = await invoke<string>('get_project_root')
  const indexPath = `${projectRoot}/docs/dist/index.html`

  console.log('项目根目录:', projectRoot)
  console.log('文档路径:', indexPath)

  // 使用系统默认应用打开文件
  const result = await invoke<string>('open_file_in_browser', { path: indexPath })
  console.log('打开成功:', result)
}
