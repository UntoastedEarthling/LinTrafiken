import { Map as MapLibreMap, NavigationControl, addProtocol, removeProtocol } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Protocol } from "pmtiles";
import { useEffect, useRef } from "react";
import { loadWarmBasemapStyle } from "../lib/basemap";
import { CATCHMENT_COLORS, heatmapColorExpression } from "../lib/colors";
import { CATCHMENT_MINUTES, type CatchmentMinutes, type DayType, type LayerMode } from "../types";

const LINKOPING_CENTER: [number, number] = [15.6214, 58.4108];

const HEATMAP_TILES_URL = `pmtiles://${window.location.origin}/tiles/heatmap.pmtiles`;
const CATCHMENTS_TILES_URL = `pmtiles://${window.location.origin}/tiles/catchments.pmtiles`;

// Basemap layers to duplicate above the data fill so roads, paths, and rail stay visible.
const OVERLAY_LAYER_IDS = [
  "tunnel_motorway_casing",
  "tunnel_motorway_inner",
  "road_area_pier",
  "road_pier",
  "highway_path",
  "highway_minor",
  "highway_major_casing",
  "highway_major_inner",
  "highway_major_subtle",
  "highway_motorway_casing",
  "highway_motorway_inner",
  "highway_motorway_subtle",
  "railway_transit",
  "railway_transit_dashline",
  "railway_service",
  "railway_service_dashline",
  "railway",
  "railway_dashline",
  "highway_motorway_bridge_casing",
  "highway_motorway_bridge_inner",
];

interface MapViewProps {
  mode: LayerMode;
  dayType: DayType;
  hour: number;
  visibleBands: Set<CatchmentMinutes>;
}

export function MapView({ mode, dayType, hour, visibleBands }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const loadedRef = useRef(false);

  useEffect(() => {
    if (!containerRef.current) return;

    const protocol = new Protocol();
    addProtocol("pmtiles", protocol.tile);

    let cancelled = false;

    loadWarmBasemapStyle().then((warmStyle) => {
      if (cancelled || !containerRef.current) return;

      const map = new MapLibreMap({
        container: containerRef.current,
        center: LINKOPING_CENTER,
        zoom: 11.5,
        style: warmStyle,
      });
      mapRef.current = map;
      map.addControl(new NavigationControl({ showCompass: false }), "bottom-right");

      map.on("load", () => {
        map.addSource("heatmap", { type: "vector", url: HEATMAP_TILES_URL });
        map.addSource("catchments", { type: "vector", url: CATCHMENTS_TILES_URL });

        // Insert below labels so street and place names stay legible on top of catchments.
        const firstSymbolId = warmStyle.layers.find((l) => l.type === "symbol")?.id;

        // No beforeId: drawn on top of everything, matching the original heatmap look.
        map.addLayer({
          id: "heatmap-fill",
          type: "fill",
          source: "heatmap",
          "source-layer": "heatmap",
          paint: {
            "fill-color": heatmapColorExpression(`${dayType}_h${hour}`),
            "fill-opacity": 0.75,
          },
        });

        // Rings are non-overlapping (see isochrone.py), so draw order no longer affects opacity.
        for (const minutes of [...CATCHMENT_MINUTES].reverse()) {
          map.addLayer(
            {
              id: `catchment-${minutes}`,
              type: "fill",
              source: "catchments",
              "source-layer": "catchments",
              filter: ["==", ["get", "minutes"], minutes],
              paint: {
                "fill-color": CATCHMENT_COLORS[minutes],
                "fill-opacity": 0.45,
              },
            },
            firstSymbolId,
          );
        }

        // Re-draw roads, paths, and rail above the fill, but still below labels.
        for (const overlayLayerId of OVERLAY_LAYER_IDS) {
          const original = warmStyle.layers.find((l) => l.id === overlayLayerId);
          if (!original) continue;
          map.addLayer({ ...original, id: `${overlayLayerId}-overlay` }, firstSymbolId);
        }

        loadedRef.current = true;
        applyLayerState(map, mode, dayType, hour, visibleBands);
      });
    });

    return () => {
      cancelled = true;
      mapRef.current?.remove();
      mapRef.current = null;
      loadedRef.current = false;
      removeProtocol("pmtiles");
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;
    applyLayerState(map, mode, dayType, hour, visibleBands);
  }, [mode, dayType, hour, visibleBands]);

  return (
    <div className="absolute inset-0">
      <div ref={containerRef} className="h-full w-full" />
    </div>
  );
}

function applyLayerState(
  map: MapLibreMap,
  mode: LayerMode,
  dayType: DayType,
  hour: number,
  visibleBands: Set<CatchmentMinutes>,
) {
  map.setLayoutProperty("heatmap-fill", "visibility", mode === "heatmap" ? "visible" : "none");
  map.setPaintProperty("heatmap-fill", "fill-color", heatmapColorExpression(`${dayType}_h${hour}`));

  for (const minutes of CATCHMENT_MINUTES) {
    const visible = mode === "catchments" && visibleBands.has(minutes);
    map.setLayoutProperty(`catchment-${minutes}`, "visibility", visible ? "visible" : "none");
  }
}
