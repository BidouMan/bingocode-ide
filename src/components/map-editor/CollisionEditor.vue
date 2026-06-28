<script setup lang="ts">
import { ref } from 'vue'
import { useMapStore } from '../../stores/map'

const mapStore = useMapStore()

type CollisionTool = 'move' | 'add' | 'delete' | 'reset'
const currentCollisionTool = ref<CollisionTool>('move')
const snapToPixel = ref(true)

function setCollisionTool(tool: CollisionTool) {
  currentCollisionTool.value = tool
}
</script>

<template>
  <div class="collision-editor">
    <div class="col-toolbar">
      <button
        class="col-tool-btn"
        :class="{ 'col-tool-active': currentCollisionTool === 'move' }"
        title="移动锚点"
        @click="setCollisionTool('move')"
      >
        <img src="../../assets/icons/移动锚点.svg" class="col-tool-icon" />
      </button>
      <button
        class="col-tool-btn"
        :class="{ 'col-tool-active': currentCollisionTool === 'add' }"
        title="添加锚点"
        @click="setCollisionTool('add')"
      >
        <img src="../../assets/icons/添加锚点.svg" class="col-tool-icon" />
      </button>
      <button
        class="col-tool-btn"
        :class="{ 'col-tool-active': currentCollisionTool === 'delete' }"
        title="删除锚点"
        @click="setCollisionTool('delete')"
      >
        <img src="../../assets/icons/删除锚点.svg" class="col-tool-icon" />
      </button>
      <button
        class="col-tool-btn"
        title="重置锚点"
        @click="setCollisionTool('reset')"
      >
        <img src="../../assets/icons/重置锚点.svg" class="col-tool-icon" />
      </button>
      <button
        class="col-tool-btn"
        :class="{ 'col-tool-active': snapToPixel }"
        title="吸附锚点"
        @click="snapToPixel = !snapToPixel"
      >
        <img src="../../assets/icons/吸附锚点.svg" class="col-tool-icon" />
      </button>
    </div>

    <div class="col-canvas">
      <div v-if="mapStore.selectedTileIndex >= 0" class="col-placeholder">
        选择瓦片编辑碰撞
      </div>
      <div v-else class="col-placeholder">
        选择瓦片编辑碰撞
      </div>
    </div>
  </div>
</template>

<style scoped>
.collision-editor {
  display: flex;
  flex-direction: column;
}

.col-toolbar {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 4px;
  gap: 2px;
}

.col-tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 24px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  padding: 2px;
  transition: background 0.15s;
}

.col-tool-btn:hover {
  background: rgb(61, 64, 72);
}

.col-tool-active {
  background: rgb(46, 49, 58);
  border: 1px solid rgb(55, 59, 68);
}

.col-tool-icon {
  width: 20px;
  height: 20px;
}

.col-canvas {
  width: 256px;
  height: 256px;
  background: rgb(30, 30, 30);
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto;
}

.col-placeholder {
  font-size: 12px;
  color: rgb(80, 80, 80);
}
</style>
