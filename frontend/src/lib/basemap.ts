// Light, warm-toned basemap: fetch OpenFreeMap's free-hosted "Positron" vector
// style (no API key, planet-scale OSM data) and re-tint the dominant layers
// from its default cool-gray palette to warm cream/beige/terracotta tones.
import type { StyleSpecification } from "maplibre-gl";

const BASE_STYLE_URL = "https://tiles.openfreemap.org/styles/positron";

// id -> paint property overrides, applied on top of the fetched style.
const WARM_OVERRIDES: Record<string, Record<string, unknown>> = {
  background: { "background-color": "#faf3e7" },
  park: { "fill-color": "#ece3c8" },
  water: { "fill-color": "#d9e5df" },
  waterway: { "line-color": "#c7d4cc" },
  landcover_wood: { "fill-color": "#e3ddc4" },
  landuse_residential: { "fill-color": "#f0e6d2" },
  building: { "fill-color": "#e9dac0", "fill-outline-color": "#d9c6a3" },
  highway_path: { "line-color": "#ddceb0" },
  highway_minor: { "line-color": "#e4d6ba" },
  highway_major_casing: { "line-color": "#d8c39d" },
  highway_major_inner: { "line-color": "#fdf8ee" },
  highway_major_subtle: { "line-color": "hsla(35,45%,70%,0.65)" },
  highway_motorway_casing: { "line-color": "#c9a876" },
  highway_motorway_inner: { "line-color": "#fdf8ee" },
  highway_motorway_subtle: { "line-color": "hsla(35,55%,60%,0.6)" },
  boundary_2: { "line-color": "#b8a888" },
  boundary_3: { "line-color": "#c2b394" },
  "label_city": { "text-color": "#5c4b3a" },
  "label_city_capital": { "text-color": "#5c4b3a" },
  "label_town": { "text-color": "#5c4b3a" },
  "highway-name-major": { "text-color": "#7a6650" },
};

export async function loadWarmBasemapStyle(): Promise<StyleSpecification> {
  const res = await fetch(BASE_STYLE_URL);
  const style = (await res.json()) as StyleSpecification;

  style.layers = style.layers.map((layer) => {
    const overrides = WARM_OVERRIDES[layer.id];
    if (!overrides || !("paint" in layer)) return layer;
    return { ...layer, paint: { ...layer.paint, ...overrides } };
  });

  return style;
}
