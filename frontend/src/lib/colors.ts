import type { ExpressionSpecification } from "maplibre-gl";

// Warm sequential ramp (amber -> orange -> deep red) for departures/hour within 500m.
export function heatmapColorExpression(propName: string): ExpressionSpecification {
  return [
    "interpolate",
    ["linear"],
    ["coalesce", ["get", propName], 0],
    0, "rgba(250,240,220,0)",
    1, "#fde3a7",
    6, "#f6b856",
    15, "#e8792f",
    30, "#c8401f",
    60, "#7a1a12",
  ];
}

// Warm ochre/terracotta bands for the 2/5/10/15-min walking catchments.
export const CATCHMENT_COLORS: Record<number, string> = {
  15: "#e3b978",
  10: "#d98c4a",
  5: "#c1502b",
  2: "#8a3418",
};

// One evenly spaced (perceptually) step per 10-min band, dark terracotta -> orange -> amber.
// Bands beyond 90 min reuse the last color.
export const AIRPORT_BAND_COLOR: ExpressionSpecification = [
  "interpolate",
  ["linear"],
  ["get", "minutes"],
  10, "#6b2110",
  20, "#853016",
  30, "#a0401d",
  40, "#bc5023",
  50, "#d8602a",
  60, "#e07a2c",
  70, "#e7922e",
  80, "#edaa2f",
  90, "#f2c230",
];
