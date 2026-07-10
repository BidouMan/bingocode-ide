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
const PARTICLE_COUNT = 60

function initParticles(width: number, height: number) {
  particles.length = 0
  for (let i = 0; i < PARTICLE_COUNT; i++) {
    particles.push({
      x: Math.random() * width,
      y: Math.random() * height,
      vx: (Math.random() - 0.5) * 0.3,
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
      <div class="loading-logo">BINGOCODE IDE</div>
      <div class="loading-dots">
        <div class="dot dot-1"></div>
        <div class="dot dot-2"></div>
        <div class="dot dot-3"></div>
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
  font-size: 36px;
  font-weight: 700;
  letter-spacing: 4px;
  color: #ffffff;
  animation: breathe 3s ease-in-out infinite;
}

.loading-dots {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-top: 32px;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: #5BFB84;
  animation: bounce 1.4s ease-in-out infinite;
}

.dot-1 {
  animation-delay: -0.32s;
}

.dot-2 {
  animation-delay: -0.16s;
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

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}
</style>