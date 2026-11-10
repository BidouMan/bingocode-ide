// 角色编辑器冒烟/压力测试挂载页（仅测试用，不进入产品构建）
// 直接挂载 SpriteEditorView，避免启动整个 IDE；所有文件操作走 window.__TAURI_INTERNALS__ 的
// mock（由 run-smoke.mjs 在页面加载前注入，并通过 /__smoke/invoke 路由落到本机真实文件系统）。
import { createApp, nextTick } from 'vue'
import { createPinia } from 'pinia'
import SpriteEditorView from '../../src/components/sprite-editor/SpriteEditorView.vue'
import { useResourceStore } from '../../src/stores/resource'
import { useProjectStore } from '../../src/stores/project'
import { vTooltip } from '../../src/directives/tooltip'
import '../../src/assets/main.css'

declare const window: any

const pinia = createPinia()
const resource = useResourceStore(pinia)
const project = useProjectStore(pinia)

project.root = window.__smoke.project as string
const spriteItems = window.__smoke.sprites as any[]
for (const item of spriteItems) {
  resource.sprites.push(item)
}
resource.selectedSpriteId = spriteItems[0].id

const app = createApp(SpriteEditorView)
app.use(pinia)
app.directive('tooltip', vTooltip)
app.mount('#app')

window.__smoke.app = app
window.__smoke.pinia = pinia
window.__smoke.resource = resource
window.__smoke.project = project
// 重新挂载（卸载泄漏 / 反复挂载测试用）
window.__smoke.mountApp = () => {
  const a = createApp(SpriteEditorView)
  a.use(pinia)
  a.directive('tooltip', vTooltip)
  a.mount('#app')
  window.__smoke.app = a
  nextTick(() => { window.__smoke.mounted = true })
  return a
}

nextTick(() => {
  window.__smoke.mounted = true
})

// 供测试读取组件内部状态的入口（dev 模式下 DOM 节点上挂着 vue 组件实例）
window.__smoke.readState = () => {
  const el = document.querySelector('.sprite-editor-page') as any
  const inst = el && el.__vueParentComponent
  const s = inst && inst.setupState
  if (!s) return null
  const clone = (v: any) => (v === undefined ? null : JSON.parse(JSON.stringify(v)))
  return {
    frameCount: s.currentSprite?.frames?.length ?? 0,
    animCount: s.currentSprite?.animations?.length ?? 0,
    defaultFrameIndex: s.currentSprite?.defaultFrameIndex ?? 0,
    selectedFrame: s.selectedFrameIndex,
    previewFrame: s.canvasDisplayIndex,
    costumeHighlight: s.costumeHighlightIndex,
    playing: s.isPlaying,
    activeTool: s.activeTool,
    rightTab: s.rightTab,
    zoom: s.canvasZoom,
    pan: [s.canvasPanX, s.canvasPanY],
    transform: clone(s.sceneTransform),
    pivot: clone(s.annoPivot),
    pivotOffset: clone(s.annoPivotOffset),
    pivotScope: s.annoScope,
    collision: clone(s.currentSprite?.bsf?.collision),
    collisionKind: s.currentSprite?.bsf?.collisionKind ?? null,
    collisionTag: s.currentSprite?.bsf?.collisionTag ?? null,
    collisionDisabled: !!s.currentSprite?.bsf?.collisionDisabled,
    markers: clone(s.currentSprite?.bsf?.markers),
    rotationMode: s.currentSprite?.bsf?.rotationMode ?? 'all',
    hidden: !!s.currentSprite?.bsf?.hidden,
    gravity: s.currentSprite?.bsf?.gravity,
    ySort: !!s.currentSprite?.bsf?.ySort,
    layer: s.currentSprite?.bsf?.layer,
    bsfFrameCount: s.currentSprite?.bsf?.frames?.length ?? 0,
    loadError: s.loadError,
    path: s.currentSpritePath,
    name: s.currentSprite?.name,
    fps: s.fpsValue,
    anims: clone(s.currentSprite?.animations ?? []),
    selectedAnimName: s.selectedAnim?.name ?? null,
    previewScale: s.previewScale,
    previewBg: s.previewBgIndex,
    spaceHeld: !!s.spaceHeld,
    pixelArt: s.spritePixelArt,
    imageRendering: s.imageRenderingStyle,
    canvasNatural: clone(s.canvasFrameNatural),
    spriteSize: clone(s.spriteSize),
    bsfCanvas: clone(s.currentSprite?.bsf?.canvas),
    canUndo: !!s.canUndo,
    canRedo: !!s.canRedo,
    canAnno: !!s.canAnno,
    gizmoVisible: !!s.gizmoVisible,
    selectionActive: !!s.selectionActive,
  }
}
