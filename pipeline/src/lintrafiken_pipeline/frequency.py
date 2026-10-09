"""Compute per-H3-hex, per-hour departure frequency for representative weekday/Saturday/Sunday dates.

Simplification: Trafiklab's otraf feed defines all service purely via calendar_dates.txt
"add" exceptions (calendar.txt has all-zero weekday flags), so representative dates are
picked as the date - per day-of-week bucket - with the most active service_ids, which is a
good proxy for a "typical" non-holiday day.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from pyproj import Transformer
from sqlalchemy import text
from sqlalchemy.engine import Engine

from .hexgrid import build_hex_grid

logger = logging.getLogger(__name__)

RADIUS_METERS = 500
DAY_TYPE_ISODOW = {"weekday": (1, 5), "saturday": (6, 6), "sunday": (7, 7)}
GEOGRAPHIC_CRS = "EPSG:4326"
METRIC_CRS = "EPSG:3006"

_to_metric = Transformer.from_crs(GEOGRAPHIC_CRS, METRIC_CRS, always_xy=True)


def pick_representative_dates(engine: Engine) -> dict[str, str]:
    query = text(
        """
        SELECT date, EXTRACT(ISODOW FROM to_date(date::text, 'YYYYMMDD'))::int AS isodow,
               count(DISTINCT service_id) AS n_services
        FROM calendar_dates
        WHERE exception_type = 1
        GROUP BY date
        """
    )
    with engine.connect() as conn:
        df = pd.DataFrame(conn.execute(query).fetchall(), columns=["date", "isodow", "n_services"])

    dates: dict[str, str] = {}
    for day_type, (lo, hi) in DAY_TYPE_ISODOW.items():
        candidates = df[df["isodow"].between(lo, hi)]
        if candidates.empty:
            raise ValueError(f"No calendar_dates entries found for day-type '{day_type}'")
        best = candidates.sort_values("n_services", ascending=False).iloc[0]
        dates[day_type] = str(int(best["date"]))
    return dates


def _departures_for_date(engine: Engine, date: str) -> pd.DataFrame:
    query = text(
        """
        SELECT st.stop_id, st.departure_time
        FROM stop_times st
        JOIN trips t ON t.trip_id = st.trip_id
        JOIN calendar_dates cd ON cd.service_id = t.service_id
        WHERE cd.date = :date AND cd.exception_type = 1
        """
    )
    with engine.connect() as conn:
        df = pd.DataFrame(
            conn.execute(query, {"date": str(date)}).fetchall(),
            columns=["stop_id", "departure_time"],
        )
    df["stop_id"] = df["stop_id"].astype(str)
    df["hour"] = df["departure_time"].str.slice(0, 2).astype(int) % 24  # GTFS times can exceed 24:00
    return df[["stop_id", "hour"]]


def compute_hex_frequencies(engine: Engine) -> pd.DataFrame:
    """Return one row per H3 hex, with `weekday_h0..h23`/`saturday_h*`/`sunday_h*` departure counts."""
    with engine.connect() as conn:
        stops = pd.DataFrame(
            conn.execute(text("SELECT stop_id, stop_lon, stop_lat FROM stops")).fetchall(),
            columns=["stop_id", "stop_lon", "stop_lat"],
        )
    stops["stop_id"] = stops["stop_id"].astype(str)

    hexes = build_hex_grid(stops["stop_lon"].to_numpy(), stops["stop_lat"].to_numpy(), buffer_meters=RADIUS_METERS)
    logger.info("Built %d H3 hex cells covering the stop network", len(hexes))

    stop_xy = np.column_stack(_to_metric.transform(stops["stop_lon"].to_numpy(), stops["stop_lat"].to_numpy()))
    hex_xy = np.column_stack(_to_metric.transform(hexes["lon"].to_numpy(), hexes["lat"].to_numpy()))
    dx = hex_xy[:, 0][:, None] - stop_xy[:, 0][None, :]
    dy = hex_xy[:, 1][:, None] - stop_xy[:, 1][None, :]
    adjacency = (np.sqrt(dx**2 + dy**2) <= RADIUS_METERS).astype(float)  # (n_hex, n_stops)

    stop_index = {sid: i for i, sid in enumerate(stops["stop_id"])}

    dates = pick_representative_dates(engine)
    logger.info("Representative dates: %s", dates)

    result = hexes[["hex_id", "lon", "lat"]].copy()
    for day_type, date in dates.items():
        departures = _departures_for_date(engine, date)
        counts = np.zeros((len(stops), 24))
        for (stop_id, hour), n in departures.groupby(["stop_id", "hour"]).size().items():
            idx = stop_index.get(stop_id)
            if idx is not None:
                counts[idx, hour] = n

        hex_hour_counts = adjacency @ counts  # (n_hex, 24)
        for h in range(24):
            result[f"{day_type}_h{h}"] = hex_hour_counts[:, h].astype(int)

    return result
