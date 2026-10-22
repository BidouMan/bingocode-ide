<script setup lang="ts">
import { computed } from 'vue'
import { useMapStore } from '../../stores/map'
import { useMapEditorStore } from '../../stores/mapEditor'
import iconSelect from '../../assets/icons/选取工具.svg'
import iconDelete from '../../assets/icons/选中删除.svg'
import iconPaint from '../../assets/icons/icon--paint.svg'
import iconCollisionRect from '../../assets/icons/矩形_rectangle.svg'
import iconCollisionPolygon from '../../assets/icons/折线.svg'
import iconCollisionVertex from '../../assets/icons/移动锚点.svg'
import iconCollisionClear from '../../assets/icons/重置.svg'
import iconCollisionShow from '../../assets/icons/hitbox.svg'

defineProps<{ disabled?: boolean }>()
const emit = defineEmits<{ 'delete-image': []; paint: [] }>()

const mapStore = useMapStore()
const mapEditorStore = useMapEditorStore()

const hasSelectedImage = computed(() => !!mapStore.selectedImage)
const hasCollisionShape = computed(() => (mapStore.selectedImage?.collisionShape?.points?.length ?? 0) >= 3)

function toggleCollisionTool(tool: 'rect' | 'polygon' | 'vertex') {
  if (!hasSelectedImage.value) return
  mapEditorStore.setImageCollisionTool(mapEditorStore.imageCollisionTool === tool ? 'none' : tool)
}

function onSelectTool() {
  mapEditorStore.setImageCollisionTool('none')
  mapEditorStore.setTool('select')
}
</script>

<template>
  <button
    class="toolbar-btn"
    :class="{ 'toolbar-btn-active': mapEditorStore.currentTool === 'select' }"
    :disabled="disabled"
    v-tooltip="'选取'"
    @click="onSelectTool"
  >
    <img :src="iconSelect" class="toolbar-icon" />
  </button>
  <button class="toolbar-btn" v-tooltip="'删除选中图像'" :disabled="disabled" @click="emit('delete-image')">
    <img :src="iconDelete" class="toolbar-icon" />
  </button>
  <button class="toolbar-btn" v-tooltip="'绘制背景图像'" :disabled="disabled" @click="emit('paint')">
    <img :src="iconPaint" class="toolbar-icon" />
  </button>

  <div class="toolbar-separator" />

  <!-- 图像碰撞编辑：先选中图片再使用 -->
  <button
    class="toolbar-btn"
    :class="{ 'toolbar-btn-active': mapEditorStore.imageCollisionTool === 'rect' }"
    :disabled="disabled || !hasSelectedImage"
    v-tooltip="hasSelectedImage ? '矩形碰撞：在图片上拖动绘制' : '先在画布上选中图像实例'"
    @click="toggleCollisionTool('rect')"
  >
    <img :src="iconCollisionRect" class="toolbar-icon" />
  </button>
  <button
    class="toolbar-btn"
    :class="{ 'toolbar-btn-active': mapEditorStore.imageCollisionTool === 'polygon' }"
    :disabled="disabled || !hasSelectedImage"
    v-tooltip="hasSelectedImage ? '多边形碰撞：逐点点击，点首点/回车闭合' : '先在画布上选中图像实例'"
    @click="toggleCollisionTool('polygon')"
  >
    <img :src="iconCollisionPolygon" class="toolbar-icon" />
  </button>
  <button
    class="toolbar-btn"
    :class="{ 'toolbar-btn-active': mapEditorStore.imageCollisionTool === 'vertex' }"
    :disabled="disabled || !hasSelectedImage"
    v-tooltip="hasSelectedImage ? '编辑锚点：拖动顶点，点边插点，右键/Del 删点' : '先在画布上选中图像实例'"
    @click="toggleCollisionTool('vertex')"
  >
    <img :src="iconCollisionVertex" class="toolbar-icon" />
  </button>
  <button class="toolbar-btn" :disabled="disabled || !hasCollisionShape" v-tooltip="'清除碰撞'" @click="mapStore.clearImageCollision()">
    <img :src="iconCollisionClear" class="toolbar-icon" />
  </button>
  <button
    class="toolbar-btn"
    :class="{ 'toolbar-btn-active': mapEditorStore.showCollision }"
    :disabled="disabled"
    v-tooltip="'显示所有图像碰撞'"
    @click="mapEditorStore.toggleShowCollision()"
  >
    <img :src="iconCollisionShow" class="toolbar-icon" />
  </button>
</template>

<style scoped>
.toolbar-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
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
.toolbar-separator { width: 1px; height: 20px; background: var(--border-light); margin: 0 2px; }
</style>
