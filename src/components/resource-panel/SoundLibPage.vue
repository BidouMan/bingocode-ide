<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { convertFileSrc } from '@tauri-apps/api/core'
import { useResourceStore } from '../../stores/resource'
import { useProjectStore } from '../../stores/project'

import iconSoundIcon from '../../assets/icons/sound_icon.svg'
import iconSoundPlay from '../../assets/icons/sound_play.svg'

const emit = defineEmits<{
  close: []
  imported: [id: string, name: string]
}>()

const resourceStore = useResourceStore()
const projectStore = useProjectStore()
const searchText = ref('')
const activeCategory = ref<string | null>(null)
const soundItems = ref<{ name: string; path: string; category: string | null }[]>([])
const isLoading = ref(false)
const hoveredPlayIndex = ref<number | null>(null)

let currentAudio: HTMLAudioElement | null = null

const categories = [
  { key: null, label: '全部' },
  { key: 'effects', label: '效果' },
  { key: 'loop', label: '音乐' },
]

const filteredSounds = computed(() => {
  let list = soundItems.value
  if (activeCategory.value !== null) {
    list = list.filter(s => s.category === activeCategory.value)
  }
  if (searchText.value) {
    const q = searchText.value.toLowerCase()
    list = list.filter(s => s.name.toLowerCase().includes(q))
  }
  return list
})

async function loadBuiltinSounds() {
  isLoading.value = true
  try {
    const engineAssetsDir = await invoke<string>('get_engine_assets_dir')
    const soundsDir = `${engineAssetsDir}/sounds`

    // 根目录下的声音文件（category = null，等同于 "全部"）
    try {
      const rootFiles = await invoke<string[]>('list_dir', { path: soundsDir })
      for (const file of rootFiles) {
        if (!file.endsWith('/') && /\.(wav|mp3|ogg|flac|m4a|aac|wma)$/i.test(file)) {
          soundItems.value.push({
            name: file.replace(/\.\w+$/, ''),
            path: `${soundsDir}/${file}`,
            category: null,
          })
        }
      }
    } catch { /* 根目录可能没有声音文件 */ }

    // effects 目录
    try {
      const effectFiles = await invoke<string[]>('list_dir', { path: `${soundsDir}/effects` })
      for (const file of effectFiles) {
        if (!file.endsWith('/') && /\.(wav|mp3|ogg|flac|m4a|aac|wma)$/i.test(file)) {
          soundItems.value.push({
            name: file.replace(/\.\w+$/, ''),
            path: `${soundsDir}/effects/${file}`,
            category: 'effects',
          })
        }
      }
    } catch { /* effects 目录可能不存在 */ }

    // loop 目录
    try {
      const loopFiles = await invoke<string[]>('list_dir', { path: `${soundsDir}/loop` })
      for (const file of loopFiles) {
        if (!file.endsWith('/') && /\.(wav|mp3|ogg|flac|m4a|aac|wma)$/i.test(file)) {
          soundItems.value.push({
            name: file.replace(/\.\w+$/, ''),
            path: `${soundsDir}/loop/${file}`,
            category: 'loop',
          })
        }
      }
    } catch { /* loop 目录可能不存在 */ }
  } catch (e) {
    console.error('[SoundLib] 加载内置声音失败:', e)
  } finally {
    isLoading.value = false
  }
}

async function selectSound(item: { name: string; path: string }) {
  const projectRoot = projectStore.root
  if (!projectRoot) return

  try {
    const ext = item.path.split('.').pop() || 'wav'
    const safeName = await getSafeSoundName(projectRoot, item.name, ext)
    const relativePath = `assets/sounds/${safeName}.${ext}`
    await invoke<string>('copy_file_to_project', {
      src: item.path,
      projectRoot,
      relativePath,
    })

    const projectPath = `${projectRoot}/${relativePath}`
    const id = resourceStore.addItem({
      name: safeName,
      type: 'sound',
      path: projectPath,
    })
    stopPlayback()
    emit('imported', id as string, safeName)
  } catch (e) {
    console.error('[SoundLib] 导入声音失败:', e)
  }
}

async function getSafeSoundName(projectRoot: string, baseName: string, ext: string): Promise<string> {
  const soundsDir = `${projectRoot}/assets/sounds`
  const exists = await invoke<boolean>('path_exists', { path: `${soundsDir}/${baseName}.${ext}` })
  if (!exists) return baseName
  let counter = 1
  while (true) {
    const candidate = `${baseName}_${counter}`
    const exists2 = await invoke<boolean>('path_exists', { path: `${soundsDir}/${candidate}.${ext}` })
    if (!exists2) return candidate
    counter++
  }
}

function onCardMouseMove(e: MouseEvent, index: number) {
  const target = e.currentTarget as HTMLElement
  const playBtn = target.querySelector('.lib-card-play') as HTMLElement | null
  if (!playBtn) return

  const btnRect = playBtn.getBoundingClientRect()
  const isOverPlay =
    e.clientX >= btnRect.left && e.clientX <= btnRect.right &&
    e.clientY >= btnRect.top && e.clientY <= btnRect.bottom

  if (isOverPlay) {
    playBtn.style.cursor = 'pointer'
    if (hoveredPlayIndex.value !== index) {
      hoveredPlayIndex.value = index
      playSound(index)
    }
  } else {
    playBtn.style.cursor = 'default'
    if (hoveredPlayIndex.value === index) {
      hoveredPlayIndex.value = null
      stopPlayback()
    }
  }
}

function onCardMouseLeave() {
  hoveredPlayIndex.value = null
  stopPlayback()
}

function playSound(index: number) {
  stopPlayback()
  const item = filteredSounds.value[index]
  if (!item) return
  try {
    const audioUrl = convertFileSrc(item.path)
    const audio = new Audio(audioUrl)
    currentAudio = audio
    audio.play().catch(() => {})
  } catch (e) {
    console.warn('播放声音失败:', e)
  }
}

function stopPlayback() {
  if (currentAudio) {
    currentAudio.pause()
    currentAudio.currentTime = 0
    currentAudio = null
  }
}

onMounted(loadBuiltinSounds)
onBeforeUnmount(stopPlayback)
</script>

<template>
  <div class="sound-lib-page">
    <div class="lib-toolbar">
      <input v-model="searchText" class="lib-search" placeholder="搜索..." />
      <div class="lib-tabs">
        <button
          v-for="cat in categories"
          :key="String(cat.key)"
          class="lib-tab"
          :class="{ 'lib-tab-active': activeCategory === cat.key }"
          @click="activeCategory = cat.key"
        >{{ cat.label }}</button>
      </div>
      <div class="lib-spacer" />
      <button class="lib-return-btn" @click="emit('close')">返回</button>
    </div>

    <div class="lib-grid">
      <div v-if="isLoading" class="lib-empty">加载中...</div>
      <template v-else>
        <div
          v-for="(item, index) in filteredSounds"
          :key="item.path"
          class="lib-card"
          @click="selectSound(item)"
          @mousemove="onCardMouseMove($event, index)"
          @mouseleave="onCardMouseLeave"
        >
          <div class="lib-card-thumb">
            <img :src="iconSoundIcon" class="lib-card-thumb-img" />
            <img
              :src="iconSoundPlay"
              class="lib-card-play"
              :class="{ 'lib-card-play-hover': hoveredPlayIndex === index }"
            />
            <div class="lib-card-name">{{ item.name }}</div>
          </div>
        </div>
        <div v-if="filteredSounds.length === 0 && !isLoading" class="lib-empty">暂无声音</div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.sound-lib-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-darker);
}

/* ─── 工具栏 ─── */
.lib-toolbar {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 5px;
  gap: 0;
  flex-shrink: 0;
  background: var(--bg-root);
  border-bottom: 1px solid var(--border);
}

.lib-search {
  width: 200px;
  height: 28px;
  padding: 0 8px;
  background: rgb(40, 43, 52);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: white;
  font-size: 12px;
  outline: none;
}
.lib-search:hover { background: rgb(50, 53, 62); border-color: rgb(65, 69, 82); }
.lib-search:focus { background: var(--border-light); border-color: #528bff; color: var(--text); }

/* ─── 分类标签 ─── */
.lib-tabs {
  display: flex;
  gap: 1px;
  margin-left: 10px;
}

.lib-tab {
  min-width: 80px;
  height: 28px;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: #9ca0a4;
  font-size: 12px;
  cursor: pointer;
  padding: 4px 10px;
  transition: background 0.15s;
}
.lib-tab:hover {
  background: var(--bg-hover);
  color: white;
}
.lib-tab-active {
  background: rgb(46, 49, 58);
  border: 1px solid var(--border-light);
  color: white;
}

.lib-spacer { flex: 1; }

.lib-return-btn {
  min-width: 80px;
  height: 28px;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: #9ca0a4;
  font-size: 12px;
  padding: 4px 8px;
  cursor: pointer;
  transition: background 0.15s;
}
.lib-return-btn:hover {
  background: var(--bg-hover);
  color: white;
}

/* ─── 卡片网格 ─── */
.lib-grid {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px;
  background: var(--bg-darker);
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  grid-auto-rows: max-content;
  gap: 0;
  align-content: start;
}

.lib-card {
  width: 170px;
  height: 170px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.lib-card:hover {
  cursor: pointer;
}

/* ─── 卡片内部（居中绘制 160x160） ─── */
.lib-card-thumb {
  width: 160px;
  height: 160px;
  background: rgb(45, 45, 45);
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;
  transition: background 0.1s;
}

.lib-card:hover .lib-card-thumb {
  background: rgb(60, 60, 60);
}

.lib-card-thumb-img {
  width: 150px;
  height: 110px;
  object-fit: contain;
  pointer-events: none;
}

.lib-card-play {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 30px;
  height: 30px;
  pointer-events: none;
  transition: transform 0.15s;
}
.lib-card-play-hover {
  transform: scale(1.1);
}

.lib-card-name {
  position: absolute;
  bottom: 6px;
  left: 0;
  right: 0;
  text-align: center;
  font-size: 10px;
  color: rgb(230, 230, 230);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  pointer-events: none;
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