<script setup lang="ts">
import { ref } from 'vue'
import { useMapEditorStore } from '../../stores/mapEditor'
import CollisionEditor from './CollisionEditor.vue'
import iconMoveAnchor from '../../assets/icons/移动锚点.svg'
import iconAddAnchor from '../../assets/icons/添加锚点.svg'
import iconDelAnchor from '../../assets/icons/删除锚点.svg'
import iconResetAnchor from '../../assets/icons/重置锚点.svg'

/**
 * 图块模式的素材碰撞编辑区：工具条 + 256×256 编辑画布。
 * 图像模式不使用该区域（图片碰撞在画布上按实例编辑）。
 */
const mapEditorStore = useMapEditorStore()
const collisionEditorRef = ref<InstanceType<typeof CollisionEditor>>()
</script>

<template>
  <div class="tile-collision-panel">
    <div class="col-toolbar">
      <button
        class="col-tool-btn"
        :class="{ 'col-tool-active': mapEditorStore.collisionTool === 'move' }"
        v-tooltip="'移动锚点'"
        @click="mapEditorStore.setCollisionTool('move')"
      >
        <img :src="iconMoveAnchor" class="col-tool-icon" />
      </button>
      <button
        class="col-tool-btn"
        :class="{ 'col-tool-active': mapEditorStore.collisionTool === 'add' }"
        v-tooltip="'添加锚点'"
        @click="mapEditorStore.setCollisionTool('add')"
      >
        <img :src="iconAddAnchor" class="col-tool-icon" />
      </button>
      <button
        class="col-tool-btn"
        :class="{ 'col-tool-active': mapEditorStore.collisionTool === 'delete' }"
        v-tooltip="'删除锚点'"
        @click="mapEditorStore.setCollisionTool('delete')"
      >
        <img :src="iconDelAnchor" class="col-tool-icon" />
      </button>
      <button class="col-tool-btn" v-tooltip="'重置锚点'" @click="collisionEditorRef?.resetCollision()">
        <img :src="iconResetAnchor" class="col-tool-icon" />
      </button>
    </div>

    <CollisionEditor ref="collisionEditorRef" />
  </div>
</template>

<style scoped>
.tile-collision-panel {
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  /* 与绘制/属性面板一致，底部信息栏才是更深的一整条 */
  background: var(--bg-base);
}

.col-toolbar {
  display: flex;
  align-items: center;
  height: 40px;
  padding: 0 8px;
  gap: 6px;
  flex-shrink: 0;
}

.col-tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  height: 24px;
  background: rgb(40, 43, 52);
  border: none;
  border-radius: 4px;
  cursor: default;
  padding: 2px;
  transition: background 0.15s;
}

.col-tool-btn:hover {
  background: var(--bg-hover);
}

.col-tool-active {
  background: var(--border-light);
  border: 1px solid rgb(65, 69, 82);
}

.col-tool-icon {
  width: 20px;
  height: 20px;
}
</style>
