export type LayerMode = "heatmap" | "catchments";
export type DayType = "weekday" | "saturday" | "sunday";
export const CATCHMENT_MINUTES = [2, 5, 10, 15] as const;
export type CatchmentMinutes = (typeof CATCHMENT_MINUTES)[number];
