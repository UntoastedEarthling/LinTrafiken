"""Valhalla pedestrian helpers for the airport layer: walk times (matrix) and walk-time rings."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests
from pyproj import Transformer
from shapely.ops import unary_union

from . import config
from .isochrone import MAX_WORKERS, REQUEST_TIMEOUT_SECONDS, query_isochrone

# Valhalla's service_limits (infra/valhalla/valhalla.json): isochrone max_contours=4,
# pedestrian matrix max_locations=50 and max_matrix_location_pairs=2500.
MAX_CONTOURS_PER_REQUEST = 4
MATRIX_BATCH = 50

# Valhalla's default pedestrian speed (5.1 km/h); a network walk is never shorter than the
# straight line, so this gives a safe straight-line prefilter before asking for real walk times.
WALK_SPEED_MPS = 5.1 / 3.6

_to_metric = Transformer.from_crs("EPSG:4326", "EPSG:3006", always_xy=True)


def _matrix_request(sources: list[tuple[float, float]], targets: list[tuple[float, float]]) -> np.ndarray:
    body = {
        "sources": [{"lon": lon, "lat": lat} for lon, lat in sources],
        "targets": [{"lon": lon, "lat": lat} for lon, lat in targets],
        "costing": "pedestrian",
    }
    resp = requests.post(
        f"{config.VALHALLA_URL}/sources_to_targets", json=body, timeout=REQUEST_TIMEOUT_SECONDS
    )
    resp.raise_for_status()
    out = np.full((len(sources), len(targets)), np.nan)
    for row in resp.json()["sources_to_targets"]:
        for cell in row:
            if cell["time"] is not None:
                out[cell["from_index"], cell["to_index"]] = cell["time"]
    return out


def walk_times_seconds(
    sources: list[tuple[float, float]], targets: list[tuple[float, float]]
) -> np.ndarray:
    """Return a (len(sources), len(targets)) matrix of walk seconds, NaN where unreachable."""
    out = np.full((len(sources), len(targets)), np.nan)
    for s0 in range(0, len(sources), MATRIX_BATCH):
        for t0 in range(0, len(targets), MATRIX_BATCH):
            s_batch = sources[s0 : s0 + MATRIX_BATCH]
            t_batch = targets[t0 : t0 + MATRIX_BATCH]
            out[s0 : s0 + len(s_batch), t0 : t0 + len(t_batch)] = _matrix_request(s_batch, t_batch)
    return out


def _stop_xy(stops: pd.DataFrame) -> np.ndarray:
    return np.column_stack(_to_metric.transform(stops["stop_lon"].to_numpy(), stops["stop_lat"].to_numpy()))


def airport_walk_seconds(
    airport_lon: float, airport_lat: float, stops: pd.DataFrame, max_minutes: int
) -> pd.Series:
    """Walk seconds between the airport and each stop within `max_minutes` (assumed symmetric).

    Returns a Series indexed by stop_id, only containing stops reachable within the limit.
    """
    max_seconds = max_minutes * 60
    airport_xy = np.array(_to_metric.transform(airport_lon, airport_lat))
    straight_m = np.linalg.norm(_stop_xy(stops) - airport_xy, axis=1)
    candidates = stops[straight_m <= max_seconds * WALK_SPEED_MPS].reset_index(drop=True)
    if candidates.empty:
        return pd.Series(dtype=float, name="walk_seconds")

    seconds = walk_times_seconds(
        [(airport_lon, airport_lat)],
        list(zip(candidates["stop_lon"], candidates["stop_lat"])),
    )[0]
    result = pd.Series(seconds, index=candidates["stop_id"].astype(str), name="walk_seconds")
    return result[result <= max_seconds].sort_values()


def transfer_walks(stops: pd.DataFrame, max_minutes: int) -> pd.DataFrame:
    """Return (from_stop, to_stop, walk_seconds) for distinct stop pairs within `max_minutes` walk."""
    max_seconds = max_minutes * 60
    stops = stops.reset_index(drop=True)
    stop_ids = stops["stop_id"].astype(str).to_numpy()
    lonlat = list(zip(stops["stop_lon"], stops["stop_lat"]))
    xy = _stop_xy(stops)
    straight_m = np.linalg.norm(xy[:, None, :] - xy[None, :, :], axis=2)

    def walks_from(i: int) -> list[tuple[str, str, float]]:
        near = [j for j in np.flatnonzero(straight_m[i] <= max_seconds * WALK_SPEED_MPS) if j != i]
        rows: list[tuple[str, str, float]] = []
        for k in range(0, len(near), MATRIX_BATCH):
            batch = near[k : k + MATRIX_BATCH]
            seconds = _matrix_request([lonlat[i]], [lonlat[j] for j in batch])[0]
            rows.extend(
                (stop_ids[i], stop_ids[j], float(s))
                for j, s in zip(batch, seconds)
                if s <= max_seconds  # NaN compares False, dropping unreachable pairs
            )
        return rows

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        all_rows = [row for rows in pool.map(walks_from, range(len(stops))) for row in rows]
    return pd.DataFrame(all_rows, columns=["from_stop", "to_stop", "walk_seconds"])


def walk_rings(lon: float, lat: float, minutes: list[int]) -> dict[int, object]:
    """Return {minutes: cumulative walk-time polygon} for one point, chunking Valhalla's contour limit."""
    by_minutes: dict[int, list] = {}
    for k in range(0, len(minutes), MAX_CONTOURS_PER_REQUEST):
        chunk = query_isochrone(lon, lat, minutes[k : k + MAX_CONTOURS_PER_REQUEST])
        for m, geoms in chunk.items():
            by_minutes.setdefault(m, []).extend(geoms)
    return {m: unary_union(geoms) for m, geoms in by_minutes.items()}


def stop_walk_rings(stops: pd.DataFrame, max_minutes: int) -> dict[str, dict[int, object]]:
    """Return {stop_id: {1..max_minutes: cumulative walk polygon}} for every stop."""
    minutes = list(range(1, max_minutes + 1))
    stop_ids = stops["stop_id"].astype(str).tolist()
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        rings = pool.map(
            lambda row: walk_rings(row.stop_lon, row.stop_lat, minutes), stops.itertuples()
        )
        return dict(zip(stop_ids, rings))
