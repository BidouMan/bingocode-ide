import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  // Vite 8: publicDir 必须是相对于项目根目录的路径
  publicDir: 'engine/assets',
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
    watch: {
      // 忽略 Rust 构建产物目录，避免 cargo 编译时 .exe 被锁定导致 Vite 监视崩溃（EBUSY）
      ignored: [
        '**/src-tauri/target/**',
        // publicDir 指向 engine/assets，dev 模式下素材整理工具会写 index.json、改名/移动文件，
        // Vite 默认把这些变更当成静态资源更新并整页刷新，导致编辑素材时页面反复重启。
        // 忽略 maps / sprites / sounds 目录即可保持编辑连续；文件仍由静态服务按需读取，不受影响。
        '**/engine/assets/maps/**',
        '**/engine/assets/sprites/**',
        '**/engine/assets/sounds/**',
      ],
    },
  },
  envPrefix: ['VITE_', 'TAURI_'],
  build: {
    target: 'es2020',
    minify: !process.env.TAURI_DEBUG ? 'esbuild' : false,
    sourcemap: !!process.env.TAURI_DEBUG,
  },
})
