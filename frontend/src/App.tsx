import { useState } from "react";
import { LayerPanel } from "./components/LayerPanel";
import { MapView } from "./components/MapView";
import { CATCHMENT_MINUTES, type CatchmentMinutes, type DayType, type LayerMode } from "./types";

function App() {
  const [mode, setMode] = useState<LayerMode>("heatmap");
  const [dayType, setDayType] = useState<DayType>("weekday");
  const [hour, setHour] = useState(8);
  const [maxBand, setMaxBand] = useState<CatchmentMinutes>(
    CATCHMENT_MINUTES[CATCHMENT_MINUTES.length - 1],
  );
  // Cumulative: the slider position shows every band at or below it (2 -> 2,5 -> 2,5,10 -> ...).
  const visibleBands = new Set(CATCHMENT_MINUTES.filter((minutes) => minutes <= maxBand));

  return (
    <div className="relative h-full w-full overflow-hidden">
      <MapView mode={mode} dayType={dayType} hour={hour} visibleBands={visibleBands} />
      <LayerPanel
        mode={mode}
        onModeChange={setMode}
        dayType={dayType}
        onDayTypeChange={setDayType}
        hour={hour}
        onHourChange={setHour}
        maxBand={maxBand}
        onMaxBandChange={setMaxBand}
      />
    </div>
  );
}

export default App;
