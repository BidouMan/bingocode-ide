<script setup lang="ts">
import { ref, onMounted, nextTick, computed } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { ask } from '@tauri-apps/plugin-dialog'
import { usePaintStore } from '../../stores/paint'
import { useResourceStore } from '../../stores/resource'
import { useProjectStore } from '../../stores/project'
import {
  readSpriteFromPath,
  loadImage,
  revokeSpriteUrls,
} from '../../composables/useSpriteData'
import { rewriteSpriteFrames, normalizeFrameToCanvas } from '../../composables/appendSpriteFrames'
import { exportCanvasPngBlob } from './utils/artboardExport'
import { packDrawnFrames, buildDrawnBsfManifest } from '../../utils/bsfPacker'
import PaintTopBar from './PaintTopBar.vue'
import PaintToolbar from './PaintToolbar.vue'
import PaintArtboard from './PaintArtboard.vue'
import PaintColorPanel from './PaintColorPanel.vue'
import PaintFrameStrip from './PaintFrameStrip.vue'

/** 编辑目标角色（null = 新建角色） */
export interface PaintTargetSprite {
  id: string
  name: string
  path: string
}

const props = defineProps<{
  /** 非空 = 编辑既有角色：载入全部帧，保存时整体回写 */
  targetSprite?: PaintTargetSprite | null
  /** edit = 双击帧进入（选中该帧）；newFrame = 抽屉「绘制新帧」（自动新建空白帧） */
  openMode?: 'edit' | 'newFrame'
  /** edit 模式初始选中帧 */
  initialFrameIndex?: number
}>()

const emit = defineEmits<{
  close: []
  /** 保存完成：新建返回新角色 id；编辑返回原角色 id */
  saved: [id: string, name: string]
}>()

const store = usePaintStore()
const resourceStore = useResourceStore()
const projectStore = useProjectStore()

const artboardRef = ref<InstanceType<typeof PaintArtboard>>()
const loadingFrames = ref(false)

const topbarTitle = computed(() =>
  props.targetSprite ? `绘制 - ${props.targetSprite.name}` : '角色绘制'
)

/** 帧图片（全画布 blob）→ 目标尺寸画布（.bgs 异尺寸帧自动归一化，动画不抖动） */
async function frameBlobToCanvas(blob: Blob, w: number, h: number): Promise<HTMLCanvasElement> {
  const norm = await normalizeFrameToCanvas(blob, w, h)
  const img = await loadImage(norm)
  const c = document.createElement('canvas')
  c.width = w
  c.height = h
  c.getContext('2d')!.drawImage(img, 0, 0)
  return c
}

// MainLayout 用 :key 递增保证每次打开全新实例；store 是全局的，挂载时重置
onMounted(async () => {
  store.reset()
  const target = props.targetSprite
  if (!target || !artboardRef.value) return

  loadingFrames.value = true
  try {
    const sprite = await readSpriteFromPath(target.path)
    try {
      if (sprite.frames.length === 0) return
      // 画板尺寸 = 角色帧画布尺寸（.bsf 用 manifest.canvas，其余用第一帧）
      let w: number
      let h: number
      if (sprite.bsf) {
        w = sprite.bsf.canvas.w
        h = sprite.bsf.canvas.h
      } else {
        const img = await loadImage(sprite.frames[0].blob)
        w = img.naturalWidth || img.width
        h = img.naturalHeight || img.height
      }
      store.artboardWidth = Math.max(1, Math.round(w))
      store.artboardHeight = Math.max(1, Math.round(h))
      store.sizeForced = true
      store.resetView()

      const canvases: HTMLCanvasElement[] = []
      for (const f of sprite.frames) {
        canvases.push(await frameBlobToCanvas(f.blob, store.artboardWidth, store.artboardHeight))
      }
      const names = sprite.frames.map(f => f.name)
      const activeIndex = props.openMode === 'edit'
        ? Math.min(Math.max(0, props.initialFrameIndex ?? 0), canvases.length - 1)
        : canvases.length - 1
      await nextTick() // 等画板 canvas 尺寸属性绑定生效后再载入
      artboardRef.value?.loadFrames(canvases, names, activeIndex)

      // 抽屉「绘制新帧」：载入后自动追加一张空白帧并选中
      if (props.openMode === 'newFrame') {
        artboardRef.value?.addFrame(false)
      }
    } finally {
      revokeSpriteUrls(sprite)
    }
  } catch (e) {
    console.error('[PaintEditor] 载入目标角色帧失败:', e)
  } finally {
    loadingFrames.value = false
  }
})

async function onClose() {
  if (store.dirty) {
    const shouldClose = await ask('画板有未保存的修改，关闭后将丢失。确定关闭吗？', {
      title: '角色绘制',
      kind: 'warning',
    })
    if (!shouldClose) return
  }
  emit('close')
}

async function onSave() {
  if (store.dirty === false) return
  const canvases = artboardRef.value?.getFrameCanvases()
  const names = artboardRef.value?.getFrameNames()
  if (!canvases || !names || canvases.length === 0) return

  try {
    const target = props.targetSprite

    // ─── 编辑模式：当前帧列表整体回写原角色 ───
    if (target) {
      const res = await rewriteSpriteFrames(target.path, canvases, names)
      if (res.newPath) {
        resourceStore.updateItemPath(target.id, res.newPath)
      }
      resourceStore.bumpSpriteThumb(target.id)
      emit('saved', target.id, target.name)
      return
    }

    // ─── 新建模式：打包输出 .bsf 目录角色 ───
    const projectRoot = projectStore.root
    if (!projectRoot) {
      console.warn('[PaintEditor] 项目目录未就绪，无法保存角色')
      return
    }

    const spriteName = resourceStore.nextSequentialName('sprite', '角色')
    const packed = packDrawnFrames(canvases, store.artboardWidth, store.artboardHeight)
    const manifest = buildDrawnBsfManifest(spriteName, packed)

    const dirPath = `${projectRoot}/assets/sprites/${spriteName}`
    await invoke('create_dir', { path: dirPath })
    const sheetBlob = await exportCanvasPngBlob(packed.sheet)
    await invoke('write_binary', {
      path: `${dirPath}/sheet.png`,
      data: Array.from(new Uint8Array(await sheetBlob.arrayBuffer())),
    })
    await invoke('write_file', {
      path: `${dirPath}/manifest.json`,
      content: JSON.stringify(manifest, null, 2),
    })

    const id = resourceStore.addItem({ name: spriteName, type: 'sprite', path: dirPath })
    emit('saved', id, spriteName)
  } catch (e) {
    console.error('[PaintEditor] 保存角色失败:', e)
  }
}
</script>

<template>
  <div class="paint-page">
    <PaintTopBar
      :title="topbarTitle"
      :save-title="targetSprite ? '保存回角色' : undefined"
      @close="onClose"
      @save="onSave"
      @undo="artboardRef?.undo()"
      @redo="artboardRef?.redo()"
      @crop="artboardRef?.cropToContent()"
      @copy="artboardRef?.copySelection()"
      @paste="artboardRef?.pasteClipboard()"
      @delete-sel="artboardRef?.deleteSelection()"
      @flip-h="artboardRef?.flipSelection('h')"
      @flip-v="artboardRef?.flipSelection('v')"
      @group="artboardRef?.groupSelection()"
      @ungroup="artboardRef?.ungroupSelection()"
      @layer-up="artboardRef?.layerMove('up')"
      @layer-down="artboardRef?.layerMove('down')"
      @curve-points="artboardRef?.curveSelectedPoints()"
      @point-points="artboardRef?.pointSelectedPoints()"
    />
    <div class="paint-body">
      <PaintToolbar @clear="artboardRef?.clear()" />
      <div class="paint-center">
        <PaintArtboard ref="artboardRef" />
        <PaintFrameStrip
          @add="artboardRef?.addFrame(false)"
          @duplicate="artboardRef?.addFrame(true)"
          @remove="artboardRef?.removeFrame($event)"
        />
      </div>
      <PaintColorPanel />
    </div>

    <!-- 载入既有角色帧的过渡提示 -->
    <div v-if="loadingFrames" class="loading-mask">载入角色帧中...</div>
  </div>
</template>

<style scoped>
.paint-page {
  position: relative;
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

.paint-center {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  min-height: 0;
}

.loading-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(34, 37, 43, 0.75);
  color: var(--accent);
  font-size: 13px;
  z-index: 50;
}
</style>
