<script setup lang="ts">
import { computed } from 'vue'
import { useMapStore } from '../../stores/map'
import CustomSelect from '../common/CustomSelect.vue'

defineProps<{
  disabled?: boolean
  /** 是否显示顶部「属性」标题（绘制页签栏已有时可关闭，避免重复） */
  showHeader?: boolean
}>()

const emit = defineEmits<{
  /** 属性面板修改了图像变换（位置/旋转/缩放/不透明度） */
  'transform-changed': []
}>()

const mapStore = useMapStore()

const collisionTypeOptions = [
  { label: '墙体', value: '墙体' },
  { label: '跳板', value: '跳板' },
  { label: '图像', value: '图像' },
  { label: '自定义', value: '自定义' },
]
const isTileMode = computed(() => mapStore.activeMode === 'tile')
const isCollisionMode = computed(() => mapStore.activeMode === 'collision')
const isImageMode = computed(() => mapStore.activeMode === 'image')

// ====== 面板信息（只读展示，用于填充属性区） ======
/** 当前图块图层已绘制的瓦片数量 */
const tileCount = computed(() => {
  const layer = mapStore.activeLayer
  if (!layer || layer.type !== 'drawing') return 0
  return Object.keys(layer.tiles).length
})
const tileSetCount = computed(() => mapStore.mapData.tileSets.length)

const imageSizeText = computed(() => {
  const img = mapStore.selectedImage
  if (!img) return '--'
  return `${Math.round(img.width || 0)} × ${Math.round(img.height || 0)}`
})
const imageOpacityPercent = computed(() =>
  Math.round((mapStore.selectedImage?.opacity ?? 1) * 100),
)

// ====== 图像变换（位置 / 旋转 / 缩放 / 不透明度） ======
const selectedImage = computed(() => mapStore.selectedImage)
const imagePosX = computed(() => Math.round(selectedImage.value?.position?.[0] ?? 0))
const imagePosY = computed(() => Math.round(selectedImage.value?.position?.[1] ?? 0))
const imageRotation = computed(() => Math.round((selectedImage.value?.rotation ?? 0) * 10) / 10)
const imageScaleX = computed(() =>
  Math.round((selectedImage.value?.scaleX ?? selectedImage.value?.scale ?? 1) * 100) / 100,
)
const imageScaleY = computed(() =>
  Math.round((selectedImage.value?.scaleY ?? selectedImage.value?.scale ?? 1) * 100) / 100,
)
// 无选中图像或图层被锁定时不可编辑变换
const transformDisabled = computed(
  () => !selectedImage.value || mapStore.activeLayer?.locked === true,
)

function setImagePosition(axis: 0 | 1, e: Event) {
  const img = selectedImage.value
  const value = Number((e.target as HTMLInputElement).value)
  if (!img || !Number.isFinite(value)) return
  const pos = [img.position?.[0] ?? 0, img.position?.[1] ?? 0]
  pos[axis] = value
  img.position = [pos[0], pos[1]]
  emit('transform-changed')
}

function setImageRotation(e: Event) {
  const img = selectedImage.value
  const value = Number((e.target as HTMLInputElement).value)
  if (!img || !Number.isFinite(value)) return
  img.rotation = value
  emit('transform-changed')
}

function setImageScale(axis: 'x' | 'y', e: Event) {
  const img = selectedImage.value
  const value = Number((e.target as HTMLInputElement).value)
  if (!img || !Number.isFinite(value)) return
  // 0 会导致矩阵退化，最小保留 0.01（负值=镜像）
  const clamped = Math.abs(value) < 0.01 ? (value < 0 ? -0.01 : 0.01) : value
  if (axis === 'x') {
    img.scaleX = clamped
    img.scale = clamped
  } else {
    img.scaleY = clamped
  }
  emit('transform-changed')
}

function setImageOpacity(e: Event) {
  const img = selectedImage.value
  const value = Number((e.target as HTMLInputElement).value)
  if (!img || !Number.isFinite(value)) return
  img.opacity = Math.max(0, Math.min(1, value / 100))
  emit('transform-changed')
}

const collisionCount = computed(() => mapStore.activeCollisionPolygons.length)
const collisionDisabledCount = computed(
  () => mapStore.activeCollisionPolygons.filter(p => p.disabled === true).length,
)

/** 图层锁定（与图层列表的锁定按钮同一状态） */
const layerLocked = computed(() => mapStore.activeLayer?.locked === true)
function onLayerLockChange(e: Event) {
  const index = mapStore.activeLayerIndex
  if (index < 0) return
  const locked = (e.target as HTMLInputElement).checked
  if (locked !== layerLocked.value) mapStore.toggleLayerLock(index)
}


// ====== 图块模式：选中瓦片/资源的碰撞属性 ======
const selectedTileData = computed(() => {
  if (mapStore.selectedTileIndex < 0) return null
  const layer = mapStore.activeLayer
  if (!layer || layer.type !== 'drawing') return null
  const tileSet = mapStore.getTileSetForResource(mapStore.selectedResource)
  if (!tileSet) return null
  return tileSet.tiles[mapStore.selectedTileIndex] ?? null
})

const collisionTypeValue = computed(() => {
  const tileData = selectedTileData.value
  if (tileData) return tileData.collisionType || '图像'
  const resource = mapStore.selectedResource
  if (resource) return resource.collisionType || '图像'
  return mapStore.mapData.collisionType || '图像'
})

const collisionEnabledValue = computed(() => {
  if (mapStore.selectedTileIndex >= 0) {
    const layer = mapStore.activeLayer
    if (layer?.type === 'drawing') {
      const tileSet = mapStore.getTileSetForResource(mapStore.selectedResource)
      if (tileSet && tileSet.tiles[mapStore.selectedTileIndex]) {
        return tileSet.tiles[mapStore.selectedTileIndex].collision
      }
    }
  }
  const resource = mapStore.selectedResource
  if (resource) {
    if (resource.collisionType === '图像') return false
    return resource.collisionEnabled
  }
  if (mapStore.mapData.collisionType === '图像') return false
  return mapStore.mapData.collisionEnabled
})

function onCollisionTypeChange(val: string) {
  // 如果选中了单个瓦片，只更新该瓦片的碰撞类型
  if (selectedTileData.value && mapStore.selectedTileIndex >= 0) {
    const layer = mapStore.activeLayer
    if (layer?.type === 'drawing') {
      const tileSetIndex = mapStore.tileSetIndexOfResource(mapStore.selectedResource)
      if (tileSetIndex >= 0) {
        mapStore.setTileCollisionType(tileSetIndex, mapStore.selectedTileIndex, val)
      }
      return
    }
  }

  // 否则更新图块集/资源级别的碰撞类型
  mapStore.updateMapProperty('collisionType', val)
  const resource = mapStore.selectedResource
  if (resource) {
    resource.collisionType = val
    resource.collisionEnabled = val !== '图像'
    const ts = mapStore.getTileSetForResource(resource)
    if (ts) {
      ts.collisionType = val
      ts.collisionEnabled = val !== '图像'
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
  mapStore.updateMapProperty('collisionEnabled', val !== '图像')
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
      const tileSet = mapStore.getTileSetForResource(mapStore.selectedResource)
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
    const ts = mapStore.getTileSetForResource(resource)
    if (ts) ts.collisionEnabled = enabled
  }
}

</script>

<template>
  <div class="property-panel">
    <div v-if="showHeader !== false" class="att-tag-name">属性</div>

    <!-- 地图属性 -->
    <div class="att-frame">
      <div class="att-group">
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
          <span class="att-label">相机跟随</span>
          <label class="att-checkbox att-checkbox-disabled">
            <input type="checkbox" disabled />
            <span class="att-checkbox-text">启用</span>
          </label>
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
      </div>

      <!-- 当前图层属性 -->
      <div class="att-group">
        <div class="att-row">
          <span class="att-label">图层锁定</span>
          <label class="att-checkbox">
            <input
              type="checkbox"
              :checked="layerLocked"
              :disabled="disabled || mapStore.activeLayerIndex < 0"
              @change="onLayerLockChange"
            />
            <span class="att-checkbox-text">锁定</span>
          </label>
        </div>

        <template v-if="isTileMode">
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

          <div class="att-row">
            <span class="att-label">瓦片数量</span>
            <span class="att-value">{{ tileCount }}</span>
          </div>

          <div class="att-row">
            <span class="att-label">图块集</span>
            <span class="att-value">{{ tileSetCount }}</span>
          </div>
        </template>

        <template v-if="isImageMode">
          <div class="att-row">
            <span class="att-label">图片尺寸</span>
            <span class="att-value">{{ imageSizeText }}</span>
          </div>
        </template>

        <template v-if="isCollisionMode">
          <div class="att-row">
            <span class="att-label">碰撞体</span>
            <span class="att-value">{{ collisionCount }}</span>
          </div>

          <div class="att-row">
            <span class="att-label">已禁用</span>
            <span class="att-value">{{ collisionDisabledCount }}</span>
          </div>
        </template>
      </div>

      <!-- 图像变换：位置 / 旋转 / 缩放 / 不透明度 -->
      <div v-if="isImageMode" class="att-group">
        <div class="att-row">
          <span class="att-label">位置</span>
          <div class="att-size-group">
            <span class="att-size-label">X</span>
            <input
              class="att-input att-input-no-spin"
              type="number"
              :value="imagePosX"
              :disabled="disabled || transformDisabled"
              @change="setImagePosition(0, $event)"
            />
            <span class="att-size-label">Y</span>
            <input
              class="att-input att-input-no-spin"
              type="number"
              :value="imagePosY"
              :disabled="disabled || transformDisabled"
              @change="setImagePosition(1, $event)"
            />
          </div>
        </div>

        <div class="att-row">
          <span class="att-label">旋转</span>
          <div class="att-size-group">
            <input
              class="att-input att-input-no-spin"
              type="number"
              :value="imageRotation"
              :disabled="disabled || transformDisabled"
              @change="setImageRotation"
            />
            <span class="att-size-label">°</span>
          </div>
        </div>

        <div class="att-row">
          <span class="att-label">缩放</span>
          <div class="att-size-group">
            <span class="att-size-label">X</span>
            <input
              class="att-input att-input-no-spin"
              type="number"
              step="0.1"
              :value="imageScaleX"
              :disabled="disabled || transformDisabled"
              @change="setImageScale('x', $event)"
            />
            <span class="att-size-label">Y</span>
            <input
              class="att-input att-input-no-spin"
              type="number"
              step="0.1"
              :value="imageScaleY"
              :disabled="disabled || transformDisabled"
              @change="setImageScale('y', $event)"
            />
          </div>
        </div>

        <div class="att-row">
          <span class="att-label">不透明度</span>
          <input
            class="att-range"
            type="range"
            min="0"
            max="100"
            :value="imageOpacityPercent"
            :disabled="disabled || transformDisabled"
            @input="setImageOpacity"
          />
          <span class="att-value">{{ imageOpacityPercent }}%</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.property-panel {
  display: flex;
  flex-direction: column;
  background: var(--bg-root);
}

.att-tag-name {
  text-align: center;
  color: #9ca0a4;
  font-size: 12px;
  height: 44px;
  line-height: 44px;
  border-bottom: 1px solid rgb(45, 45, 45);
  flex-shrink: 0;
  /* 面板自身滚动时标题常驻，切换图层后始终能看到分区标题 */
  position: sticky;
  top: 0;
  z-index: 2;
  background: var(--bg-root);
}

.att-frame {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 12px 16px 16px 16px;
  background: var(--bg-root);
}

/* 属性分组：地图 / 图层 / 变换（不显示分组标题，仅用间距区分） */
.att-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
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
  border: 1px solid var(--border-light);
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
  background: var(--border-light);
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

/* 同一行两个数值输入（地图尺寸 / 位置 / 缩放）等分剩余宽度 */
.att-size-group .att-input {
  flex: 1 1 0;
  width: 100%;
  min-width: 0;
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

/* 只读信息值（瓦片数量 / 图片尺寸 / 碰撞体数量等） */
.att-value {
  color: #d5d8dc;
  font-size: 12px;
  white-space: nowrap;
}

/* 占位控件：禁用态（功能开发中） */
.att-range {
  flex: 1;
  min-width: 0;
  height: 4px;
  accent-color: var(--accent);
}

.att-range:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.att-checkbox-disabled {
  opacity: 0.5;
  cursor: default;
}
</style>
