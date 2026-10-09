import { useEffect, useState } from "react";
import { LayerPanel } from "./components/LayerPanel";
import { MapView } from "./components/MapView";
import { airportBands, loadAirportMeta } from "./lib/airport";
import {
  CATCHMENT_MINUTES,
  type AirportMeta,
  type AirportView,
  type CatchmentMinutes,
  type DayType,
  type LayerMode,
} from "./types";

function App() {
  const [mode, setMode] = useState<LayerMode>("heatmap");
  const [dayType, setDayType] = useState<DayType>("weekday");
  const [hour, setHour] = useState(8);
  const [maxBand, setMaxBand] = useState<CatchmentMinutes>(
    CATCHMENT_MINUTES[CATCHMENT_MINUTES.length - 1],
  );
  // Cumulative: the slider position shows every band at or below it (2 -> 2,5 -> 2,5,10 -> ...).
  const visibleBands = new Set(CATCHMENT_MINUTES.filter((minutes) => minutes <= maxBand));

  const [airportMeta, setAirportMeta] = useState<AirportMeta | null>(null);
  const [airportError, setAirportError] = useState(false);
  const [airportFlightId, setAirportFlightId] = useState<string | null>(null);
  // null = show every band; reset whenever the flight or day type changes the available range.
  const [airportLimit, setAirportLimit] = useState<number | null>(null);

  useEffect(() => {
    loadAirportMeta().then(setAirportMeta).catch(() => setAirportError(true));
  }, []);

  const flightId = airportFlightId ?? airportMeta?.defaultFlightId ?? null;
  const airportBandList = airportMeta && flightId ? airportBands(airportMeta, flightId, dayType) : [];
  const airportTopBand = airportBandList[airportBandList.length - 1] ?? 0;
  const airportMaxBand = Math.min(airportLimit ?? airportTopBand, airportTopBand);

  const airportView: AirportView | null =
    airportMeta && flightId
      ? { flightId, maxBand: airportMaxBand, lat: airportMeta.airport.lat, lon: airportMeta.airport.lon }
      : null;

  return (
    <div className="relative h-full w-full overflow-hidden">
      <MapView
        mode={mode}
        dayType={dayType}
        hour={hour}
        visibleBands={visibleBands}
        airport={airportView}
      />
      <LayerPanel
        mode={mode}
        onModeChange={setMode}
        dayType={dayType}
        onDayTypeChange={(next) => {
          setDayType(next);
          setAirportLimit(null);
        }}
        hour={hour}
        onHourChange={setHour}
        maxBand={maxBand}
        onMaxBandChange={setMaxBand}
        airport={{
          meta: airportMeta,
          error: airportError,
          flightId,
          onFlightChange: (id) => {
            setAirportFlightId(id);
            setAirportLimit(null);
          },
          bands: airportBandList,
          maxBand: airportMaxBand,
          onMaxBandChange: setAirportLimit,
        }}
      />
    </div>
  );
}

export default App;
