<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import JSZip from 'jszip'
import { useFileDialog } from '../../composables/useFileDialog'
import { useResourceStore } from '../../stores/resource'
import { useEditorStore } from '../../stores/editor'
import { useProjectStore } from '../../stores/project'
import { svgToPngBlob } from '../../utils/imageConvert'

import iconFileUpload from '../../assets/icons/icon--file-upload.svg'
import iconPaint from '../../assets/icons/icon--paint.svg'
import iconSelectSprite from '../../assets/icons/icon--select--sprite.svg'
import iconSpriteUpload from '../../assets/icons/sprite_upload.svg'
import iconMapUpload from '../../assets/icons/map_upload.svg'
import iconAddSound from '../../assets/icons/add_sound.svg'
import iconPythonFile from '../../assets/icons/python_file_1.svg'
import iconEdit from '../../assets/icons/编辑.svg'

const props = defineProps<{
  type: 'sprite' | 'map' | 'sound' | 'code'
}>()

const emit = defineEmits<{
  uploaded: [type: string, name: string, content?: string]
  openLibrary: [type: string]
  createMap: []
  importMapImage: [name: string, data: number[]]
}>()

const resourceStore = useResourceStore()
const editorStore = useEditorStore()
const projectStore = useProjectStore()
const fileDialog = useFileDialog()
const menuOpen = ref(false)

const acceptMap: Record<string, string> = {
  sprite: '.bgs,.png,.jpg,.gif,.jpeg,.svg',
  map: '.bgm,.json,.info,.png,.jpg,.jpeg,.gif,.bmp,.webp,.svg',
  sound: '.wav,.mp3,.ogg,.flac',
  code: '.py',
}

const menuConfig: Record<string, { items: { key: string; icon: string }[]; uploadIcon: string }> = {
  sprite: {
    items: [
      { key: 'import', icon: iconFileUpload },
      { key: 'paint', icon: iconPaint },
      { key: 'library', icon: iconSelectSprite },
    ],
    uploadIcon: iconSpriteUpload,
  },
  map: {
    items: [
      { key: 'import', icon: iconFileUpload },
      { key: 'create', icon: iconEdit },
      { key: 'library', icon: iconSelectSprite },
    ],
    uploadIcon: iconMapUpload,
  },
  sound: {
    items: [
      { key: 'import', icon: iconFileUpload },
      { key: 'library', icon: iconSelectSprite },
    ],
    uploadIcon: iconAddSound,
  },
  code: {
    items: [
      { key: 'import', icon: iconFileUpload },
      { key: 'new', icon: iconPythonFile },
    ],
    uploadIcon: iconPythonFile,
  },
}

const config = computed(() => menuConfig[props.type])

// 抽屉按钮功能提示文案（Scratch 风格 tooltip，悬停时显示在按钮左侧）
const tipTextMap: Record<string, Record<string, string>> = {
  sprite: { import: '上传角色', paint: '选择角色', library: '选择角色' },
  map: { import: '上传地图', create: '创建地图', library: '选择地图' },
  sound: { import: '上传声音', library: '选择声音' },
  code: { import: '上传代码文件', new: '新建代码文件' },
}
const tipState = ref<{ text: string; top: number } | null>(null)

function showTip(e: MouseEvent, key: string) {
  const btn = e.currentTarget as HTMLElement
  const texts = tipTextMap[props.type]
  if (!texts || !texts[key]) { tipState.value = null; return }
  // drawer-btn 的 offsetParent 是 .upload-drawer（absolute），offsetTop 即相对抽屉容器的位置
  tipState.value = { text: texts[key], top: btn.offsetTop + btn.offsetHeight / 2 }
}
function hideTip() {
  tipState.value = null
}
watch(menuOpen, (open) => {
  if (!open) hideTip()
})

const IMAGE_EXTS = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp']
function isImageFile(filename: string): boolean {
  const lower = filename.toLowerCase()
  return IMAGE_EXTS.some(ext => lower.endsWith(ext))
}

async function handleAction(key: string) {
  menuOpen.value = false
  switch (key) {
    case 'import': {
      const result = await fileDialog.openFile(acceptMap[props.type])
      if (!result) return

      if (props.type === 'sprite' && result.name.toLowerCase().endsWith('.svg')) {
        // SVG 角色：引擎（Pillow）不支持 SVG，导入时栅格化为 PNG 再入库
        try {
          const pngBlob = await svgToPngBlob(result.file)
          const baseName = result.name.replace(/\.svg$/i, '')
          const projectRoot = projectStore.root
          if (projectRoot) {
            const projectPath = `${projectRoot}/assets/sprites/${baseName}.png`
            await invoke('write_binary', {
              path: projectPath,
              data: Array.from(new Uint8Array(await pngBlob.arrayBuffer())),
            })
            resourceStore.addItem({ name: baseName, type: 'sprite', path: projectPath })
            emit('uploaded', 'sprite', baseName)
          } else {
            console.warn('[UploadDrawer] 项目目录未就绪，无法导入 SVG 角色')
          }
        } catch (e) {
          console.error('[UploadDrawer] SVG 转 PNG 失败:', e)
        }
      } else if (props.type === 'sprite' && result.name.toLowerCase().endsWith('.bgs')) {
        // .bgs 文件：解压到项目目录（与精灵库选择流程一致）
        // 引擎从 assets/sprites/<名字>/ 加载角色，缩略图也依赖磁盘路径
        try {
          const zip = await JSZip.loadAsync(result.file)
          const configEntry = zip.file('config.json')
          if (!configEntry) {
            console.error('[UploadDrawer] .bgs 缺少 config.json:', result.name)
            return
          }
          const config = JSON.parse(await configEntry.async('text'))
          const spriteName = config.name || result.name.replace(/\.bgs$/i, '')
          const projectRoot = projectStore.root
          if (!projectRoot) {
            console.warn('[UploadDrawer] 项目目录未就绪，无法导入 .bgs 角色')
            return
          }
          // 先把 .bgs 写到项目目录，再用 Rust 命令解压，最后删除临时 .bgs 文件
          const tmpBgsPath = `${projectRoot}/assets/sprites/${spriteName}.bgs`
          await invoke('write_binary', {
            path: tmpBgsPath,
            data: Array.from(new Uint8Array(await result.file.arrayBuffer())),
          })
          try {
            await invoke('extract_bgs_to_project', {
              bgsPath: tmpBgsPath,
              projectRoot,
              spriteName,
            })
          } finally {
            // 临时 .bgs 必须删除：项目重载时会把 assets/sprites 下所有条目当角色列出
            await invoke('delete_path', { path: tmpBgsPath }).catch(() => {})
          }
          resourceStore.addItem({
            name: spriteName,
            type: 'sprite',
            path: `${projectRoot}/assets/sprites/${spriteName}`,
          })
          emit('uploaded', 'sprite', spriteName)
        } catch (e) {
          console.error('[UploadDrawer] 导入 .bgs 失败:', e)
        }
      } else if (props.type === 'sprite' && isImageFile(result.name)) {
        // 图片文件：复制到项目目录
        const projectRoot = projectStore.root
        if (projectRoot) {
          try {
            const arrayBuffer = await result.file.arrayBuffer()
            const uint8Array = new Uint8Array(arrayBuffer)
            const relativePath = `assets/sprites/${result.name}`
            // write_binary 返回 ()，路径需自行拼接
            const projectPath = `${projectRoot}/${relativePath}`
            await invoke('write_binary', {
              path: projectPath,
              data: Array.from(uint8Array),
            })
            resourceStore.addItem({ name: result.name.replace(/\.[^.]+$/, ''), type: 'sprite', path: projectPath })
            emit('uploaded', 'sprite', result.name)
          } catch (e) {
            console.error('[UploadDrawer] 复制图片文件失败:', e)
            const objectUrl = URL.createObjectURL(result.file)
            resourceStore.addItem({ name: result.name, type: 'sprite', path: objectUrl })
            emit('uploaded', 'sprite', result.name)
          }
        } else {
          const objectUrl = URL.createObjectURL(result.file)
          resourceStore.addItem({ name: result.name, type: 'sprite', path: objectUrl })
          emit('uploaded', 'sprite', result.name)
        }
      } else if (props.type === 'map' && (isImageFile(result.name) || result.name.toLowerCase().endsWith('.svg'))) {
        // 图片文件（含 SVG）：读取字节交给主布局创建图像模式地图（图片直接作为地图使用）
        try {
          const arrayBuffer = await result.file.arrayBuffer()
          emit('importMapImage', result.name, Array.from(new Uint8Array(arrayBuffer)))
        } catch (e) {
          console.error('[UploadDrawer] 读取图片文件失败:', e)
        }
      } else if (props.type === 'code') {
        resourceStore.addItem({ name: result.name, type: 'code', path: result.name, content: result.content || undefined })
        editorStore.createTab(result.name, result.name, result.content || '')
        emit('uploaded', 'code', result.name, result.content || undefined)
      } else {
        // 声音文件：复制到项目目录
        if (props.type === 'sound') {
          const projectRoot = projectStore.root
          if (projectRoot) {
            try {
              // 读取文件内容为 ArrayBuffer
              const arrayBuffer = await result.file.arrayBuffer()
              const uint8Array = new Uint8Array(arrayBuffer)
              
              // 写入项目目录
              const relativePath = `assets/sounds/${result.name}`
              await invoke('write_binary', {
                path: `${projectRoot}/${relativePath}`,
                data: Array.from(uint8Array),
              })
              
              // 添加到资源管理器
              const projectPath = `${projectRoot}/${relativePath}`
              resourceStore.addItem({ name: result.name, type: 'sound', path: projectPath })
              emit('uploaded', 'sound', result.name)
            } catch (e) {
              console.error('[UploadDrawer] 复制声音文件失败:', e)
              // 回退：使用 object URL
              const objectUrl = URL.createObjectURL(result.file)
              resourceStore.addItem({ name: result.name, type: 'sound', path: objectUrl })
              emit('uploaded', 'sound', result.name)
            }
          } else {
            // 没有项目目录，使用 object URL
            const objectUrl = URL.createObjectURL(result.file)
            resourceStore.addItem({ name: result.name, type: 'sound', path: objectUrl })
            emit('uploaded', 'sound', result.name)
          }
        } else {
          // 其他图片文件：直接添加
          const objectUrl = URL.createObjectURL(result.file)
          resourceStore.addItem({ name: result.name, type: props.type, path: objectUrl })
          emit('uploaded', props.type, result.name)
        }
      }
      break
    }
    case 'new':
      if (props.type === 'code') {
        editorStore.createTab('未命名.py', '')
      }
      break
    case 'library':
    case 'paint':
    case 'create':
      if (props.type === 'map' && key === 'create') {
        emit('createMap')
      } else {
        emit('openLibrary', props.type)
      }
      break
  }
}
</script>

<template>
  <div class="upload-drawer" @mouseenter="menuOpen = true" @mouseleave="menuOpen = false">
    <!-- 绿色抽屉菜单 -->
    <Transition name="drawer">
      <div v-show="menuOpen" class="drawer-menu">
        <button
          v-for="(item, idx) in config.items"
          :key="item.key"
          class="drawer-btn"
          :class="{ 'drawer-btn-first': idx === 0 }"
          @click="handleAction(item.key)"
          @mouseenter="showTip($event, item.key)"
          @mouseleave="hideTip"
        >
          <img :src="item.icon" class="drawer-btn-icon" />
        </button>
        <!-- 填充抽屉和按钮之间的缝隙 -->
        <div class="drawer-gap-fill"></div>
      </div>
    </Transition>

    <!-- Scratch 风格功能提示：显示在悬停按钮左侧 -->
    <Transition name="tip">
      <div v-if="tipState" class="drawer-tip" :style="{ top: tipState.top + 'px' }">
        {{ tipState.text }}
        <span class="drawer-tip-arrow"></span>
      </div>
    </Transition>

    <!-- 上传按钮 -->
    <button class="upload-btn" @click="menuOpen = !menuOpen">
      <img :src="config.uploadIcon" class="upload-icon" />
    </button>
  </div>
</template>

<style scoped>
.upload-drawer {
  position: absolute;
  bottom: 0;
  right: 8px;
  width: 50px;
  display: flex;
  flex-direction: column;
  align-items: center;
  z-index: 20;
}

/* 绿色抽屉菜单 */
.drawer-menu {
  display: flex;
  flex-direction: column;
  width: 30px;
  background: #4B9B5C;
  border-top-left-radius: 15px;
  border-top-right-radius: 15px;
  overflow: hidden;
  margin-bottom: -25px;
  z-index: 1;
}

.drawer-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  background: transparent;
  border: none;
  cursor: pointer;
  transition: background 0.15s;
  padding: 0;
  margin: 0;
}
.drawer-btn:hover {
  background: #5bc772;
}
.drawer-btn-first:hover {
  border-top-left-radius: 15px;
  border-top-right-radius: 15px;
}

.drawer-btn-icon {
  width: 20px;
  height: 20px;
}

/* 缝隙填充 */
.drawer-gap-fill {
  width: 100%;
  height: 20px;
  background: #4B9B5C;
}

/* Scratch 风格功能提示气泡（显示在悬停按钮左侧） */
.drawer-tip {
  position: absolute;
  right: 48px;
  transform: translateY(-50%);
  background: #5bc772;
  color: #fff;
  font-size: 12px;
  line-height: 1;
  padding: 7px 12px;
  border-radius: 8px;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.35);
  pointer-events: none;
  z-index: 50;
}
/* 气泡右侧小箭头，指向按钮 */
.drawer-tip-arrow {
  position: absolute;
  left: 100%;
  top: 50%;
  transform: translateY(-50%);
  border-top: 5px solid transparent;
  border-bottom: 5px solid transparent;
  border-left: 6px solid #5bc772;
}
.tip-enter-active,
.tip-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}
.tip-enter-from,
.tip-leave-to {
  opacity: 0;
  transform: translateY(-50%) translateX(-4px);
}

/* 上传按钮 */
.upload-btn {
  width: 50px;
  height: 50px;
  background: transparent;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  margin: 0;
  transition: transform 0.2s;
  position: relative;
  z-index: 2;
}
.upload-btn:hover {
  transform: scale(1.05);
}

.upload-icon {
  width: 40px;
  height: 40px;
}

/* 滑入动画 */
.drawer-enter-active {
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  transform-origin: bottom center;
}
.drawer-leave-active {
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  transform-origin: bottom center;
}
.drawer-enter-from {
  opacity: 0;
  transform: scaleY(0);
}
.drawer-leave-to {
  opacity: 0;
  transform: scaleY(0);
}
</style>
