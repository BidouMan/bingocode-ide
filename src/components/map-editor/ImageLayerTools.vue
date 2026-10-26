<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useMapStore } from '../../stores/map'
import { useMapEditorStore } from '../../stores/mapEditor'
import { usePaintStore } from '../../stores/paint'
import iconSelectArrow from '../../assets/icons/选择箭头.svg'
import iconSelect from '../../assets/icons/选取工具.svg'
import iconReshape from '../../assets/icons/移动锚点.svg'
import iconPaint from '../../assets/icons/icon--paint.svg'
import iconErase from '../../assets/icons/清空.svg'
import iconFill from '../../assets/icons/填充_fill.svg'
import iconText from '../../assets/icons/文字_text.svg'
import iconLine from '../../assets/icons/直线工具.svg'
import iconRect from '../../assets/icons/矩形_rectangle.svg'
import iconEllipse from '../../assets/icons/圆形_round.svg'
import iconPen from '../../assets/icons/钢笔工具.svg'
import iconCopy from '../../assets/icons/copy.svg'
import iconPaste from '../../assets/icons/粘贴.svg'
import iconFlipH from '../../assets/icons/水平翻转.svg'
import iconFlipV from '../../assets/icons/垂直翻转.svg'
import iconDelete from '../../assets/icons/选中删除.svg'
import iconGroup from '../../assets/icons/组合.svg'
import iconUngroup from '../../assets/icons/取消组合.svg'
import iconLayerUp from '../../assets/icons/上移图层.svg'
import iconLayerDown from '../../assets/icons/下移图层.svg'
import iconEdit from '../../assets/icons/编辑1.svg'

defineProps<{ disabled?: boolean }>()
const emit = defineEmits<{
  'delete-selection': []
  'copy-selection': []
  'paste-selection': []
  'flip-h': []
  'flip-v': []
  'group': []
  'ungroup': []
  'layer-up': []
  'layer-down': []
  'switch-paint-mode': [mode: 'bitmap' | 'vector']
  'create-layer': [tool: 'brush' | 'eraser' | 'fill' | 'line' | 'rect' | 'ellipse' | 'pen' | 'text' | 'reshape' | 'eyedropper']
}>()

const mapStore = useMapStore()
const mapEditorStore = useMapEditorStore()
const paintStore = usePaintStore()

const BITMAP_TOOLS = [
  { id: 'brush' as const, icon: iconPaint, label: '画笔' },
  { id: 'eraser' as const, icon: iconErase, label: '橡皮' },
  { id: 'fill' as const, icon: iconFill, label: '填充' },
  { id: 'line' as const, icon: iconLine, label: '直线' },
  { id: 'rect' as const, icon: iconRect, label: '矩形' },
  { id: 'ellipse' as const, icon: iconEllipse, label: '椭圆' },
]
const VECTOR_TOOLS = [
  { id: 'reshape' as const, icon: iconReshape, label: '塑形' },
  { id: 'brush' as const, icon: iconPaint, label: '画笔' },
  { id: 'eraser' as const, icon: iconErase, label: '橡皮' },
  { id: 'fill' as const, icon: iconFill, label: '填充' },
  { id: 'text' as const, icon: iconText, label: '文字' },
  { id: 'line' as const, icon: iconLine, label: '直线' },
  { id: 'rect' as const, icon: iconRect, label: '矩形' },
  { id: 'ellipse' as const, icon: iconEllipse, label: '椭圆' },
  { id: 'pen' as const, icon: iconPen, label: '自定义形状' },
]

const isVector = computed(() => mapEditorStore.paintMode === 'vector')
const paintTools = computed(() => (isVector.value ? VECTOR_TOOLS : BITMAP_TOOLS))
const selectIcon = computed(() => (isVector.value ? iconSelectArrow : iconSelect))
const canCopy = computed(() =>
  isVector.value ? paintStore.vectorSelectedCount > 0 : mapEditorStore.hasPixelSelection
)
const canPaste = computed(() =>
  isVector.value ? paintStore.hasVectorClipboard : mapEditorStore.hasPaintClipboard
)

// 选区操作菜单：常驻显示
const editMenuOpen = ref(false)
const editMenuStyle = ref<Record<string, string>>({})

function toggleEditMenu(e: MouseEvent) {
  if (editMenuOpen.value) {
    editMenuOpen.value = false
    return
  }
  const btn = e.currentTarget as HTMLElement
  const r = btn.getBoundingClientRect()
  const width = 132
  const height = isVector.value ? 306 : 196
  let left = Math.min(window.innerWidth - width - 8, r.left)
  left = Math.max(8, left)
  let top = r.bottom + 4
  if (top + height > window.innerHeight - 8) top = Math.max(8, r.top - height - 4)
  editMenuStyle.value = { left: `${left}px`, top: `${top}px` }
  editMenuOpen.value = true
}

function runEditAction(action: () => void) {
  editMenuOpen.value = false
  action()
}

function onWindowPointerDown(e: PointerEvent) {
  if (!editMenuOpen.value) return
  const t = e.target as HTMLElement | null
  if (!t || !t.closest('.edit-op-wrap')) editMenuOpen.value = false
}

onMounted(() => window.addEventListener('pointerdown', onWindowPointerDown))
onBeforeUnmount(() => window.removeEventListener('pointerdown', onWindowPointerDown))

function switchMode(mode: 'bitmap' | 'vector') {
  if (mode === 'vector' && !mapStore.selectedImage && mapStore.activeLayer?.type === 'image') {
    mapStore.selectImage(mapStore.activeLayer.id)
  }
  emit('switch-paint-mode', mode)
}

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
  mapEditorStore.setImageTool(tool)
  paintStore.setTool(tool)
}
</script>

<template>
  <!-- 矢量/位图模式切换 -->
  <div class="mode-switch">
    <button
      class="mode-btn"
      :class="{ 'mode-btn-active': isVector }"
      :disabled="disabled"
      title="矢量模式"
      @click="switchMode('vector')"
    >矢量</button>
    <button
      class="mode-btn"
      :class="{ 'mode-btn-active': !isVector }"
      :disabled="disabled"
      title="位图模式"
      @click="switchMode('bitmap')"
    >位图</button>
  </div>

  <div class="toolbar-separator" />

  <button
    class="toolbar-btn"
    :class="{ 'toolbar-btn-active': mapEditorStore.imageTool === 'select' }"
    :disabled="disabled"
    v-tooltip="'选取/移动'"
    @click="setTool('select')"
  >
    <img :src="selectIcon" class="toolbar-icon" />
  </button>

  <!-- 选区操作折叠菜单：常驻显示，位于选择工具右侧 -->
  <div class="edit-op-wrap">
    <button
      class="toolbar-btn"
      :class="{ 'toolbar-btn-active': editMenuOpen }"
      :disabled="disabled"
      v-tooltip="'选区操作'"
      @click.stop="toggleEditMenu($event)"
    >
      <img :src="iconEdit" class="toolbar-icon" />
    </button>
    <div v-if="editMenuOpen" class="edit-op-menu" :style="editMenuStyle">
      <button class="edit-op-item" :disabled="disabled || !canCopy" @click="runEditAction(() => emit('copy-selection'))">
        <img :src="iconCopy" class="edit-op-icon" />
        <span>复制</span>
      </button>
      <button class="edit-op-item" :disabled="disabled || !canPaste" @click="runEditAction(() => emit('paste-selection'))">
        <img :src="iconPaste" class="edit-op-icon" />
        <span>粘贴</span>
      </button>
      <button class="edit-op-item" :disabled="disabled || !canCopy" @click="runEditAction(() => emit('delete-selection'))">
        <img :src="iconDelete" class="edit-op-icon" />
        <span>删除</span>
      </button>
      <div class="edit-op-sep" />
      <button class="edit-op-item" :disabled="disabled" @click="runEditAction(() => emit('flip-h'))">
        <img :src="iconFlipH" class="edit-op-icon" />
        <span>水平翻转</span>
      </button>
      <button class="edit-op-item" :disabled="disabled" @click="runEditAction(() => emit('flip-v'))">
        <img :src="iconFlipV" class="edit-op-icon" />
        <span>垂直翻转</span>
      </button>
      <template v-if="isVector">
        <div class="edit-op-sep" />
        <button class="edit-op-item" :disabled="disabled || paintStore.vectorSelectedCount < 2" @click="runEditAction(() => emit('group'))">
          <img :src="iconGroup" class="edit-op-icon" />
          <span>组合</span>
        </button>
        <button class="edit-op-item" :disabled="disabled || !paintStore.vectorCanUngroup" @click="runEditAction(() => emit('ungroup'))">
          <img :src="iconUngroup" class="edit-op-icon" />
          <span>取消组合</span>
        </button>
        <button class="edit-op-item" :disabled="disabled || paintStore.vectorSelectedCount < 1" @click="runEditAction(() => emit('layer-up'))">
          <img :src="iconLayerUp" class="edit-op-icon" />
          <span>上移一层</span>
        </button>
        <button class="edit-op-item" :disabled="disabled || paintStore.vectorSelectedCount < 1" @click="runEditAction(() => emit('layer-down'))">
          <img :src="iconLayerDown" class="edit-op-icon" />
          <span>下移一层</span>
        </button>
      </template>
    </div>
  </div>

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

/* 矢量|位图 分段切换：与角色编辑器 PaintTopBar 完全一致 */
.mode-switch {
  display: flex;
  align-items: center;
  background: var(--bg-panel);
  border-radius: 6px;
  padding: 2px;
  gap: 2px;
  flex-shrink: 0;
}

.mode-btn {
  padding: 4px 12px;
  font-size: 12px;
  color: var(--text-muted);
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s, color 0.15s;
}

.mode-btn:hover:not(:disabled):not(.mode-btn-active) {
  color: var(--text-secondary);
}

.mode-btn-active {
  background: var(--accent);
  color: #16201a;
  font-weight: 600;
}

.mode-btn:disabled {
  opacity: 0.45;
  cursor: default;
}

.brush-color:disabled,
.brush-size:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.toolbar-separator { width: 1px; height: 20px; background: var(--border-light); margin: 0 2px; }

/* 选区操作折叠菜单 */
.edit-op-wrap {
  position: relative;
  display: flex;
}

.edit-op-menu {
  position: fixed;
  z-index: 1000;
  width: 132px;
  padding: 4px;
  display: flex;
  flex-direction: column;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
}

.edit-op-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  height: 30px;
  padding: 0 8px;
  background: transparent;
  border: none;
  border-radius: 5px;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  text-align: left;
  white-space: nowrap;
}

.edit-op-item:hover:not(:disabled) {
  background: var(--bg-hover);
  color: var(--text);
}

.edit-op-item:disabled {
  opacity: 0.35;
  cursor: default;
}

.edit-op-icon {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.edit-op-sep {
  height: 1px;
  margin: 4px 6px;
  background: var(--border-light);
}
</style>
