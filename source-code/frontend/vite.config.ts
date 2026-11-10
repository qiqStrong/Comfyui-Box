import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  root: __dirname,
  // 静态资源统一放在 ../resource/img，构建时原样复制到 dist 根，
  // 因此前端引用写作 /logo/... 、/icons/... 、/qr/... 、/avatars/...
  publicDir: path.resolve(__dirname, '../resource/img'),
  plugins: [
    react(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  base: './',
  build: {
    outDir: '../dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, 'index.html'),
        floating: path.resolve(__dirname, 'floating.html'),
      },
    },
  },
  server: {
    proxy: {
      '/comfyui': {
        target: 'http://127.0.0.1:8188',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/comfyui/, ''),
      },
      '/comfyui/ws': {
        target: 'ws://127.0.0.1:8188',
        ws: true,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/comfyui\/ws/, '/ws'),
      },
    },
  },
})
