import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// base './' 让构建产物可以部署到任意子路径
export default defineConfig({
  plugins: [vue()],
  base: './',
  server: { port: 5173 },
})
