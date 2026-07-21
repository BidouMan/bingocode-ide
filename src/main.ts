import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './assets/main.css'
import './assets/theme-variables.css'
import { vTooltip } from './directives/tooltip'
import { preloadMonaco } from './utils/monaco-init'

const appBootT0 = performance.now()
console.log(`[Perf] main.ts start at ${appBootT0.toFixed(0)}`)

// 在 Vue 挂载之前就开始预加载 Monaco，让 Monaco 加载与 Vue 组件树挂载并行
// （CodeEditor 挂载时会 await waitForMonaco，提前启动可节省数秒）
preloadMonaco()

const app = createApp(App)
app.use(createPinia())
app.directive('tooltip', vTooltip)
app.mount('#app')
console.log(`[Perf] app.mount: ${(performance.now() - appBootT0).toFixed(1)}ms`)
