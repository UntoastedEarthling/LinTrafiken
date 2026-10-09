"""Airport entrypoint: per flight and day type, 10-min travel-time bands to/from the airport,
exported as PMTiles (layer "airport") and airport-meta.json.

Requires PostGIS (Phase 1 data) and Valhalla running locally, like the catchments pipeline.

A location belongs to band B when some way of getting there takes at most B minutes: walking
only (airport within the walk-only limit), or a bus journey with a walk of at most the home
access limit to/from the stop. Bands are cumulative internally and exported as exclusive rings.
"""
from __future__ import annotations

import json
import logging
import math
from datetime import datetime

import geopandas as gpd
import pandas as pd
from shapely.ops import unary_union
from shapely.validation import make_valid
from sqlalchemy import text
from sqlalchemy.engine import Engine

from . import config, db
from .export import export_geojson
from .flights import AirportConfig, Flight, Rules, load_airport_config
from .frequency import pick_representative_dates
from .tile import tile_to_pmtiles
from .transit_scan import (
    Network,
    anchor_seconds,
    build_network,
    seconds_from_airport,
    seconds_to_airport,
)
from .walking import airport_walk_seconds, stop_walk_rings, transfer_walks, walk_rings

logger = logging.getLogger(__name__)

OUTPUT_PATH = config.DATA_DIR / "processed" / "airport.geojson"
META_PATH = config.DATA_DIR / "processed" / "airport-meta.json"


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.capitalize() for part in rest)


def pick_weekday_date(engine: Engine) -> str:
    """A Tuesday-Thursday date with the most active services (Fridays run extra night buses)."""
    query = text(
        """
        SELECT date, count(DISTINCT service_id) AS n_services
        FROM calendar_dates
        WHERE exception_type = 1
          AND EXTRACT(ISODOW FROM to_date(date::text, 'YYYYMMDD')) BETWEEN 2 AND 4
        GROUP BY date
        ORDER BY n_services DESC, date
        LIMIT 1
        """
    )
    with engine.connect() as conn:
        row = conn.execute(query).fetchone()
    if row is None:
        raise ValueError("No Tuesday-Thursday service dates found in calendar_dates")
    return str(row[0])


def service_dates(engine: Engine) -> dict[str, str]:
    dates = pick_representative_dates(engine)
    return {"weekday": pick_weekday_date(engine), "saturday": dates["saturday"], "sunday": dates["sunday"]}


def _fetch_stops(engine: Engine) -> pd.DataFrame:
    with engine.connect() as conn:
        stops = pd.DataFrame(
            conn.execute(text("SELECT stop_id, stop_lon, stop_lat FROM stops")).fetchall(),
            columns=["stop_id", "stop_lon", "stop_lat"],
        )
    stops["stop_id"] = stops["stop_id"].astype(str)
    return stops


def _band_unions(
    seconds_at_stop: pd.Series,
    stop_rings: dict[str, dict[int, object]],
    walk_only: dict[int, object],
    cfg: AirportConfig,
) -> dict[int, object]:
    """Return {band minutes: cumulative reachable area} for every band that has any area."""
    rules = cfg.rules
    step = rules.band_step_minutes
    longest = seconds_at_stop.max() if len(seconds_at_stop) else 0
    last_band = min(
        rules.max_band_minutes,
        math.ceil((longest / 60 + rules.home_access_max_minutes) / step) * step,
    )
    last_band = max(last_band, max(walk_only, default=0))

    unions: dict[int, object] = {}
    for band in range(step, last_band + 1, step):
        parts = [geom for walk_minutes, geom in walk_only.items() if walk_minutes <= band]
        for stop_id, seconds in seconds_at_stop.items():
            # Whole minutes only, so the walk never exceeds the band.
            budget = min(rules.home_access_max_minutes, int((band * 60 - seconds) // 60))
            ring = stop_rings.get(stop_id, {}).get(budget) if budget >= 1 else None
            if ring is not None:
                parts.append(ring)
        union = _valid_polygons(unary_union(parts)) if parts else None
        if union is not None and not union.is_empty:
            unions[band] = union
    return unions


def _valid_polygons(geom):
    """Valhalla contours occasionally self-intersect; repair and keep only the polygonal parts."""
    fixed = make_valid(geom)
    if fixed.geom_type == "GeometryCollection":
        return unary_union([g for g in fixed.geoms if g.geom_type in ("Polygon", "MultiPolygon")])
    return fixed


def _feature_rows(
    flight: Flight, day_type: str, unions: dict[int, object]
) -> tuple[list[dict], list[int]]:
    rows: list[dict] = []
    bands: list[int] = []
    previous = None
    for band in sorted(unions):
        ring = unions[band] if previous is None else unions[band].difference(previous)
        previous = unions[band]
        ring = _valid_polygons(ring)
        if ring.is_empty:
            continue
        bands.append(band)
        rows.append(
            {"flight_id": flight.id, "day_type": day_type, "minutes": band, "geometry": ring}
        )
    return rows, bands


def compute_airport_layer(engine: Engine, cfg: AirportConfig) -> tuple[gpd.GeoDataFrame, dict]:
    rules = cfg.rules
    airport = cfg.airport
    stops = _fetch_stops(engine)

    airport_walk = airport_walk_seconds(
        airport.lon, airport.lat, stops, rules.airport_access_max_minutes
    )
    if airport_walk.empty:
        logger.warning(
            "No stop within %d min walk of the airport; no area will have a bus connection",
            rules.airport_access_max_minutes,
        )
    else:
        logger.info("%d stops within %d min walk of the airport", len(airport_walk), rules.airport_access_max_minutes)

    transfers = transfer_walks(stops, rules.transfer_walk_max_minutes)
    stop_rings = stop_walk_rings(stops, rules.home_access_max_minutes)

    # Walk-only zone: cumulative polygons at the band edges up to the walk-only limit.
    step = rules.band_step_minutes
    edges = list(range(step, rules.walk_only_max_minutes, step)) + [rules.walk_only_max_minutes]
    walk_only = walk_rings(airport.lon, airport.lat, edges)
    # A 15-min walk counts toward the first band that contains it (20 for 15), not the one below.
    walk_only = {step * math.ceil(m / step): geom for m, geom in walk_only.items()}

    dates = service_dates(engine)
    logger.info("Service dates: %s", dates)
    stop_ids = stops["stop_id"].tolist()

    rows: list[dict] = []
    bands_meta: dict[str, dict[str, list[int]]] = {}
    for day_type, date in dates.items():
        network: Network = build_network(engine, date, stop_ids)
        for flight in cfg.flights:
            anchor = anchor_seconds(flight, rules)
            if flight.direction == "departure":
                at_stop = seconds_to_airport(network, transfers, airport_walk, anchor, rules)
            else:
                at_stop = seconds_from_airport(network, transfers, airport_walk, anchor, rules)

            unions = _band_unions(at_stop, stop_rings, walk_only, cfg)
            flight_rows, bands = _feature_rows(flight, day_type, unions)
            rows.extend(flight_rows)
            bands_meta.setdefault(flight.id, {})[day_type] = bands
            logger.info(
                "%s %s: %d stops with a connection, bands %s",
                flight.id, day_type, len(at_stop), bands,
            )

    gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
    meta = {
        "airport": {"iata": airport.iata, "name": airport.name, "lat": airport.lat, "lon": airport.lon},
        "bandStepMinutes": step,
        "rules": {_camel(name): getattr(rules, name) for name in Rules.__dataclass_fields__},
        "serviceDates": dates,
        "flights": [{"id": f.id, "direction": f.direction, "time": f.time} for f in cfg.flights],
        "defaultFlightId": cfg.default_flight_id,
        "bands": bands_meta,
        "generatedAt": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    return gdf, meta


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    cfg = load_airport_config()
    gdf, meta = compute_airport_layer(db.get_engine(), cfg)

    export_geojson(gdf, OUTPUT_PATH)
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Exported %d features to %s and metadata to %s", len(gdf), OUTPUT_PATH, META_PATH)

    tile_to_pmtiles(OUTPUT_PATH, layer_name="airport", extra_args=["--simplification=0.1"])


if __name__ == "__main__":
    main()
