import {
  Map as MapLibreMap,
  Marker,
  NavigationControl,
  addProtocol,
  removeProtocol,
  type FilterSpecification,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { Protocol } from "pmtiles";
import { useEffect, useRef } from "react";
import { loadWarmBasemapStyle } from "../lib/basemap";
import {
  AIRPORT_BAND_COLOR,
  CATCHMENT_COLORS,
  heatmapColorExpression,
} from "../lib/colors";
import {
  CATCHMENT_MINUTES,
  type AirportView,
  type CatchmentMinutes,
  type DayType,
  type LayerMode,
} from "../types";

const LINKOPING_CENTER: [number, number] = [15.6214, 58.4108];

const HEATMAP_TILES_URL = `pmtiles://${window.location.origin}/tiles/heatmap.pmtiles`;
const CATCHMENTS_TILES_URL = `pmtiles://${window.location.origin}/tiles/catchments.pmtiles`;
const AIRPORT_TILES_URL = `pmtiles://${window.location.origin}/tiles/airport.pmtiles`;

// Static Material "flight" glyph, no user-supplied content.
const PLANE_SVG =
  '<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/></svg>';

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
  airport: AirportView | null;
}

export function MapView({ mode, dayType, hour, visibleBands, airport }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markerRef = useRef<Marker | null>(null);
  const loadedRef = useRef(false);
  // The map's load callback outlives the first render, and the airport data may arrive after it.
  const latestRef = useRef({ mode, dayType, hour, visibleBands, airport });
  latestRef.current = { mode, dayType, hour, visibleBands, airport };

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
        map.addSource("airport", { type: "vector", url: AIRPORT_TILES_URL });

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

        // Bands are exclusive rings, so draw order does not affect their opacity.
        map.addLayer(
          {
            id: "airport-bands",
            type: "fill",
            source: "airport",
            "source-layer": "airport",
            paint: { "fill-color": AIRPORT_BAND_COLOR, "fill-opacity": 0.45 },
          },
          firstSymbolId,
        );

        // Re-draw roads, paths, and rail above the fill, but still below labels.
        for (const overlayLayerId of OVERLAY_LAYER_IDS) {
          const original = warmStyle.layers.find((l) => l.id === overlayLayerId);
          if (!original) continue;
          map.addLayer({ ...original, id: `${overlayLayerId}-overlay` }, firstSymbolId);
        }

        loadedRef.current = true;
        applyLayerState(map, markerRef, latestRef.current);
      });
    });

    return () => {
      cancelled = true;
      markerRef.current?.remove();
      markerRef.current = null;
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
    applyLayerState(map, markerRef, latestRef.current);
  }, [mode, dayType, hour, visibleBands, airport?.flightId, airport?.maxBand, airport?.lat, airport?.lon]);

  return (
    <div className="absolute inset-0">
      <div ref={containerRef} className="h-full w-full" />
    </div>
  );
}

function airportFilter(airport: AirportView, dayType: DayType): FilterSpecification {
  return [
    "all",
    ["==", ["get", "flight_id"], airport.flightId],
    ["==", ["get", "day_type"], dayType],
    ["<=", ["get", "minutes"], airport.maxBand],
  ];
}

function createAirportMarker(airport: AirportView): Marker {
  const el = document.createElement("div");
  el.className =
    "flex h-8 w-8 items-center justify-center rounded-full bg-stone-900 text-white shadow-lg ring-2 ring-white";
  el.innerHTML = PLANE_SVG;
  return new Marker({ element: el }).setLngLat([airport.lon, airport.lat]);
}

interface LayerState {
  mode: LayerMode;
  dayType: DayType;
  hour: number;
  visibleBands: Set<CatchmentMinutes>;
  airport: AirportView | null;
}

function applyLayerState(
  map: MapLibreMap,
  markerRef: { current: Marker | null },
  { mode, dayType, hour, visibleBands, airport }: LayerState,
) {
  map.setLayoutProperty("heatmap-fill", "visibility", mode === "heatmap" ? "visible" : "none");
  map.setPaintProperty("heatmap-fill", "fill-color", heatmapColorExpression(`${dayType}_h${hour}`));

  for (const minutes of CATCHMENT_MINUTES) {
    const visible = mode === "catchments" && visibleBands.has(minutes);
    map.setLayoutProperty(`catchment-${minutes}`, "visibility", visible ? "visible" : "none");
  }

  const airportVisible = mode === "airport" && airport !== null;
  map.setLayoutProperty("airport-bands", "visibility", airportVisible ? "visible" : "none");
  if (airport) {
    map.setFilter("airport-bands", airportFilter(airport, dayType));

    if (!markerRef.current) markerRef.current = createAirportMarker(airport).addTo(map);
    markerRef.current.getElement().style.display = mode === "airport" ? "" : "none";
  }
}
