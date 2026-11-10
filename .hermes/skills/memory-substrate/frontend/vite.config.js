import { defineConfig } from 'vite'

export default defineConfig({
  root: '.',
  publicDir: 'public',
  server: {
    port: 8080,
    host: '127.0.0.1',
    proxy: {
      '/ws': {
        target: 'ws://127.0.0.1:8081',
        ws: true
      },
      '/api': {
        target: 'http://127.0.0.1:3120',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    minify: 'esbuild',
    sourcemap: true
  }
})