import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './assets/main.css'
import './assets/theme-variables.css'
import { vTooltip } from './directives/tooltip'

const app = createApp(App)
app.use(createPinia())
app.directive('tooltip', vTooltip)
app.mount('#app')
