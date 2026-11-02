<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { UNGROUPED, joinPath, useMapResourceLibStore } from '../../stores/mapResourceLib'
import type { IndexEntry, MapResourceItem, ResourceCategory } from '../../stores/mapResourceLib'
import { searchItems } from '../../utils/assetSearch'
import { fitPixelThumb, THUMB_SIZE } from '../../utils/thumbFit'

/**
 * 开发模式专用：内置素材整理页（多选 / 批量改目录 / 批量打标签 / 改名）。
 * 整页只在 dev 构建里被动态 import，正式包不会包含它。
 */
const emit = defineEmits<{ close: [] }>()

const store = useMapResourceLibStore()

const CATEGORIES: Array<{ id: ResourceCategory; label: string }> = [
  { id: 'tiles', label: '图块' },
  { id: 'tilesets', label: '集合' },
  { id: 'images', label: '图像' },
]

const activeCategory = ref<ResourceCategory>('tiles')
const searchQuery = ref('')
const viewMode = ref<'grid' | 'list'>('grid')
const activeGroup = ref<string | null>(null)

const selectedRels = ref<string[]>([])
const lastClicked = ref<string | null>(null)
/** 多选模式：勾选后可累积选择；不勾选时点击即切换为只选当前这一个 */
const multiSelect = ref(false)

const entries = ref<Record<string, IndexEntry>>({})
const tagPool = ref<string[]>([])
const version = ref(1)

const busy = ref(false)
const error = ref('')
const info = ref('')

/** 列表模式缩略图比图标模式小一档 */
const LIST_THUMB_SIZE = 32

function onListThumbLoad(event: Event) {
  fitPixelThumb(event, LIST_THUMB_SIZE)
}

const groupTarget = ref('')
const newGroupInput = ref('')
const tagInput = ref('')
const nameInput = ref('')
const fileInput = ref('')

// ─── 数据加载 ───

async function loadIndex() {
  const idx = await store.readCategoryIndex(activeCategory.value)
  entries.value = idx.entries
  tagPool.value = [...idx.tagPool]
  version.value = idx.version
}

onMounted(async () => {
  await store.loadBuiltinResources()
  await loadIndex()
})

watch(activeCategory, async () => {
  activeGroup.value = null
  selectedRels.value = []
  lastClicked.value = null
  await loadIndex()
})

// ─── 列表 / 筛选 ───

const groupOptions = computed(() => {
  const groups: string[] = []
  for (const item of store.items) {
    if (item.category !== activeCategory.value) continue
    if (!groups.includes(item.group)) groups.push(item.group)
  }
  return groups
})

const filtered = computed(() => {
  let list = store.items.filter(r => r.category === activeCategory.value)
  if (activeGroup.value) list = list.filter(r => r.group === activeGroup.value)
  return searchItems(list, searchQuery.value)
})

const selectedItems = computed(() =>
  selectedRels.value
    .map(rel => store.items.find(i => i.category === activeCategory.value && i.rel === rel))
    .filter((i): i is MapResourceItem => Boolean(i))
)

const singleItem = computed(() => (selectedItems.value.length === 1 ? selectedItems.value[0] : null))

/** 标签芯片 = 标签池 ∪ 当前分类里用到的标签，保证已有标签不会“隐身” */
const chipTags = computed(() => {
  const list = [...tagPool.value]
  for (const item of store.items) {
    if (item.category !== activeCategory.value) continue
    for (const tag of item.tags) if (!list.includes(tag)) list.push(tag)
  }
  return list
})

// 单选时把名字/文件名填入输入框；多选或清空时不覆盖用户输入内容
watch(
  () => singleItem.value?.rel ?? '',
  () => {
    nameInput.value = singleItem.value?.name ?? ''
    fileInput.value = singleItem.value?.file.replace(/[.][^.]+$/, '') ?? ''
  },
  { immediate: true },
)

// ─── 选择 ───

function isSelected(rel: string) {
  return selectedRels.value.includes(rel)
}

function toggle(rel: string) {
  if (!multiSelect.value) {
    selectedRels.value = [rel]
    lastClicked.value = rel
    return
  }
  const index = selectedRels.value.indexOf(rel)
  if (index >= 0) selectedRels.value.splice(index, 1)
  else selectedRels.value.push(rel)
  lastClicked.value = rel
}

/** Shift + 点击：从上次点击的位置连选（仅多选模式） */
function onItemClick(rel: string, event: MouseEvent) {
  if (multiSelect.value && event.shiftKey && lastClicked.value) {
    const list = filtered.value.map(i => i.rel)
    const from = list.indexOf(lastClicked.value)
    const to = list.indexOf(rel)
    if (from >= 0 && to >= 0) {
      const [start, end] = from < to ? [from, to] : [to, from]
      selectedRels.value = [...new Set([...selectedRels.value, ...list.slice(start, end + 1)])]
      return
    }
  }
  toggle(rel)
}

function selectAllVisible() {
  // 全选本身就是多选动作，自动把多选开关打开，避免开关和结果互相矛盾
  multiSelect.value = true
  selectedRels.value = [...new Set([...selectedRels.value, ...filtered.value.map(i => i.rel)])]
  lastClicked.value = null
}

function clearSelection() {
  selectedRels.value = []
  lastClicked.value = null
}

// ─── 索引读写 ───

function ensureEntry(rel: string): IndexEntry {
  if (!entries.value[rel]) entries.value[rel] = {}
  return entries.value[rel]
}

function entryTags(rel: string): string[] {
  return entries.value[rel]?.tags ?? []
}

async function writeIndex(): Promise<boolean> {
  try {
    await invoke('write_file', {
      path: store.indexFilePath(activeCategory.value),
      content: JSON.stringify(
        { version: version.value, tagPool: tagPool.value, entries: entries.value },
        null,
        2,
      ) + '\n',
    })
    return true
  } catch (e) {
    error.value = `保存索引失败：${e}`
    return false
  }
}

/** 手动重新扫描并刷新列表（不自动调用：编辑过程中页面保持不动） */
async function manualReload() {
  busy.value = true
  const keep = [...selectedRels.value]
  await store.loadBuiltinResources()
  await loadIndex()
  const category = activeCategory.value
  selectedRels.value = keep.filter(rel => store.items.some(i => i.category === category && i.rel === rel))
  lastClicked.value = null
  busy.value = false
  info.value = '已重新加载'
}

function findItem(rel: string) {
  return store.items.find(i => i.category === activeCategory.value && i.rel === rel)
}

/** 名字/标签改完只同步这一个条目，避免整页重扫导致列表跳动 */
function syncItemMeta(rel: string) {
  const item = findItem(rel)
  const entry = entries.value[rel]
  if (!item || !entry) return
  if (entry.name) item.name = entry.name
  item.tags = [...(entry.tags ?? [])]
  item.py = entry.py ?? ''
  item.pyi = entry.pyi ?? ''
}

/** 文件移动/改名后同步路径、分类与缩略图（只更新这一项，不重扫） */
function syncItemPath(oldRel: string, newRel: string) {
  const item = findItem(oldRel)
  if (!item) return
  const dir = store.categoryDir(activeCategory.value)
  item.rel = newRel
  item.file = newRel.split('/').pop() ?? item.file
  item.group = newRel.includes('/') ? newRel.slice(0, newRel.lastIndexOf('/')) : UNGROUPED
  item.name = entries.value[newRel]?.name || item.file.replace(/[.][^.]+$/, '')
  item.path = `/maps/${activeCategory.value}/${newRel}`
  item.thumbnail = `${convertFileSrc(joinPath(dir, newRel))}?t=${Date.now()}`
}

// 拼音只在保存名字时预算好写进索引，正式包运行时不加载拼音库
let pinyinModule: typeof import('pinyin-pro') | null = null
async function computePinyin(text: string) {
  pinyinModule ??= await import('pinyin-pro')
  const full = pinyinModule.pinyin(text, { toneType: 'none', type: 'array' }).join('')
  const initials = pinyinModule.pinyin(text, { pattern: 'first', toneType: 'none', type: 'array' }).join('')
  return { py: full, pyi: initials }
}

// ─── 文件移动 ───

/** 目标目录内重名时自动加 -2 / -3，避免批量移动互相覆盖 */
function uniqueRel(group: string, file: string, used: Set<string>): string {
  const build = (name: string) => (group ? `${group}/${name}` : name)
  if (!used.has(build(file))) return build(file)
  const dot = file.lastIndexOf('.')
  const base = dot >= 0 ? file.slice(0, dot) : file
  const ext = dot >= 0 ? file.slice(dot) : ''
  let n = 2
  while (used.has(build(`${base}-${n}${ext}`))) n++
  return build(`${base}-${n}${ext}`)
}

async function applyGroup(group: string) {
  const rels = [...selectedRels.value]
  if (!rels.length || busy.value) return
  busy.value = true
  error.value = ''
  info.value = ''

  const category = activeCategory.value
  const dir = store.categoryDir(category)
  const used = new Set(store.items.filter(i => i.category === category).map(i => i.rel))
  const moved: Array<{ oldRel: string; newRel: string }> = []

  try {
    if (group) await invoke('create_dir', { path: joinPath(dir, group) })
  } catch (e) {
    error.value = `创建目录失败：${e}`
    busy.value = false
    return
  }

  for (const rel of rels) {
    const item = store.items.find(i => i.category === category && i.rel === rel)
    if (!item) continue
    const newRel = uniqueRel(group, item.file, used)
    if (newRel === rel) continue
    try {
      await invoke('rename_path', { oldPath: joinPath(dir, rel), newPath: joinPath(dir, newRel) })
    } catch (e) {
      error.value = `「${item.name}」移动失败：${e}`
      continue
    }
    used.delete(rel)
    used.add(newRel)
    moved.push({ oldRel: rel, newRel })
    const meta = entries.value[rel]
    if (meta) {
      delete entries.value[rel]
      entries.value[newRel] = meta
    }
  }

  if (moved.length === 0) {
    busy.value = false
    return
  }

  // 索引写失败就把文件逐个移回去，保持文件和索引一致
  if (!(await writeIndex())) {
    for (const m of [...moved].reverse()) {
      const meta = entries.value[m.newRel]
      if (meta) {
        delete entries.value[m.newRel]
        entries.value[m.oldRel] = meta
      }
      try {
        await invoke('rename_path', { oldPath: joinPath(dir, m.newRel), newPath: joinPath(dir, m.oldRel) })
      } catch {
        // 回滚失败时不再叠加提示，用户已能看到根因
      }
    }
    busy.value = false
    return
  }

  // 移动完只更新对应条目，不重扫整个目录：列表位置、滚动位置都保持不动
  for (const m of moved) syncItemPath(m.oldRel, m.newRel)
  const movedMap = new Map(moved.map(m => [m.oldRel, m.newRel]))
  selectedRels.value = selectedRels.value.map(rel => movedMap.get(rel) ?? rel)
  if (lastClicked.value) lastClicked.value = movedMap.get(lastClicked.value) ?? lastClicked.value
  info.value = `已移动 ${moved.length} 项到「${group || UNGROUPED}」`
  busy.value = false
}

async function createGroupAndApply() {
  const group = newGroupInput.value.trim()
  if (!group) return
  if (group === UNGROUPED) {
    error.value = `「${UNGROUPED}」是保留名称，换一个吧`
    return
  }
  if (/[\\/:*?"<>|]/.test(group)) {
    error.value = '目录名不能包含 \\ / : * ? " < > |'
    return
  }
  newGroupInput.value = ''
  groupTarget.value = group
  await applyGroup(group)
}

async function moveOne(oldRel: string, newRel: string) {
  const dir = store.categoryDir(activeCategory.value)
  busy.value = true
  error.value = ''
  try {
    await invoke('rename_path', { oldPath: joinPath(dir, oldRel), newPath: joinPath(dir, newRel) })
  } catch (e) {
    error.value = `重命名失败：${e}`
    busy.value = false
    return
  }
  const meta = entries.value[oldRel]
  if (meta) {
    delete entries.value[oldRel]
    entries.value[newRel] = meta
  }
  if (!(await writeIndex())) {
    if (meta) {
      delete entries.value[newRel]
      entries.value[oldRel] = meta
    }
    try {
      await invoke('rename_path', { oldPath: joinPath(dir, newRel), newPath: joinPath(dir, oldRel) })
    } catch {
      // 同上
    }
    busy.value = false
    return
  }
  syncItemPath(oldRel, newRel)
  selectedRels.value = selectedRels.value.map(rel => (rel === oldRel ? newRel : rel))
  if (lastClicked.value === oldRel) lastClicked.value = newRel
  busy.value = false
}

// ─── 批量标签 ───

function tagAll(tag: string) {
  return selectedRels.value.length > 0 && selectedRels.value.every(rel => entryTags(rel).includes(tag))
}

function tagSome(tag: string) {
  return selectedRels.value.some(rel => entryTags(rel).includes(tag))
}

async function toggleTagOnSelection(tag: string) {
  const rels = [...selectedRels.value]
  if (!rels.length || busy.value) return
  busy.value = true
  error.value = ''
  info.value = ''
  const removeAll = rels.every(rel => entryTags(rel).includes(tag))
  for (const rel of rels) {
    const entry = ensureEntry(rel)
    const tags = [...(entry.tags ?? [])]
    entry.tags = removeAll ? tags.filter(t => t !== tag) : [...tags, tag]
  }
  const ok = await writeIndex()
  busy.value = false
  if (ok) {
    for (const rel of rels) syncItemMeta(rel)
    info.value = removeAll ? `已给 ${rels.length} 项去掉「${tag}」` : `已给 ${rels.length} 项加上「${tag}」`
  }
}

async function addTag() {
  const tag = tagInput.value.trim()
  if (!tag) return
  tagInput.value = ''
  if (!tagPool.value.includes(tag)) tagPool.value.push(tag)

  const rels = [...selectedRels.value]
  if (!rels.length) {
    if (await writeIndex()) info.value = `标签「${tag}」已加入标签池`
    return
  }

  busy.value = true
  error.value = ''
  for (const rel of rels) {
    const entry = ensureEntry(rel)
    const tags = [...(entry.tags ?? [])]
    if (!tags.includes(tag)) tags.push(tag)
    entry.tags = tags
  }
  const ok = await writeIndex()
  busy.value = false
  if (ok) {
    for (const rel of rels) syncItemMeta(rel)
    info.value = `已给 ${rels.length} 项加上「${tag}」`
  }
}

// ─── 单个改名 ───

async function saveName() {
  const item = singleItem.value
  if (!item) return
  const next = nameInput.value.trim()
  if (!next) {
    nameInput.value = item.name
    return
  }
  if (next === item.name) return
  const entry = ensureEntry(item.rel)
  const pin = await computePinyin(next)
  entry.name = next
  entry.py = pin.py
  entry.pyi = pin.pyi
  if (await writeIndex()) {
    syncItemMeta(item.rel)
    info.value = `已改名为「${next}」`
  }
}

async function saveFileName() {
  const item = singleItem.value
  if (!item) return
  const base = fileInput.value.trim()
  const currentBase = item.file.replace(/[.][^.]+$/, '')
  if (!base) {
    fileInput.value = currentBase
    return
  }
  if (base === currentBase) return
  if (/[\\/:*?"<>|]/.test(base)) {
    error.value = '文件名不能包含 \\ / : * ? " < > |'
    return
  }
  const ext = item.file.match(/[.][^.]+$/)?.[0] ?? '.png'
  const group = item.group === UNGROUPED ? '' : item.group
  const newFile = base + ext
  const newRel = group ? `${group}/${newFile}` : newFile
  if (store.items.some(i => i.category === activeCategory.value && i.rel === newRel)) {
    error.value = '同目录已有同名文件'
    return
  }
  await moveOne(item.rel, newRel)
}
</script>

<template>
  <div class="studio" :style="{ '--thumb-size': `${THUMB_SIZE}px`, '--list-thumb-size': `${LIST_THUMB_SIZE}px` }">
    <!-- 工具栏 -->
    <div class="bar">
      <button
        v-for="cat in CATEGORIES"
        :key="cat.id"
        class="tab"
        :class="{ 'tab-on': activeCategory === cat.id }"
        @click="activeCategory = cat.id"
      >{{ cat.label }}</button>
      <input v-model="searchQuery" class="search" placeholder="搜索名字 / 拼音 / 标签" />
      <button class="btn" @click="selectAllVisible">全选</button>
      <button class="btn" @click="clearSelection">清空</button>
      <label class="multi">
        <input v-model="multiSelect" type="checkbox" class="multi-check" />
        多选
      </label>
      <span class="count">已选 {{ selectedRels.length }} / {{ filtered.length }}</span>
      <div class="spacer" />
      <button class="btn" :disabled="busy" @click="manualReload">重新加载</button>
      <button class="btn" :class="{ 'btn-on': viewMode === 'grid' }" @click="viewMode = 'grid'">图标</button>
      <button class="btn" :class="{ 'btn-on': viewMode === 'list' }" @click="viewMode = 'list'">列表</button>
      <button class="btn" @click="emit('close')">返回</button>
    </div>

    <!-- 分类筛选 -->
    <div v-if="groupOptions.length > 1" class="groups">
      <button class="chip" :class="{ 'chip-on': activeGroup === null }" @click="activeGroup = null">全部</button>
      <button
        v-for="group in groupOptions"
        :key="group"
        class="chip"
        :class="{ 'chip-on': activeGroup === group }"
        @click="activeGroup = activeGroup === group ? null : group"
      >{{ group }}</button>
    </div>

    <div class="body">
      <!-- 图标模式：大缩略图 -->
      <div v-if="viewMode === 'grid'" class="grid">
        <div
          v-for="item in filtered"
          :key="item.rel"
          class="card"
          :class="{ 'card-on': isSelected(item.rel) }"
          @click="onItemClick(item.rel, $event)"
        >
          <input
            type="checkbox"
            class="check"
            :checked="isSelected(item.rel)"
            @click.stop="toggle(item.rel)"
          />
          <div class="card-thumb">
            <img class="thumb-img" :src="item.thumbnail" loading="lazy" @load="fitPixelThumb" />
          </div>
          <div class="card-name">{{ item.name }}</div>
          <div class="card-meta">{{ item.group }} · {{ item.file }}</div>
        </div>
        <div v-if="filtered.length === 0" class="empty">没有素材</div>
      </div>

      <!-- 列表模式 -->
      <div v-else class="list">
        <div class="row row-head">
          <span class="col-check" />
          <span class="col-thumb-head" />
          <span class="col-name">名字</span>
          <span class="col-file">文件名</span>
          <span class="col-group">目录</span>
          <span class="col-tags">标签</span>
        </div>
        <div
          v-for="item in filtered"
          :key="item.rel"
          class="row"
          :class="{ 'row-on': isSelected(item.rel) }"
          @click="onItemClick(item.rel, $event)"
        >
          <input
            type="checkbox"
            class="check col-check"
            :checked="isSelected(item.rel)"
            @click.stop="toggle(item.rel)"
          />
          <span class="col-thumb">
            <img class="thumb-img" :src="item.thumbnail" loading="lazy" @load="onListThumbLoad" />
          </span>
          <span class="col-name" :title="item.name">{{ item.name }}</span>
          <span class="col-file" :title="item.file">{{ item.file }}</span>
          <span class="col-group">{{ item.group }}</span>
          <span class="col-tags">
            <span v-for="tag in item.tags" :key="tag" class="mini-tag">{{ tag }}</span>
          </span>
        </div>
        <div v-if="filtered.length === 0" class="empty">没有素材</div>
      </div>

      <!-- 右侧操作面板 -->
      <div class="panel">
        <div class="panel-title">已选 {{ selectedRels.length }} 项</div>

        <div v-if="selectedRels.length === 0" class="hint">
          点素材选中；勾选工具栏的「多选」后可再选多个（Shift 连选），没勾选时每次点击只选当前这个。改动会立即保存，想刷新列表点「重新加载」。
        </div>

        <template v-else>
          <div class="field">
            <label>目录（批量移动到）</label>
            <div class="inline">
              <select v-model="groupTarget" class="input">
                <option value="">未分类</option>
                <option v-for="group in groupOptions.filter(g => g !== '未分类')" :key="group" :value="group">{{ group }}</option>
              </select>
              <button class="btn" :disabled="busy" @click="applyGroup(groupTarget)">应用</button>
            </div>
            <div class="inline">
              <input v-model="newGroupInput" class="input" placeholder="新建目录名" @keydown.enter="createGroupAndApply" />
              <button class="btn" :disabled="busy" @click="createGroupAndApply">新建并移动</button>
            </div>
          </div>

          <div class="field">
            <label>标签（点一下批量添加 / 再点移除）</label>
            <div class="tags">
              <button
                v-for="tag in chipTags"
                :key="tag"
                class="tag"
                :class="{ 'tag-all': tagAll(tag), 'tag-part': !tagAll(tag) && tagSome(tag) }"
                :disabled="busy"
                @click="toggleTagOnSelection(tag)"
              >{{ tag }}</button>
              <span v-if="chipTags.length === 0" class="hint">还没有标签</span>
            </div>
            <div class="inline">
              <input v-model="tagInput" class="input" placeholder="新标签，回车添加" @keydown.enter="addTag" />
              <button class="btn" :disabled="busy" @click="addTag">添加</button>
            </div>
          </div>

          <template v-if="singleItem">
            <div class="field">
              <label>名字（只对单个生效）</label>
              <input
                v-model="nameInput"
                class="input"
                @blur="saveName"
                @keydown.enter="($event.target as HTMLInputElement).blur()"
              />
            </div>
            <div class="field">
              <label>文件名（不含扩展名）</label>
              <div class="inline">
                <input
                  v-model="fileInput"
                  class="input"
                  @blur="saveFileName"
                  @keydown.enter="($event.target as HTMLInputElement).blur()"
                />
                <span class="ext">{{ singleItem.file.match(/[.][^.]+$/)?.[0] ?? '.png' }}</span>
              </div>
            </div>
          </template>
        </template>

        <div v-if="error" class="msg err">{{ error }}</div>
        <div v-if="info" class="msg ok">{{ info }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.studio {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-root);
  color: var(--text-secondary);
  font-size: 12px;
}

.bar {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 40px;
  padding: 0 8px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--border);
  overflow-x: auto;
  scrollbar-width: none;
}

.bar::-webkit-scrollbar {
  display: none;
}

.tab,
.btn {
  height: 26px;
  padding: 0 10px;
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
  transition: background 0.15s;
}

.tab:hover,
.btn:hover {
  background: var(--bg-hover);
  color: white;
}

.tab-on,
.btn-on {
  background: rgb(46, 49, 58);
  border-color: var(--accent);
  color: var(--accent);
}

.btn[disabled] {
  opacity: 0.5;
  cursor: default;
}

.search {
  width: 260px;
  min-width: 260px;
  flex-shrink: 0;
  height: 26px;
  padding: 0 8px;
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: var(--text-secondary);
  font-size: 12px;
  outline: none;
}

.search:focus {
  border-color: var(--accent);
}

.count {
  color: #8a8f93;
}

.multi {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--text-secondary);
  white-space: nowrap;
  cursor: pointer;
  user-select: none;
}

.multi-check {
  accent-color: #5bfb84;
  cursor: pointer;
}

.spacer {
  flex: 1;
}

.groups {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 8px;
  flex-shrink: 0;
  overflow-x: auto;
  scrollbar-width: none;
}

.groups::-webkit-scrollbar {
  display: none;
}

.chip {
  height: 24px;
  padding: 0 10px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  color: #9ca0a4;
  font-size: 12px;
  white-space: nowrap;
  cursor: pointer;
}

.chip:hover {
  background: var(--bg-hover);
  color: white;
}

.chip-on {
  background: rgb(46, 49, 58);
  border-color: var(--border-light);
  color: white;
}

.body {
  flex: 1;
  min-height: 0;
  display: flex;
}

/* ─── 图标模式 ─── */
.grid {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  padding: 10px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  grid-auto-rows: max-content;
  gap: 10px;
  align-content: start;
}

.card {
  position: relative;
  background: rgb(45, 45, 45);
  border: 1px solid transparent;
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
}

.card:hover {
  background: rgb(60, 60, 60);
}

.card-on {
  border-color: var(--accent);
  background: rgb(56, 58, 64);
}

.card-thumb {
  width: var(--thumb-size);
  height: var(--thumb-size);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: rgb(38, 38, 38);
  border-radius: 4px;
  margin: 0 auto 8px;
}

.card-thumb img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.card-name {
  color: white;
  font-size: 12px;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-meta {
  color: #8a8f93;
  font-size: 11px;
  text-align: center;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 2px;
}

.check {
  cursor: pointer;
  accent-color: #5bfb84;
}

.card > .check {
  position: absolute;
  top: 12px;
  left: 12px;
  width: 14px;
  height: 14px;
}

/* ─── 列表模式 ─── */
.list {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow-y: auto;
  overflow-x: auto;
}

.row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  border-bottom: 1px solid rgb(50, 50, 50);
  cursor: pointer;
}

.row:hover {
  background: rgb(52, 54, 58);
}

.row-on {
  background: rgb(56, 58, 64);
  box-shadow: inset 2px 0 0 var(--accent);
}

.row-head {
  position: sticky;
  top: 0;
  z-index: 2;
  background: var(--bg-panel);
  color: #8a8f93;
  cursor: default;
}

.col-check {
  width: 16px;
  flex: none;
}

.col-thumb {
  width: var(--list-thumb-size);
  height: var(--list-thumb-size);
  flex: none;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  background: rgb(38, 38, 38);
  border-radius: 4px;
}

/* 表头只占位、不显示缩略图方框 */
.col-thumb-head {
  width: var(--list-thumb-size);
  flex: none;
}

.col-thumb img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}

.col-name {
  width: 160px;
  flex: none;
  color: white;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.col-file {
  width: 200px;
  flex: none;
  color: #9ca0a4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.col-group {
  width: 90px;
  flex: none;
  color: #9ca0a4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.col-tags {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.mini-tag {
  padding: 0 6px;
  border: 1px solid var(--border-light);
  border-radius: 3px;
  color: #8a8f93;
  font-size: 11px;
  line-height: 18px;
}

.empty {
  grid-column: 1 / -1;
  padding: 40px;
  text-align: center;
  color: #7c8084;
}

/* ─── 操作面板 ─── */
.panel {
  width: 320px;
  min-width: 320px;
  flex-shrink: 0;
  overflow-y: auto;
  padding: 10px;
  background: var(--bg-panel);
  border-left: 1px solid var(--border);
}

.panel-title {
  color: white;
  margin-bottom: 10px;
}

.hint {
  color: #7c8084;
  line-height: 1.6;
}

.field {
  margin-bottom: 14px;
}

.field > label {
  display: block;
  margin-bottom: 6px;
  color: #9ca0a4;
}

.inline {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
}

.input {
  flex: 1;
  min-width: 0;
  height: 26px;
  padding: 0 8px;
  background: var(--bg-root);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: var(--text-secondary);
  font-size: 12px;
  outline: none;
}

.input:focus {
  border-color: var(--accent);
}

.ext {
  color: #7c8084;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag {
  height: 24px;
  padding: 0 8px;
  background: transparent;
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: #9ca0a4;
  font-size: 12px;
  cursor: pointer;
}

.tag:hover {
  background: var(--bg-hover);
  color: white;
}

.tag-all {
  background: rgb(46, 49, 58);
  border-color: var(--accent);
  color: var(--accent);
}

/* 部分选中：虚线边框，一眼能看出不是所有选中项都有这个标签 */
.tag-part {
  border-style: dashed;
  border-color: var(--accent);
  color: var(--accent);
}

.msg {
  margin-top: 10px;
  line-height: 1.5;
}

.err {
  color: #e06c5a;
}

.ok {
  color: #5bfb84;
}
</style>
