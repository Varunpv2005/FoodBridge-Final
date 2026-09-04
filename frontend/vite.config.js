import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { loadEnv } from 'vite'
import path from 'node:path'

export default defineConfig(({ mode }) => {
  const frontendEnv = loadEnv(mode, process.cwd(), '')
  const backendEnv = loadEnv(mode, path.resolve(process.cwd(), '../backend'), '')
  return {
    plugins: [react()],
    define: {
      'import.meta.env.VITE_GOOGLE_MAPS_API_KEY': JSON.stringify(frontendEnv.VITE_GOOGLE_MAPS_API_KEY || backendEnv.GOOGLE_MAPS_API_KEY || ''),
    },
    server: {
      host: true,
      port: 5173,
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
        '/ws': {
          target: 'ws://127.0.0.1:8000',
          ws: true,
          changeOrigin: true,
        },
      },
    },
  }
})
