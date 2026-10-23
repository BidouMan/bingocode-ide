<script setup lang="ts">
import { useMapStore } from '../../stores/map'
import { useMapEditorStore } from '../../stores/mapEditor'
import type { CollisionLayerTool } from '../../stores/map'
import iconSelect from '../../assets/icons/移动工具.svg'
import iconAddPoint from '../../assets/icons/添加锚点.svg'
import iconDeletePoint from '../../assets/icons/删除锚点.svg'
import iconDelete from '../../assets/icons/选中删除.svg'

defineProps<{ disabled?: boolean }>()

const mapStore = useMapStore()
const mapEditorStore = useMapEditorStore()

function setTool(tool: CollisionLayerTool) {
  mapEditorStore.setCollisionLayerTool(tool)
}

function removeActivePolygon() {
  const poly = mapStore.activeCollisionPolygon
  if (poly) mapStore.removeCollisionPolygon(poly.id)
}
</script>

<template>
  <div class="collision-tools">
    <!-- 形状：矩形 / 圆形 / 胶囊 / 自定义（文字分段按钮，与角色编辑器碰撞类型一致） -->
    <div class="shape-seg">
      <button type="button" :class="{ on: mapEditorStore.collisionShapeTool === 'rect' }" :disabled="disabled" @click="setTool('rect')">矩形</button>
      <button type="button" :class="{ on: mapEditorStore.collisionShapeTool === 'circle' }" :disabled="disabled" @click="setTool('circle')">圆形</button>
      <button type="button" :class="{ on: mapEditorStore.collisionShapeTool === 'capsule' }" :disabled="disabled" @click="setTool('capsule')">胶囊</button>
      <button type="button" :class="{ on: mapEditorStore.collisionShapeTool === 'polygon' }" :disabled="disabled" @click="setTool('polygon')">自定义</button>
    </div>

    <div class="toolbar-separator" />

    <!-- 选取移动 / 添加锚点 / 删除锚点 -->
    <button
      class="toolbar-btn"
      :class="{ 'toolbar-btn-active': mapEditorStore.collisionLayerTool === 'select' }"
      :disabled="disabled"
      v-tooltip="'选择移动'"
      @click="setTool('select')"
    >
      <img :src="iconSelect" class="toolbar-icon" />
    </button>
    <button
      class="toolbar-btn"
      :class="{ 'toolbar-btn-active': mapEditorStore.collisionLayerTool === 'addPoint' }"
      :disabled="disabled || !mapStore.activeCollisionPolygon"
      v-tooltip="'添加锚点'"
      @click="setTool('addPoint')"
    >
      <img :src="iconAddPoint" class="toolbar-icon" />
    </button>
    <button
      class="toolbar-btn"
      :class="{ 'toolbar-btn-active': mapEditorStore.collisionLayerTool === 'deletePoint' }"
      :disabled="disabled || !mapStore.activeCollisionPolygon"
      v-tooltip="'删除锚点'"
      @click="setTool('deletePoint')"
    >
      <img :src="iconDeletePoint" class="toolbar-icon" />
    </button>

    <div class="toolbar-separator" />

    <button
      class="toolbar-btn"
      :disabled="disabled || !mapStore.activeCollisionPolygon"
      v-tooltip="'删除当前碰撞'"
      @click="removeActivePolygon"
    >
      <img :src="iconDelete" class="toolbar-icon" />
    </button>
  </div>
</template>

<style scoped>
.collision-tools {
  display: flex;
  align-items: center;
  gap: 4px;
}

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

.shape-seg {
  display: flex;
  border: 1px solid var(--border-light);
  border-radius: 4px;
  overflow: hidden;
  flex-shrink: 0;
}

.shape-seg button {
  padding: 4px 10px;
  border: none;
  background: transparent;
  color: #8a8f98;
  cursor: pointer;
  font-size: 12px;
  white-space: nowrap;
}

.shape-seg button:hover:not(:disabled):not(.on) {
  background: var(--bg-hover);
}

.shape-seg button.on {
  background: var(--accent);
  color: #10131a;
  font-weight: 600;
}

.shape-seg button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.toolbar-separator { width: 1px; height: 20px; background: var(--border-light); margin: 0 2px; }
</style>
