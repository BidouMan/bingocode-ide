<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, computed } from 'vue'
import { invoke, convertFileSrc } from '@tauri-apps/api/core'
import { useSpriteLibStore, CATEGORY_LABELS } from '../../stores/spriteLib'
import { useResourceStore } from '../../stores/resource'
import { useProjectStore } from '../../stores/project'

const emit = defineEmits<{
  close: []
  imported: [id: string, name: string, bgsUrl: string]
}>()

const spriteLibStore = useSpriteLibStore()
const resourceStore = useResourceStore()
const projectStore = useProjectStore()
const searchText = ref('')

// 分类标签：默认显示角色（characters）
const activeCategory = ref('characters')

onMounted(async () => {
  await spriteLibStore.loadBuiltinLibrary()
  ensureValidCategory()
})

// 分类列表加载后校验当前选中（无 characters 时回退第一个分类）
function ensureValidCategory() {
  const cats = spriteLibStore.categories
  if (cats.length > 0 && !cats.includes(activeCategory.value)) {
    activeCategory.value = cats.includes('characters') ? 'characters' : cats[0]
  }
}

function categoryLabel(cat: string): string {
  return CATEGORY_LABELS[cat] || cat
}

// 当前分类 + 搜索过滤后的资源列表
const visibleItems = computed(() => {
  const q = searchText.value.trim().toLowerCase()
  return spriteLibStore.items.filter(item =>
    item.category === activeCategory.value &&
    (!q || item.name.toLowerCase().includes(q))
  )
})

// ====== 悬停动画预览 ======
// .bgs：解析帧按 fps 轮播（解析结果缓存在 store，每个包只解析一次）
// gif：换成原始文件 URL，<img> 原生播放动画
// 普通图片：无反应 = 无动画
const hoverPath = ref('')
const previewState = ref<{ urls: string[]; fps: number; index: number } | null>(null)
let previewTimer: ReturnType<typeof setInterval> | null = null

const previewUrl = computed(() => {
  const p = previewState.value
  if (!p || p.urls.length === 0) return ''
  return p.urls[p.index % p.urls.length]
})

function isPreviewing(filePath: string): boolean {
  return hoverPath.value === filePath && previewUrl.value !== ''
}

function stopPreview() {
  if (previewTimer) { clearInterval(previewTimer); previewTimer = null }
  previewState.value = null
  hoverPath.value = ''
}

async function onCardEnter(item: { filePath: string; type: string }) {
  stopPreview()
  hoverPath.value = item.filePath
  if (item.type === 'image' && item.filePath.toLowerCase().endsWith('.gif')) {
    previewState.value = { urls: [convertFileSrc(item.filePath)], fps: 0, index: 0 }
    return
  }
  if (item.type !== 'bgs') return
  const preview = await spriteLibStore.getSpritePreview(item.filePath)
  // 悬停已移走或已切换到其他卡片时丢弃过期结果
  if (!preview || hoverPath.value !== item.filePath) return
  previewState.value = { urls: preview.urls, fps: preview.fps, index: 0 }
  previewTimer = setInterval(() => {
    if (!previewState.value) return
    previewState.value.index = (previewState.value.index + 1) % previewState.value.urls.length
  }, Math.max(40, Math.round(1000 / preview.fps)))
}

onBeforeUnmount(stopPreview)

async function selectSprite(item: { name: string; filePath: string; type: string }) {
  const projectRoot = projectStore.root
  if (!projectRoot) return

  if (item.type === 'bgs') {
    // .bgs 包文件：解压到项目目录
    try {
      await invoke<string>('extract_bgs_to_project', {
        bgsPath: item.filePath,
        projectRoot,
        spriteName: item.name,
      })
    } catch (e) {
      console.error('[SpriteLib] 解压 .bgs 失败:', e)
      return
    }

    const projectPath = `${projectRoot}/assets/sprites/${item.name}`
    const id = resourceStore.addItem({
      name: item.name,
      type: 'sprite',
      path: projectPath,
    })
    emit('imported', id as string, item.name, item.filePath)
  } else {
    // 常规图片文件：复制到项目目录
    try {
      const ext = item.filePath.split('.').pop() || 'png'
      const relativePath = `assets/sprites/${item.name}.${ext}`
      const projectPath = await invoke<string>('copy_file_to_project', {
        src: item.filePath,
        projectRoot,
        relativePath,
      })

      const id = resourceStore.addItem({
        name: item.name,
        type: 'sprite',
        path: projectPath,
      })
      emit('imported', id as string, item.name, item.filePath)
    } catch (e) {
      console.error('[SpriteLib] 复制图片失败:', e)
    }
  }
}
</script>

<template>
  <div class="sprite-lib-page">
    <div class="lib-toolbar">
      <input v-model="searchText" class="lib-search" placeholder="搜索角色..." />
      <div style="width:10px" />
      <button
        v-for="cat in spriteLibStore.categories"
        :key="cat"
        class="lib-tab-btn"
        :class="{ 'lib-tab-active': activeCategory === cat }"
        @click="activeCategory = cat"
      >
        {{ categoryLabel(cat) }}
      </button>
      <div class="lib-spacer"></div>
      <div style="width:120px"></div>
      <button class="lib-return-btn" @click="emit('close')">返回</button>
    </div>

    <div class="lib-grid">
      <div
        v-for="item in visibleItems"
        :key="item.filePath"
        class="sprite-card"
        @click="selectSprite(item)"
        @mouseenter="onCardEnter(item)"
        @mouseleave="stopPreview"
      >
        <div class="sprite-thumb">
          <img v-if="isPreviewing(item.filePath)" :src="previewUrl" class="sprite-thumb-img" />
          <img v-else-if="item.thumbUrl" :src="item.thumbUrl" class="sprite-thumb-img" />
          <div v-else class="sprite-thumb-placeholder">{{ item.name.charAt(0) }}</div>
        </div>
        <span class="sprite-name">{{ item.name }}</span>
      </div>
      <div v-if="visibleItems.length === 0" class="lib-empty">暂无资源</div>
    </div>
  </div>
</template>

<style scoped>
.sprite-lib-page {
  width: 100%;
  height: 100%;
  background: var(--bg-root);
  display: flex;
  flex-direction: column;
}
.lib-toolbar {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 5px;
  flex-shrink: 0;
}
.lib-search {
  width: 200px;
  height: 28px;
  padding: 0 8px;
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 6px;
  color: var(--text-secondary);
  font-size: 12px;
  outline: none;
}
.lib-search:focus {   border-color: var(--accent); }
.lib-spacer { flex: 1; }

/* 分类标签按钮（与地图内置资源页同款样式） */
.lib-tab-btn {
  min-width: 80px;
  height: 28px;
  padding: 4px 10px;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: #9ca0a4;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.lib-tab-btn:hover {
  background: var(--bg-hover);
  color: white;
}
.lib-tab-active {
  background: rgb(46, 49, 58);
  border: 1px solid var(--border-light);
  color: white;
}
.lib-empty {
  grid-column: 1 / -1;
  text-align: center;
  padding: 40px 0;
  color: var(--text-muted);
  font-size: 12px;
}
.lib-return-btn {
  width: 80px;
  height: 28px;
  background: var(--bg-panel);
  border: 1px solid var(--border-light);
  border-radius: 4px;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
}
.lib-return-btn:hover { background: var(--bg-hover); color: var(--text); }
.lib-grid {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  grid-auto-rows: max-content;
  gap: 8px;
  align-content: start;
}
.sprite-card {
  aspect-ratio: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
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
  flex: 1;
  min-height: 0;
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
