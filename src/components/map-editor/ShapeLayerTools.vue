<script setup lang="ts">
import { useMapStore } from '../../stores/map'
import { useMapEditorStore } from '../../stores/mapEditor'
import type { ShapeTool } from '../../stores/map'
import iconSelect from '../../assets/icons/选择箭头.svg'
import iconAddPoint from '../../assets/icons/添加锚点.svg'
import iconDeletePoint from '../../assets/icons/删除锚点.svg'
import iconDelete from '../../assets/icons/选中删除.svg'

defineProps<{ disabled?: boolean }>()

const mapStore = useMapStore()
const mapEditorStore = useMapEditorStore()

function setTool(tool: ShapeTool) {
  mapEditorStore.setShapeTool(tool)
}

function removeActiveShape() {
  const shape = mapStore.activeShape
  if (shape) mapStore.removeShape(shape.id)
}
</script>

<template>
  <div class="shape-tools">
    <!-- 形状：矩形 / 圆形 / 胶囊 / 自定义
         按钮亮起表示「当前要画的形状」，切换鼠标/锚点工具不会熄灭 -->
    <div class="shape-seg">
      <button
        type="button"
        :class="{ on: mapEditorStore.shapeDrawTool === 'rect', 'tool-current': mapEditorStore.shapeTool === 'rect' }"
        :disabled="disabled"
        @click="setTool('rect')"
      >矩形</button>
      <button
        type="button"
        :class="{ on: mapEditorStore.shapeDrawTool === 'circle', 'tool-current': mapEditorStore.shapeTool === 'circle' }"
        :disabled="disabled"
        @click="setTool('circle')"
      >圆形</button>
      <button
        type="button"
        :class="{ on: mapEditorStore.shapeDrawTool === 'capsule', 'tool-current': mapEditorStore.shapeTool === 'capsule' }"
        :disabled="disabled"
        @click="setTool('capsule')"
      >胶囊</button>
      <button
        type="button"
        :class="{ on: mapEditorStore.shapeDrawTool === 'polygon', 'tool-current': mapEditorStore.shapeTool === 'polygon' }"
        :disabled="disabled"
        @click="setTool('polygon')"
      >自定义</button>
    </div>

    <!-- 鼠标选择：点选 / 拖动，紧跟在「自定义」后面 -->
    <button
      class="toolbar-btn"
      :class="{ 'toolbar-btn-active': mapEditorStore.shapeTool === 'select' }"
      :disabled="disabled"
      v-tooltip="'鼠标选择（点选 / 拖动）'"
      @click="setTool('select')"
    >
      <img :src="iconSelect" class="toolbar-icon" />
    </button>

    <div class="toolbar-separator" />

    <!-- 添加锚点 / 删除锚点 -->
    <button
      class="toolbar-btn"
      :class="{ 'toolbar-btn-active': mapEditorStore.shapeTool === 'addPoint' }"
      :disabled="disabled || !mapStore.activeShape"
      v-tooltip="'添加锚点'"
      @click="setTool('addPoint')"
    >
      <img :src="iconAddPoint" class="toolbar-icon" />
    </button>
    <button
      class="toolbar-btn"
      :class="{ 'toolbar-btn-active': mapEditorStore.shapeTool === 'deletePoint' }"
      :disabled="disabled || !mapStore.activeShape"
      v-tooltip="'删除锚点'"
      @click="setTool('deletePoint')"
    >
      <img :src="iconDeletePoint" class="toolbar-icon" />
    </button>

    <div class="toolbar-separator" />

    <button
      class="toolbar-btn"
      :disabled="disabled || !mapStore.activeShape"
      v-tooltip="'删除当前碰撞体'"
      @click="removeActiveShape"
    >
      <img :src="iconDelete" class="toolbar-icon" />
    </button>
  </div>
</template>

<style scoped>
.shape-tools {
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
/* 选中指示：绿色小条（与绘制图像图层的工具栏一致，画在按钮外侧下沿） */
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

.shape-seg {
  display: flex;
  border: 1px solid var(--border-light);
  border-radius: 4px;
  /* 允许当前工具的绿色指示条画在分段控件下沿之外 */
  overflow: visible;
  flex-shrink: 0;
}

.shape-seg button {
  position: relative;
  padding: 4px 10px;
  border: none;
  background: transparent;
  color: #8a8f98;
  cursor: default;
  font-size: 12px;
  white-space: nowrap;
}

/* 选中形状标签的圆角贴合外层分段控件边框 */
.shape-seg button.on:first-child { border-radius: 3px 0 0 3px; }
.shape-seg button.on:last-child { border-radius: 0 3px 3px 0; }

.shape-seg button:hover:not(:disabled):not(.on) {
  background: var(--bg-hover);
}

/* 标签状态：当前要画的形状（切换鼠标/锚点工具后仍常亮） */
.shape-seg button.on {
  background: var(--accent);
  color: #10131a;
  font-weight: 600;
}

/* 当前工具指示：按钮下方绿色小条，与图标按钮一致 */
.shape-seg button.tool-current::before {
  content: '';
  position: absolute;
  left: 4px;
  right: 4px;
  bottom: -7px;
  height: 2.5px;
  border-radius: 1.25px;
  background: var(--accent);
}

.shape-seg button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.toolbar-separator { width: 1px; height: 20px; background: var(--border-light); margin: 0 2px; }
</style>
