<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useMapResourceLibStore } from '../../stores/mapResourceLib'

const props = defineProps<{
  /** 打开范围：图层面板=图像，图块面板=图块（不跟随当前图层类型） */
  scope?: 'image' | 'tile'
}>()

const emit = defineEmits<{
  'close': []
  /** 第二个参数：素材自带的图块尺寸（图集才有，单图块缺省时由导入方按图片边长判断） */
  'imported': [path: string, nativeTileSize?: number]
}>()

const store = useMapResourceLibStore()
const searchQuery = ref('')

// 只按打开来源过滤分类：图层面板打开时只显示图像，图块面板打开时只显示图块/集合
const isImageMode = computed(() => props.scope === 'image')

const activeCategory = ref<'images' | 'tiles' | 'tilesets'>(isImageMode.value ? 'images' : 'tiles')

const categories = computed(() =>
  isImageMode.value
    ? [{ id: 'images' as const, label: '图像' }]
    : [{ id: 'tiles' as const, label: '图块' }, { id: 'tilesets' as const, label: '集合' }]
)

onMounted(() => {
  store.loadBuiltinResources()
})

const filteredResources = computed(() => {
  let list = store.items.filter(r => r.category === activeCategory.value)
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(r => r.name.toLowerCase().includes(q))
  }
  return list
})
</script>

<template>
  <div class="map-res-lib-page">
    <div class="lib-toolbar">
      <input v-model="searchQuery" class="lib-search" placeholder="搜索素材..." />
      <div style="width:10px" />
      <button
        v-for="cat in categories"
        :key="cat.id"
        class="lib-tab-btn"
        :class="{ 'lib-tab-active': activeCategory === cat.id }"
        @click="activeCategory = cat.id"
      >
        {{ cat.label }}
      </button>
      <div class="lib-spacer" />
      <div style="width:120px" />
      <button class="lib-return-btn" @click="emit('close')">返回</button>
    </div>
    <div class="lib-grid">
      <div
        v-for="res in filteredResources"
        :key="res.path"
        class="lib-card"
        @click="emit('imported', res.path, res.nativeTileSize)"
      >
        <div class="lib-card-thumb">
          <img :src="res.thumbnail" />
        </div>
        <div class="lib-card-name">{{ res.name }}</div>
      </div>
      <div v-if="filteredResources.length === 0" class="lib-empty">暂无素材</div>
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
  min-width: 80px;
  height: 28px;
  padding: 4px 10px;
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
  transition: background 0.15s;
  display: flex;
  flex-direction: column;
}

.lib-card:hover {
  background: rgb(60, 60, 60);
}

.lib-card-thumb {
  width: 100%;
  height: 120px;
  flex: none;
  margin: 0 0 8px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.lib-card-thumb img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
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
