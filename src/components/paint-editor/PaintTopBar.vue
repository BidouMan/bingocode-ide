<script setup lang="ts">
import { computed } from 'vue'
import { usePaintStore, ARTBOARD_MAX } from '../../stores/paint'

import iconCrop from '../../assets/icons/裁切画板.svg'
import iconCopy from '../../assets/icons/copy.svg'
import iconPaste from '../../assets/icons/粘贴.svg'
import iconDeleteSel from '../../assets/icons/选中删除.svg'
import iconFlipH from '../../assets/icons/水平翻转.svg'
import iconFlipV from '../../assets/icons/垂直翻转.svg'
import iconGroup from '../../assets/icons/组合.svg'
import iconUngroup from '../../assets/icons/取消组合.svg'
import iconLayerUp from '../../assets/icons/上移图层.svg'
import iconLayerDown from '../../assets/icons/下移图层.svg'
import iconCurve from '../../assets/icons/曲线.svg'
import iconStraight from '../../assets/icons/折线.svg'
import iconSnap from '../../assets/icons/吸附锚点.svg'
import iconGrid from '../../assets/icons/显示网格.svg'

const props = defineProps<{
  /** 保存按钮提示（编辑模式为「保存回角色」） */
  saveTitle?: string
  /** 是否允许保存（地图绘制即使未落笔也要能把画板落盘；未传则按画板 dirty 判断） */
  canSave?: boolean
}>()

/** 保存按钮可用性：外部显式指定优先（地图绘制恒可保存） */
const saveAllowed = computed(() => props.canSave ?? store.dirty)

const emit = defineEmits<{
  close: []
  save: []
  crop: []
  /** 画布尺寸变更（手动输入宽高，居中锚定；offset = 新画布左上角在原画布中的坐标） */
  resize: [w: number, h: number, offsetX: number, offsetY: number]
  /** 选中图形尺寸变更（输入宽高，绕图形中心缩放；矢量/位图统一路由到画板） */
  resizeShape: [w: number, h: number]
  copy: []
  paste: []
  deleteSel: []
  flipH: []
  flipV: []
  group: []
  ungroup: []
  layerUp: []
  layerDown: []
  /** 塑形：选中锚点曲线化/折线化 */
  curvePoints: []
  pointPoints: []
}>()

const store = usePaintStore()

/** 网格尺寸输入：clamp 1~ARTBOARD_MAX，失焦/回车提交（默认值 = 当前地图图块尺寸） */
function commitGridSize(e: Event) {
  const el = e.target as HTMLInputElement
  let v = Math.round(Number(el.value))
  if (!Number.isFinite(v)) v = store.gridSize
  v = Math.min(ARTBOARD_MAX, Math.max(1, v))
  store.gridSize = v
  el.value = String(v)
}

// ─── 模式感知的可用状态（位图看选区/剪贴板，矢量看对象选中/矢量剪贴板）───
const isVector = () => store.mode === 'vector'
const canCopy = () => (isVector() ? store.vectorSelectedCount > 0 : !!store.selection)
const canPaste = () => (isVector() ? store.hasVectorClipboard : !!store.hasClipboard)

// ─── 塑形锚点形态 toggle：选中锚点含手柄=曲线态；无手柄或未选=折线态（默认折线）───
const reshapeCurveActive = () => store.reshapeHasPointed
// 激活侧点击为安全空操作；未激活侧仅在确有可转换锚点时可点
const curveDisabled = () => !store.reshapeHasUncurved && !store.reshapeHasPointed
const pointDisabled = () => false

/** 选中图形尺寸模式：有图形选中时，同一组输入框改为显示/修改该图形的宽高 */
const shapeMode = computed(() => store.shapeSize !== null)
const sizeW = computed(() => Math.round(shapeMode.value ? store.shapeSize!.w : store.artboardWidth))
const sizeH = computed(() => Math.round(shapeMode.value ? store.shapeSize!.h : store.artboardHeight))

/** 手动输入尺寸：clamp 1~2048，失焦/回车提交（画板居中锚定；选中图形绕中心缩放） */
function commitSize(axis: 'w' | 'h', e: Event) {
  const el = e.target as HTMLInputElement
  let v = Math.round(Number(el.value))
  if (!Number.isFinite(v)) {
    v = axis === 'w' ? sizeW.value : sizeH.value
  }
  v = Math.min(ARTBOARD_MAX, Math.max(1, v))
  // 有选中图形：输入框改的是图形尺寸（保持中心与旋转角不变）
  if (shapeMode.value) {
    const s = store.shapeSize!
    // 未编辑的那一轴用原始精确值，避免四舍五入顺带改动另一方向
    const w = axis === 'w' ? v : Math.max(1, s.w)
    const h = axis === 'h' ? v : Math.max(1, s.h)
    emit('resizeShape', w, h)
    el.value = String(axis === 'w' ? (Math.round(store.shapeSize?.w ?? w)) : (Math.round(store.shapeSize?.h ?? h)))
    return
  }
  const w = axis === 'w' ? v : store.artboardWidth
  const h = axis === 'h' ? v : store.artboardHeight
  // 居中锚定（对齐 Photoshop「画布大小」默认锚点）：内容保持居中，四周均匀增减；
  // 缩小时两侧各裁一半，扩大时两侧各加一半空边
  emit(
    'resize',
    w,
    h,
    Math.round((store.artboardWidth - w) / 2),
    Math.round((store.artboardHeight - h) / 2)
  )
  el.value = String(axis === 'w' ? store.artboardWidth : store.artboardHeight)
}
</script>

<template>
  <div class="paint-topbar">
    <!-- 左：矢量 | 位图 模式切换 -->
    <div class="mode-switch">
      <button
        class="mode-btn"
        :class="{ 'mode-btn-active': store.mode === 'vector' }"
        :disabled="!store.vectorEnabled"
        :title="store.vectorEnabled ? '矢量模式' : '矢量模式即将开放'"
        @click="store.setMode('vector')"
      >
        矢量
      </button>
      <button
        class="mode-btn"
        :class="{ 'mode-btn-active': store.mode === 'bitmap' }"
        title="位图模式"
        @click="store.setMode('bitmap')"
      >
        位图
      </button>
    </div>

    <!-- 中右：尺寸输入（有选中图形时显示/编辑该图形尺寸，否则为画板尺寸）+ 手动裁切 -->
    <div
      class="size-inputs"
      :title="
        shapeMode
          ? '选中图形尺寸（输入后回车生效）'
          : store.sizeForced
            ? '当前模式画布尺寸已锁定，不可修改'
            : '画板尺寸（失焦或回车生效）'
      "
    >
      <input
        class="size-input"
        type="number"
        min="1"
        :max="ARTBOARD_MAX"
        :disabled="!shapeMode && store.sizeForced"
        :value="sizeW"
        :aria-label="shapeMode ? '图形宽度' : '画板宽度'"
        @change="commitSize('w', $event)"
        @keydown.enter="commitSize('w', $event)"
      />
      <span class="size-x">×</span>
      <input
        class="size-input"
        type="number"
        min="1"
        :max="ARTBOARD_MAX"
        :disabled="!shapeMode && store.sizeForced"
        :value="sizeH"
        :aria-label="shapeMode ? '图形高度' : '画板高度'"
        @change="commitSize('h', $event)"
        @keydown.enter="commitSize('h', $event)"
      />
      <span class="size-unit">px</span>
    </div>
    <button
      class="icon-btn"
      :class="{ 'icon-btn-active': store.cropMode }"
      :disabled="store.sizeForced"
      v-tooltip="store.sizeForced ? '当前模式画布尺寸已锁定' : '手动裁切画布（拖拽锚点，回车确认）'"
      @click="emit('crop')"
    >
      <img :src="iconCrop" class="icon-sm" draggable="false" />
    </button>

    <!-- 塑形工具专属：选中锚点形态 toggle（曲线 ⇄ 折线，二选一激活；默认折线） -->
    <div v-if="store.mode === 'vector' && store.activeTool === 'reshape'" class="op-group">
      <button
        class="icon-btn"
        :class="{ 'icon-btn-active': reshapeCurveActive() }"
        :disabled="curveDisabled()"
        v-tooltip="reshapeCurveActive() ? '曲线（当前）' : '选中锚点转为曲线'"
        @click="emit('curvePoints')"
      >
        <img :src="iconCurve" class="icon-sm" draggable="false" />
      </button>
      <button
        class="icon-btn"
        :class="{ 'icon-btn-active': !reshapeCurveActive() }"
        :disabled="pointDisabled()"
        v-tooltip="!reshapeCurveActive() ? '折线（当前）' : '选中锚点转为折线（尖角）'"
        @click="emit('pointPoints')"
      >
        <img :src="iconStraight" class="icon-sm" draggable="false" />
      </button>
    </div>

    <!-- 选区/对象操作组（工业软件 options bar 风格，按模式切换可用性） -->
    <div class="op-group">
      <button class="icon-btn" :disabled="!canCopy()" v-tooltip="isVector() ? '复制对象 (Ctrl+C)' : '复制选区 (Ctrl+C)'" @click="emit('copy')">
        <img :src="iconCopy" class="icon-sm" draggable="false" />
      </button>
      <button class="icon-btn" :disabled="!canPaste()" v-tooltip="isVector() ? '粘贴对象 (Ctrl+V)' : '粘贴 (Ctrl+V)'" @click="emit('paste')">
        <img :src="iconPaste" class="icon-sm" draggable="false" />
      </button>
      <button class="icon-btn" :disabled="!canCopy()" v-tooltip="isVector() ? '删除对象 (Delete)' : '删除选区 (Delete)'" @click="emit('deleteSel')">
        <img :src="iconDeleteSel" class="icon-sm" draggable="false" />
      </button>
      <!-- 矢量专属：组合/解组/图层（位图无对象层级，整组隐藏） -->
      <template v-if="isVector()">
        <div class="op-divider"></div>
        <button class="icon-btn" :disabled="store.vectorSelectedCount < 2" v-tooltip="'组合选中对象'" @click="emit('group')">
          <img :src="iconGroup" class="icon-sm" draggable="false" />
        </button>
        <button class="icon-btn" :disabled="!store.vectorCanUngroup" v-tooltip="'取消组合'" @click="emit('ungroup')">
          <img :src="iconUngroup" class="icon-sm" draggable="false" />
        </button>
        <button class="icon-btn" :disabled="store.vectorSelectedCount < 1" v-tooltip="'上移一层'" @click="emit('layerUp')">
          <img :src="iconLayerUp" class="icon-sm" draggable="false" />
        </button>
        <button class="icon-btn" :disabled="store.vectorSelectedCount < 1" v-tooltip="'下移一层'" @click="emit('layerDown')">
          <img :src="iconLayerDown" class="icon-sm" draggable="false" />
        </button>
      </template>
      <div class="op-divider"></div>
      <button class="icon-btn" v-tooltip="'水平翻转（无选区时翻转整层/整帧）'" @click="emit('flipH')">
        <img :src="iconFlipH" class="icon-sm" draggable="false" />
      </button>
      <button class="icon-btn" v-tooltip="'垂直翻转（无选区时翻转整层/整帧）'" @click="emit('flipV')">
        <img :src="iconFlipV" class="icon-sm" draggable="false" />
      </button>
      <div class="op-divider"></div>
      <button
        class="icon-btn"
        :class="{ 'icon-btn-active': store.smartSnap }"
        v-tooltip="
          store.smartSnap
            ? (store.showGrid
              ? '智能吸附已开启（对齐画板的边与中心、其它图形，以及网格线）'
              : '智能吸附已开启（拖动/缩放时对齐画板的边与中心、其它图形的边与中心）')
            : '智能吸附已关闭（完全自由移动）'
        "
        @click="store.toggleSmartSnap()"
      >
        <img :src="iconSnap" class="icon-sm" draggable="false" />
      </button>
    </div>

    <!-- 网格开关组（吸附按钮右侧）：开启后显示网格线，并在右侧出现「网格尺寸」输入框；
         与吸附按钮保持 4px 同组间距，输入控件展开后自带 4px 间距，不再额外加分割线 -->
    <div class="grid-group">
      <button
        class="icon-btn"
        :class="{ 'icon-btn-active': store.showGrid }"
        v-tooltip="store.showGrid ? '隐藏网格' : '显示网格（按地图图块的网格尺寸）'"
        @click="store.toggleGrid()"
      >
        <img :src="iconGrid" class="icon-sm" draggable="false" />
      </button>
      <template v-if="store.showGrid">
        <span class="grid-label">网格尺寸</span>
        <input
          class="size-input grid-size-input"
          type="number"
          min="1"
          :max="ARTBOARD_MAX"
          :value="store.gridSize"
          title="网格尺寸（px，失焦或回车生效）"
          aria-label="网格尺寸"
          @change="commitGridSize"
          @keydown.enter="commitGridSize"
        />
        <span class="size-unit">px</span>
      </template>
    </div>

    <div class="topbar-spacer"></div>

    <!-- 最右：关闭 + 保存 -->
    <div class="topbar-actions">
      <button class="back-btn" v-tooltip="'关闭'" @click="emit('close')">
        <span>关闭</span>
      </button>
      <button
        class="save-btn"
        :disabled="!saveAllowed"
        :title="saveAllowed ? (props.saveTitle || '保存为新角色') : '画板为空，先画点什么'"
        @click="emit('save')"
      >
        <span>保存</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.paint-topbar {
  --ctl-h: 30px; /* 顶栏所有按钮/输入框统一高度 */
  display: flex;
  align-items: center;
  height: 44px;
  padding: 0 10px 0 4px;
  /* 统一间距基准：工具栏内按钮/控件/分组之间、分隔线两侧一律 4px
     （矢量|位图 属于整体分段控件，其内部 2px 缝隙保持不变） */
  gap: 4px;
  background: var(--bg-base);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
  user-select: none;
  position: relative;
  /* 窄窗口下按钮不压缩、不换行：内容超出由窗口裁剪，图标保持原样 */
  flex-wrap: nowrap;
  overflow: hidden;
}

/* 纯白 SVG 图标在暗色主题下直接可见，无需滤镜 */

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: var(--ctl-h);
  height: var(--ctl-h);
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  padding: 0;
  flex-shrink: 0;
  transition: background 0.15s;
}
.icon-btn:hover:not(:disabled) {
  background: var(--bg-hover);
}
.icon-btn:disabled {
  opacity: 0.35;
  cursor: default;
}
/* toggle 激活态（曲线/折线互斥）：对齐 mode-btn-active */
.icon-btn-active,
.icon-btn-active:hover:not(:disabled) {
  background: var(--bg-active);
}

.icon-sm {
  width: 18px;
  height: 18px;
  pointer-events: none;
}

/* 矢量|位图 分段切换（不参与压缩：窄窗口下文字不竖排） */
.mode-switch {
  display: flex;
  align-items: center;
  height: var(--ctl-h);
  background: var(--bg-panel);
  border-radius: 6px;
  padding: 2px;
  gap: 2px;
  flex-shrink: 0;
}

.mode-btn {
  height: calc(var(--ctl-h) - 4px);
  padding: 0 12px;
  font-size: 12px;
  line-height: calc(var(--ctl-h) - 4px);
  color: var(--text-muted);
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
}
.mode-btn:hover:not(:disabled):not(.mode-btn-active) {
  color: var(--text-secondary);
}
/* 激活态：强调绿底 + 深色文字（亮绿底上深色对比最佳） */
.mode-btn-active {
  background: var(--accent);
  color: #16201a;
  font-weight: 600;
}
.mode-btn:disabled {
  opacity: 0.45;
  cursor: default;
}

.size-inputs {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.size-input {
  width: 54px;
  height: var(--ctl-h);
  padding: 0 6px;
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 5px;
  outline: none;
  text-align: center;
  /* 隐藏 number 上下箭头，保持紧凑 */
  -moz-appearance: textfield;
  appearance: textfield;
}
.size-input::-webkit-outer-spin-button,
.size-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
/* 悬停时不要压过聚焦描边：否则刚点进去还是悬停色，必须先移开鼠标才变绿 */
.size-input:hover:not(:disabled):not(:focus) {
  border-color: var(--text-muted);
}
.size-input:focus {
  border-color: var(--accent);
}
.size-input:disabled {
  opacity: 0.45;
  cursor: default;
}

.size-x {
  font-size: 12px;
  color: var(--text-muted);
}

.size-unit {
  font-size: 11px;
  color: var(--text-muted);
}

.topbar-spacer {
  flex: 1;
}

/* 网格开关组：紧跟吸附按钮，间距与其它按钮一致（4px） */
.grid-group {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

/* 网格尺寸标签（仅网格开启时出现在开关右侧） */
.grid-label {
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
  flex-shrink: 0;
}

.grid-size-input {
  width: 52px;
}

/* 选区/对象操作组 */
.op-group {
  display: flex;
  align-items: center;
  gap: 4px;
  /* 与组内间距一致：分割线左侧 4px（由顶栏 gap 提供），右侧 4px */
  padding-left: 4px;
  border-left: 1px solid var(--border-light);
  flex-shrink: 0;
}

.op-divider {
  width: 1px;
  height: 16px;
  margin: 0;
  background: var(--border-light);
}

/* 最右关闭/保存组：与下方 200px 颜色面板左右各留 10px，
   两个按钮等宽并与颜色面板整体水平居中 */
.topbar-actions {
  position: absolute;
  right: 10px;
  width: 180px; /* 面板 200px − 左右各 10px 间距 */
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

/* 关闭：次级按钮（描边幽灵风，占列内剩余宽度） */
.back-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  height: var(--ctl-h);
  flex: 1 1 0;
  min-width: 0;
  padding: 0 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  white-space: nowrap;
  background: transparent;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, border-color 0.15s;
}
.back-btn:hover {
  background: var(--bg-hover);
  color: var(--text);
  border-color: var(--text-muted);
}

/* 保存：主操作（中深绿底 + 纯白文字；brightness 1.15 = 背景与前景整体提亮 15%） */
.save-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  height: var(--ctl-h);
  flex: 1 1 0; /* 与关闭等宽 */
  min-width: 0;
  padding: 0 8px;
  font-size: 12px;
  font-weight: 600;
  color: #ffffff;
  white-space: nowrap;
  background: #2b8a48;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  filter: brightness(1.15);
  transition: background 0.15s, opacity 0.15s;
}
.save-btn:hover:not(:disabled) {
  background: #33a056;
}
.save-btn:disabled {
  opacity: 0.45;
  cursor: default;
}
</style>
