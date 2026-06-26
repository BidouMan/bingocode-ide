<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useSpriteLibStore } from '../../stores/spriteLib'
import { useResourceStore } from '../../stores/resource'

const emit = defineEmits<{
  close: []
  imported: [id: string, name: string, bgsUrl: string]
}>()

const spriteLibStore = useSpriteLibStore()
const resourceStore = useResourceStore()
const searchText = ref('')

onMounted(() => {
  spriteLibStore.loadBuiltinLibrary()
})

function selectSprite(item: { name: string; bgsUrl: string }) {
  const id = resourceStore.addItem({
    name: item.name,
    type: 'sprite',
    path: item.bgsUrl,
  })
  emit('imported', id as string, item.name, item.bgsUrl)
}
</script>

<template>
  <div class="sprite-lib-page">
    <div class="lib-toolbar">
      <input v-model="searchText" class="lib-search" placeholder="搜索角色..." />
      <div class="lib-spacer"></div>
      <span class="lib-hint">请选择角色</span>
      <div class="lib-spacer"></div>
      <div style="width:120px"></div>
      <button class="lib-return-btn" @click="emit('close')">返回</button>
    </div>

    <div class="lib-grid">
      <div
        v-for="item in spriteLibStore.items"
        :key="item.name"
        v-show="!searchText || item.name.toLowerCase().includes(searchText.toLowerCase())"
        class="sprite-card"
        @click="selectSprite(item)"
      >
        <div class="sprite-thumb">
          <img v-if="item.thumbUrl" :src="item.thumbUrl" class="sprite-thumb-img" />
          <div v-else class="sprite-thumb-placeholder">{{ item.name.charAt(0) }}</div>
        </div>
        <span class="sprite-name">{{ item.name }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.sprite-lib-page {
  width: 100%;
  height: 100%;
  background: rgb(34, 37, 43);
  display: flex;
  flex-direction: column;
}
.lib-toolbar {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 5px;
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
.lib-search:focus { border-color: rgb(91, 251, 132); }
.lib-spacer { flex: 1; }
.lib-hint { font-size: 12px; color: rgb(128, 128, 128); }
.lib-return-btn {
  width: 80px;
  height: 28px;
  background: rgb(52, 55, 62);
  border: 1px solid rgb(73, 76, 86);
  border-radius: 4px;
  color: rgb(150, 150, 150);
  font-size: 12px;
  cursor: pointer;
}
.lib-return-btn:hover { background: rgb(62, 65, 72); color: white; }
.lib-grid {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}
.sprite-card {
  display: flex;
  flex-direction: column;
  align-items: center;
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
.sprite-thumb {
  width: 140px;
  height: 110px;
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
.sprite-name {
  font-size: 12px;
  color: rgb(230, 230, 230);
  text-align: center;
}
</style>
