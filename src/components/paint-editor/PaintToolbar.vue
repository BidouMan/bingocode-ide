<script setup lang="ts">
import { computed } from 'vue'
import { usePaintStore, type PaintTool } from '../../stores/paint'

import iconSelect from '../../assets/icons/选择箭头.svg'
import iconReshape from '../../assets/icons/移动锚点.svg'
import iconBrush from '../../assets/icons/icon--paint.svg'
import iconEraser from '../../assets/icons/清空.svg'
import iconFill from '../../assets/icons/填充_fill.svg'
import iconLine from '../../assets/icons/直线工具.svg'
import iconRect from '../../assets/icons/矩形_rectangle.svg'
import iconEllipse from '../../assets/icons/圆形_round.svg'
import iconText from '../../assets/icons/文字_text.svg'
import iconEyedropper from '../../assets/icons/取色器.svg'
import iconClear from '../../assets/icons/清空画布.svg'

const ICONS: Record<PaintTool, string> = {
  select: iconSelect,
  reshape: iconReshape,
  brush: iconBrush,
  eraser: iconEraser,
  fill: iconFill,
  line: iconLine,
  rect: iconRect,
  ellipse: iconEllipse,
  text: iconText,
  eyedropper: iconEyedropper,
}

const LABELS: Record<PaintTool, string> = {
  select: '选择',
  reshape: '塑形',
  brush: '画笔',
  eraser: '橡皮',
  fill: '填充',
  line: '直线',
  rect: '矩形',
  ellipse: '椭圆',
  text: '文字',
  eyedropper: '取色',
}

// 工具集随模式切换（对齐 Scratch 官方两套工具集，仅参考 UX 规格）：
// 矢量 = 选择/塑形/画笔/橡皮/填充/文字/直线/矩形/椭圆（reshape 仅矢量）
// 位图 = 画笔/直线/矩形/椭圆/文字/填充/橡皮/选择（无 reshape，Brush 打头）
const VECTOR_TOOLS: PaintTool[] = [
  'select', 'reshape', 'brush', 'eraser', 'fill', 'text', 'line', 'rect', 'ellipse', 'eyedropper',
]
const BITMAP_TOOLS: PaintTool[] = [
  'brush', 'line', 'rect', 'ellipse', 'text', 'fill', 'eraser', 'select', 'eyedropper',
]

const store = usePaintStore()

const tools = computed(() =>
  (store.mode === 'vector' ? VECTOR_TOOLS : BITMAP_TOOLS).map((key) => ({
    key,
    icon: ICONS[key],
    label: LABELS[key],
  }))
)

const emit = defineEmits<{
  clear: []
}>()
</script>

<template>
  <div class="paint-toolbar">
    <button
      v-for="tool in tools"
      :key="tool.key"
      class="tool-btn"
      :class="{ 'tool-btn-active': store.activeTool === tool.key }"
      v-tooltip="tool.label"
      @click="store.setTool(tool.key)"
    >
      <img :src="tool.icon" class="tool-icon" draggable="false" />
    </button>

    <div class="tool-divider"></div>

    <button class="tool-btn" v-tooltip="'清空画板'" @click="emit('clear')">
      <img :src="iconClear" class="tool-icon" draggable="false" />
    </button>
  </div>
</template>

<style scoped>
.paint-toolbar {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 48px;
  padding: 6px 0;
  gap: 4px;
  background: var(--bg-base);
  border-right: 1px solid var(--border);
  flex-shrink: 0;
  overflow-y: auto;
}

.tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  padding: 0;
  transition: background 0.15s;
  position: relative;
}
.tool-btn:hover {
  background: var(--bg-hover);
}
.tool-btn-active {
  background: var(--bg-hover);
}
.tool-btn-active::before {
  content: '';
  position: absolute;
  left: -4px;
  top: 6px;
  bottom: 6px;
  width: 2px;
  border-radius: 1px;
  background: var(--accent);
}

.tool-icon {
  width: 22px;
  height: 22px;
  pointer-events: none;
}

.tool-divider {
  width: 28px;
  height: 1px;
  margin: 4px 0;
  background: var(--border-light);
  flex-shrink: 0;
}
</style>
