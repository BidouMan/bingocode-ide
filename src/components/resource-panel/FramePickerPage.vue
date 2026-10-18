<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { useSpriteLibStore, SPRITE_CATEGORIES } from '../../stores/spriteLib'
import { readBgsFile, readBsfFile, revokeSpriteUrls } from '../../composables/useSpriteData'

/**
 * 内置素材选帧页：选择一个内置角色，把它的全部帧作为【新造型帧】追加到当前编辑的角色。
 * 只负责取帧并发回，追加与刷新由 MainLayout / SpriteEditorView 完成。
 */
const emit = defineEmits<{
  close: []
  picked: [blobs: Blob[]]
}>()

const spriteLibStore = useSpriteLibStore()
const searchText = ref('')
const activeCategory = ref('characters')
const pickingFilePath = ref('') // 正在取帧的卡片（防重复点击 + loading 态）

onMounted(async () => {
  await spriteLibStore.loadBuiltinLibrary()
  ensureValidCategory()
})

function ensureValidCategory() {
  const cats = spriteLibStore.categories
  if (cats.length > 0 && !cats.includes(activeCategory.value)) {
    activeCategory.value = cats.includes('characters') ? 'characters' : cats[0]
  }
}

function categoryLabel(cat: string): string {
  const found = SPRITE_CATEGORIES.find(c => c.dir === cat)
  return found?.label || cat
}

const visibleItems = computed(() => {
  const q = searchText.value.trim().toLowerCase()
  return spriteLibStore.items.filter(item =>
    item.category === activeCategory.value &&
    (!q || item.name.toLowerCase().includes(q))
  )
})

/** 读取内置素材的全部帧（.bgs/.bsf zip 包直接在内存解析，不落项目目录） */
async function loadBuiltinFrameBlobs(filePath: string, type: string): Promise<Blob[]> {
  if (type === 'image') {
    const dataUrl = await invoke<string>('read_image_as_data_url', { path: filePath })
    const resp = await fetch(dataUrl)
    return [await resp.blob()]
  }
  const bytes = await invoke<number[]>('read_binary', { path: filePath })
  const file = new File([new Uint8Array(bytes)], filePath.split(/[\\/]/).pop() || 'sprite')
  if (type === 'bsf') {
    const sprite = await readBsfFile(file)
    try {
      return sprite.frames.map(f => f.blob)
    } finally {
      revokeSpriteUrls(sprite)
    }
  }
  const sprite = await readBgsFile(file)
  try {
    return sprite.frames.map(f => f.blob)
  } finally {
    revokeSpriteUrls(sprite)
  }
}

async function pickSprite(item: { filePath: string; type: string }) {
  if (pickingFilePath.value) return
  pickingFilePath.value = item.filePath
  try {
    const blobs = await loadBuiltinFrameBlobs(item.filePath, item.type)
    if (blobs.length > 0) {
      emit('picked', blobs)
    }
  } catch (e) {
    console.error('[FramePicker] 读取内置素材帧失败:', e)
  } finally {
    pickingFilePath.value = ''
  }
}
</script>

<template>
  <div class="frame-picker-page">
    <div class="lib-toolbar">
      <span class="picker-title">选择内置素材帧（将追加到当前角色）</span>
      <div style="width: 10px" />
      <input v-model="searchText" class="lib-search" placeholder="搜索素材..." />
      <div style="width: 10px" />
      <button
        v-for="cat in spriteLibStore.categories"
        :key="cat"
        class="lib-tab-btn"
        :class="{ 'lib-tab-active': activeCategory === cat }"
        @click="activeCategory = cat"
      >
        {{ categoryLabel(cat) }}
      </button>
      <div class="lib-spacer"></div>
      <button class="lib-return-btn" @click="emit('close')">返回</button>
    </div>

    <div class="lib-grid">
      <div
        v-for="item in visibleItems"
        :key="item.filePath"
        class="sprite-card"
        :class="{ 'sprite-card-picking': pickingFilePath === item.filePath }"
        @click="pickSprite(item)"
      >
        <div class="sprite-thumb">
          <img v-if="item.thumbUrl" :src="item.thumbUrl" class="sprite-thumb-img" />
          <div v-else class="sprite-thumb-placeholder">{{ item.name.charAt(0) }}</div>
          <div v-if="pickingFilePath === item.filePath" class="picking-mask">读取中...</div>
        </div>
        <span class="sprite-name">{{ item.name }}</span>
      </div>
      <div v-if="visibleItems.length === 0" class="lib-empty">暂无资源</div>
    </div>
  </div>
</template>

<style scoped>
.frame-picker-page {
  width: 100%;
  height: 100%;
  background: var(--bg-root);
  display: flex;
  flex-direction: column;
}
.lib-toolbar {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 5px;
  flex-shrink: 0;
}
.picker-title {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
}
.lib-search {
  width: 180px;
  height: 28px;
  padding: 0 8px;
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  outline: none;
}
.lib-search:focus {
  border-color: var(--accent);
}
.lib-spacer {
  flex: 1;
}
.lib-tab-btn {
  min-width: 80px;
  height: 28px;
  padding: 4px 10px;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: #9ca0a4;
  font-size: 12px;
  cursor: pointer;
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
.lib-return-btn {
  width: 80px;
  height: 28px;
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
}
.lib-return-btn:hover {
  background: var(--bg-hover);
  color: var(--text);
}
.lib-grid {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  grid-auto-rows: max-content;
  gap: 8px;
  align-content: start;
}
.sprite-card {
  aspect-ratio: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 8px;
  background: rgb(45, 45, 45);
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
}
.sprite-card:hover {
  background: rgb(60, 60, 60);
  transform: translateY(-2px);
}
.sprite-card-picking {
  opacity: 0.6;
  pointer-events: none;
}
.sprite-thumb {
  position: relative;
  flex: 1;
  min-height: 0;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.sprite-thumb-img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
.sprite-thumb-placeholder {
  width: 60px;
  height: 60px;
  background: rgb(55, 58, 65);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  color: rgb(120, 120, 120);
}
.picking-mask {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.55);
  color: var(--accent);
  font-size: 12px;
  border-radius: 8px;
}
.sprite-name {
  font-size: 12px;
  color: rgb(230, 230, 230);
  text-align: center;
}
.lib-empty {
  grid-column: 1 / -1;
  text-align: center;
  padding: 40px 0;
  color: var(--text-muted);
  font-size: 12px;
}
</style>
