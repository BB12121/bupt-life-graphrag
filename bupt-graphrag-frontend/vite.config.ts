import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const proxy = { '/api': { target: env.BUPT_BACKEND_URL || 'http://127.0.0.1:8000', changeOrigin: true, timeout: 240_000, proxyTimeout: 240_000 } }
  return {
    plugins: [vue()],
    server: { port: 5173, strictPort: true, proxy },
    preview: { port: 4173, strictPort: true, proxy },
    build: { sourcemap: false },
    test: { include: ['tests/**/*.test.ts'] },
  }
})
