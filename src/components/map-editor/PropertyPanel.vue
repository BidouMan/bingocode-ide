<script setup lang="ts">
import { computed } from 'vue'
import { useMapStore } from '../../stores/map'
import CustomSelect from '../common/CustomSelect.vue'

const mapStore = useMapStore()

const tileSizeOptions = [
  { label: '16x16', value: '16x16' },
  { label: '32x32', value: '32x32' },
  { label: '64x64', value: '64x64' },
]
const collisionTypeOptions = [
  { label: '墙体', value: '墙体' },
  { label: '跳板', value: '跳板' },
  { label: '图像', value: '图像' },
  { label: '自定义', value: '自定义' },
]

const tileSizeValue = computed(() => `${mapStore.mapData.tileSize}x${mapStore.mapData.tileSize}`)
function onTileSizeChange(val: string) {
  mapStore.updateMapProperty('tileSize', Number(val.split('x')[0]))
}

const collisionTypeValue = computed(() => mapStore.mapData.collisionType || '图像')
function onCollisionTypeChange(val: string) {
  mapStore.updateMapProperty('collisionType', val)
}

const customCollisionType = computed(() => mapStore.mapData.collisionType || '')
function onCustomCollisionTypeChange(val: string) {
  mapStore.updateMapProperty('collisionType', val)
}
</script>

<template>
  <div class="property-panel">
    <div class="att-tag-name">属性</div>

    <div class="att-frame">
      <div class="att-row">
        <span class="att-label">地图名称</span>
        <input
          class="att-input"
          :value="mapStore.mapData.name"
          @input="mapStore.updateMapProperty('name', ($event.target as HTMLInputElement).value)"
        />
      </div>

      <div class="att-row">
        <span class="att-label">地图尺寸</span>
        <div class="att-size-group">
          <span class="att-size-label">X</span>
          <input
            class="att-input att-input-no-spin"
            type="number"
            :value="mapStore.mapData.width"
            @input="mapStore.updateMapProperty('width', Number(($event.target as HTMLInputElement).value))"
          />
        </div>
      </div>

      <div class="att-row">
        <span class="att-label"></span>
        <div class="att-size-group">
          <span class="att-size-label">Y</span>
          <input
            class="att-input att-input-no-spin"
            type="number"
            :value="mapStore.mapData.height"
            @input="mapStore.updateMapProperty('height', Number(($event.target as HTMLInputElement).value))"
          />
        </div>
      </div>

      <div class="att-row">
        <span class="att-label">偏移量</span>
        <div class="att-size-group">
          <span class="att-size-label">X</span>
          <input
            class="att-input att-input-no-spin"
            type="number"
            :value="mapStore.mapData.offsetX"
            @input="mapStore.updateMapProperty('offsetX', Number(($event.target as HTMLInputElement).value))"
          />
        </div>
      </div>

      <div class="att-row">
        <span class="att-label"></span>
        <div class="att-size-group">
          <span class="att-size-label">Y</span>
          <input
            class="att-input att-input-no-spin"
            type="number"
            :value="mapStore.mapData.offsetY"
            @input="mapStore.updateMapProperty('offsetY', Number(($event.target as HTMLInputElement).value))"
          />
        </div>
      </div>

      <div class="att-row">
        <span class="att-label">地图重力</span>
        <label class="att-checkbox">
          <input
            type="checkbox"
            :checked="mapStore.mapData.gravity"
            @change="mapStore.updateMapProperty('gravity', ($event.target as HTMLInputElement).checked)"
          />
          <span class="att-checkbox-text">启用</span>
        </label>
      </div>

      <div class="att-row">
        <span class="att-label">图块尺寸</span>
        <CustomSelect :model-value="tileSizeValue" :options="tileSizeOptions" @update:model-value="onTileSizeChange" />
      </div>

      <div class="att-row">
        <span class="att-label">物理属性</span>
        <CustomSelect :model-value="collisionTypeValue" :options="collisionTypeOptions" @update:model-value="onCollisionTypeChange" />
      </div>

      <div v-if="collisionTypeValue === '自定义'" class="att-row">
        <span class="att-label"></span>
        <input class="att-input" :value="customCollisionType" @input="onCustomCollisionTypeChange(($event.target as HTMLInputElement).value)" placeholder="输入自定义类型" />
      </div>

      <div class="att-row">
        <span class="att-label">碰撞</span>
        <label class="att-checkbox">
          <input
            type="checkbox"
            :checked="mapStore.mapData.collisionEnabled"
            @change="mapStore.updateMapProperty('collisionEnabled', ($event.target as HTMLInputElement).checked)"
          />
          <span class="att-checkbox-text">启用</span>
        </label>
      </div>
    </div>
  </div>
</template>

<style scoped>
.property-panel {
  display: flex;
  flex-direction: column;
  background: rgb(34, 37, 43);
}

.att-tag-name {
  text-align: center;
  color: #9ca0a4;
  font-size: 12px;
  height: 30px;
  line-height: 30px;
  border-bottom: 1px solid rgb(45, 45, 45);
  flex-shrink: 0;
}

.att-frame {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 8px 16px 10px 16px;
  background: rgb(34, 37, 43);
}

.att-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.att-label {
  color: #9ca0a4;
  font-size: 12px;
  min-width: 60px;
  flex-shrink: 0;
}

.att-input {
  width: 100%;
  height: 24px;
  background: rgb(40, 43, 52);
  border: 1px solid rgb(55, 59, 68);
  border-radius: 4px;
  color: white;
  padding: 0 6px;
  font-size: 12px;
  outline: none;
  box-sizing: border-box;
}

.att-input:hover {
  background: rgb(50, 53, 62);
  border: 1px solid rgb(65, 69, 82);
}

.att-input:focus {
  background: rgb(55, 59, 68);
  border: 1px solid rgb(65, 69, 82);
  color: white;
}

.att-input-no-spin::-webkit-inner-spin-button,
.att-input-no-spin::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.att-input-no-spin[type="number"] {
  -moz-appearance: textfield;
}

.att-size-group {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}

.att-size-label {
  color: #9ca0a4;
  font-size: 12px;
}

.att-checkbox {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
}

.att-checkbox input[type="checkbox"] {
  width: 14px;
  height: 14px;
  accent-color: #528bff;
  border-radius: 3px;
}

.att-checkbox-text {
  color: #9ca0a4;
  font-size: 12px;
}
</style>
