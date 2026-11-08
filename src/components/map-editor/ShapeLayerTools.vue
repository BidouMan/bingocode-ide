<script setup lang="ts">
import { useMapStore } from '../../stores/map'
import { useMapEditorStore } from '../../stores/mapEditor'
import type { ShapeTool } from '../../stores/map'
import iconSelect from '../../assets/icons/选择箭头.svg'
import iconAddPoint from '../../assets/icons/添加锚点.svg'
import iconDeletePoint from '../../assets/icons/删除锚点.svg'
import iconRect from '../../assets/icons/矩形_rectangle.svg'
import iconCapsule from '../../assets/icons/圆形_round.svg'
import iconPolygon from '../../assets/icons/钢笔工具.svg'

defineProps<{ disabled?: boolean }>()

const mapStore = useMapStore()
const mapEditorStore = useMapEditorStore()

function setTool(tool: ShapeTool) {
  mapEditorStore.setShapeTool(tool)
}
</script>

<template>
  <div class="shape-tools">
    <!-- 鼠标选择：点选 / 拖动 -->
    <button
      class="tool-chip"
      :class="{ active: mapEditorStore.shapeTool === 'select' }"
      :disabled="disabled"
      v-tooltip="'鼠标选择（点选 / 拖动）'"
      @click="setTool('select')"
    >
      <img :src="iconSelect" class="tool-chip-icon ic-select" />选择
    </button>

    <!-- 创建工具：独立按钮，点一次画一个，画完自动回到选择 -->
    <button
      class="tool-chip"
      :class="{ active: mapEditorStore.shapeTool === 'rect' }"
      :disabled="disabled"
      v-tooltip="'拖拽创建矩形'"
      @click="setTool('rect')"
    >
      <img :src="iconRect" class="tool-chip-icon ic-rect" />矩形
    </button>
    <button
      class="tool-chip"
      :class="{ active: mapEditorStore.shapeTool === 'capsule' }"
      :disabled="disabled"
      v-tooltip="'拖拽创建胶囊，按住 Shift 创建正圆'"
      @click="setTool('capsule')"
    >
      <img :src="iconCapsule" class="tool-chip-icon ic-round" />胶囊
    </button>
    <button
      class="tool-chip"
      :class="{ active: mapEditorStore.shapeTool === 'polygon' }"
      :disabled="disabled"
      v-tooltip="'逐个点击锚点创建自定义形状'"
      @click="setTool('polygon')"
    >
      <img :src="iconPolygon" class="tool-chip-icon ic-pen" />自定义
    </button>

    <!-- 添加锚点 / 删除锚点 -->
    <button
      class="tool-chip"
      :class="{ active: mapEditorStore.shapeTool === 'addPoint' }"
      :disabled="disabled || !mapStore.activeShape"
      v-tooltip="'添加锚点'"
      @click="setTool('addPoint')"
    >
      <img :src="iconAddPoint" class="tool-chip-icon ic-add" />添加
    </button>
    <button
      class="tool-chip"
      :class="{ active: mapEditorStore.shapeTool === 'deletePoint' }"
      :disabled="disabled || !mapStore.activeShape"
      v-tooltip="'删除锚点'"
      @click="setTool('deletePoint')"
    >
      <img :src="iconDeletePoint" class="tool-chip-icon ic-del" />移除
    </button>
  </div>
</template>

<style scoped>
.shape-tools {
  display: flex;
  align-items: center;
  gap: 6px;
}
</style>

<style scoped src="./ToolbarChip.css"></style>
