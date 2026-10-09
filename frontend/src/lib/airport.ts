import type { AirportFlight, AirportMeta, DayType } from "../types";

function shiftClock(time: string, minutes: number): string {
  const [h, m] = time.split(":").map(Number);
  const total = (((h * 60 + m + minutes) % 1440) + 1440) % 1440;
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

function formatServiceDate(yyyymmdd: string): string {
  const date = new Date(Number(yyyymmdd.slice(0, 4)), Number(yyyymmdd.slice(4, 6)) - 1, Number(yyyymmdd.slice(6, 8)));
  return date.toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
}

// Every assumption behind the airport layer, filled in from the pipeline's own configuration.
export function airportAssumptions(meta: AirportMeta, flight: AirportFlight | undefined, dayType: DayType): string[] {
  const r = meta.rules;
  const items: string[] = [
    `Bus timetable of ${formatServiceDate(meta.serviceDates[dayType])}. Flights are assumed to run every day at their scheduled local time; delays are not modelled.`,
  ];
  if (flight?.direction === "departure") {
    items.push(
      `${flight.id} departs ${flight.time}, so you must be at the airport ${r.arriveBeforeDepartureMinutes} min earlier, at ${shiftClock(flight.time, -r.arriveBeforeDepartureMinutes)}.`,
      "Travel time is counted from leaving home until that arrive-by time, so waiting for the bus and any spare time at the airport are included. The latest departure that still arrives in time is assumed.",
    );
  } else if (flight?.direction === "arrival") {
    items.push(
      `${flight.id} lands ${flight.time}, and the journey home starts ${r.leaveAfterLandingMinutes} min later, at ${shiftClock(flight.time, r.leaveAfterLandingMinutes)}.`,
      "Travel time is counted from that start time until arriving at the destination, so waiting for the bus is included.",
    );
  }
  items.push(
    `If the airport is within ${r.walkOnlyMaxMinutes} min on foot, walking is used and no bus is needed.`,
    `Otherwise a bus is needed. The start/end point must be within ${r.homeAccessMaxMinutes} min on foot of the used bus stop, and the airport within ${r.airportAccessMaxMinutes} min on foot of the used bus stop.`,
    "Only Linköping city bus routes are used, no regional buses or trains.",
    `Bus changes are allowed with at most ${r.transferWalkMaxMinutes} min walk between stops and at least ${r.minTransferMinutes} min to change.`,
    "Walking times follow the street network at about 5 km/h, are the same in both directions, and are rounded down to whole minutes.",
    `Areas with no connection, or that take more than ${r.maxBandMinutes} min, are left uncoloured.`,
  );
  return items;
}

export async function loadAirportMeta(): Promise<AirportMeta> {
  const res = await fetch("/tiles/airport-meta.json");
  if (!res.ok) throw new Error(`airport-meta.json: HTTP ${res.status}`);
  return res.json();
}

// Bands that have area can skip a step (e.g. 100 then 120), so the slider uses every step up to the highest.
export function airportBands(meta: AirportMeta, flightId: string, dayType: DayType): number[] {
  const listed = meta.bands[flightId]?.[dayType] ?? [];
  const step = meta.bandStepMinutes;
  const count = Math.floor(Math.max(0, ...listed) / step);
  return Array.from({ length: count }, (_, i) => (i + 1) * step);
}
