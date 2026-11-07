<script setup lang="ts">
import { computed } from 'vue'
import { useMapStore } from '../../stores/map'
import { useMapEditorStore } from '../../stores/mapEditor'
import iconSelect from '../../assets/icons/选择箭头.svg'
import iconCopy from '../../assets/icons/copy.svg'
import iconRotate from '../../assets/icons/旋转.svg'
import iconFlipH from '../../assets/icons/水平翻转.svg'
import iconFlipV from '../../assets/icons/垂直翻转.svg'
import iconEdit from '../../assets/icons/编辑1.svg'

defineProps<{ disabled?: boolean }>()
const emit = defineEmits<{
  /** 复制当前图像图层（含图片文件） */
  'copy-layer': []
  /** 顺时针旋转 90° */
  'rotate': []
  /** 水平镜像 */
  'flip-h': []
  /** 垂直镜像 */
  'flip-v': []
  /** 进入绘制页编辑这张图像 */
  'edit-image': []
}>()

const mapStore = useMapStore()
const mapEditorStore = useMapEditorStore()

/** 只有选中图像才能执行变换 */
const canOperate = computed(() => !!mapStore.selectedImage)

/** 移动工具：选中当前图像图层，之后可在画布上拖动 / 缩放 / 旋转 */
function pickMove() {
  mapEditorStore.setImageTool('select')
  const layer = mapStore.activeLayer
  if (!mapStore.selectedImage && layer?.type === 'image') mapStore.selectImage(layer.id)
}
</script>

<template>
  <button
    class="toolbar-btn"
    :class="{ 'toolbar-btn-active': mapEditorStore.imageTool === 'select' }"
    :disabled="disabled"
    v-tooltip="'移动 / 缩放 / 旋转'"
    @click="pickMove"
  >
    <img :src="iconSelect" class="toolbar-icon" />
  </button>

  <div class="toolbar-separator" />

  <button
    class="toolbar-btn"
    :disabled="disabled || !canOperate"
    v-tooltip="'复制图层'"
    @click="emit('copy-layer')"
  >
    <img :src="iconCopy" class="toolbar-icon" />
  </button>
  <button
    class="toolbar-btn"
    :disabled="disabled || !canOperate"
    v-tooltip="'顺时针旋转 90°'"
    @click="emit('rotate')"
  >
    <img :src="iconRotate" class="toolbar-icon" />
  </button>
  <button
    class="toolbar-btn"
    :disabled="disabled || !canOperate"
    v-tooltip="'水平镜像'"
    @click="emit('flip-h')"
  >
    <img :src="iconFlipH" class="toolbar-icon" />
  </button>
  <button
    class="toolbar-btn"
    :disabled="disabled || !canOperate"
    v-tooltip="'垂直镜像'"
    @click="emit('flip-v')"
  >
    <img :src="iconFlipV" class="toolbar-icon" />
  </button>

  <div class="toolbar-separator" />

  <button
    class="toolbar-btn"
    :disabled="disabled || !canOperate"
    v-tooltip="'进入绘制页编辑这张图像'"
    @click="emit('edit-image')"
  >
    <img :src="iconEdit" class="toolbar-icon" />
  </button>
</template>

<style scoped>
.toolbar-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: default;
  padding: 0;
  flex-shrink: 0;
  transition: background 0.15s;
}

.toolbar-btn:hover { background: var(--bg-hover); }
.toolbar-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.toolbar-btn:disabled:hover { background: transparent; }
.toolbar-btn:active { background: rgb(72, 75, 82); }

.toolbar-btn-active {
  position: relative;
  background: rgb(46, 49, 58);
  border: 1px solid var(--border-light);
}

/* 选中指示：绿色小条（与角色绘制页左侧工具栏一致） */
.toolbar-btn-active::before {
  content: '';
  position: absolute;
  left: 1px;
  right: 1px;
  bottom: -6px;
  height: 2.5px;
  border-radius: 1.25px;
  background: var(--accent);
}

.toolbar-btn-active:hover { background: var(--border-light); }

.toolbar-icon { width: 20px; height: 20px; flex-shrink: 0; }

.toolbar-separator { width: 1px; height: 20px; background: var(--border-light); margin: 0 2px; }
</style>
