<script setup lang="ts">
import { useMapEditorStore } from '../../stores/mapEditor'
import type { MapTool } from '../../stores/map'
import iconMove from '../../assets/icons/移动工具.svg'
import iconPaint from '../../assets/icons/icon--paint.svg'
import iconEraseRaw from '../../assets/icons/清空.svg?raw'
import iconLine from '../../assets/icons/直线工具.svg'
import iconRect from '../../assets/icons/矩形_rectangle.svg'

defineProps<{ disabled?: boolean }>()

const mapEditorStore = useMapEditorStore()

const drawingTools: { id: MapTool; icon: string; label: string }[] = [
  { id: 'draw', icon: iconPaint, label: '绘制' },
  { id: 'line', icon: iconLine, label: '直线' },
  { id: 'rect', icon: iconRect, label: '矩形' },
]
const moveTool: { id: MapTool; icon: string; label: string } = {
  id: 'move',
  icon: iconMove,
  label: '移动',
}

// 擦除图标原来是白色填充，改成 currentColor 才能随激活状态换色（保留原图标外形）
const eraseIconSvg = iconEraseRaw.replace(/fill:\s*white/g, 'fill:currentColor')
</script>

<template>
  <button
    v-for="tool in drawingTools"
    :key="tool.id"
    class="toolbar-btn"
    :class="{ 'toolbar-btn-active': mapEditorStore.currentTool === tool.id }"
    :disabled="disabled"
    v-tooltip="tool.label"
    @click="mapEditorStore.setTool(tool.id)"
  >
    <img :src="tool.icon" class="toolbar-icon" />
  </button>

  <!-- 擦除是开关而不是工具：开启后画笔/直线/矩形都改为擦除 -->
  <button
    class="toolbar-btn"
    :class="{ 'erase-btn-active': mapEditorStore.eraseMode }"
    :disabled="disabled"
    v-tooltip="mapEditorStore.eraseMode ? '关闭擦除模式' : '擦除模式（开启后画笔 / 直线 / 矩形都会擦除）'"
    @click="mapEditorStore.toggleEraseMode()"
  >
    <span
      class="erase-icon"
      :class="{ 'erase-icon-active': mapEditorStore.eraseMode }"
      v-html="eraseIconSvg"
    />
  </button>

  <button
    class="toolbar-btn"
    :class="{ 'toolbar-btn-active': mapEditorStore.currentTool === moveTool.id }"
    :disabled="disabled"
    v-tooltip="moveTool.label"
    @click="mapEditorStore.setTool(moveTool.id)"
  >
    <img :src="moveTool.icon" class="toolbar-icon" />
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
.toolbar-btn-active { background: rgb(46, 49, 58); border: 1px solid var(--border-light); }

/* 选中指示：绿色小条（与绘制图像图层的工具栏一致，画在按钮外侧下沿） */
.toolbar-btn-active {
  position: relative;
}

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

/* 擦除开关：只保留按下底色，不画「当前工具」的绿线 */
.erase-btn-active {
  background: rgb(46, 49, 58);
  border: 1px solid var(--border-light);
}

.erase-btn-active:hover { background: var(--border-light); }

/* 擦除图标：保留原图标外形，只把填充色换成主题绿，不会填满整个按钮 */
.erase-icon {
  display: block;
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  color: #fff;
  transition: color 0.15s;
}

.erase-icon :deep(svg) {
  display: block;
  width: 100%;
  height: 100%;
}

.erase-icon-active {
  color: var(--accent);
}

.toolbar-icon { width: 20px; height: 20px; flex-shrink: 0; }
</style>
