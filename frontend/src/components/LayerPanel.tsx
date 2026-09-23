import { CATCHMENT_MINUTES, type CatchmentMinutes, type DayType, type LayerMode } from "../types";

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

interface LayerPanelProps {
  mode: LayerMode;
  onModeChange: (mode: LayerMode) => void;
  dayType: DayType;
  onDayTypeChange: (dayType: DayType) => void;
  hour: number;
  onHourChange: (hour: number) => void;
  maxBand: CatchmentMinutes;
  onMaxBandChange: (minutes: CatchmentMinutes) => void;
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
}: LayerPanelProps) {
  return (
    <div className="absolute top-4 left-4 w-80 rounded-2xl border border-white/30 bg-white/40 p-4 shadow-lg backdrop-blur-md">
      <h1 className="text-lg font-semibold text-stone-800">LinTrafiken</h1>
      <p className="mb-3 text-xs text-stone-500">
        Explore Linköping's local public transit system based on open GTFS data.
      </p>

      <div className="mb-3 flex rounded-full bg-stone-200/70 p-1 text-sm font-medium">
        {(["heatmap", "catchments"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => onModeChange(m)}
            className={`flex-1 rounded-full px-3 py-1.5 transition-colors ${
              mode === m ? "bg-orange-600 text-white shadow" : "text-stone-600 hover:text-stone-900"
            }`}
          >
            {m === "heatmap" ? "Bus Frequency" : "Walking Distance"}
          </button>
        ))}
      </div>

      <p className="mb-3 text-xs text-stone-500">{MODE_DESCRIPTIONS[mode]}</p>

      {mode === "heatmap" ? (
        <div className="space-y-3">
          <div className="flex gap-1 text-xs font-medium">
            {(Object.keys(DAY_TYPE_LABELS) as DayType[]).map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => onDayTypeChange(d)}
                className={`flex-1 rounded-lg px-2 py-1 transition-colors ${
                  dayType === d ? "bg-stone-800 text-white" : "bg-stone-100 text-stone-600 hover:bg-stone-200"
                }`}
              >
                {DAY_TYPE_LABELS[d]}
              </button>
            ))}
          </div>
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
      ) : (
        <div>
          <div className="mb-1 flex justify-between text-xs text-stone-500">
            <span>Walking time</span>
            <span className="font-mono">Up to {maxBand} min</span>
          </div>
          <input
            type="range"
            min={0}
            max={CATCHMENT_MINUTES.length - 1}
            step={1}
            list="catchment-band-ticks"
            value={CATCHMENT_MINUTES.indexOf(maxBand)}
            onChange={(e) => onMaxBandChange(CATCHMENT_MINUTES[Number(e.target.value)])}
            className="w-full accent-orange-600"
          />
          <datalist id="catchment-band-ticks">
            {CATCHMENT_MINUTES.map((_, i) => (
              <option key={i} value={i} />
            ))}
          </datalist>
          <div className="mt-1 flex justify-between text-[10px] text-stone-500">
            {CATCHMENT_MINUTES.map((minutes) => (
              <span key={minutes}>{minutes} min</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
