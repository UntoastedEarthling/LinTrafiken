// Copies freshly-generated PMTiles from the pipeline's output dir into
// public/tiles/ for local dev (Phase 5's CI build does the equivalent before
// `vite build`, uploading straight to S3 instead of public/).
import { copyFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const srcDir = join(here, "..", "..", "pipeline", "data", "processed");
const destDir = join(here, "..", "public", "tiles");

mkdirSync(destDir, { recursive: true });
for (const name of ["heatmap.pmtiles", "catchments.pmtiles", "airport.pmtiles", "airport-meta.json"]) {
  copyFileSync(join(srcDir, name), join(destDir, name));
  console.log(`Copied ${name}`);
}
