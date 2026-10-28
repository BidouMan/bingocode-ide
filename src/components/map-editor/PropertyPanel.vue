<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { useMapStore, DEFAULT_CAMERA_SETTINGS } from '../../stores/map'
import { useEditorStore } from '../../stores/editor'
import { useResourceStore } from '../../stores/resource'
import CustomSelect from '../common/CustomSelect.vue'
import { toUserX, toWorldX, toUserY, toWorldY, toUserAngle, toWorldAngle } from '../../utils/coords'
import iconSettings from '../../assets/icons/icon--settings.svg'
import iconMarker from '../../assets/icons/标记.svg'
import iconCopy from '../../assets/icons/copy.svg'
import iconDelete from '../../assets/icons/选中删除.svg'

defineProps<{
  disabled?: boolean
}>()

const emit = defineEmits<{
  /** 属性面板修改了图像变换（位置/旋转/缩放/不透明度） */
  'transform-changed': []
}>()

const mapStore = useMapStore()
const editorStore = useEditorStore()
const resourceStore = useResourceStore()

// ====== 场景标记检视器 ======
/** 选中的图钉：选中时属性面板整体切换为该标记的检视器 */
const selectedMarker = computed(() => mapStore.selectedMarker)

/** 检视器分区的折叠状态（Godot / Unity 风格的可折叠分组，默认全展开） */
const markerFold = reactive({ basic: true, type: true, range: true, display: true, actions: true })

/** 地图 / 图层检视器分区折叠状态（与标记检视器共用同一套外观） */
const fold = reactive({ map: true, camera: true, physics: true, layer: true, transform: true })

const markerTypeOptions = [
  { label: '出生点', value: '出生点' },
  { label: '敌人', value: '敌人' },
  { label: '道具', value: '道具' },
  { label: '触发器', value: '触发器' },
  { label: '镜头', value: '镜头' },
  { label: '存档点', value: '存档点' },
]

/** 标记的扩展设置：半径 / 角度 / 显示 / 锁定
 *  暂为界面占位（未接入引擎与存档），按标记 id 在本次会话内保留，便于先确认交互与排版 */
interface MarkerExtra {
  radius: number
  angle: number
  visible: boolean
  locked: boolean
}

const markerExtraMap = reactive<Record<string, MarkerExtra>>({})
const markerExtra = computed(() => {
  const id = selectedMarker.value?.id
  return id ? markerExtraMap[id] : null
})

watch(
  () => selectedMarker.value?.id,
  (id) => {
    if (id && !markerExtraMap[id]) {
      markerExtraMap[id] = { radius: 0, angle: 0, visible: true, locked: false }
    }
  },
  { immediate: true },
)

const markerNameInputRef = ref<HTMLInputElement>()

/** 双击图钉后把焦点交给名称输入框（由父组件转调） */
function focusMarkerName() {
  markerNameInputRef.value?.focus()
  markerNameInputRef.value?.select()
}

defineExpose({ focusMarkerName })

/** 名称提交：空名或重名时回填原名 */
function onMarkerRename(e: Event) {
  const marker = selectedMarker.value
  const el = e.target as HTMLInputElement
  if (!marker) return
  if (!mapStore.renameMarker(marker.id, el.value)) el.value = marker.name
}

/** 坐标输入：用户坐标 ↔ 世界坐标；空值或非数字回填当前值 */
function onMarkerCoord(axis: 'x' | 'y', e: Event) {
  const marker = selectedMarker.value
  const el = e.target as HTMLInputElement
  if (!marker) return
  const raw = el.value.trim()
  const value = Number(raw)
  if (!raw || !Number.isFinite(value)) {
    el.value = String(Math.round(axis === 'x' ? toUserX(marker.x) : toUserY(marker.y)))
    return
  }
  const user = Math.round(value)
  if (axis === 'x') mapStore.updateMarkerPosition(marker.id, toWorldX(user), marker.y)
  else mapStore.updateMarkerPosition(marker.id, marker.x, toWorldY(user))
  el.value = String(user)
}

/** 半径 / 角度：滑杆与数值输入共用，统一取整并钳制范围 */
function onMarkerNumber(key: 'radius' | 'angle', e: Event) {
  const extra = markerExtra.value
  if (!extra) return
  const raw = Number((e.target as HTMLInputElement).value)
  if (!Number.isFinite(raw)) return
  const max = key === 'radius' ? 500 : 360
  extra[key] = Math.min(max, Math.max(0, Math.round(raw)))
}

/** 类型：写入标记本体，代码里 get_markers(类型) 按它分组 */
function setMarkerType(value: string) {
  const marker = selectedMarker.value
  if (marker) mapStore.setMarkerType(marker.id, value)
}

function setMarkerFlag(key: 'visible' | 'locked', e: Event) {
  const extra = markerExtra.value
  if (!extra) return
  extra[key] = (e.target as HTMLInputElement).checked
}

/** 名称/坐标输入框按回车直接生效并退出编辑 */
function blurPanelInput(e: KeyboardEvent) {
  (e.target as HTMLInputElement).blur()
}

/** 下滑设置子面板展开状态（选项为占位，功能后续版本实现） */
const showSlopeSettings = ref(false)

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
// 位置与旋转按用户坐标显示：原点在地图左下角、y 向上为正、角度逆时针为正；
// 内部仍以世界坐标（左上原点、y 向下）存储，只在显示/输入时换算。
const selectedImage = computed(() => mapStore.selectedImage)
const imagePosX = computed(() => Math.round(toUserX(selectedImage.value?.position?.[0] ?? 0)))
const imagePosY = computed(() => Math.round(toUserY(selectedImage.value?.position?.[1] ?? 0)))
const imageRotation = computed(() =>
  Math.round(toUserAngle(selectedImage.value?.rotation ?? 0) * 10) / 10,
)
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
  // 输入的是用户坐标，写回前换算成世界坐标
  pos[axis] = axis === 0 ? toWorldX(value) : toWorldY(value)
  img.position = [pos[0], pos[1]]
  emit('transform-changed')
}

function setImageRotation(e: Event) {
  const img = selectedImage.value
  const value = Number((e.target as HTMLInputElement).value)
  if (!img || !Number.isFinite(value)) return
  // 输入的是用户角度（逆时针为正），写回前换算成世界角度（顺时针为正）
  img.rotation = toWorldAngle(value)
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

/** 地图尺寸提交：输入过程中不实时生效，失焦/回车时统一校验后调整，
 *  避免逐字输入（如 40 → 450）触发多次画板重建与内容裁剪 */
function commitMapSize(axis: 'width' | 'height', e: Event) {
  const el = e.target as HTMLInputElement
  const parsed = Number(el.value)
  const current = axis === 'width' ? mapStore.mapData.width : mapStore.mapData.height
  const value = Number.isFinite(parsed) && parsed >= 1 ? Math.round(parsed) : current
  if (value !== current) mapStore.updateMapProperty(axis, value)
  // 非法/空值回填当前合法值，避免输入框与实际地图尺寸不一致
  el.value = String(value)
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

// ====== 相机跟随（勾选后在下发展开设置；运行时由引擎读取） ======
const camera = computed(() => ({ ...DEFAULT_CAMERA_SETTINGS, ...(mapStore.mapData.camera ?? {}) }))
const cameraSmoothingPercent = computed(() => Math.round(camera.value.smoothing * 100))

/**
 * 从项目代码里静态收集可跟随的角色变量名（`变量 = Sprite(...)`，按出现顺序）。
 * 只做正则扫描（面板打开/代码变更时），不执行代码，开销可忽略。
 */
const spriteTargetOptions = computed(() => {
  const names = new Set<string>()
  const scan = (text: string) => {
    if (!text) return
    const re = /^[ \t]*([^\s=#,()[\]{}]+)[ \t]*=[ \t]*Sprite[ \t]*\(/gm
    let match: RegExpExecArray | null
    while ((match = re.exec(text)) !== null) names.add(match[1])
  }
  for (const tab of [...editorStore.gameTabs, ...editorStore.codeTabs]) scan(tab.content)
  for (const item of resourceStore.codes) if (item.content) scan(item.content)
  return [...names].map(name => ({ label: name, value: name }))
})

/** 目标必须始终是存在的角色名：为空/失效时自动取第一个（= 第一个创建的角色） */
watch(
  spriteTargetOptions,
  (options) => {
    if (!camera.value.enabled) return
    const names = options.map(o => o.value)
    if (!names.includes(camera.value.target)) {
      mapStore.updateCameraSettings({ target: names[0] ?? '' })
    }
  },
  { immediate: true },
)

function onCameraEnabledChange(e: Event) {
  const enabled = (e.target as HTMLInputElement).checked
  mapStore.updateCameraSettings({ enabled })
  // 勾选时把目标补成第一个角色；场景里没有任何角色时留空（引擎会安全跳过）
  if (enabled) {
    const names = spriteTargetOptions.value.map(o => o.value)
    if (!names.includes(camera.value.target)) {
      mapStore.updateCameraSettings({ target: names[0] ?? '' })
    }
  }
}
function onCameraTargetChange(val: string) {
  mapStore.updateCameraSettings({ target: val })
}
function onCameraSmoothingChange(e: Event) {
  const value = Number((e.target as HTMLInputElement).value)
  if (!Number.isFinite(value)) return
  mapStore.updateCameraSettings({ smoothing: Math.max(0, Math.min(0.95, value / 100)) })
}
function onCameraOffsetChange(axis: 'x' | 'y', e: Event) {
  const value = Number((e.target as HTMLInputElement).value)
  if (!Number.isFinite(value)) return
  mapStore.updateCameraSettings(axis === 'x' ? { offsetX: value } : { offsetY: value })
}
function onCameraLimitChange(e: Event) {
  mapStore.updateCameraSettings({ limitBounds: (e.target as HTMLInputElement).checked })
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
    <div class="att-tag-name">属性</div>

    <!-- 地图属性 -->
    <div class="att-frame">
      <!-- 标记检视器：选中图钉时替代地图 / 图层属性 -->
      <div v-if="selectedMarker && markerExtra" class="att-group marker-inspector">
        <div class="mi-title">
          <img :src="iconMarker" alt="" class="mi-title-icon" />
          <span>标记</span>
        </div>

        <!-- 基本：名称 / 坐标 -->
        <div class="mi-section" :class="{ open: markerFold.basic }">
          <button class="mi-head" :disabled="disabled" @click="markerFold.basic = !markerFold.basic">
            <span class="mi-chevron" />
            <span class="mi-head-title">基本</span>
          </button>
          <div v-if="markerFold.basic" class="mi-body">
            <div class="att-row">
              <span class="att-label">名称</span>
              <input
                ref="markerNameInputRef"
                class="att-input"
                :value="selectedMarker?.name"
                maxlength="20"
                placeholder="标记名"
                :disabled="disabled"
                @change="onMarkerRename"
                @keydown.enter="blurPanelInput"
              />
            </div>
            <div class="att-row">
              <span class="att-label">位置</span>
              <div class="att-size-group">
                <span class="att-size-label">X</span>
                <input
                  class="att-input att-input-no-spin"
                  type="number"
                  :value="Math.round(toUserX(selectedMarker?.x ?? 0))"
                  :disabled="disabled"
                  @change="onMarkerCoord('x', $event)"
                />
                <span class="att-size-label">Y</span>
                <input
                  class="att-input att-input-no-spin"
                  type="number"
                  :value="Math.round(toUserY(selectedMarker?.y ?? 0))"
                  :disabled="disabled"
                  @change="onMarkerCoord('y', $event)"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- 类型：写入标记本体，代码里可按类型批量查找 -->
        <div class="mi-section" :class="{ open: markerFold.type }">
          <button class="mi-head" :disabled="disabled" @click="markerFold.type = !markerFold.type">
            <span class="mi-chevron" />
            <span class="mi-head-title">类型</span>
          </button>
          <div v-if="markerFold.type" class="mi-body">
            <div class="att-row">
              <span class="att-label">类型</span>
              <CustomSelect
                class="att-select"
                :model-value="selectedMarker.type"
                :options="markerTypeOptions"
                :disabled="disabled"
                @update:model-value="setMarkerType"
              />
            </div>
          </div>
        </div>

        <!-- 范围：半径 / 角度，数值输入与滑杆联动 -->
        <div class="mi-section" :class="{ open: markerFold.range }">
          <button class="mi-head" :disabled="disabled" @click="markerFold.range = !markerFold.range">
            <span class="mi-chevron" />
            <span class="mi-head-title">范围</span>
            <span class="mi-head-hint">占位</span>
          </button>
          <div v-if="markerFold.range" class="mi-body">
            <div class="att-row mi-range-row">
              <span class="att-label">半径</span>
              <input
                class="att-range"
                type="range"
                min="0"
                max="500"
                step="1"
                :value="markerExtra?.radius ?? 0"
                :disabled="disabled"
                @input="onMarkerNumber('radius', $event)"
              />
              <input
                class="att-input att-input-no-spin mi-number"
                type="number"
                min="0"
                max="500"
                :value="markerExtra?.radius ?? 0"
                :disabled="disabled"
                @change="onMarkerNumber('radius', $event)"
              />
            </div>
            <div class="att-row mi-range-row">
              <span class="att-label">角度</span>
              <input
                class="att-range"
                type="range"
                min="0"
                max="360"
                step="1"
                :value="markerExtra?.angle ?? 0"
                :disabled="disabled"
                @input="onMarkerNumber('angle', $event)"
              />
              <input
                class="att-input att-input-no-spin mi-number"
                type="number"
                min="0"
                max="360"
                :value="markerExtra?.angle ?? 0"
                :disabled="disabled"
                @change="onMarkerNumber('angle', $event)"
              />
            </div>
          </div>
        </div>

        <!-- 显示与锁定：占位 -->
        <div class="mi-section" :class="{ open: markerFold.display }">
          <button class="mi-head" :disabled="disabled" @click="markerFold.display = !markerFold.display">
            <span class="mi-chevron" />
            <span class="mi-head-title">显示与锁定</span>
            <span class="mi-head-hint">占位</span>
          </button>
          <div v-if="markerFold.display" class="mi-body">
            <div class="att-row">
              <span class="att-label">显示</span>
              <label class="att-checkbox">
                <input
                  type="checkbox"
                  :checked="markerExtra?.visible ?? true"
                  :disabled="disabled"
                  @change="setMarkerFlag('visible', $event)"
                />
                <span class="att-checkbox-text">在地图上显示</span>
              </label>
            </div>
            <div class="att-row">
              <span class="att-label">锁定</span>
              <label class="att-checkbox">
                <input
                  type="checkbox"
                  :checked="markerExtra?.locked ?? false"
                  :disabled="disabled"
                  @change="setMarkerFlag('locked', $event)"
                />
                <span class="att-checkbox-text">禁止拖动</span>
              </label>
            </div>
          </div>
        </div>

        <!-- 操作：复制 / 删除可用，复制代码为占位 -->
        <div class="mi-section" :class="{ open: markerFold.actions }">
          <button class="mi-head" :disabled="disabled" @click="markerFold.actions = !markerFold.actions">
            <span class="mi-chevron" />
            <span class="mi-head-title">操作</span>
          </button>
          <div v-if="markerFold.actions" class="mi-body">
            <div class="mi-actions">
              <button
                class="mi-btn"
                :disabled="disabled"
                @click="selectedMarker && mapStore.duplicateMarker(selectedMarker.id)"
              >
                <img :src="iconCopy" alt="" />
                <span>复制</span>
              </button>
              <button
                class="mi-btn mi-btn-danger"
                :disabled="disabled"
                @click="selectedMarker && mapStore.removeMarker(selectedMarker.id)"
              >
                <img :src="iconDelete" alt="" />
                <span>删除</span>
              </button>
            </div>
            <button class="mi-btn" :disabled="disabled" title="功能待接入">
              <span>复制代码</span>
            </button>
          </div>
        </div>
      </div>

      <template v-else>
      <div class="att-group">
        <!-- 地图：名称 / 尺寸 -->
        <div class="mi-section" :class="{ open: fold.map }">
          <button class="mi-head" :disabled="disabled" @click="fold.map = !fold.map">
            <span class="mi-chevron" />
            <span class="mi-head-title">地图</span>
          </button>
          <div v-if="fold.map" class="mi-body">
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
                  min="1"
                  step="1"
                  :value="mapStore.mapData.width"
                  :disabled="disabled"
                  @change="commitMapSize('width', $event)"
                />
                <span class="att-size-label">Y</span>
                <input
                  class="att-input att-input-no-spin"
                  type="number"
                  min="1"
                  step="1"
                  :value="mapStore.mapData.height"
                  :disabled="disabled"
                  @change="commitMapSize('height', $event)"
                />
              </div>
            </div>
          </div>
        </div>

        <!-- 相机：跟随开关与相机参数 -->
        <div class="mi-section" :class="{ open: fold.camera }">
          <button class="mi-head" :disabled="disabled" @click="fold.camera = !fold.camera">
            <span class="mi-chevron" />
            <span class="mi-head-title">相机</span>
          </button>
          <div v-if="fold.camera" class="mi-body">
            <div class="att-row">
              <span class="att-label">相机跟随</span>
          <label class="att-checkbox">
            <input
              type="checkbox"
              :checked="camera.enabled"
              :disabled="disabled"
              @change="onCameraEnabledChange"
            />
            <span class="att-checkbox-text">启用</span>
          </label>
        </div>

        <!-- 相机设置：勾选后展开为「相机跟随」的缩进子菜单，取消勾选即隐藏 -->
        <div v-if="camera.enabled" class="att-subgroup">
          <div class="att-row">
            <span class="att-label">跟随角色</span>
            <CustomSelect
              class="att-select"
              :model-value="camera.target"
              :options="spriteTargetOptions"
              :disabled="disabled || spriteTargetOptions.length === 0"
              placeholder="暂无角色"
              @update:model-value="onCameraTargetChange"
            />
          </div>

          <div class="att-row">
            <span class="att-label">平滑跟随</span>
            <input
              class="att-range"
              type="range"
              min="0"
              max="95"
              :value="cameraSmoothingPercent"
              :disabled="disabled"
              @input="onCameraSmoothingChange"
            />
            <span class="att-value">{{ cameraSmoothingPercent }}%</span>
          </div>

          <div class="att-row">
            <span class="att-label">偏移</span>
            <div class="att-size-group">
              <span class="att-size-label">X</span>
              <input
                class="att-input att-input-no-spin"
                type="number"
                :value="camera.offsetX"
                :disabled="disabled"
                @change="onCameraOffsetChange('x', $event)"
              />
              <span class="att-size-label">Y</span>
              <input
                class="att-input att-input-no-spin"
                type="number"
                :value="camera.offsetY"
                :disabled="disabled"
                @change="onCameraOffsetChange('y', $event)"
              />
            </div>
          </div>

            <div class="att-row">
              <span class="att-label">边界限制</span>
              <label class="att-checkbox">
                <input
                  type="checkbox"
                  :checked="camera.limitBounds"
                  :disabled="disabled"
                  @change="onCameraLimitChange"
                />
                <span class="att-checkbox-text">限制在地图内</span>
              </label>
            </div>
          </div>
          </div>
        </div>

        <!-- 物理：重力 / 边界 / 下滑 -->
        <div class="mi-section" :class="{ open: fold.physics }">
          <button class="mi-head" :disabled="disabled" @click="fold.physics = !fold.physics">
            <span class="mi-chevron" />
            <span class="mi-head-title">物理</span>
          </button>
          <div v-if="fold.physics" class="mi-body">
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
          <span class="att-label">限制边界</span>
          <label class="att-checkbox">
            <input
              type="checkbox"
              :checked="mapStore.mapData.boundaryCollision"
              :disabled="disabled"
              @change="mapStore.updateMapProperty('boundaryCollision', ($event.target as HTMLInputElement).checked)"
            />
            <span class="att-checkbox-text">启用</span>
          </label>
        </div>

        <div class="att-row">
          <span class="att-label">禁止下滑</span>
          <label class="att-checkbox">
            <input
              type="checkbox"
              :checked="mapStore.mapData.stopOnSlope"
              :disabled="disabled"
              @change="mapStore.updateMapProperty('stopOnSlope', ($event.target as HTMLInputElement).checked)"
            />
            <span class="att-checkbox-text">启用</span>
          </label>
          <button
            class="att-gear-btn"
            :class="{ active: showSlopeSettings }"
            :disabled="disabled"
            title="下滑设置"
            @click="showSlopeSettings = !showSlopeSettings"
          >
            <img :src="iconSettings" alt="下滑设置" />
          </button>
        </div>

        <!-- 下滑设置：占位选项，功能后续版本实现
             参考成熟引擎：坡度上限=Godot floor_max_angle / Unity slopeLimit，
             下坡贴地=Godot floor_snap_length，坡上匀速=Godot floor_constant_speed -->
        <div v-if="showSlopeSettings" class="att-subgroup">
          <div class="att-row">
            <span class="att-label">坡度上限</span>
            <input class="att-input att-input-no-spin" type="number" value="45" disabled />
            <span class="att-value">度</span>
          </div>

          <div class="att-row">
            <span class="att-label">下滑速度</span>
            <input class="att-range" type="range" min="0" max="100" value="50" disabled />
            <span class="att-value">50%</span>
          </div>

          <div class="att-row">
            <span class="att-label">下坡贴地</span>
            <label class="att-checkbox">
              <input type="checkbox" checked disabled />
              <span class="att-checkbox-text">启用</span>
            </label>
          </div>

          <div class="att-row">
            <span class="att-label">坡上匀速</span>
            <label class="att-checkbox">
              <input type="checkbox" disabled />
              <span class="att-checkbox-text">启用</span>
            </label>
          </div>
        </div>
          </div>
        </div>
      </div>

      <!-- 当前图层属性 -->
      <div class="att-group">
        <!-- 图层：锁定与按类型的图层信息 -->
        <div class="mi-section" :class="{ open: fold.layer }">
          <button class="mi-head" :disabled="disabled" @click="fold.layer = !fold.layer">
            <span class="mi-chevron" />
            <span class="mi-head-title">图层</span>
          </button>
          <div v-if="fold.layer" class="mi-body">
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
            <CustomSelect class="att-select" :model-value="collisionTypeValue" :options="collisionTypeOptions" :disabled="disabled" @update:model-value="onCollisionTypeChange" />
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
        </div>
      </div>

      <!-- 图像变换：位置 / 旋转 / 缩放 / 不透明度 -->
      <div v-if="isImageMode" class="att-group">
        <!-- 变换：图片位置与形态 -->
        <div class="mi-section" :class="{ open: fold.transform }">
          <button class="mi-head" :disabled="disabled" @click="fold.transform = !fold.transform">
            <span class="mi-chevron" />
            <span class="mi-head-title">变换</span>
          </button>
          <div v-if="fold.transform" class="mi-body">
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

/* 下拉框：固定占满标签右侧剩余宽度，右边缘对齐属性区 */
.att-select {
  flex: 1;
  width: 100%;
  min-width: 0;
}

/* 子菜单：相机跟随展开后的设置（缩进 + 左侧竖线，表明从属于上方开关） */
.att-subgroup {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-left: 2px;
  padding: 2px 0 2px 12px;
  border-left: 2px solid rgb(58, 62, 72);
}

.att-label {
  color: #9ca0a4;
  font-size: 12px;
  min-width: 60px;
  flex-shrink: 0;
}

/* 下滑设置齿轮按钮：靠右对齐，hover/展开时用底色高亮提示状态 */
.att-gear-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  margin-left: auto;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: default;
  flex-shrink: 0;
}

.att-gear-btn img {
  width: 14px;
  height: 14px;
  opacity: 0.55;
}

.att-gear-btn:hover {
  background: rgb(61, 64, 72);
}

.att-gear-btn:hover img {
  opacity: 0.9;
}

.att-gear-btn.active {
  background: rgb(61, 64, 72);
}

.att-gear-btn.active img {
  opacity: 1;
}

.att-gear-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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
  cursor: default;
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
}

.att-range:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

/* ====== 标记检视器（Godot / Unity 风格的可折叠分区） ====== */
.marker-inspector {
  gap: 0;
}

.mi-title {
  display: flex;
  align-items: center;
  gap: 6px;
  padding-bottom: 8px;
  font-size: 12px;
  font-weight: 600;
  color: #d5d8dc;
}

.mi-title-icon {
  width: 14px;
  height: 14px;
  opacity: 0.9;
}

.mi-section {
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

/* 分区标题：整行可点，右侧小三角指示展开状态 */
.mi-head {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  height: 28px;
  padding: 0 2px;
  background: transparent;
  border: none;
  color: #a8adb4;
  font-size: 12px;
  font-family: inherit;
  text-align: left;
  cursor: default;
}

.mi-head:hover {
  color: #d5d8dc;
}

.mi-head:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mi-chevron {
  flex-shrink: 0;
  width: 5px;
  height: 5px;
  margin: 0 1px;
  border-right: 1.5px solid currentColor;
  border-bottom: 1.5px solid currentColor;
  transform: rotate(-45deg);
  transition: transform 0.15s ease;
}

.mi-section.open .mi-chevron {
  transform: rotate(45deg);
}

.mi-head-title {
  flex: 1;
}

.mi-head-hint {
  font-size: 10px;
  color: #6b7078;
}

.mi-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 2px 0 12px;
}

/* 半径 / 角度：滑杆 + 数值输入联动 */
.mi-range-row {
  gap: 10px;
}

.mi-range-row .mi-number {
  width: 56px;
  flex-shrink: 0;
  text-align: center;
}

.mi-actions {
  display: flex;
  gap: 8px;
}

.mi-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  flex: 1;
  height: 26px;
  padding: 0 8px;
  background: rgb(48, 51, 60);
  border: 1px solid var(--border-light);
  border-radius: 5px;
  color: #cfd3d9;
  font-size: 12px;
  font-family: inherit;
  cursor: default;
  transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
}

.mi-btn img {
  width: 13px;
  height: 13px;
  opacity: 0.75;
}

.mi-btn:hover {
  background: rgb(61, 64, 72);
  color: #fff;
}

.mi-btn:hover img {
  opacity: 1;
}

.mi-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.mi-btn-danger:hover {
  background: rgba(95, 45, 39, 0.75);
  border-color: rgba(224, 92, 78, 0.5);
  color: #ffb4ab;
}
</style>