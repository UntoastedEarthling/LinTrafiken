import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // maplibre-gl loads a sibling worker file (maplibre-gl-worker.mjs) at runtime via a
  // relative URL; Vite's dep pre-bundler only emits the main entry chunk, so the worker
  // 404s and silently dies unless the package is served unbundled from node_modules.
  optimizeDeps: {
    exclude: ['maplibre-gl'],
  },
})
