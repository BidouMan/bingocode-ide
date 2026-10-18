<script setup lang="ts">
import { ref, watch } from 'vue'
import { svgToPngBlob } from '../../utils/imageConvert'

import iconFileUpload from '../../assets/icons/icon--file-upload.svg'
import iconPaint from '../../assets/icons/icon--paint.svg'
import iconSelectSprite from '../../assets/icons/icon--select--sprite.svg'
import iconSpriteUpload from '../../assets/icons/sprite_upload.svg'

/**
 * 造型列表追加抽屉（视觉与资源管理器 UploadDrawer 完全一致：悬停展开绿色抽屉）。
 * 三个动作：上传新帧（本地图片，可多选）/ 绘制新帧 / 内置素材选帧。
 * 只负责意图与选文件，实际追加逻辑由父组件（SpriteEditorView）执行。
 */
const emit = defineEmits<{
  /** 上传的图片帧（SVG 已栅格化为 PNG） */
  imported: [blobs: Blob[]]
  paint: []
  library: []
}>()

const menuOpen = ref(false)

const BUTTONS = [
  { key: 'import', icon: iconFileUpload, tip: '上传新帧' },
  { key: 'paint', icon: iconPaint, tip: '绘制新帧' },
  { key: 'library', icon: iconSelectSprite, tip: '内置素材帧' },
] as const

const tipState = ref<{ text: string; top: number } | null>(null)

function showTip(e: MouseEvent, text: string) {
  const btn = e.currentTarget as HTMLElement
  tipState.value = { text, top: btn.offsetTop + btn.offsetHeight / 2 }
}
function hideTip() {
  tipState.value = null
}
watch(menuOpen, (open) => {
  if (!open) hideTip()
})

async function onAction(key: string) {
  menuOpen.value = false
  if (key === 'paint') {
    emit('paint')
  } else if (key === 'library') {
    emit('library')
  } else {
    await pickImages()
  }
}

/** 多选本地图片 → SVG 先栅格化为 PNG（引擎 Pillow 不支持 SVG）→ 发给父组件追加 */
async function pickImages() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.png,.jpg,.jpeg,.gif,.bmp,.webp,.svg'
  input.multiple = true
  document.body.appendChild(input)
  input.onchange = async () => {
    const files = Array.from(input.files ?? [])
    input.remove()
    if (files.length === 0) return
    try {
      const blobs: Blob[] = []
      for (const f of files) {
        if (f.name.toLowerCase().endsWith('.svg')) {
          blobs.push(await svgToPngBlob(f))
        } else {
          blobs.push(f)
        }
      }
      emit('imported', blobs)
    } catch (e) {
      console.error('[FrameUploadDrawer] 读取图片失败:', e)
    }
  }
  input.oncancel = () => input.remove()
  input.click()
}
</script>

<template>
  <div class="upload-drawer" @mouseenter="menuOpen = true" @mouseleave="menuOpen = false">
    <!-- 绿色抽屉菜单（与资源管理器同款） -->
    <Transition name="drawer">
      <div v-show="menuOpen" class="drawer-menu">
        <button
          v-for="(item, idx) in BUTTONS"
          :key="item.key"
          class="drawer-btn"
          :class="{ 'drawer-btn-first': idx === 0 }"
          @click="onAction(item.key)"
          @mouseenter="showTip($event, item.tip)"
          @mouseleave="hideTip"
        >
          <img :src="item.icon" class="drawer-btn-icon" draggable="false" />
        </button>
        <div class="drawer-gap-fill"></div>
      </div>
    </Transition>

    <!-- Scratch 风格提示气泡（按钮左侧） -->
    <Transition name="tip">
      <div v-if="tipState" class="drawer-tip" :style="{ top: tipState.top + 'px' }">
        {{ tipState.text }}
        <span class="drawer-tip-arrow"></span>
      </div>
    </Transition>

    <!-- 主按钮：与资源管理器同款大圆上传图标 -->
    <button class="upload-btn" title="添加造型" @click="menuOpen = !menuOpen">
      <img :src="iconSpriteUpload" class="upload-icon" draggable="false" />
    </button>
  </div>
</template>

<style scoped>
.upload-drawer {
  /* 大圆主按钮水平居中于造型列表底部，抽屉菜单向上弹出 */
  position: absolute;
  bottom: 2px;
  left: 50%;
  transform: translateX(-50%);
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
  background: #4b9b5c;
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

.drawer-gap-fill {
  width: 100%;
  height: 20px;
  background: #4b9b5c;
}

/* 提示气泡（显示在悬停按钮左侧，指向造型列表内侧） */
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

/* 主上传按钮 */
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
