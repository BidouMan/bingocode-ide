<script setup lang="ts">
import { ref } from 'vue'
import iconDev from '../../assets/icons/开发工具.svg'

/**
 * 开发工具菜单（仅 dev 构建可见）。
 * 集中放所有开发者工具入口，新增工具在这里加菜单项即可。
 * 通过事件通知父组件执行具体操作（父组件用动态 import 加载工具页）。
 */
const visible = ref(false)
function toggle() { visible.value = !visible.value }
function close() { visible.value = false }

const emit = defineEmits<{
  (e: 'open-asset-studio'): void
}>()

function onAssetStudio() {
  close()
  emit('open-asset-studio')
}
</script>

<template>
  <div class="menu-file-wrapper" @mouseleave="close">
    <button class="menu-btn" @click="toggle">
      <img :src="iconDev" class="menu-icon" />
      <span>DEV工具</span>
    </button>
    <div v-show="visible" class="file-menu-dropdown">
      <button class="file-menu-item" @click="onAssetStudio">素材整理</button>
    </div>
  </div>
</template>

<style scoped>
.menu-icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}
.menu-btn {
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex-shrink: 0;
  background: transparent;
  border: none;
  color: white;
  cursor: pointer;
  transition: background 0.15s;
  padding: 0 12px;
}
.menu-btn span {
  font-size: 11px;
  line-height: 1;
  white-space: nowrap;
}
.menu-btn:hover { background: var(--bg-hover); }
.menu-file-wrapper {
  position: relative;
  display: flex;
  align-items: stretch;
}
.file-menu-dropdown {
  position: absolute;
  top: 100%;
  left: 0;
  width: 144px;
  background: var(--bg-root);
  border-radius: 6px;
  padding: 4px 0;
  z-index: 100;
  box-shadow: 0 4px 16px rgba(0,0,0,0.4);
}
.file-menu-item {
  display: block;
  width: calc(100% - 16px);
  height: 32px;
  padding: 0 15px;
  background: transparent;
  border: none;
  color: white;
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  border-radius: 4px;
  margin: 2px 8px;
  transition: background 0.12s;
}
.file-menu-item:hover { background: var(--bg-hover); }
</style>
