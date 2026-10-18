<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ask } from '@tauri-apps/plugin-dialog'
import { usePaintStore } from '../../stores/paint'
import { useResourceStore } from '../../stores/resource'
import { useProjectStore } from '../../stores/project'
import { saveImageSpriteToDirectory, type SpriteData } from '../../composables/useSpriteData'
import { exportCanvasPngBlob } from './utils/artboardExport'
import PaintTopBar from './PaintTopBar.vue'
import PaintToolbar from './PaintToolbar.vue'
import PaintArtboard from './PaintArtboard.vue'
import PaintColorPanel from './PaintColorPanel.vue'

const emit = defineEmits<{
  close: []
  /** 绘制完成保存为新角色后：id + 角色名 */
  saved: [id: string, name: string]
}>()

const store = usePaintStore()
const resourceStore = useResourceStore()
const projectStore = useProjectStore()

const artboardRef = ref<InstanceType<typeof PaintArtboard>>()

// MainLayout 用 :key 递增保证每次打开全新实例；store 是全局的，挂载时重置
onMounted(() => {
  store.reset()
})

async function onClose() {
  if (store.dirty) {
    const shouldClose = await ask('画板有未保存的绘制，关闭后将丢失。确定关闭吗？', {
      title: '角色绘制',
      kind: 'warning',
    })
    if (!shouldClose) return
  }
  emit('close')
}

async function onSave() {
  if (!store.dirty) return
  const canvas = artboardRef.value?.getCanvas()
  if (!canvas) return

  try {
    // 位图画板 → PNG Blob（棋盘格是视图辅助，canvas 本身透明背景）
    const blob = await exportCanvasPngBlob(canvas)
    const projectRoot = projectStore.root
    if (!projectRoot) {
      console.warn('[PaintEditor] 项目目录未就绪，无法保存角色')
      return
    }

    // 名字统一为「角色N」顺序名；落盘为目录角色（config.json + 帧 PNG），多帧时直接扩展
    const spriteName = resourceStore.nextSequentialName('sprite', '角色')
    const sprite: SpriteData = {
      name: spriteName,
      frames: [{ name: `${spriteName}_01.png`, blob, url: '' }],
      animations: [{ name: '默认动画', start: 1, end: 1, fps: 10, loop: true }],
    }
    const dirPath = `${projectRoot}/assets/sprites/${spriteName}`
    await saveImageSpriteToDirectory(dirPath, sprite)

    const id = resourceStore.addItem({ name: spriteName, type: 'sprite', path: dirPath })
    emit('saved', id, spriteName)
  } catch (e) {
    console.error('[PaintEditor] 保存角色失败:', e)
  }
}
</script>

<template>
  <div class="paint-page">
    <PaintTopBar @close="onClose" @save="onSave" @undo="artboardRef?.undo()" @redo="artboardRef?.redo()" />
    <div class="paint-body">
      <PaintToolbar @clear="artboardRef?.clear()" />
      <PaintArtboard ref="artboardRef" />
      <PaintColorPanel />
    </div>
  </div>
</template>

<style scoped>
.paint-page {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  background: var(--bg-root);
}

.paint-body {
  display: flex;
  flex: 1;
  min-height: 0;
}
</style>
