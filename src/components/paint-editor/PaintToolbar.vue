<script setup lang="ts">
import { usePaintStore, type PaintTool } from '../../stores/paint'

import iconSelect from '../../assets/icons/选取工具.svg'
import iconReshape from '../../assets/icons/移动锚点.svg'
import iconBrush from '../../assets/icons/icon--paint.svg'
import iconEraser from '../../assets/icons/icon--delete.svg'
import iconFill from '../../assets/icons/填充.svg'
import iconLine from '../../assets/icons/添加锚点.svg'
import iconRect from '../../assets/icons/新建地图.svg'
import iconEllipse from '../../assets/icons/btn_preview_scale.svg'
import iconText from '../../assets/icons/代码编辑.svg'
import iconEyedropper from '../../assets/icons/重置.svg'
import iconClear from '../../assets/icons/清空.svg'

// 工具顺序与 Scratch 造型编辑器一致（选择/塑形/画笔/橡皮/填充/直线/矩形/椭圆/文字/取色）
// 图标均为现有资源占位，功能完成后统一替换
const TOOLS: { key: PaintTool; icon: string; label: string }[] = [
  { key: 'select', icon: iconSelect, label: '选择' },
  { key: 'reshape', icon: iconReshape, label: '塑形' },
  { key: 'brush', icon: iconBrush, label: '画笔' },
  { key: 'eraser', icon: iconEraser, label: '橡皮' },
  { key: 'fill', icon: iconFill, label: '填充' },
  { key: 'line', icon: iconLine, label: '直线' },
  { key: 'rect', icon: iconRect, label: '矩形' },
  { key: 'ellipse', icon: iconEllipse, label: '椭圆' },
  { key: 'text', icon: iconText, label: '文字' },
  { key: 'eyedropper', icon: iconEyedropper, label: '取色' },
]

const store = usePaintStore()

const emit = defineEmits<{
  clear: []
}>()
</script>

<template>
  <div class="paint-toolbar">
    <button
      v-for="tool in TOOLS"
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
