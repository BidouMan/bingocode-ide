<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'

interface Option {
  label: string
  value: string
}

const props = defineProps<{
  modelValue: string
  options: Option[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const isOpen = ref(false)
const selectRef = ref<HTMLDivElement>()

const selectedLabel = computed(() => {
  const opt = props.options.find(o => o.value === props.modelValue)
  return opt ? opt.label : props.modelValue
})

function toggle() {
  isOpen.value = !isOpen.value
}

function selectOption(value: string) {
  emit('update:modelValue', value)
  isOpen.value = false
}

function onClickOutside(e: MouseEvent) {
  if (selectRef.value && !selectRef.value.contains(e.target as Node)) {
    isOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', onClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutside)
})
</script>

<template>
  <div ref="selectRef" class="custom-select" :class="{ open: isOpen }" @click="toggle">
    <span class="custom-select-value">{{ selectedLabel }}</span>
    <span class="custom-select-arrow">
      <svg width="10" height="6" viewBox="0 0 10 6" fill="none">
        <path d="M1 1L5 5L9 1" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </span>
    <Transition name="dropdown">
      <div v-if="isOpen" class="custom-select-dropdown" @click.stop>
        <div
          v-for="opt in options"
          :key="opt.value"
          class="custom-select-option"
          :class="{ selected: opt.value === modelValue }"
          @click="selectOption(opt.value)"
        >
          {{ opt.label }}
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.custom-select {
  position: relative;
  display: flex;
  align-items: center;
  height: 24px;
  background: rgb(40, 43, 52);
  border: 1px solid rgb(55, 59, 68);
  border-radius: 4px;
  color: white;
  padding: 0 6px;
  font-size: 12px;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s, border-color 0.15s;
}

.custom-select:hover {
  background: rgb(50, 53, 62);
  border-color: rgb(65, 69, 82);
}

.custom-select.open {
  background: rgb(55, 59, 68);
  border-color: rgb(65, 69, 82);
}

.custom-select-value {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.custom-select-arrow {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: 4px;
  color: #9ca0a4;
  transition: transform 0.2s;
}

.custom-select.open .custom-select-arrow {
  transform: rotate(180deg);
}

.custom-select-dropdown {
  position: absolute;
  top: calc(100% + 2px);
  left: -1px;
  right: -1px;
  background: rgb(34, 37, 43);
  border: 1px solid rgb(55, 59, 68);
  border-radius: 4px;
  z-index: 1000;
  overflow: hidden;
}

.custom-select-option {
  padding: 4px 8px;
  font-size: 12px;
  color: #c9cdd4;
  cursor: pointer;
  transition: background 0.1s;
}

.custom-select-option:hover {
  background: rgb(50, 53, 62);
}

.custom-select-option.selected {
  background: #528bff;
  color: white;
}

.dropdown-enter-active,
.dropdown-leave-active {
  transition: opacity 0.15s, transform 0.15s;
}

.dropdown-enter-from,
.dropdown-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
