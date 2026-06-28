<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  'close': []
  'imported': [path: string]
}>()

const searchQuery = ref('')

// Placeholder for built-in map library
const maps = ref<{ name: string; path: string; thumbnail?: string }[]>([])
</script>

<template>
  <div class="map-lib-page">
    <div class="lib-toolbar">
      <input v-model="searchQuery" class="lib-search" placeholder="搜索..." />
      <div class="lib-spacer" />
      <span class="lib-hint">请选择地图</span>
      <div class="lib-spacer" />
      <div style="width:120px" />
      <button class="lib-return-btn" @click="emit('close')">返回</button>
    </div>
    <div class="lib-grid">
      <div v-for="map in maps" :key="map.path" class="lib-card" @click="emit('imported', map.path)">
        <div class="lib-card-thumb">
          <img v-if="map.thumbnail" :src="map.thumbnail" />
          <span v-else class="lib-card-placeholder">{{ map.name.charAt(0) }}</span>
        </div>
        <div class="lib-card-name">{{ map.name }}</div>
      </div>
      <div v-if="maps.length === 0" class="lib-empty">暂无地图</div>
    </div>
  </div>
</template>

<style scoped>
.map-lib-page {
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

.lib-hint {
  font-size: 12px;
  color: rgb(128, 128, 128);
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
  gap: 8px;
}

.lib-card {
  background: rgb(45, 45, 45);
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.lib-card:hover {
  background: rgb(60, 60, 60);
}

.lib-card-thumb {
  width: 150px;
  height: 110px;
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

.lib-card-placeholder {
  font-size: 16px;
  color: rgb(230, 230, 230);
}

.lib-card-name {
  text-align: center;
  font-size: 10px;
  color: rgb(230, 230, 230);
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
