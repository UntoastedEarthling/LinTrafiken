export type LayerMode = "heatmap" | "catchments" | "airport";
export type DayType = "weekday" | "saturday" | "sunday";
export const CATCHMENT_MINUTES = [2, 5, 10, 15] as const;
export type CatchmentMinutes = (typeof CATCHMENT_MINUTES)[number];

export interface AirportFlight {
  id: string;
  direction: "departure" | "arrival";
  time: string;
}

export interface AirportRules {
  walkOnlyMaxMinutes: number;
  homeAccessMaxMinutes: number;
  airportAccessMaxMinutes: number;
  transferWalkMaxMinutes: number;
  minTransferMinutes: number;
  arriveBeforeDepartureMinutes: number;
  leaveAfterLandingMinutes: number;
  bandStepMinutes: number;
  maxBandMinutes: number;
}

// Mirrors pipeline/src/lintrafiken_pipeline/airport.py's airport-meta.json.
export interface AirportMeta {
  airport: { iata: string; name: string; lat: number; lon: number };
  bandStepMinutes: number;
  rules: AirportRules;
  serviceDates: Record<DayType, string>; // YYYYMMDD
  flights: AirportFlight[];
  defaultFlightId: string;
  bands: Record<string, Record<DayType, number[]>>;
}

export interface AirportView {
  flightId: string;
  maxBand: number;
  lat: number;
  lon: number;
}
