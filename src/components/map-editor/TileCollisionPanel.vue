<script setup lang="ts">
import { ref } from 'vue'
import { useMapEditorStore } from '../../stores/mapEditor'
import CollisionEditor from './CollisionEditor.vue'
import iconMoveAnchor from '../../assets/icons/移动锚点.svg'
import iconAddAnchor from '../../assets/icons/添加锚点.svg'
import iconDelAnchor from '../../assets/icons/删除锚点.svg'
import iconResetAnchor from '../../assets/icons/重置锚点.svg'

/**
 * 图块模式的素材碰撞编辑区：工具条 + 自适应碰撞画布（内部坐标 256×256）。
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
  flex: 1 1 auto;
  min-height: 0;
  /* 与绘制/属性面板一致，底部信息栏才是更深的一整条 */
  background: var(--bg-base);
}

.col-toolbar {
  display: flex;
  align-items: center;
  height: 44px;
  padding: 0 8px;
  gap: 6px;
  flex-shrink: 0;
}

.col-tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  height: 28px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 4px;
  cursor: default;
  padding: 2px;
  transition: background 0.15s, border-color 0.15s;
}

.col-tool-btn:hover {
  background: rgba(255, 255, 255, 0.07);
}

.col-tool-active {
  position: relative;
  background: rgb(46, 49, 58);
  border-color: var(--border-light);
}

/* 选中指示：绿色小条（与绘制图层工具栏一致，画在按钮外侧下沿） */
.col-tool-active::before {
  content: '';
  position: absolute;
  left: 1px;
  right: 1px;
  bottom: -6px;
  height: 2.5px;
  border-radius: 1.25px;
  background: var(--accent);
}

.col-tool-icon {
  width: 20px;
  height: 20px;
}
</style>
