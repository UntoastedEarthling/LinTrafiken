import { airportAssumptions } from "../lib/airport";
import {
  CATCHMENT_MINUTES,
  type AirportFlight,
  type AirportMeta,
  type CatchmentMinutes,
  type DayType,
  type LayerMode,
} from "../types";

const DAY_TYPE_LABELS: Record<DayType, string> = {
  weekday: "Weekday",
  saturday: "Saturday",
  sunday: "Sunday",
};

const MODE_DESCRIPTIONS: Record<LayerMode, string> = {
  heatmap:
    "Shows how often buses serve each area, for a chosen day type and hour.",
  catchments:
    "Shows the walking distance to the nearest bus stop.",
  airport:
    "How bad is the airport connected? Shows how long it takes to get to or from the airport by bus and on foot for a chosen flight. Walking distances are limited as you carry a heavy suitcase.",
};

const MODE_LABELS: Record<LayerMode, string> = {
  heatmap: "Bus Frequency",
  catchments: "Walking Distance",
  airport: "Airport",
};

function formatHourRange(hour: number): string {
  const pad = (n: number) => String(n % 24).padStart(2, "0");
  return `${pad(hour)}:00–${pad(hour + 1)}:00`;
}

// Mirrors the color stops in lib/colors.ts's heatmapColorExpression, positioned
// by value (0-60) so tick labels line up with where each color actually appears.
const LEGEND_STOPS: Array<{ value: number; color: string }> = [
  { value: 0, color: "rgba(250,240,220,0)" },
  { value: 1, color: "#fde3a7" },
  { value: 6, color: "#f6b856" },
  { value: 15, color: "#e8792f" },
  { value: 30, color: "#c8401f" },
  { value: 60, color: "#7a1a12" },
];
const LEGEND_MAX = LEGEND_STOPS[LEGEND_STOPS.length - 1].value;
const LEGEND_GRADIENT = `linear-gradient(to right, ${LEGEND_STOPS.map(
  (s) => `${s.color} ${(s.value / LEGEND_MAX) * 100}%`,
).join(", ")})`;
// Value 1 sits too close to 0 on this scale to label without overlapping it.
const LEGEND_LABEL_VALUES = [0, 6, 15, 30, 60];

function HeatmapLegend() {
  return (
    <div>
      <div className="h-2 w-full rounded-full" style={{ background: LEGEND_GRADIENT }} />
      <div className="relative mt-1 h-3 text-[10px] text-stone-500">
        {LEGEND_LABEL_VALUES.map((value, i) => {
          const pct = (value / LEGEND_MAX) * 100;
          const translate = i === 0 ? "0%" : i === LEGEND_LABEL_VALUES.length - 1 ? "-100%" : "-50%";
          return (
            <span
              key={value}
              className="absolute"
              style={{ left: `${pct}%`, transform: `translateX(${translate})` }}
            >
              {value === LEGEND_MAX ? `${value}+` : value}
            </span>
          );
        })}
      </div>
      <p className="mt-0.5 text-[10px] text-stone-400">Departures / hour within 500m</p>
    </div>
  );
}

function DayTypeToggle({ dayType, onChange }: { dayType: DayType; onChange: (d: DayType) => void }) {
  return (
    <div className="flex gap-1 text-xs font-medium">
      {(Object.keys(DAY_TYPE_LABELS) as DayType[]).map((d) => (
        <button
          key={d}
          type="button"
          onClick={() => onChange(d)}
          className={`flex-1 rounded-lg px-2 py-1 transition-colors ${
            dayType === d ? "bg-stone-800 text-white" : "bg-stone-100 text-stone-600 hover:bg-stone-200"
          }`}
        >
          {DAY_TYPE_LABELS[d]}
        </button>
      ))}
    </div>
  );
}

interface BandSliderProps {
  label: string;
  bands: readonly number[];
  value: number;
  onChange: (minutes: number) => void;
  tickLabel: (minutes: number) => string;
  listId: string;
}

// Cumulative band slider: the position shows every band at or below it.
function BandSlider({ label, bands, value, onChange, tickLabel, listId }: BandSliderProps) {
  const last = bands.length - 1;
  // Thin out tick labels once there are too many to fit under the slider.
  const stride = Math.max(1, Math.ceil(bands.length / 7));
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs text-stone-500">
        <span>{label}</span>
        <span className="font-mono">Up to {value} min</span>
      </div>
      <input
        type="range"
        min={0}
        max={last}
        step={1}
        list={listId}
        value={Math.max(0, bands.indexOf(value))}
        onChange={(e) => onChange(bands[Number(e.target.value)])}
        className="w-full accent-orange-600"
      />
      <datalist id={listId}>
        {bands.map((_, i) => (
          <option key={i} value={i} />
        ))}
      </datalist>
      <div className="relative mt-1 h-3 text-[10px] text-stone-500">
        {bands.map((minutes, i) => {
          if (!(i === 0 || i === last || (i % stride === 0 && last - i >= stride))) return null;
          const pct = last > 0 ? (i / last) * 100 : 0;
          const translate = i === 0 ? "0%" : i === last ? "-100%" : "-50%";
          return (
            <span
              key={minutes}
              className="absolute whitespace-nowrap"
              style={{ left: `${pct}%`, transform: `translateX(${translate})` }}
            >
              {tickLabel(minutes)}
            </span>
          );
        })}
      </div>
    </div>
  );
}

export interface AirportPanelState {
  meta: AirportMeta | null;
  error: boolean;
  flightId: string | null;
  onFlightChange: (flightId: string) => void;
  bands: number[];
  maxBand: number;
  onMaxBandChange: (minutes: number) => void;
}

function FlightGroup({ label, flights }: { label: string; flights: AirportFlight[] }) {
  if (flights.length === 0) return null;
  return (
    <optgroup label={label}>
      {[...flights]
        .sort((a, b) => a.time.localeCompare(b.time))
        .map((f) => (
          <option key={f.id} value={f.id}>
            {f.time} · {f.id}
          </option>
        ))}
    </optgroup>
  );
}

function AirportControls({
  airport,
  dayType,
  onDayTypeChange,
}: {
  airport: AirportPanelState;
  dayType: DayType;
  onDayTypeChange: (d: DayType) => void;
}) {
  if (airport.error) {
    return (
      <p className="text-xs text-red-700">
        Airport data is missing. Run the airport pipeline, then <code>npm run sync-tiles</code>.
      </p>
    );
  }
  if (!airport.meta) return <p className="text-xs text-stone-500">Loading airport data…</p>;

  const { flights } = airport.meta;
  return (
    <div className="space-y-3">
      <label className="block">
        <span className="mb-1 block text-xs text-stone-500">Flight</span>
        <select
          value={airport.flightId ?? ""}
          onChange={(e) => airport.onFlightChange(e.target.value)}
          className="w-full rounded-lg border border-stone-300 bg-white/70 px-2 py-1.5 text-sm text-stone-800"
        >
          <FlightGroup label="Departures" flights={flights.filter((f) => f.direction === "departure")} />
          <FlightGroup label="Arrivals" flights={flights.filter((f) => f.direction === "arrival")} />
        </select>
      </label>
      <DayTypeToggle dayType={dayType} onChange={onDayTypeChange} />
      {airport.bands.length > 0 && (
        <BandSlider
          label="Travel time"
          bands={airport.bands}
          value={airport.maxBand}
          onChange={airport.onMaxBandChange}
          tickLabel={(m) => String(m)}
          listId="airport-band-ticks"
        />
      )}
      <details open className="text-[11px] text-stone-600">
        <summary className="cursor-pointer font-medium text-stone-700">Assumptions</summary>
        <ul className="mt-1 list-disc space-y-1 pl-4">
          {airportAssumptions(
            airport.meta,
            flights.find((f) => f.id === airport.flightId),
            dayType,
          ).map((text) => (
            <li key={text}>{text}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}

interface LayerPanelProps {
  mode: LayerMode;
  onModeChange: (mode: LayerMode) => void;
  dayType: DayType;
  onDayTypeChange: (dayType: DayType) => void;
  hour: number;
  onHourChange: (hour: number) => void;
  maxBand: CatchmentMinutes;
  onMaxBandChange: (minutes: CatchmentMinutes) => void;
  airport: AirportPanelState;
}

export function LayerPanel({
  mode,
  onModeChange,
  dayType,
  onDayTypeChange,
  hour,
  onHourChange,
  maxBand,
  onMaxBandChange,
  airport,
}: LayerPanelProps) {
  return (
    <div className="absolute top-4 left-4 max-h-[calc(100%-2rem)] w-96 overflow-y-auto rounded-2xl border border-white/30 bg-white/40 p-4 shadow-lg backdrop-blur-md">
      <h1 className="text-lg font-semibold text-stone-800">LinTrafiken</h1>
      <p className="mb-3 text-xs text-stone-500">
        Explore Linköping's local public transit system based on open GTFS data.
      </p>

      <div className="mb-3 flex rounded-full bg-stone-200/70 p-1 text-xs font-medium">
        {(["heatmap", "catchments", "airport"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => onModeChange(m)}
            className={`flex-1 rounded-full px-2 py-1.5 whitespace-nowrap transition-colors ${
              mode === m ? "bg-orange-600 text-white shadow" : "text-stone-600 hover:text-stone-900"
            }`}
          >
            {MODE_LABELS[m]}
          </button>
        ))}
      </div>

      <p className="mb-3 text-xs text-stone-500">{MODE_DESCRIPTIONS[mode]}</p>

      {mode === "heatmap" ? (
        <div className="space-y-3">
          <DayTypeToggle dayType={dayType} onChange={onDayTypeChange} />
          <div>
            <div className="mb-1 flex justify-between text-xs text-stone-500">
              <span>Time period</span>
              <span className="font-mono">{formatHourRange(hour)}</span>
            </div>
            <input
              type="range"
              min={0}
              max={23}
              step={1}
              value={hour}
              onChange={(e) => onHourChange(Number(e.target.value))}
              className="w-full accent-orange-600"
            />
          </div>
          <HeatmapLegend />
        </div>
      ) : mode === "catchments" ? (
        <BandSlider
          label="Walking time"
          bands={CATCHMENT_MINUTES}
          value={maxBand}
          onChange={(minutes) => onMaxBandChange(minutes as CatchmentMinutes)}
          tickLabel={(minutes) => `${minutes} min`}
          listId="catchment-band-ticks"
        />
      ) : (
        <AirportControls airport={airport} dayType={dayType} onDayTypeChange={onDayTypeChange} />
      )}
    </div>
  );
}
