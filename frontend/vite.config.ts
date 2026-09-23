import { copyFileSync, mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const root = fileURLToPath(new URL('.', import.meta.url))

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    // maplibre-gl resolves its worker URL at runtime via a dynamic `new URL()` call,
    // which Rollup can't statically detect, so the worker chunk is never emitted in
    // production builds - copy the currently-installed version manually.
    {
      name: 'copy-maplibre-worker',
      writeBundle() {
        mkdirSync(`${root}dist/assets`, { recursive: true })
        copyFileSync(
          `${root}node_modules/maplibre-gl/dist/maplibre-gl-worker.mjs`,
          `${root}dist/assets/maplibre-gl-worker.mjs`,
        )
      },
    },
  ],
  // maplibre-gl loads a sibling worker file (maplibre-gl-worker.mjs) at runtime via a
  // relative URL; Vite's dep pre-bundler only emits the main entry chunk, so the worker
  // 404s and silently dies unless the package is served unbundled from node_modules.
  optimizeDeps: {
    exclude: ['maplibre-gl'],
  },
})
