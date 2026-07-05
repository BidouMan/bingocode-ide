<script setup lang="ts">
import { computed } from 'vue'
import { useMapStore } from '../../stores/map'
import CustomSelect from '../common/CustomSelect.vue'

const props = defineProps<{
  disabled?: boolean
}>()

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
  const newSize = Number(val.split('x')[0])
  mapStore.updateTileSize(newSize)
}

// 选中的瓦片数据（仅绘制图层 + 选中瓦片时有值）
const selectedTileData = computed(() => {
  if (mapStore.selectedTileIndex < 0) return null
  const layer = mapStore.activeLayer
  if (!layer || layer.type !== 'drawing') return null
  const globalIdx = mapStore.globalResourceOffset + mapStore.selectedResourceIndex
  const tileSet = mapStore.mapData.tileSets[globalIdx]
  if (!tileSet) return null
  return tileSet.tiles[mapStore.selectedTileIndex] ?? null
})

const collisionTypeValue = computed(() => {
  // 优先显示选中瓦片的碰撞类型
  const tileData = selectedTileData.value
  if (tileData) return tileData.collisionType || '图像'
  // 其次显示选中资源的碰撞类型
  const resource = mapStore.selectedResource
  if (resource) return resource.collisionType || '图像'
  return mapStore.mapData.collisionType || '图像'
})

// 碰撞checkbox：直接根据物理属性类型决定勾选状态
const collisionEnabledValue = computed(() => {
  // 选中瓦片时，使用该瓦片的碰撞状态
  if (mapStore.selectedTileIndex >= 0) {
    const layer = mapStore.activeLayer
    if (layer?.type === 'drawing') {
      const globalIdx = mapStore.globalResourceOffset + mapStore.selectedResourceIndex
      const tileSet = mapStore.mapData.tileSets[globalIdx]
      if (tileSet && tileSet.tiles[mapStore.selectedTileIndex]) {
        return tileSet.tiles[mapStore.selectedTileIndex].collision
      }
    }
  }
  // 选中资源时，优先资源的collisionEnabled，其次看物理属性类型
  const resource = mapStore.selectedResource
  if (resource) {
    if (resource.collisionType === '图像') return false
    return resource.collisionEnabled
  }
  // 地图级别
  if (mapStore.mapData.collisionType === '图像') return false
  return mapStore.mapData.collisionEnabled
})

function onCollisionTypeChange(val: string) {
  // 如果选中了单个瓦片，只更新该瓦片的碰撞类型
  if (selectedTileData.value && mapStore.selectedTileIndex >= 0) {
    const layer = mapStore.activeLayer
    if (layer?.type === 'drawing') {
      const globalIdx = mapStore.globalResourceOffset + mapStore.selectedResourceIndex
      mapStore.setTileCollisionType(globalIdx, mapStore.selectedTileIndex, val)
      return
    }
  }

  // 否则更新图块集/资源级别的碰撞类型
  mapStore.updateMapProperty('collisionType', val)
  const resource = mapStore.selectedResource
  if (resource) {
    resource.collisionType = val
    resource.collisionEnabled = val !== '图像'
    const ts = mapStore.mapData.tileSets.find(t => t.name === resource.name)
    if (ts) {
      ts.collisionType = val
      ts.collisionEnabled = val !== '图像'
      // 设为"图像"时清除该图块集中所有瓦片的碰撞标记
      if (val === '图像') {
        for (const tile of ts.tiles) {
          tile.collision = false
        }
      }
    }
    if (val !== '图像') {
      resource.collisionShape = undefined
    }
  }
  if (val === '图像') {
    mapStore.updateMapProperty('collisionEnabled', false)
  } else {
    mapStore.updateMapProperty('collisionEnabled', true)
  }
}

const customCollisionType = computed(() => mapStore.mapData.collisionType || '')
function onCustomCollisionTypeChange(val: string) {
  mapStore.updateMapProperty('collisionType', val)
}

function onCollisionEnabledChange(enabled: boolean) {
  // 如果选中了单个瓦片，更新该瓦片的碰撞状态
  if (selectedTileData.value && mapStore.selectedTileIndex >= 0) {
    const layer = mapStore.activeLayer
    if (layer?.type === 'drawing') {
      const globalIdx = mapStore.globalResourceOffset + mapStore.selectedResourceIndex
      const tileSet = mapStore.mapData.tileSets[globalIdx]
      if (tileSet && tileSet.tiles[mapStore.selectedTileIndex]) {
        tileSet.tiles[mapStore.selectedTileIndex].collision = enabled
      }
      return
    }
  }
  // 否则更新图块集/地图级别
  mapStore.updateMapProperty('collisionEnabled', enabled)
  const resource = mapStore.selectedResource
  if (resource) {
    resource.collisionEnabled = enabled
    const ts = mapStore.mapData.tileSets.find(t => t.name === resource.name)
    if (ts) ts.collisionEnabled = enabled
  }
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
          :disabled="disabled"
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
            :disabled="disabled"
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
            :disabled="disabled"
            @input="mapStore.updateMapProperty('height', Number(($event.target as HTMLInputElement).value))"
          />
        </div>
      </div>

      <div class="att-row">
        <span class="att-label">地图重力</span>
        <label class="att-checkbox">
          <input
            type="checkbox"
            :checked="mapStore.mapData.gravity"
            :disabled="disabled"
            @change="mapStore.updateMapProperty('gravity', ($event.target as HTMLInputElement).checked)"
          />
          <span class="att-checkbox-text">启用</span>
        </label>
      </div>

      <div class="att-row">
        <span class="att-label">图块尺寸</span>
        <CustomSelect :model-value="tileSizeValue" :options="tileSizeOptions" :disabled="disabled" @update:model-value="onTileSizeChange" />
      </div>

      <div class="att-row">
        <span class="att-label">物理属性</span>
        <CustomSelect :model-value="collisionTypeValue" :options="collisionTypeOptions" :disabled="disabled" @update:model-value="onCollisionTypeChange" />
      </div>

      <div v-if="collisionTypeValue === '自定义'" class="att-row">
        <span class="att-label"></span>
        <input class="att-input" :value="customCollisionType" :disabled="disabled" @input="onCustomCollisionTypeChange(($event.target as HTMLInputElement).value)" placeholder="输入自定义类型" />
      </div>

      <div class="att-row">
        <span class="att-label">碰撞</span>
        <label class="att-checkbox">
          <input
            type="checkbox"
            :checked="collisionEnabledValue"
            :disabled="disabled"
            @change="onCollisionEnabledChange(($event.target as HTMLInputElement).checked)"
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

.att-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.att-checkbox input[type="checkbox"]:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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
