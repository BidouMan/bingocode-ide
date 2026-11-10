<script setup lang="ts">
import { computed } from 'vue'
import { useMapStore } from '../../stores/map'
import { useMapEditorStore } from '../../stores/mapEditor'
import iconSelect from '../../assets/icons/选择箭头.svg'
import iconCopy from '../../assets/icons/copy.svg'
import iconPaint from '../../assets/icons/画笔工具.svg'
import iconFlipH from '../../assets/icons/水平翻转.svg'
import iconFlipV from '../../assets/icons/垂直翻转.svg'

defineProps<{ disabled?: boolean }>()
const emit = defineEmits<{
  /** 复制当前图像图层（含图片文件） */
  'copy-layer': []
  /** 进入绘制页编辑当前图像 */
  'edit-image': []
  /** 水平镜像 */
  'flip-h': []
  /** 垂直镜像 */
  'flip-v': []
}>()

const mapStore = useMapStore()
const mapEditorStore = useMapEditorStore()

/** 只有选中图像才能执行变换 */
const canOperate = computed(() => !!mapStore.selectedImage)
/** 当前是否选中图像图层：决定「编辑」按钮能否使用 */
const canEditImage = computed(() => mapStore.activeLayer?.type === 'image')

/** 移动工具：选中当前图像图层，之后可在画布上拖动 / 缩放 / 旋转 */
function pickMove() {
  mapEditorStore.setImageTool('select')
  const layer = mapStore.activeLayer
  if (!mapStore.selectedImage && layer?.type === 'image') mapStore.selectImage(layer.id)
}
</script>

<template>
  <button
    class="tool-chip"
    :class="{ active: mapEditorStore.imageTool === 'select' }"
    :disabled="disabled"
    v-tooltip="'移动 / 缩放 / 旋转'"
    @click="pickMove"
  >
    <img :src="iconSelect" class="tool-chip-icon ic-select" />选择
  </button>

  <button
    class="tool-chip"
    :disabled="disabled || !canOperate"
    v-tooltip="'复制图层'"
    @click="emit('copy-layer')"
  >
    <img :src="iconCopy" class="tool-chip-icon ic-copy" />复制
  </button>
  <button
    class="tool-chip"
    :disabled="disabled || !canEditImage"
    v-tooltip="'进入绘制页编辑这张图像'"
    @click="emit('edit-image')"
  >
    <img :src="iconPaint" class="tool-chip-icon ic-paint" />绘制
  </button>
  <button
    class="tool-chip"
    :disabled="disabled || !canOperate"
    v-tooltip="'水平镜像'"
    @click="emit('flip-h')"
  >
    <img :src="iconFlipH" class="tool-chip-icon ic-flip-h" />水平
  </button>
  <button
    class="tool-chip"
    :disabled="disabled || !canOperate"
    v-tooltip="'垂直镜像'"
    @click="emit('flip-v')"
  >
    <img :src="iconFlipV" class="tool-chip-icon ic-flip-v" />垂直
  </button>
</template>

<style scoped src="./ToolbarChip.css"></style>
