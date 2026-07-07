<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useMapResourceLibStore } from '../../stores/mapResourceLib'

const emit = defineEmits<{
  'close': []
  'imported': [path: string]
}>()

const store = useMapResourceLibStore()
const searchQuery = ref('')
const activeCategory = ref<'all' | 'images' | 'tiles' | 'tilesets'>('all')

const categories = [
  { id: 'all' as const, label: '全部' },
  { id: 'images' as const, label: '图像' },
  { id: 'tiles' as const, label: '图块' },
  { id: 'tilesets' as const, label: '集合' },
]

onMounted(() => {
  store.loadBuiltinResources()
})

const filteredResources = computed(() => {
  let list = store.items
  if (activeCategory.value !== 'all') {
    list = list.filter(r => r.category === activeCategory.value)
  }
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
        @click="emit('imported', res.path)"
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
  background: rgb(34, 37, 43);
}

.lib-toolbar {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 5px;
  gap: 0;
  flex-shrink: 0;
  border-bottom: 1px solid rgb(12, 12, 12);
}

.lib-search {
  width: 200px;
  height: 28px;
  padding: 0 8px;
  background: rgb(52, 55, 62);
  border: 1px solid rgb(73, 76, 86);
  border-radius: 6px;
  color: rgb(150, 150, 150);
  font-size: 12px;
  outline: none;
}

.lib-search:focus {
  border-color: rgb(91, 251, 132);
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
  transition: all 0.15s;
}

.lib-tab-btn:hover {
  background: rgb(61, 64, 72);
  color: white;
}

.lib-tab-active {
  background: rgb(46, 49, 58);
  border: 1px solid rgb(55, 59, 68);
  color: white;
}

.lib-return-btn {
  width: 80px;
  height: 28px;
  background: rgb(52, 55, 62);
  border: 1px solid rgb(73, 76, 86);
  border-radius: 4px;
  color: rgb(150, 150, 150);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.lib-return-btn:hover {
  background: rgb(62, 65, 72);
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
  aspect-ratio: 1;
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
  flex: 1;
  min-height: 0;
  margin: 0 auto 8px;
  background: rgb(61, 61, 61);
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
