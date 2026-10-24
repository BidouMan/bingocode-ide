<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useMapLibStore } from '../../stores/mapLib'
import { useMapResourceLibStore } from '../../stores/mapResourceLib'

const emit = defineEmits<{
  'close': []
  'imported': [bgmUrl: string, name: string]
  'imported-image': [engineRelPath: string, name: string]
}>()

const mapLibStore = useMapLibStore()
const mapResLibStore = useMapResourceLibStore()
const searchQuery = ref('')
const activeTab = ref<'maps' | 'images'>('images')

onMounted(() => {
  mapLibStore.loadBuiltinLibrary()
  mapResLibStore.loadBuiltinResources()
})

const filteredMaps = computed(() => {
  if (!searchQuery.value) return mapLibStore.items
  const q = searchQuery.value.toLowerCase()
  return mapLibStore.items.filter(m => m.name.toLowerCase().includes(q))
})

const filteredImages = computed(() => {
  let list = mapResLibStore.items.filter(r => r.category === 'images')
  if (searchQuery.value) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(r => r.name.toLowerCase().includes(q))
  }
  return list
})

const tabs = [
  { id: 'images' as const, label: '图像' },
  { id: 'maps' as const, label: '地图' },
]
</script>

<template>
  <div class="map-lib-page">
    <div class="lib-toolbar">
      <input v-model="searchQuery" class="lib-search" :placeholder="activeTab === 'maps' ? '搜索地图...' : '搜索图像...'" />
      <div style="width:10px" />
      <button
        v-for="tab in tabs"
        :key="tab.id"
        class="lib-tab-btn"
        :class="{ 'lib-tab-active': activeTab === tab.id }"
        @click="activeTab = tab.id"
      >
        {{ tab.label }}
      </button>
      <div class="lib-spacer" />
      <span class="lib-hint">{{ activeTab === 'maps' ? '请选择地图' : '选择图像作为地图' }}</span>
      <div class="lib-spacer" />
      <div style="width:120px" />
      <button class="lib-return-btn" @click="emit('close')">返回</button>
    </div>
    <div v-if="activeTab === 'maps'" class="lib-grid">
      <div
        v-for="map in filteredMaps"
        :key="map.bgmUrl"
        class="lib-card"
        @click="emit('imported', map.bgmUrl, map.name)"
      >
        <div class="lib-card-thumb">
          <img v-if="map.thumbUrl" :src="map.thumbUrl" />
          <span v-else class="lib-card-placeholder">{{ map.name.charAt(0) }}</span>
        </div>
        <div class="lib-card-name">{{ map.name }}</div>
      </div>
      <div v-if="filteredMaps.length === 0" class="lib-empty">暂无地图</div>
    </div>
    <div v-else class="lib-grid">
      <div
        v-for="img in filteredImages"
        :key="img.path"
        class="lib-card"
        @click="emit('imported-image', img.path, img.name)"
      >
        <div class="lib-card-thumb">
          <img :src="img.thumbnail" />
        </div>
        <div class="lib-card-name">{{ img.name }}</div>
      </div>
      <div v-if="filteredImages.length === 0" class="lib-empty">暂无图像</div>
    </div>
  </div>
</template>

<style scoped>
.map-lib-page {
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

.lib-hint {
  font-size: 12px;
  color: var(--text-muted);
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
  background: var(--bg-active);
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

.lib-card-placeholder {
  font-size: 16px;
  color: rgb(230, 230, 230);
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
