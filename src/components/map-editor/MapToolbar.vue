<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useMapStore } from '../../stores/map'
import { useResourceStore } from '../../stores/resource'
import type { MapTool } from '../../stores/map'
import CustomSelect from '../common/CustomSelect.vue'
import iconMove from '../../assets/icons/移动工具.svg'
import iconSelect from '../../assets/icons/选取工具.svg'
import iconPaint from '../../assets/icons/icon--paint.svg'
import iconErase from '../../assets/icons/清空.svg'
import iconFill from '../../assets/icons/填充.svg'
import iconNewMap from '../../assets/icons/新建地图.svg'
import iconImportMap from '../../assets/icons/导入地图.svg'
import iconExportMap from '../../assets/icons/导出地图.svg'
import iconGrid from '../../assets/icons/显示网格.svg'

const emit = defineEmits<{
  'new-map': []
  'import-map': []
  'export-map': []
}>()

const mapStore = useMapStore()
const resourceStore = useResourceStore()

const selectedMap = ref('')

const mapOptions = computed(() => {
  return resourceStore.maps.map(m => ({ label: m.name, value: m.id }))
})

watch(() => mapStore.currentMapPath, (path) => {
  const item = resourceStore.maps.find(m => m.id === path || m.path === path || m.name === path)
  if (item) selectedMap.value = item.id
}, { immediate: true })

function onMapChange(value: string) {
  selectedMap.value = value
  const item = resourceStore.maps.find(m => m.id === value)
  if (item) {
    mapStore.setMapPath(item.path || item.name)
    // 尝试从 localStorage 加载已保存的地图数据
    const saved = localStorage.getItem(`map_autosave_${item.path || item.name}`)
    if (saved) {
      try {
        const data = JSON.parse(saved)
        mapStore.loadMap(data)
        return
      } catch {}
    }
    // 没有保存的数据，创建新地图
    mapStore.loadMap({
      name: item.name,
      version: 5,
      width: 40,
      height: 30,
      tileSize: 16,
      offsetX: 0,
      offsetY: 0,
      gravity: false,
      collisionType: '图像',
      collisionEnabled: false,
      layers: [
        {
          id: 0,
          name: '图层',
          type: 'drawing',
          visible: true,
          locked: false,
          tiles: {},
          resources: [],
          images: [],
        },
      ],
      tileSets: [],
    })
  }
}

const tools: { id: MapTool; icon: string; label: string }[] = [
  { id: 'select', icon: iconSelect, label: '选取' },
  { id: 'move', icon: iconMove, label: '移动' },
  { id: 'draw', icon: iconPaint, label: '绘制' },
  { id: 'erase', icon: iconErase, label: '擦除' },
  { id: 'fill', icon: iconFill, label: '填充' },
]
</script>

<template>
  <div class="map-toolbar">
    <button class="toolbar-btn" title="新建地图" @click="emit('new-map')">
      <img :src="iconNewMap" class="toolbar-icon" />
    </button>
    <button class="toolbar-btn" title="导入 .bgm" @click="emit('import-map')">
      <img :src="iconImportMap" class="toolbar-icon" />
    </button>
    <button class="toolbar-btn" title="导出 .bgm" @click="emit('export-map')">
      <img :src="iconExportMap" class="toolbar-icon" />
    </button>

    <div class="toolbar-separator" />

    <button
      v-for="tool in tools"
      :key="tool.id"
      class="toolbar-btn"
      :class="{ 'toolbar-btn-active': mapStore.currentTool === tool.id }"
      :title="tool.label"
      @click="mapStore.setTool(tool.id)"
    >
      <img :src="tool.icon" class="toolbar-icon" />
    </button>

    <div class="toolbar-separator" />

    <button
      class="toolbar-btn"
      :class="{ 'toolbar-btn-active': mapStore.showGrid }"
      title="显示网格"
      @click="mapStore.toggleGrid()"
    >
      <img :src="iconGrid" class="toolbar-icon" />
    </button>

    <div class="toolbar-spacer" />

    <div class="toolbar-select-wrapper">
      <CustomSelect v-model="selectedMap" :options="mapOptions" @update:modelValue="onMapChange" />
    </div>
  </div>
</template>

<style scoped>
.map-toolbar {
  display: flex;
  align-items: center;
  height: 30px;
  padding: 0 8px;
  gap: 4px;
  background: rgb(34, 37, 43);
  border-bottom: 1px solid rgb(12, 12, 12);
  flex-shrink: 0;
}

.toolbar-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  padding: 0;
  flex-shrink: 0;
  transition: background 0.15s;
}

.toolbar-btn:hover {
  background: rgb(61, 64, 72);
}

.toolbar-btn:active {
  background: rgb(72, 75, 82);
}

.toolbar-btn-active {
  background: rgb(46, 49, 58);
  border: 1px solid rgb(55, 59, 68);
}

.toolbar-btn-active:hover {
  background: rgb(55, 59, 68);
}

.toolbar-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.toolbar-separator {
  width: 1px;
  height: 20px;
  background: rgb(55, 59, 68);
  margin: 0 2px;
}

.toolbar-spacer {
  flex: 1;
}

.toolbar-select-wrapper {
  width: 120px;
  flex-shrink: 0;
}
</style>
