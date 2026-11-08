<script setup lang="ts">
import { useMapEditorStore } from '../../stores/mapEditor'
import type { MapTool } from '../../stores/map'
import iconMove from '../../assets/icons/移动工具.svg'
import iconPaint from '../../assets/icons/画笔工具.svg'
import iconLine from '../../assets/icons/直线工具.svg'
import iconRect from '../../assets/icons/矩形_rectangle.svg'

defineProps<{ disabled?: boolean }>()

const mapEditorStore = useMapEditorStore()

const drawingTools: { id: MapTool; icon: string; label: string; cls: string }[] = [
  { id: 'draw', icon: iconPaint, label: '绘制', cls: 'ic-paint' },
  { id: 'line', icon: iconLine, label: '直线', cls: 'ic-line' },
  { id: 'rect', icon: iconRect, label: '矩形', cls: 'ic-rect' },
]
const moveTool: { id: MapTool; icon: string; label: string; cls: string } = {
  id: 'move',
  icon: iconMove,
  label: '移动',
  cls: 'ic-move',
}
</script>

<template>
  <button
    v-for="tool in drawingTools"
    :key="tool.id"
    class="tool-chip"
    :class="{ active: mapEditorStore.currentTool === tool.id }"
    :disabled="disabled"
    v-tooltip="tool.label"
    @click="mapEditorStore.setTool(tool.id)"
  >
    <img :src="tool.icon" class="tool-chip-icon" :class="tool.cls" />{{ tool.label }}
  </button>

  <!-- 擦除是开关而不是工具：开启后画笔/直线/矩形都改为擦除 -->
  <button
    class="tool-chip check-chip"
    :class="{ active: mapEditorStore.eraseMode }"
    :disabled="disabled"
    v-tooltip="mapEditorStore.eraseMode ? '关闭擦除模式' : '擦除模式（开启后画笔 / 直线 / 矩形都会擦除）'"
    @click="mapEditorStore.toggleEraseMode()"
  >
    <span class="chip-check" :class="{ on: mapEditorStore.eraseMode }"></span>擦除
  </button>

  <button
    class="tool-chip"
    :class="{ active: mapEditorStore.currentTool === moveTool.id }"
    :disabled="disabled"
    v-tooltip="moveTool.label"
    @click="mapEditorStore.setTool(moveTool.id)"
  >
    <img :src="moveTool.icon" class="tool-chip-icon" :class="moveTool.cls" />{{ moveTool.label }}
  </button>
</template>

<style scoped src="./ToolbarChip.css"></style>
