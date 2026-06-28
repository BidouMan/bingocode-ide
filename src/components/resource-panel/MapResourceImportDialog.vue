<script setup lang="ts">
import { ref } from 'vue'

const emit = defineEmits<{
  'close': []
  'imported': [options: { path: string; mode: 'image' | 'tileset'; size: string }]
}>()

const resourcePath = ref('')
const mode = ref<'image' | 'tileset'>('image')
const tileSize = ref('16x16')

const sizes = ['16x16', '32x32', '64x64']

function onBrowse() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.png,.jpg,.jpeg,.bmp,.gif'
  input.onchange = (e: Event) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (file) resourcePath.value = file.name
  }
  input.click()
}

function onConfirm() {
  emit('imported', {
    path: resourcePath.value,
    mode: mode.value,
    size: tileSize.value,
  })
}
</script>

<template>
  <div class="dialog-overlay" @click.self="emit('close')">
    <div class="dialog-box">
      <div class="dialog-row">
        <label class="dialog-label">资源路径:</label>
        <input v-model="resourcePath" class="dialog-input" />
        <button class="dialog-btn" @click="onBrowse">浏览</button>
      </div>

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

      <div class="dialog-row dialog-actions">
        <div class="dialog-spacer" />
        <button class="dialog-btn" @click="emit('close')">取消</button>
        <button class="dialog-btn dialog-btn-primary" @click="onConfirm">确定</button>
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
  background: rgb(34, 37, 43);
  border: 1px solid rgb(55, 59, 68);
  border-radius: 8px;
  padding: 20px;
  min-width: 380px;
  display: flex;
  flex-direction: column;
  gap: 12px;
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
  border: 1px solid rgb(55, 59, 68);
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
  border: 1px solid rgb(55, 59, 68);
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

.dialog-radio-group {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: rgb(156, 160, 164);
  cursor: pointer;
}

.dialog-spacer { flex: 1; }

.dialog-actions {
  padding-top: 8px;
  border-top: 1px solid rgb(55, 59, 68);
}
</style>
