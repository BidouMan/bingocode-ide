<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { invoke } from '@tauri-apps/api/core'

const props = defineProps<{
  layerType: 'image' | 'drawing'
}>()

const emit = defineEmits<{
  'close': []
  'imported': [options: { path: string; mode: 'image' | 'tileset'; size: string; tileIndices?: number[] }]
}>()

const resourcePath = ref('')
const mode = ref<'image' | 'tileset'>('image')
const tileSize = ref('16x16')

const sizes = ['16x16', '32x32', '64x64']

// ─── 图块集选择（全部 / 部分导入）───
const tileThumbs = ref<string[]>([])
const tileSelected = ref<boolean[]>([])
const tileEmpty = ref<boolean[]>([])
const loadingTiles = ref(false)
const tileError = ref('')
const selectedCount = computed(() => tileSelected.value.filter(Boolean).length)

async function onBrowse() {
  try {
    const path = await invoke<string | null>('pick_image_file')
    if (path) {
      resourcePath.value = path
      // 路径 watcher 会自动读取图块
    }
  } catch (e) {
    console.error('选择文件失败:', e)
  }
}

async function loadTiles() {
  tileThumbs.value = []
  tileSelected.value = []
  tileEmpty.value = []
  tileError.value = ''
  if (!resourcePath.value || mode.value !== 'tileset' || props.layerType !== 'drawing') return
  loadingTiles.value = true
  try {
    const url = await invoke<string>('read_image_as_data_url', { path: resourcePath.value })
    const img = await new Promise<HTMLImageElement>((resolve, reject) => {
      const im = new Image()
      im.onload = () => resolve(im)
      im.onerror = reject
      im.src = url
    })
    const [tw, th] = tileSize.value.split('x').map(Number)
    const cols = Math.floor(img.width / tw)
    const rows = Math.floor(img.height / th)
    const count = cols * rows
    if (count <= 0) {
      tileError.value = '图片尺寸不足以切分图块'
      loadingTiles.value = false
      return
    }
    const thumbs: string[] = []
    const emptyFlags: boolean[] = []
    for (let i = 0; i < count; i++) {
      const row = Math.floor(i / cols)
      const col = i % cols
      const canvas = document.createElement('canvas')
      canvas.width = tw
      canvas.height = th
      const ctx = canvas.getContext('2d', { willReadFrequently: true })!
      ctx.drawImage(img, col * tw, row * th, tw, th, 0, 0, tw, th)
      // 全透明图块视为空格子：默认不导入
      const data = ctx.getImageData(0, 0, tw, th).data
      let empty = true
      for (let p = 3; p < data.length; p += 4) {
        if (data[p] > 8) { empty = false; break }
      }
      emptyFlags.push(empty)
      thumbs.push(canvas.toDataURL())
    }
    tileThumbs.value = thumbs
    tileEmpty.value = emptyFlags
    tileSelected.value = emptyFlags.map(e => !e)
  } catch {
    tileError.value = '读取图块失败'
  } finally {
    loadingTiles.value = false
  }
}

function toggleTile(index: number) {
  if (tileEmpty.value[index]) return
  tileSelected.value[index] = !tileSelected.value[index]
}

function selectAll(v: boolean) {
  tileSelected.value = tileSelected.value.map((_, i) => (tileEmpty.value[i] ? false : v))
}

watch(mode, (m) => {
  if (m === 'tileset') void loadTiles()
  else {
    tileThumbs.value = []
    tileSelected.value = []
    tileEmpty.value = []
    tileError.value = ''
  }
})
watch(tileSize, () => { if (mode.value === 'tileset') void loadTiles() })
watch(resourcePath, () => { if (mode.value === 'tileset') void loadTiles() })

function onConfirm() {
  if (!resourcePath.value) return
  const isImageLayer = props.layerType === 'image'
  if (!isImageLayer && mode.value === 'tileset') {
    if (selectedCount.value === 0) return
    const indices = tileSelected.value
      .map((s, i) => (s ? i : -1))
      .filter(i => i >= 0)
    emit('imported', {
      path: resourcePath.value,
      mode: 'tileset',
      size: tileSize.value,
      tileIndices: indices,
    })
    return
  }
  emit('imported', {
    path: resourcePath.value,
    mode: isImageLayer ? 'image' : mode.value,
    size: isImageLayer ? '64x64' : tileSize.value,
  })
}
</script>

<template>
  <div class="dialog-overlay" @click.self="emit('close')">
    <div class="dialog-box">
      <div class="dialog-row">
        <label class="dialog-label">资源路径:</label>
        <input v-model="resourcePath" class="dialog-input" readonly />
        <button class="dialog-btn" @click="onBrowse">浏览</button>
      </div>

      <!-- 绘制图层才显示模式和尺寸选择 -->
      <template v-if="layerType === 'drawing'">
        <div class="dialog-row">
          <label class="dialog-radio-group">
            <input type="radio" v-model="mode" value="image" />
            <span>图像模式</span>
          </label>
          <label class="dialog-radio-group">
            <input type="radio" v-model="mode" value="tileset" />
            <span>图块集合</span>
          </label>

          <div class="dialog-spacer" />

          <label class="dialog-label">尺寸:</label>
          <select v-model="tileSize" class="dialog-select">
            <option v-for="s in sizes" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
      </template>

      <!-- 图块集：导入前选择部分图块（可全部导入） -->
      <div
        v-if="layerType === 'drawing' && mode === 'tileset' && resourcePath"
        class="tile-picker"
      >
        <div class="tile-picker-head">
          <span class="tile-picker-label">选择图块（{{ selectedCount }}/{{ tileThumbs.length }}）</span>
          <button class="dialog-btn tile-mini-btn" @click="selectAll(true)">全选</button>
          <button class="dialog-btn tile-mini-btn" @click="selectAll(false)">全不选</button>
        </div>
        <div v-if="loadingTiles" class="tile-picker-hint">读取中…</div>
        <div v-else-if="tileError" class="tile-picker-hint">{{ tileError }}</div>
        <div v-else class="tile-picker-grid">
          <button
            v-for="(thumb, i) in tileThumbs"
            :key="i"
            class="tile-pick-cell"
            :class="{ 'tile-pick-on': tileSelected[i], 'tile-pick-empty': tileEmpty[i] }"
            :style="{ backgroundImage: `url(${thumb})` }"
            :title="tileEmpty[i] ? '空图块（不导入）' : `#${i}`"
            @click="toggleTile(i)"
          ></button>
        </div>
      </div>

      <!-- 图像图层提示 -->
      <div v-else class="dialog-hint">
        图像图层：资源将作为整图导入
      </div>

      <div class="dialog-row dialog-actions">
        <div class="dialog-spacer" />
        <button class="dialog-btn" @click="emit('close')">取消</button>
        <button
          class="dialog-btn dialog-btn-primary"
          :disabled="layerType === 'drawing' && mode === 'tileset' && selectedCount === 0"
          @click="onConfirm"
        >确定</button>
        <div class="dialog-spacer" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.dialog-box {
  background: var(--bg-root);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 20px;
  min-width: 460px;
  max-width: 620px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 图块集选择面板 */
.tile-picker {
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-top: 1px solid var(--border-light);
  padding-top: 10px;
}

.tile-picker-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tile-picker-label {
  flex: 1;
  font-size: 12px;
  color: rgb(156, 160, 164);
}

.tile-mini-btn {
  height: 24px;
  padding: 0 8px;
  font-size: 11px;
}

.tile-picker-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, 34px);
  gap: 3px;
  max-height: 260px;
  overflow: auto;
  padding: 4px;
  background: rgb(30, 30, 30);
  border-radius: 6px;
}

.tile-pick-cell {
  width: 34px;
  height: 34px;
  border: 2px solid transparent;
  border-radius: 4px;
  background-color: rgb(50, 53, 62);
  background-size: contain;
  background-repeat: no-repeat;
  background-position: center;
  image-rendering: pixelated;
  cursor: pointer;
  padding: 0;
  opacity: 0.45;
}

.tile-pick-on {
  border-color: var(--accent);
  opacity: 1;
}

.tile-pick-empty {
  opacity: 0.12;
  cursor: default;
}

.tile-picker-hint {
  font-size: 12px;
  color: rgb(120, 120, 120);
  padding: 6px 2px;
}

.dialog-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dialog-label {
  font-size: 12px;
  color: rgb(156, 160, 164);
  white-space: nowrap;
}

.dialog-input {
  flex: 1;
  height: 28px;
  background: rgb(40, 43, 52);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: white;
  padding: 0 8px;
  font-size: 12px;
  outline: none;
}

.dialog-input:focus {
  border: 1px solid #528bff;
}

.dialog-select {
  height: 28px;
  background: rgb(40, 43, 52);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: white;
  padding: 0 8px;
  font-size: 12px;
  outline: none;
}

.dialog-btn {
  height: 28px;
  padding: 0 12px;
  background: rgb(52, 55, 62);
  border: 1px solid rgb(73, 76, 86);
  border-radius: 4px;
  color: rgb(150, 150, 150);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}

.dialog-btn:hover {
  background: rgb(62, 65, 72);
  color: white;
}

.dialog-btn-primary {
  background: rgb(55, 120, 200);
  border-color: rgb(55, 120, 200);
  color: white;
}

.dialog-btn-primary:hover {
  background: rgb(65, 140, 220);
}

.dialog-btn-primary:disabled {
  opacity: 0.45;
  cursor: default;
}

.dialog-radio-group {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: rgb(156, 160, 164);
  cursor: pointer;
}

.dialog-hint {
  font-size: 12px;
  color: rgb(120, 160, 120);
  padding: 4px 0;
}

.dialog-spacer { flex: 1; }

.dialog-actions {
  padding-top: 8px;
  border-top: 1px solid var(--border-light);
}
</style>
