import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const isProduction = mode === 'production'
  
  return {
    plugins: [react()],
    base: isProduction ? './' : '/', // Use relative paths in production
    optimizeDeps: {
      include: ['@tauri-apps/api']
    },
    build: {
      sourcemap: false,
      assetsInlineLimit: 4096,
      chunkSizeWarningLimit: 1600,
      rollupOptions: {
        external: [],
        // NOTE: do NOT hand-split React and antd into separate vendor chunks.
        // antd's top-level code calls React.createContext at module-eval time;
        // when React and antd are in different chunks, the chunk load order is
        // not guaranteed and antd can evaluate before React's CJS-interop is
        // initialized, leaving `React` undefined → "Cannot read properties of
        // undefined (reading 'createContext')" → blank/black screen. Letting
        // Rollup decide chunking keeps React's evaluation ordered correctly.
      },
      // Production environment disabled Service Worker
      serviceWorker: false
    },
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      port: parseInt(process.env.FRONTEND_PORT || '3001'),
      strictPort: false,
      hmr: {
        overlay: false // Disable error overriding layer
      },
      proxy: {
        '/api': {
          target: `http://localhost:${process.env.BACKEND_PORT || '8001'}`,
          changeOrigin: true
        }
      }
    }
  }
})