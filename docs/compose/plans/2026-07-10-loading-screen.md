# Loading页面实现计划

> [!NOTE]
> This document may not reflect the current implementation.
> See the final report for up-to-date state:
> [Final Report](../reports/loading-screen.md)

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建一个粒子背景 + Logo动画 + 渐变发光进度条的Loading页面，提升IDE启动体验

**Architecture:** 创建独立的LoadingScreen.vue组件，使用Canvas实现粒子效果，集成到App.vue中，在启动时显示

**Tech Stack:** Vue 3, Canvas API, CSS动画

## Global Constraints

- 项目使用Vue 3 + TypeScript
- 遵循项目现有的组件结构和命名规范
- 使用项目主题色：#5BFB84（accent green）
- 保持性能优化，粒子数量控制在50-100个

---

### Task 1: 创建LoadingScreen.vue组件基础结构

**Covers:** [S3, S4]

**Files:**
- Create: `src/components/loading/LoadingScreen.vue`

**Interfaces:**
- Consumes: 无
- Produces: LoadingScreen组件，接受progress属性

- [ ] **Step 1: 创建组件文件**

```vue
<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'

interface Props {
  progress: number
  show: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  complete: []
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const containerRef = ref<HTMLDivElement | null>(null)
let animationId: number | null = null

// 粒子系统
interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  radius: number
  opacity: number
}

const particles: Particle[] = []
const PARTICLE_COUNT = 80

function initParticles(width: number, height: number) {
  particles.length = 0
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    particles.push({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.5,
      vy: (Math.random() - 0.5) * 0.5,
      radius: Math.random() * 2 + 1,
      opacity: Math.random() * 0.5 + 0.2,
    })
  }
}

function animateParticles(ctx: CanvasRenderingContext2D, width: number, height: number) {
  ctx.clearRect(0, 0, width, height)
  
  for (const p of particles) {
    p.x += p.vx
    p.y += p.vy
    
    // 边界反弹
    if (p.x < 0 || p.x > width) p.vx *= -1
    if (p.y < 0 || p.y > height) p.vy *= -1
    
    // 绘制粒子
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(255, 255, 255, ${p.opacity})`
    ctx.fill()
  }
  
  animationId = requestAnimationFrame(() => animateParticles(ctx, width, height))
}

onMounted(() => {
  if (canvasRef.value) {
    const canvas = canvasRef.value
    const ctx = canvas.getContext('2d')
    if (ctx) {
      const resize = () => {
        canvas.width = window.innerWidth
        canvas.height = window.innerHeight
        initParticles(canvas.width, canvas.height)
      }
      resize()
      window.addEventListener('resize', resize)
      animateParticles(ctx, canvas.width, canvas.height)
    }
  }
})

onUnmounted(() => {
  if (animationId) {
    cancelAnimationFrame(animationId)
  }
})

watch(() => props.progress, (val) => {
  if (val >= 100) {
    setTimeout(() => {
      emit('complete')
    }, 500)
  }
})
</script>

<template>
  <div v-show="show" ref="containerRef" class="loading-screen">
    <canvas ref="canvasRef" class="loading-canvas"></canvas>
    <div class="loading-content">
      <div class="loading-logo">
        <span class="logo-text">Bingo</span>
        <span class="logo-highlight">Code</span>
      </div>
      <div class="loading-subtitle">IDE</div>
      <div class="loading-progress-container">
        <div class="loading-progress-bar">
          <div class="loading-progress-fill" :style="{ width: progress + '%' }"></div>
        </div>
        <div class="loading-progress-text">{{ progress }}%</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.loading-screen {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  transition: opacity 0.5s ease;
}

.loading-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.loading-content {
  position: relative;
  z-index: 1;
  text-align: center;
}

.loading-logo {
  font-size: 48px;
  font-weight: 700;
  letter-spacing: 2px;
  animation: breathe 3s ease-in-out infinite;
}

.logo-text {
  color: #ffffff;
}

.logo-highlight {
  color: #5BFB84;
}

.loading-subtitle {
  font-size: 18px;
  color: rgba(255, 255, 255, 0.6);
  margin-top: 8px;
  letter-spacing: 8px;
}

.loading-progress-container {
  margin-top: 48px;
  width: 300px;
}

.loading-progress-bar {
  width: 100%;
  height: 4px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
  overflow: hidden;
}

.loading-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #5BFB84, #4B9B5C);
  border-radius: 2px;
  transition: width 0.3s ease;
  box-shadow: 0 0 12px rgba(91, 251, 132, 0.5);
}

.loading-progress-text {
  margin-top: 12px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
  font-family: 'JetBrains Mono', monospace;
}

@keyframes breathe {
  0%, 100% {
    opacity: 0.8;
    transform: scale(1);
  }
  50% {
    opacity: 1;
    transform: scale(1.02);
  }
}
</style>
```

- [ ] **Step 2: 验证组件结构**

运行开发服务器确认组件无语法错误：
```bash
pnpm dev
```

- [ ] **Step 3: 提交**

```bash
git add src/components/loading/LoadingScreen.vue
git commit -m "feat: create LoadingScreen component with particle animation"
```

---

### Task 2: 集成LoadingScreen到App.vue

**Covers:** [S5, S7]

**Files:**
- Modify: `src/App.vue`

**Interfaces:**
- Consumes: LoadingScreen组件
- Produces: 启动时显示Loading页面

- [ ] **Step 1: 修改App.vue**

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import MainLayout from './components/layout/MainLayout.vue'
import LoadingScreen from './components/loading/LoadingScreen.vue'

const loadingProgress = ref(0)
const showLoading = ref(true)
const showMain = ref(false)

onMounted(() => {
  // 模拟加载过程
  const interval = setInterval(() => {
    if (loadingProgress.value < 100) {
      loadingProgress.value += Math.random() * 15 + 5
      if (loadingProgress.value > 100) {
        loadingProgress.value = 100
      }
    }
  }, 200)
})

function onLoadingComplete() {
  showLoading.value = false
  showMain.value = true
}
</script>

<template>
  <LoadingScreen 
    :progress="loadingProgress" 
    :show="showLoading"
    @complete="onLoadingComplete"
  />
  <MainLayout v-if="showMain" />
</template>
```

- [ ] **Step 2: 测试Loading效果**

运行开发服务器查看效果：
```bash
pnpm dev
```

- [ ] **Step 3: 提交**

```bash
git add src/App.vue
git commit -m "feat: integrate LoadingScreen into App with simulated loading"
```

---

### Task 3: 添加热重载支持

**Covers:** [S5]

**Files:**
- Modify: `src/App.vue`

**Interfaces:**
- Consumes: 无
- Produces: 支持手动触发Loading效果

- [ ] **Step 1: 添加热重载触发功能**

在App.vue中添加开发模式下的热重载支持：

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import MainLayout from './components/layout/MainLayout.vue'
import LoadingScreen from './components/loading/LoadingScreen.vue'

const loadingProgress = ref(0)
const showLoading = ref(true)
const showMain = ref(false)

onMounted(() => {
  // 模拟加载过程
  const interval = setInterval(() => {
    if (loadingProgress.value < 100) {
      loadingProgress.value += Math.random() * 15 + 5
      if (loadingProgress.value > 100) {
        loadingProgress.value = 100
      }
    }
  }, 200)
})

function onLoadingComplete() {
  showLoading.value = false
  showMain.value = true
}

// 开发模式：手动触发Loading效果
if (import.meta.env.DEV) {
  // 暴露到window以便控制台调用
  (window as any).triggerLoading = () => {
    showLoading.value = true
    showMain.value = false
    loadingProgress.value = 0
    
    const interval = setInterval(() => {
      if (loadingProgress.value < 100) {
        loadingProgress.value += Math.random() * 15 + 5
        if (loadingProgress.value > 100) {
          loadingProgress.value = 100
        }
      } else {
        clearInterval(interval)
      }
    }, 200)
  }
}
</script>

<template>
  <LoadingScreen 
    :progress="loadingProgress" 
    :show="showLoading"
    @complete="onLoadingComplete"
  />
  <MainLayout v-if="showMain" />
</template>
```

- [ ] **Step 2: 测试热重载功能**

1. 运行开发服务器：`pnpm dev`
2. 打开浏览器控制台
3. 输入 `triggerLoading()` 触发Loading效果

- [ ] **Step 3: 提交**

```bash
git add src/App.vue
git commit -m "feat: add hot reload support for LoadingScreen in dev mode"
```

---

### Task 4: 优化性能和视觉效果

**Covers:** [S6]

**Files:**
- Modify: `src/components/loading/LoadingScreen.vue`

**Interfaces:**
- Consumes: 无
- Produces: 优化后的Loading效果

- [ ] **Step 1: 优化粒子动画**

添加性能优化和视觉增强：

```vue
<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'

interface Props {
  progress: number
  show: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  complete: []
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const containerRef = ref<HTMLDivElement | null>(null)
let animationId: number | null = null

// 粒子系统
interface Particle {
  x: number
  y: number
  vx: number
  vy: number
  radius: number
  opacity: number
}

const particles: Particle[] = []
const PARTICLE_COUNT = 60  // 减少粒子数量以提升性能

function initParticles(width: number, height: number) {
  particles.length = 0
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    particles.push({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.3,  // 降低速度
      vy: (Math.random() - 0.5) * 0.3,
      radius: Math.random() * 1.5 + 0.5,
      opacity: Math.random() * 0.4 + 0.1,
    })
  }
}

function animateParticles(ctx: CanvasRenderingContext2D, width: number, height: number) {
  ctx.clearRect(0, 0, width, height)
  
  for (const p of particles) {
    p.x += p.vx
    p.y += p.vy
    
    // 边界反弹
    if (p.x < 0 || p.x > width) p.vx *= -1
    if (p.y < 0 || p.y > height) p.vy *= -1
    
    // 绘制粒子
    ctx.beginPath()
    ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2)
    ctx.fillStyle = `rgba(255, 255, 255, ${p.opacity})`
    ctx.fill()
  }
  
  animationId = requestAnimationFrame(() => animateParticles(ctx, width, height))
}

onMounted(() => {
  if (canvasRef.value) {
    const canvas = canvasRef.value
    const ctx = canvas.getContext('2d')
    if (ctx) {
      const resize = () => {
        canvas.width = window.innerWidth
        canvas.height = window.innerHeight
        initParticles(canvas.width, canvas.height)
      }
      resize()
      window.addEventListener('resize', resize)
      animateParticles(ctx, canvas.width, canvas.height)
    }
  }
})

onUnmounted(() => {
  if (animationId) {
    cancelAnimationFrame(animationId)
  }
})

watch(() => props.progress, (val) => {
  if (val >= 100) {
    setTimeout(() => {
      emit('complete')
    }, 500)
  }
})
</script>

<template>
  <div v-show="show" ref="containerRef" class="loading-screen">
    <canvas ref="canvasRef" class="loading-canvas"></canvas>
    <div class="loading-content">
      <div class="loading-logo">
        <span class="logo-text">Bingo</span>
        <span class="logo-highlight">Code</span>
      </div>
      <div class="loading-subtitle">IDE</div>
      <div class="loading-progress-container">
        <div class="loading-progress-bar">
          <div class="loading-progress-fill" :style="{ width: progress + '%' }"></div>
        </div>
        <div class="loading-progress-text">{{ Math.floor(progress) }}%</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.loading-screen {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10000;
  transition: opacity 0.5s ease;
}

.loading-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
}

.loading-content {
  position: relative;
  z-index: 1;
  text-align: center;
}

.loading-logo {
  font-size: 48px;
  font-weight: 700;
  letter-spacing: 2px;
  animation: breathe 3s ease-in-out infinite;
}

.logo-text {
  color: #ffffff;
}

.logo-highlight {
  color: #5BFB84;
}

.loading-subtitle {
  font-size: 18px;
  color: rgba(255, 255, 255, 0.6);
  margin-top: 8px;
  letter-spacing: 8px;
}

.loading-progress-container {
  margin-top: 48px;
  width: 300px;
}

.loading-progress-bar {
  width: 100%;
  height: 4px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
  overflow: hidden;
}

.loading-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #5BFB84, #4B9B5C);
  border-radius: 2px;
  transition: width 0.3s ease;
  box-shadow: 0 0 12px rgba(91, 251, 132, 0.5);
}

.loading-progress-text {
  margin-top: 12px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.5);
  font-family: 'JetBrains Mono', monospace;
}

@keyframes breathe {
  0%, 100% {
    opacity: 0.8;
    transform: scale(1);
  }
  50% {
    opacity: 1;
    transform: scale(1.02);
  }
}
</style>
```

- [ ] **Step 2: 测试优化效果**

运行开发服务器确认性能良好：
```bash
pnpm dev
```

- [ ] **Step 3: 提交**

```bash
git add src/components/loading/LoadingScreen.vue
git commit -m "perf: optimize particle animation performance"
```

---

### Task 5: 集成到Tauri启动流程

**Covers:** [S7, S8]

**Files:**
- Modify: `src/App.vue`
- Modify: `src-tauri/tauri.conf.json` (可选)

**Interfaces:**
- Consumes: LoadingScreen组件
- Produces: 真实的启动加载流程

- [ ] **Step 1: 修改App.vue集成真实加载**

```vue
<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import MainLayout from './components/layout/MainLayout.vue'
import LoadingScreen from './components/loading/LoadingScreen.vue'

const loadingProgress = ref(0)
const showLoading = ref(true)
const showMain = ref(false)

onMounted(async () => {
  try {
    // 模拟真实加载过程
    // 1. 初始化项目
    loadingProgress.value = 10
    await invoke('init_default_project')
    
    // 2. 加载主题
    loadingProgress.value = 30
    await new Promise(resolve => setTimeout(resolve, 300))
    
    // 3. 加载资源
    loadingProgress.value = 60
    await new Promise(resolve => setTimeout(resolve, 400))
    
    // 4. 准备编辑器
    loadingProgress.value = 90
    await new Promise(resolve => setTimeout(resolve, 200))
    
    // 5. 完成
    loadingProgress.value = 100
  } catch (e) {
    console.error('Loading failed:', e)
    loadingProgress.value = 100
  }
})

function onLoadingComplete() {
  showLoading.value = false
  showMain.value = true
}

// 开发模式：手动触发Loading效果
if (import.meta.env.DEV) {
  (window as any).triggerLoading = () => {
    showLoading.value = true
    showMain.value = false
    loadingProgress.value = 0
    
    const interval = setInterval(() => {
      if (loadingProgress.value < 100) {
        loadingProgress.value += Math.random() * 15 + 5
        if (loadingProgress.value > 100) {
          loadingProgress.value = 100
        }
      } else {
        clearInterval(interval)
      }
    }, 200)
  }
}
</script>

<template>
  <LoadingScreen 
    :progress="loadingProgress" 
    :show="showLoading"
    @complete="onLoadingComplete"
  />
  <MainLayout v-if="showMain" />
</template>
```

- [ ] **Step 2: 测试完整启动流程**

运行Tauri开发模式：
```bash
pnpm tauri dev
```

- [ ] **Step 3: 提交**

```bash
git add src/App.vue
git commit -m "feat: integrate LoadingScreen with Tauri startup flow"
```

---

### Task 6: 最终验证和清理

**Covers:** [S8]

**Files:**
- 无新增文件

**Interfaces:**
- 无

- [ ] **Step 1: 运行完整测试**

```bash
# 启动开发服务器
pnpm dev

# 启动Tauri桌面应用
pnpm tauri dev
```

验证：
1. Loading页面正确显示
2. 粒子动画流畅运行
3. Logo呼吸动画正常
4. 进度条正确更新
5. 加载完成后平滑过渡
6. 热重载功能正常（开发模式下输入`triggerLoading()`）

- [ ] **Step 2: 代码审查**

检查所有修改的文件，确保：
- 无语法错误
- 性能优化到位
- 代码风格一致

- [ ] **Step 3: 最终提交**

```bash
git add .
git commit -m "feat: complete LoadingScreen implementation with particles and progress bar"
```

---

## 验收标准检查

- [ ] Loading页面在启动时正确显示
- [ ] 粒子效果流畅运行（50-100个粒子）
- [ ] Logo呼吸动画正常工作（3秒循环）
- [ ] 进度条正确显示加载进度
- [ ] 加载完成后平滑过渡到主界面（0.5秒淡出）
- [ ] 热重载功能正常工作（开发模式下可手动触发）
- [ ] 性能良好，无卡顿
- [ ] 颜色方案符合设计：背景#1a1a2e→#16213e，进度条#5BFB84→#4B9B5C