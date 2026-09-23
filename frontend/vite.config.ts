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
    // production builds - copy the currently-installed version manually. The raw worker
    // file itself statically imports a sibling "maplibre-gl-shared.mjs", which must be
    // copied alongside it since it's loaded outside Rollup's module graph.
    {
      name: 'copy-maplibre-worker',
      writeBundle() {
        mkdirSync(`${root}dist/assets`, { recursive: true })
        for (const file of ['maplibre-gl-worker.mjs', 'maplibre-gl-shared.mjs']) {
          copyFileSync(
            `${root}node_modules/maplibre-gl/dist/${file}`,
            `${root}dist/assets/${file}`,
          )
        }
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
