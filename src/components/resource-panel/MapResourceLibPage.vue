<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useMapResourceLibStore } from '../../stores/mapResourceLib'
import type { MapResourceItem, ResourceCategory } from '../../stores/mapResourceLib'
import { searchItems } from '../../utils/assetSearch'
import { fitPixelThumb, THUMB_SIZE } from '../../utils/thumbFit'

const props = withDefaults(defineProps<{
  /** 打开范围：图层面板=图像，图块面板=图块（不跟随当前图层类型） */
  scope?: 'image' | 'tile'
}>(), { scope: 'image' })

const emit = defineEmits<{
  'close': []
  /** 第二个参数：素材类型（tiles=单图块 / tilesets=图集；图像模式不传）；
   *  第三个参数：图集在素材库里设定的每格边长（未设定不传） */
  'imported': [path: string, kind?: 'tile' | 'tileset', tileSize?: number]
}>()

const store = useMapResourceLibStore()
const searchQuery = ref('')

// 只按打开来源过滤分类：图层面板打开时只显示图像，图块面板打开时只显示图块/集合
const isImageMode = computed(() => props.scope === 'image')

/** 当前浏览的资源类型：图块 / 集合（图像模式固定为 images） */
const activeCategory = ref<ResourceCategory>(isImageMode.value ? 'images' : 'tiles')
/** 当前选中的分类（子目录名），null = 全部 */
const activeGroup = ref<string | null>(null)

/** 分类标签取哪个目录：图像模式看 images，其余看 tiles（集合不参与分类） */
const groupSource = computed<ResourceCategory>(() => (isImageMode.value ? 'images' : 'tiles'))

/** 分类 chips：由子目录名自动推导，不额外维护词表 */
const groupOptions = computed(() => {
  const groups: string[] = []
  for (const item of store.items) {
    if (item.category !== groupSource.value) continue
    if (!groups.includes(item.group)) groups.push(item.group)
  }
  return groups
})

// 目录被移空/改名后，已选中的分类 chip 跟着失效
watch(groupOptions, groups => {
  if (activeGroup.value && !groups.includes(activeGroup.value)) activeGroup.value = null
})

onMounted(() => {
  store.loadBuiltinResources()
})

function selectAll() {
  activeCategory.value = groupSource.value
  activeGroup.value = null
}

function selectGroup(group: string) {
  activeCategory.value = groupSource.value
  activeGroup.value = group
}

function selectTilesets() {
  activeCategory.value = 'tilesets'
  activeGroup.value = null
}

const filteredResources = computed(() => {
  let list = store.items.filter(r => r.category === activeCategory.value)
  if (activeGroup.value) list = list.filter(r => r.group === activeGroup.value)
  return searchItems(list, searchQuery.value)
})

// ====== 多选状态（勾选框 / Cmd/Ctrl 都能操作同一份选择集） ======
const multiSelectMode = ref(false)
const selectedPaths = ref(new Set<string>())

// 勾选框取消 → 自动清空选中
watch(multiSelectMode, on => {
  if (!on) selectedPaths.value = new Set()
})

// 分类/搜索变化后，选中集里可能有不再显示的条目 → 清理掉
watch(filteredResources, list => {
  if (selectedPaths.value.size === 0) return
  const visible = new Set(list.map(r => r.path))
  let changed = false
  const next = new Set<string>()
  for (const p of selectedPaths.value) {
    if (visible.has(p)) next.add(p)
    else changed = true
  }
  if (changed) selectedPaths.value = next
})

const multiSelectedCount = computed(() => selectedPaths.value.size)

function toggleCardSelection(path: string) {
  const next = new Set(selectedPaths.value)
  if (next.has(path)) next.delete(path)
  else next.add(path)
  selectedPaths.value = next
}

function onCardClick(res: MapResourceItem, e: MouseEvent) {
  // Cmd/Ctrl 点选切换（Windows 也是 Ctrl）
  if (e.metaKey || e.ctrlKey) {
    toggleCardSelection(res.path)
    return
  }

  // 勾选框开启：纯点击 = 切换选中（不需要修饰键）
  if (multiSelectMode.value) {
    toggleCardSelection(res.path)
    return
  }

  // 默认：纯点击 = 立即导入
  emitImportSingle(res)
}

function emitImportSingle(res: MapResourceItem) {
  const kind = res.category === 'tilesets' ? 'tileset' : res.category === 'tiles' ? 'tile' : undefined
  // 只有图集带「图块尺寸」设定，单图块不需要
  emit('imported', res.path, kind, kind === 'tileset' ? res.tileSize : undefined)
}

/** 批量导入：逐个 emit，MainLayout 那边本来就是单个处理 */
async function confirmMultiImport() {
  const paths = [...selectedPaths.value]
  selectedPaths.value = new Set()
  for (const p of paths) {
    const item = store.items.find(r => r.path === p)
    if (!item) continue
    emitImportSingle(item)
  }
}
</script>

<template>
  <div class="map-res-lib-page" :style="{ '--thumb-size': `${THUMB_SIZE}px` }">
    <div class="lib-toolbar">
      <input v-model="searchQuery" class="lib-search" placeholder="搜索素材..." />
      <div style="width:10px" />
      <!-- 同一行：全部 + 分类 chips + 集合（集合固定放最后） -->
      <button
        class="lib-tab-btn"
        :class="{ 'lib-tab-active': activeCategory === groupSource && activeGroup === null }"
        @click="selectAll"
      >全部</button>
      <button
        v-for="group in groupOptions"
        :key="group"
        class="lib-group-btn"
        :class="{ 'lib-group-active': activeCategory === groupSource && activeGroup === group }"
        @click="selectGroup(group)"
      >{{ group }}</button>
      <button
        v-if="!isImageMode"
        class="lib-tab-btn"
        :class="{ 'lib-tab-active': activeCategory === 'tilesets' }"
        @click="selectTilesets"
      >集合</button>
      <!-- 多选勾选框：勾选后纯点击也会进入选中模式；取消勾选自动清除选中 -->
      <label class="lib-multi-check">
        <input type="checkbox" v-model="multiSelectMode" />
        <span>多选</span>
      </label>
      <div class="lib-spacer" />
      <!-- 主操作：导入 → 关闭（主操作在左、关闭在右，macOS/Finder 标准） -->
      <button
        v-if="multiSelectedCount > 0"
        class="lib-confirm-btn"
        @click="confirmMultiImport"
      >导入 {{ multiSelectedCount }} 个</button>
      <button class="lib-return-btn" @click="emit('close')">返回</button>
    </div>

    <div class="lib-grid">
      <div
        v-for="res in filteredResources"
        :key="res.path"
        class="lib-card"
        :class="{ 'lib-card-selected': selectedPaths.has(res.path) }"
        @click="onCardClick(res, $event)"
      >
        <div class="lib-card-thumb">
          <img class="thumb-img" :src="res.thumbnail" @load="fitPixelThumb" />
        </div>
        <div class="lib-card-name">{{ res.name }}</div>
      </div>
      <div v-if="filteredResources.length === 0" class="lib-empty">
        {{ searchQuery || activeGroup ? '没有找到素材' : '暂无素材' }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.map-res-lib-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-root);
}

.lib-toolbar {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 5px;
  gap: 0;
  flex-shrink: 0;
  /* 窄窗口下按钮不压缩、不换行：内容超出横向滚动（滚动条隐藏） */
  flex-wrap: nowrap;
  white-space: nowrap;
  overflow-x: auto;
  overflow-y: hidden;
  scrollbar-width: none;
}

.lib-toolbar::-webkit-scrollbar {
  display: none;
}

.lib-search {
  width: 200px;
  min-width: 200px;
  height: 28px;
  padding: 0 8px;
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  outline: none;
  flex-shrink: 0;
}

.lib-search:focus {
  border-color: var(--accent);
}

.lib-spacer { flex: 1; }

.lib-tab-btn {
  min-width: 53px;
  height: 28px;
  padding: 4px 6px;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: #9ca0a4;
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all 0.15s;
}

.lib-tab-btn:hover {
  background: var(--bg-hover);
  color: white;
}

.lib-tab-active {
  background: rgb(46, 49, 58);
  border: 1px solid var(--border-light);
  color: white;
}

/* 分类 chips：与「全部 / 集合」同处一行，统一按钮宽度 */
.lib-group-btn {
  min-width: 53px;
  height: 28px;
  padding: 0 6px;
  margin-left: 2px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  color: #9ca0a4;
  font-size: 12px;
  white-space: nowrap;
  flex-shrink: 0;
  cursor: pointer;
  transition: all 0.15s;
}

.lib-group-btn:hover {
  background: var(--bg-hover);
  color: white;
}

.lib-group-active {
  background: rgb(46, 49, 58);
  border-color: var(--border-light);
  color: white;
}

/* 多选勾选框 */
.lib-multi-check {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-left: 12px;
  height: 28px;
  padding: 0 8px;
  border-radius: 4px;
  color: #9ca0a4;
  font-size: 12px;
  cursor: pointer;
  flex-shrink: 0;
  user-select: none;
  transition: background 0.15s;
}
.lib-multi-check:hover {
  background: var(--bg-hover);
  color: white;
}
.lib-multi-check input {
  width: 16px;
  height: 16px;
  margin: 0;
  cursor: pointer;
  accent-color: var(--accent, #5BFB84);
  flex-shrink: 0;
}

/* 导入主操作按钮（与返回按钮同排，在返回左侧） */
.lib-confirm-btn {
  height: 28px;
  padding: 0 14px;
  margin-right: 8px;
  background: var(--accent, #5BFB84);
  border: none;
  border-radius: 4px;
  color: #1a1a1a;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: filter 0.15s;
}
.lib-confirm-btn:hover {
  filter: brightness(1.1);
}

.lib-return-btn {
  width: 80px;
  min-width: 80px;
  height: 28px;
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: var(--text-secondary);
  font-size: 12px;
  white-space: nowrap;
  flex-shrink: 0;
  cursor: pointer;
  transition: all 0.15s;
}

.lib-return-btn:hover {
  background: var(--bg-hover);
  color: white;
}

.lib-grid {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  grid-auto-rows: max-content;
  gap: 8px;
  align-content: start;
}

.lib-card {
  background: rgb(45, 45, 45);
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
  transition: background 0.15s, box-shadow 0.15s;
  display: flex;
  flex-direction: column;
  border: 2px solid transparent;
}

.lib-card:hover {
  background: rgb(60, 60, 60);
}

/* 选中高亮：绿色边框 + 微亮背景 */
.lib-card-selected {
  border-color: var(--accent, #5BFB84);
  background: rgb(50, 70, 55);
}

.lib-card-thumb {
  width: var(--thumb-size);
  height: var(--thumb-size);
  flex: none;
  margin: 0 auto 8px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.lib-card-thumb img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  image-rendering: pixelated;
}

.lib-card-name {
  text-align: center;
  font-size: 10px;
  color: rgb(230, 230, 230);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.lib-empty {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  justify-content: center;
  height: 200px;
  color: rgb(80, 80, 80);
  font-size: 12px;
}
</style>
