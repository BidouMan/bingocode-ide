import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './assets/main.css'
import './assets/theme-variables.css'

// 在挂载Vue前设置webview背景色，防止白屏闪烁
import { getCurrentWebviewWindow } from '@tauri-apps/api/webviewWindow'
getCurrentWebviewWindow().setBackground?.('#1a1a2e')

const app = createApp(App)
app.use(createPinia())
app.mount('#app')
