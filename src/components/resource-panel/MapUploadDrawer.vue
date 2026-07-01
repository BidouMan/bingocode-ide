<script setup lang="ts">
import { ref } from 'vue'
import iconFileUpload from '../../assets/icons/icon--file-upload.svg'
import iconEdit from '../../assets/icons/编辑.svg'
import iconSelectSprite from '../../assets/icons/icon--select--sprite.svg'
import iconMapUpload from '../../assets/icons/map_upload.svg'

const emit = defineEmits<{
  'import-file': []
  'create-map': []
  'open-library': []
}>()

const menuVisible = ref(false)
let hideTimeout: ReturnType<typeof setTimeout> | null = null

function onMouseEnter() {
  if (hideTimeout) { clearTimeout(hideTimeout); hideTimeout = null }
  menuVisible.value = true
}

function onMouseLeave() {
  hideTimeout = setTimeout(() => { menuVisible.value = false }, 200)
}

function onAction(action: string) {
  menuVisible.value = false
  if (action === 'import') emit('import-file')
  else if (action === 'create') emit('create-map')
  else if (action === 'library') emit('open-library')
}
</script>

<template>
  <div class="upload-drawer" @mouseenter="onMouseEnter" @mouseleave="onMouseLeave">
    <transition name="slide-up">
      <div v-show="menuVisible" class="drawer-menu">
        <button class="drawer-btn" @click="onAction('import')" title="从文件导入">
          <img :src="iconFileUpload" class="drawer-icon" />
        </button>
        <button class="drawer-btn" @click="onAction('create')" title="创建地图">
          <img :src="iconEdit" class="drawer-icon" />
        </button>
        <button class="drawer-btn" @click="onAction('library')" title="选择库文件">
          <img :src="iconSelectSprite" class="drawer-icon" />
        </button>
      </div>
    </transition>
    <button class="drawer-main-btn" @mouseenter="onMouseEnter">
      <img :src="iconMapUpload" class="drawer-main-icon" />
    </button>
  </div>
</template>

<style scoped>
.upload-drawer {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 70px;
  height: 226px;
  z-index: 100;
}

.drawer-menu {
  position: absolute;
  bottom: 50px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 4px;
}

.drawer-btn {
  width: 30px;
  height: 30px;
  background: #4B9B5C;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s;
}

.drawer-btn:hover {
  background: #5bc772;
}

.drawer-icon {
  width: 20px;
  height: 20px;
}

.drawer-main-btn {
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 50px;
  height: 50px;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.drawer-main-icon {
  width: 40px;
  height: 40px;
}

.slide-up-enter-active,
.slide-up-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-up-enter-from,
.slide-up-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(20px);
}
</style>
