<script setup lang="ts">
import { ref, computed, nextTick, onMounted, onBeforeUnmount, watch } from 'vue'
import iconRightArrow from '../../assets/icons/right_arrow.svg'
import apiHelpData from '../../data/apiHelp.json'

defineProps<{ visible: boolean }>()
const emit = defineEmits<{ close: [] }>()

// ─── 面板宽度：可左右拖动调整，并记住上次宽度 ───
const MIN_PANEL_WIDTH = 280
const MAX_PANEL_WIDTH_RATIO = 0.9
const PANEL_WIDTH_KEY = 'bingo-help-panel-width'
const panelWidth = ref(340)
let resizeStartX = 0
let resizeStartWidth = 0
let resizing = false

function clampPanelWidth(w: number) {
  const max = Math.max(MIN_PANEL_WIDTH, Math.floor(window.innerWidth * MAX_PANEL_WIDTH_RATIO))
  return Math.min(Math.max(w, MIN_PANEL_WIDTH), max)
}

function startResize(e: MouseEvent) {
  if (e.button !== 0) return
  resizing = true
  resizeStartX = e.clientX
  resizeStartWidth = panelWidth.value
  // 拖动期间禁止选中文字，避免出现蓝色选区
  document.body.style.userSelect = 'none'
  document.body.style.cursor = 'col-resize'
  window.addEventListener('mousemove', onResizeMove)
  window.addEventListener('mouseup', stopResize)
  e.preventDefault()
}

function onResizeMove(e: MouseEvent) {
  if (!resizing) return
  // 向左拖动 = 变宽
  panelWidth.value = clampPanelWidth(resizeStartWidth + (resizeStartX - e.clientX))
}

function stopResize() {
  if (!resizing) return
  resizing = false
  document.body.style.userSelect = ''
  document.body.style.cursor = ''
  window.removeEventListener('mousemove', onResizeMove)
  window.removeEventListener('mouseup', stopResize)
  localStorage.setItem(PANEL_WIDTH_KEY, String(panelWidth.value))
}

onMounted(() => {
  const saved = Number(localStorage.getItem(PANEL_WIDTH_KEY))
  if (Number.isFinite(saved) && saved >= MIN_PANEL_WIDTH) {
    panelWidth.value = clampPanelWidth(saved)
  }
})

onBeforeUnmount(stopResize)

const expandedCards = ref<Record<string, boolean>>({})
const activeCategory = ref(0)
const searchQuery = ref('')

// 卡片各自独立展开/收起，切换卡片不会让已展开的卡片自动关闭
function toggleCard(ci: number, fi: number) {
  const key = `${ci}-${fi}`
  expandedCards.value[key] = !expandedCards.value[key]
}

// 搜索条件变化后卡片索引会变，先全部收起，避免展开到错误的卡片
watch(searchQuery, () => {
  expandedCards.value = {}
})

// ─── 展开/收起动画：按真实内容高度过渡，内容始终向下长出来，不做位移动画 ───
function animateHeight(el: Element, from: number, to: number, duration: number, done: () => void, extraFrom = 0, extraTo = 0) {
  const e = el as HTMLElement
  let finished = false
  const finish = () => {
    if (finished) return
    finished = true
    done()
  }
  const anim = e.animate(
    [
      { height: `${from}px`, opacity: extraFrom },
      { height: `${to}px`, opacity: extraTo },
    ],
    { duration, easing: 'cubic-bezier(0.25, 1, 0.5, 1)' },
  )
  anim.addEventListener('finish', finish)
  anim.addEventListener('cancel', finish)
}

function onBodyEnter(el: Element, done: () => void) {
  animateHeight(el, 0, (el as HTMLElement).scrollHeight, 220, done, 0, 1)
}

function onBodyLeave(el: Element, done: () => void) {
  animateHeight(el, (el as HTMLElement).offsetHeight, 0, 160, done, 1, 0)
}

function scrollToCategory(index: number) {
  activeCategory.value = index
  nextTick(() => {
    document.getElementById(`help-cat-${index}`)?.scrollIntoView()
  })
}

interface HelpFunc {
  label: string
  code: string
  desc: string
  badgeType?: string
}

interface HelpCategory {
  name: string
  color: string
  funcs: HelpFunc[]
}

// 文案数据来自 src/data/apiHelp.json：直接编辑 JSON 即可增删 API，保存后热更新
const categories: HelpCategory[] = (apiHelpData as unknown as { categories: HelpCategory[] }).categories

function getBadgeColor(type?: string) {
  switch (type) {
    case 'module': return '#4C97FF'
    case 'object': return '#59C759'
    case 'property': return '#FF8C1A'
    case 'function': return '#9966FF'
    default: return '#9966FF'
  }
}

const filteredCategories = computed(() => {
  if (!searchQuery.value.trim()) return categories

  const query = searchQuery.value.toLowerCase()
  return categories
    .map(cat => ({
      ...cat,
      funcs: cat.funcs.filter(
        f =>
          f.label.toLowerCase().includes(query) ||
          f.desc.toLowerCase().includes(query) ||
          f.code.toLowerCase().includes(query)
      ),
    }))
    .filter(cat => cat.funcs.length > 0)
})
</script>

<template>
  <Teleport to="body">
    <Transition name="help-slide">
      <div v-if="visible" class="help-overlay">
        <div class="help-panel" :style="{ width: panelWidth + 'px' }">
          <!-- 左侧拖拽把手：左右拖动调整面板宽度 -->
          <div class="help-resize-handle" @mousedown="startResize"></div>
          <!-- 标题栏 -->
          <div class="help-header">
            <div class="help-title-row">
              <img src="../../assets/icons/help.svg" class="help-header-icon" />
              <span class="help-title">API 帮助文档</span>
            </div>
            <button class="help-close-btn" @click="emit('close')">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M1 1L13 13M13 1L1 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <!-- 搜索框 -->
          <div class="help-search">
            <div class="help-search-box">
              <svg class="help-search-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
              </svg>
              <input
                v-model="searchQuery"
                type="text"
                class="help-search-input"
                placeholder="搜索 API、函数、属性..."
              />
              <button v-if="searchQuery" class="help-search-clear" @click="searchQuery = ''">
                <svg width="12" height="12" viewBox="0 0 14 14" fill="none">
                  <path d="M1 1L13 13M13 1L1 13" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
              </button>
            </div>
          </div>

          <!-- 主体：左侧分类 + 右侧内容 -->
          <div class="help-body">
            <!-- 左侧分类栏 -->
            <div class="help-sidebar">
              <button
                v-for="(cat, ci) in filteredCategories"
                :key="ci"
                class="help-sidebar-btn"
                :class="{ 'help-sidebar-btn-active': activeCategory === ci }"
                :style="{
                  borderLeftColor: activeCategory === ci ? cat.color : 'transparent',
                }"
                @click="scrollToCategory(ci)"
              >
                <span class="help-sidebar-dot" :style="{ background: cat.color }"></span>
                <span class="help-sidebar-name" :style="{ color: activeCategory === ci ? cat.color : '' }">{{ cat.name }}</span>
              </button>
            </div>

            <!-- 右侧内容 -->
            <div class="help-content">
              <div
                v-for="(cat, ci) in filteredCategories"
                :key="ci"
                :id="`help-cat-${ci}`"
                class="help-category-section"
              >
                <div class="help-category-header">
                  <span class="help-category-name" :style="{ color: cat.color }">{{ cat.name }}</span>
                  <div class="help-category-line" :style="{ background: cat.color }"></div>
                </div>

                <div class="help-card-list">
                  <div
                    v-for="(func, fi) in cat.funcs"
                    :key="fi"
                    class="help-func-card"
                    :class="{ 'help-func-card-expanded': expandedCards[`${ci}-${fi}`] }"
                  >
                    <button class="help-func-header" @click="toggleCard(ci, fi)">
                      <img
                        :src="iconRightArrow"
                        class="help-arrow-icon"
                        :class="{ 'help-arrow-expanded': expandedCards[`${ci}-${fi}`] }"
                      />
                      <span class="help-func-dot" :style="{ background: getBadgeColor(func.badgeType) }"></span>
                      <span class="help-func-label">{{ func.label }}</span>
                    </button>
                    <Transition :css="false" @enter="onBodyEnter" @leave="onBodyLeave">
                      <div v-if="expandedCards[`${ci}-${fi}`]" class="help-func-body">
                        <div class="help-func-body-inner">
                          <div class="help-func-code">
                            <code>{{ func.code }}</code>
                          </div>
                          <div class="help-func-desc">{{ func.desc }}</div>
                        </div>
                      </div>
                    </Transition>
                  </div>
                </div>
              </div>

              <!-- 无搜索结果 -->
              <div v-if="filteredCategories.length === 0" class="help-empty">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5">
                  <circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/>
                </svg>
                <span>没有找到匹配的内容</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.help-slide-enter-active,
.help-slide-leave-active { transition: opacity 0.25s ease; }
.help-slide-enter-active .help-panel,
.help-slide-leave-active .help-panel { transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1); }
.help-slide-enter-from,
.help-slide-leave-to { opacity: 0; }
.help-slide-enter-from .help-panel,
.help-slide-leave-to .help-panel { transform: translateX(100%); }

.help-overlay {
  position: fixed; inset: 0; z-index: 9000;
  display: flex; justify-content: flex-end;
  pointer-events: none;
}

.help-panel {
  position: relative;
  width: 340px; max-width: 90vw; height: 100%;
  pointer-events: auto;
  display: flex; flex-direction: column;
  background: var(--bg-root);
  border-left: 1px solid var(--border);
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.4);
}

/* 左侧拖拽把手：6px 热区，悬停显示一条浅灰竖线 */
.help-resize-handle {
  position: absolute; left: -3px; top: 0; bottom: 0; width: 6px;
  cursor: col-resize; z-index: 10;
}
.help-resize-handle:hover,
.help-resize-handle:active {
  background: linear-gradient(
    to right,
    transparent 0,
    transparent 2px,
    rgba(160, 160, 170, 0.45) 2px,
    rgba(160, 160, 170, 0.45) 4px,
    transparent 4px
  );
}

/* ── 标题栏 ── */
.help-header {
  display: flex; align-items: center; justify-content: space-between;
  height: 40px; min-height: 40px; padding: 0 16px;
  border-bottom: 1px solid var(--border);
}
.help-title-row { display: flex; align-items: center; gap: 8px; }
.help-header-icon { width: 20px; height: 20px; }
.help-title { font-size: 14px; font-weight: 600; color: white; }
.help-close-btn {
  display: flex; align-items: center; justify-content: center;
  width: 28px; height: 28px;
  background: transparent; border: none; border-radius: 4px;
  color: var(--text-secondary); cursor: pointer; transition: all 0.15s;
}
.help-close-btn:hover {   background: var(--bg-hover); color: white; }

/* ── 搜索框 ── */
.help-search {
  padding: 8px 12px; border-bottom: 1px solid var(--border);
}
.help-search-box {
  display: flex; align-items: center; gap: 8px;
  padding: 6px 10px;
  background: var(--bg-hover);
  border-radius: 6px; border: 1px solid var(--border-light);
}
.help-search-icon { color: var(--text-muted); flex-shrink: 0; }
.help-search-input {
  flex: 1; background: transparent; border: none; outline: none;
  font-size: 13px; color: white;
}
.help-search-input::placeholder { color: var(--text-muted); }
.help-search-clear {
  display: flex; align-items: center; justify-content: center;
  width: 20px; height: 20px; padding: 0;
  background: transparent; border: none; border-radius: 3px;
  color: var(--text-muted); cursor: pointer; transition: all 0.15s;
}
.help-search-clear:hover { background: rgba(255,255,255,0.1); color: white; }

/* ── 主体布局 ── */
.help-body {
  flex: 1; min-height: 0; overflow: hidden;
  display: flex;
}

/* ── 左侧分类栏 ── */
.help-sidebar {
  width: 40px; min-width: 40px;
  display: flex; flex-direction: column;
  border-right: 1px solid var(--border);
  overflow-y: auto; padding: 0;
}
.help-sidebar::-webkit-scrollbar { display: none; }

.help-sidebar-btn {
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 4px;
  height: 50px; min-height: 50px;
  background: transparent;
  border: none; border-left: 3px solid transparent;
  cursor: pointer; transition: all 0.15s;
  padding: 0;
}
.help-sidebar-btn:hover { background: rgba(255, 255, 255, 0.04); }
.help-sidebar-btn-active { background: rgba(255, 255, 255, 0.06); }

.help-sidebar-dot {
  width: 10px; height: 10px; min-width: 10px; min-height: 10px;
  border-radius: 50%;
}
.help-sidebar-name {
  font-size: 11px; color: rgb(140, 140, 140);
  line-height: 1; white-space: nowrap;
}
.help-sidebar-btn-active .help-sidebar-name { font-weight: 600; }

/* ── 内容滚动区 ── */
.help-content {
  flex: 1; min-height: 0; overflow-y: auto; padding: 12px 16px 0;
}
.help-content::after {
  content: '';
  display: block;
  height: 50vh;
}
.help-content::-webkit-scrollbar { width: 6px; }
.help-content::-webkit-scrollbar-track { background: transparent; }
.help-content::-webkit-scrollbar-thumb { background: rgb(60, 63, 70); border-radius: 3px; }

/* ── 分类区块 ── */
.help-category-section { margin-bottom: 24px; }
.help-category-section:last-child { margin-bottom: 0; }
.help-category-header {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 10px; padding: 4px 0;
}
.help-category-name { font-size: 14px; font-weight: 700; white-space: nowrap; }
.help-category-line { flex: 1; height: 2px; border-radius: 1px; opacity: 0.3; }

/* ── 卡片列表 ── */
.help-card-list { display: flex; flex-direction: column; gap: 3px; }

.help-func-card {
  border-radius: 8px; border: 1px solid var(--border-light);
  background: transparent; overflow: hidden; transition: background 0.12s;
}
.help-func-card:hover { background: rgba(255, 255, 255, 0.04); }
.help-func-card-expanded { background: rgba(255, 255, 255, 0.06); }

.help-func-header {
  display: flex; align-items: center; gap: 8px;
  width: 100%; padding: 8px 12px;
  background: transparent; border: none;
  color: white; cursor: pointer; text-align: left;
}
.help-func-header:hover { background: rgba(255, 255, 255, 0.03); }

.help-arrow-icon {
  width: 14px; height: 14px; flex-shrink: 0; opacity: 0.5;
  transition: transform 0.22s cubic-bezier(0.25, 1, 0.5, 1), opacity 0.22s ease;
}
/* 同一个右箭头旋转 90° 变向下箭头，过渡自然，不再切换两张图 */
.help-arrow-expanded { transform: rotate(90deg); opacity: 0.8; }

.help-func-dot {
  width: 8px; height: 8px; min-width: 8px;
  border-radius: 50%; flex-shrink: 0;
}

.help-func-label {
  font-size: 13px; color: rgb(230, 230, 230);
  font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
}

/* ── 展开内容 ── */
.help-func-body { overflow: hidden; }
.help-func-body-inner { padding: 0 12px 10px 34px; }

.help-func-code {
  margin-bottom: 6px; padding: 6px 10px;
  background: rgb(28, 28, 32);
  border-radius: 6px; border: 1px solid var(--border-light);
  overflow-x: auto;
}
.help-func-code::-webkit-scrollbar { height: 4px; }
.help-func-code::-webkit-scrollbar-track { background: transparent; }
.help-func-code::-webkit-scrollbar-thumb { background: rgb(60, 63, 70); border-radius: 2px; }
.help-func-code code {
  font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
  font-size: 12px; color: rgb(156, 227, 170);
  white-space: pre; user-select: all;
}

.help-func-desc {
  font-size: 12.5px; line-height: 1.7;
  color: rgb(180, 180, 180);
  /* JSON 文案里的 \n 会渲染成换行，长句仍自动折行 */
  white-space: pre-line;
}

/* ── 空状态 ── */
.help-empty {
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 12px; padding: 60px 20px;
  color: var(--text-muted); font-size: 13px;
}
</style>
