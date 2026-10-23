/**
 * 角色文件导入：资源抽屉「上传角色」与角色编辑器空状态共用。
 * 支持 .bgs / .bsf 精灵包、普通图片、SVG（栅格化为 PNG 再入库）。
 */
import { invoke } from '@tauri-apps/api/core'
import JSZip from 'jszip'
import { useResourceStore } from '../stores/resource'
import { useProjectStore } from '../stores/project'
import { svgToPngBlob } from '../utils/imageConvert'

/** 角色上传可选的文件类型 */
export const SPRITE_ACCEPT = '.bgs,.bsf,.png,.jpg,.gif,.jpeg,.svg'

const IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']

/** 是否为常见位图格式（SVG 单独处理） */
export function isImageFile(filename: string): boolean {
  const lower = filename.toLowerCase()
  return IMAGE_EXTS.some(ext => lower.endsWith(ext))
}

/**
 * 导入单个角色文件到项目目录，返回新资源 id；失败或项目目录未就绪返回 null。
 */
export async function importSpriteFile(file: File, fileName: string): Promise<string | null> {
  const resourceStore = useResourceStore()
  const projectStore = useProjectStore()
  const projectRoot = projectStore.root
  const lowerName = fileName.toLowerCase()

  try {
    // SVG 角色：引擎（Pillow）不支持 SVG，导入时栅格化为 PNG 再入库
    if (lowerName.endsWith('.svg')) {
      if (!projectRoot) {
        console.warn('[SpriteImport] 项目目录未就绪，无法导入 SVG 角色')
        return null
      }
      const pngBlob = await svgToPngBlob(file)
      // 默认名字统一为「角色N」顺序名，磁盘文件名与 store 名字保持一致（引擎按名字查找）
      const spriteName = resourceStore.nextSequentialName('sprite', '角色')
      const projectPath = `${projectRoot}/assets/sprites/${spriteName}.png`
      await invoke('write_binary', {
        path: projectPath,
        data: Array.from(new Uint8Array(await pngBlob.arrayBuffer())),
      })
      return resourceStore.addItem({ name: spriteName, type: 'sprite', path: projectPath })
    }

    // .bgs / .bsf 包文件：解压到项目目录（与精灵库选择流程一致）
    // 引擎从 assets/sprites/<名字>/ 加载角色，缩略图也依赖磁盘路径
    if (lowerName.endsWith('.bgs') || lowerName.endsWith('.bsf')) {
      const isBsf = lowerName.endsWith('.bsf')
      const zip = await JSZip.loadAsync(file)
      const metaEntry = isBsf ? zip.file('manifest.json') : zip.file('config.json')
      if (!metaEntry) {
        console.error(`[SpriteImport] ${isBsf ? '.bsf 缺少 manifest.json' : '.bgs 缺少 config.json'}:`, fileName)
        return null
      }
      if (!projectRoot) {
        console.warn(`[SpriteImport] 项目目录未就绪，无法导入 ${isBsf ? '.bsf' : '.bgs'} 角色`)
        return null
      }
      const spriteName = resourceStore.nextSequentialName('sprite', '角色')
      // 先把包文件写到项目目录，再用 Rust 命令解压，最后删除临时文件
      const tmpPkgPath = `${projectRoot}/assets/sprites/${spriteName}${isBsf ? '.bsf' : '.bgs'}`
      await invoke('write_binary', {
        path: tmpPkgPath,
        data: Array.from(new Uint8Array(await file.arrayBuffer())),
      })
      try {
        await invoke('extract_bgs_to_project', {
          bgsPath: tmpPkgPath,
          projectRoot,
          spriteName,
        })
      } finally {
        // 临时包文件必须删除：项目重载时会把 assets/sprites 下所有条目当角色列出
        await invoke('delete_path', { path: tmpPkgPath }).catch(() => {})
      }
      return resourceStore.addItem({
        name: spriteName,
        type: 'sprite',
        path: `${projectRoot}/assets/sprites/${spriteName}`,
      })
    }

    // 普通图片：复制到项目目录（磁盘文件名与 store 名字一致，保留原扩展名供引擎查找）
    if (isImageFile(fileName)) {
      const spriteName = resourceStore.nextSequentialName('sprite', '角色')
      const ext = fileName.match(/\.[^.]+$/)?.[0] || '.png'
      if (!projectRoot) {
        const objectUrl = URL.createObjectURL(file)
        return resourceStore.addItem({ name: spriteName, type: 'sprite', path: objectUrl })
      }
      try {
        const uint8Array = new Uint8Array(await file.arrayBuffer())
        const projectPath = `${projectRoot}/assets/sprites/${spriteName}${ext}`
        await invoke('write_binary', { path: projectPath, data: Array.from(uint8Array) })
        return resourceStore.addItem({ name: spriteName, type: 'sprite', path: projectPath })
      } catch (e) {
        console.error('[SpriteImport] 复制图片文件失败:', e)
        const objectUrl = URL.createObjectURL(file)
        return resourceStore.addItem({ name: spriteName, type: 'sprite', path: objectUrl })
      }
    }

    return null
  } catch (e) {
    console.error('[SpriteImport] 导入角色失败:', e)
    return null
  }
}
