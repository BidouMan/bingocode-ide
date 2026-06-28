<script setup lang="ts">
import { useMapStore } from '../../stores/map'

const mapStore = useMapStore()

const tileSizes = [16, 32, 64]
const collisionTypes = ['图像', '墙体', '跳板', '自定义']
</script>

<template>
  <div class="property-panel">
    <div class="prop-header">地图属性</div>

    <div class="prop-grid">
      <label class="prop-label">名称</label>
      <input
        class="prop-input"
        :value="mapStore.mapData.name"
        @input="mapStore.updateMapProperty('name', ($event.target as HTMLInputElement).value)"
      />

      <label class="prop-label">尺寸 X</label>
      <input
        class="prop-input"
        type="number"
        :value="mapStore.mapData.width"
        @input="mapStore.updateMapProperty('width', Number(($event.target as HTMLInputElement).value))"
      />

      <label class="prop-label">尺寸 Y</label>
      <input
        class="prop-input"
        type="number"
        :value="mapStore.mapData.height"
        @input="mapStore.updateMapProperty('height', Number(($event.target as HTMLInputElement).value))"
      />

      <label class="prop-label">重力</label>
      <label class="prop-checkbox">
        <input
          type="checkbox"
          :checked="mapStore.mapData.gravity"
          @change="mapStore.updateMapProperty('gravity', ($event.target as HTMLInputElement).checked)"
        />
      </label>

      <label class="prop-label">瓦片大小</label>
      <select
        class="prop-select"
        :value="mapStore.mapData.tileSize"
        @change="mapStore.updateMapProperty('tileSize', Number(($event.target as HTMLSelectElement).value))"
      >
        <option v-for="size in tileSizes" :key="size" :value="size">{{ size }}x{{ size }}</option>
      </select>

      <label class="prop-label">碰撞类型</label>
      <select class="prop-select" value="图像">
        <option v-for="ct in collisionTypes" :key="ct" :value="ct">{{ ct }}</option>
      </select>

      <label class="prop-label">标签</label>
      <input class="prop-input" placeholder="" />

      <label class="prop-label">碰撞启用</label>
      <label class="prop-checkbox">
        <input type="checkbox" />
      </label>
    </div>
  </div>
</template>

<style scoped>
.property-panel {
  width: 256px;
  min-width: 256px;
  background: rgb(34, 37, 43);
  border-left: 1px solid rgb(12, 12, 12);
}

.prop-header {
  text-align: center;
  color: rgb(156, 160, 164);
  font-size: 12px;
  padding: 8px 0;
  border-bottom: 1px solid rgb(55, 59, 68);
}

.prop-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px 8px;
  padding: 10px 8px;
  align-items: center;
}

.prop-label {
  color: rgb(156, 160, 164);
  font-size: 12px;
}

.prop-input {
  background: rgb(40, 43, 52);
  border: 1px solid rgb(55, 59, 68);
  border-radius: 4px;
  color: white;
  padding: 3px 6px;
  font-size: 12px;
  outline: none;
  width: 100%;
}

.prop-input:hover {
  background: rgb(50, 53, 62);
  border: 1px solid rgb(65, 69, 82);
}

.prop-input:focus {
  background: rgb(55, 59, 68);
  border: 1px solid #528bff;
  color: white;
}

.prop-select {
  border: 1px solid rgb(55, 59, 68);
  border-radius: 4px;
  background: rgb(40, 43, 52);
  color: white;
  padding: 3px 6px;
  font-size: 12px;
  outline: none;
  width: 100%;
}

.prop-select:hover {
  border: 1px solid rgb(65, 69, 82);
  background: rgb(50, 53, 62);
}

.prop-checkbox {
  display: flex;
  align-items: center;
}

.prop-checkbox input[type="checkbox"] {
  width: 14px;
  height: 14px;
  accent-color: #528bff;
}
</style>
