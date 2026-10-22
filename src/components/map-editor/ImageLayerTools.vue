<script setup lang="ts">
import { useMapStore } from '../../stores/map'
import { useMapEditorStore } from '../../stores/mapEditor'
import { usePaintStore } from '../../stores/paint'
import iconSelect from '../../assets/icons/选取工具.svg'
import iconPaint from '../../assets/icons/icon--paint.svg'
import iconErase from '../../assets/icons/清空.svg'
import iconFill from '../../assets/icons/填充_fill.svg'
import iconLine from '../../assets/icons/直线工具.svg'
import iconRect from '../../assets/icons/矩形_rectangle.svg'
import iconEllipse from '../../assets/icons/圆形_round.svg'
import iconUndo from '../../assets/icons/undo.svg'
import iconRedo from '../../assets/icons/redo.svg'
import iconDelete from '../../assets/icons/选中删除.svg'

defineProps<{ disabled?: boolean }>()
const emit = defineEmits<{
  'delete-image': []
  'paint-undo': []
  'paint-redo': []
  'create-layer': [tool: 'brush' | 'eraser' | 'fill' | 'line' | 'rect' | 'ellipse']
}>()

const mapStore = useMapStore()
const mapEditorStore = useMapEditorStore()
const paintStore = usePaintStore()

const paintTools = [
  { id: 'brush' as const, icon: iconPaint, label: '画笔' },
  { id: 'eraser' as const, icon: iconErase, label: '橡皮' },
  { id: 'fill' as const, icon: iconFill, label: '填充' },
  { id: 'line' as const, icon: iconLine, label: '直线' },
  { id: 'rect' as const, icon: iconRect, label: '矩形' },
  { id: 'ellipse' as const, icon: iconEllipse, label: '椭圆' },
]

function setTool(tool: typeof mapEditorStore.imageTool) {
  if (tool !== 'select') {
    // 没有选中图片时自动选中当前图片图层；连图片图层都没有就新建一张
    if (!mapStore.selectedImage && mapStore.activeLayer?.type === 'image') {
      mapStore.selectImage(mapStore.activeLayer.id)
    }
    if (!mapStore.selectedImage) {
      emit('create-layer', tool)
      return
    }
  }
  mapEditorStore.setImageCollisionTool('none')
  paintStore.setTool(tool)
  mapEditorStore.setImageTool(tool)
}
</script>

<template>
  <!-- 矢量/位图模式切换：地图画布绘制目前只支持位图 -->
  <div class="mode-switch">
    <button class="mode-btn" disabled title="矢量模式即将开放">矢量</button>
    <button class="mode-btn mode-btn-active" title="位图模式">位图</button>
  </div>

  <div class="toolbar-separator" />

  <button
    class="toolbar-btn"
    :class="{ 'toolbar-btn-active': mapEditorStore.imageTool === 'select' }"
    :disabled="disabled"
    v-tooltip="'选取/移动'"
    @click="setTool('select')"
  >
    <img :src="iconSelect" class="toolbar-icon" />
  </button>

  <div class="toolbar-separator" />

  <button
    v-for="tool in paintTools"
    :key="tool.id"
    class="toolbar-btn"
    :class="{ 'toolbar-btn-active': mapEditorStore.imageTool === tool.id }"
    :disabled="disabled"
    v-tooltip="tool.label"
    @click="setTool(tool.id)"
  >
    <img :src="tool.icon" class="toolbar-icon" />
  </button>

  <button
    class="toolbar-btn"
    :disabled="disabled || mapEditorStore.imageTool === 'select'"
    v-tooltip="'撤销绘制'"
    @click="emit('paint-undo')"
  >
    <img :src="iconUndo" class="toolbar-icon" />
  </button>
  <button
    class="toolbar-btn"
    :disabled="disabled || mapEditorStore.imageTool === 'select'"
    v-tooltip="'重做绘制'"
    @click="emit('paint-redo')"
  >
    <img :src="iconRedo" class="toolbar-icon" />
  </button>

  <div class="toolbar-separator" />

  <button class="toolbar-btn" :disabled="disabled" v-tooltip="'删除选中图像'" @click="emit('delete-image')">
    <img :src="iconDelete" class="toolbar-icon" />
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
  cursor: pointer;
  padding: 0;
  flex-shrink: 0;
  transition: background 0.15s;
}

.toolbar-btn:hover { background: var(--bg-hover); }
.toolbar-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.toolbar-btn:disabled:hover { background: transparent; }
.toolbar-btn:active { background: rgb(72, 75, 82); }
.toolbar-btn-active { background: rgb(46, 49, 58); border: 1px solid var(--border-light); }
.toolbar-btn-active:hover { background: var(--border-light); }
.toolbar-icon { width: 20px; height: 20px; flex-shrink: 0; }

.mode-switch {
  display: flex;
  align-items: center;
  height: 26px;
  border: 1px solid var(--border-light);
  border-radius: 4px;
  overflow: hidden;
  flex-shrink: 0;
}

.mode-btn {
  height: 100%;
  padding: 0 8px;
  background: transparent;
  border: none;
  color: #9ca0a4;
  font-size: 11px;
  cursor: pointer;
}

.mode-btn-active {
  background: rgb(46, 49, 58);
  color: #fff;
}

.mode-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.brush-color:disabled,
.brush-size:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.toolbar-separator { width: 1px; height: 20px; background: var(--border-light); margin: 0 2px; }
</style>
