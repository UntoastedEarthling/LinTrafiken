"""Time-dependent public-transit scans (Connection Scan Algorithm) to and from the airport.

Both scans return, per stop, the time in seconds between that stop and the anchor:
- arrivals: earliest arrival at the stop minus the start time at the airport (landing + offset);
- departures: the arrive-by deadline at the airport minus the latest departure from the stop.

Walking is only used to reach the first stop / leave the last stop at the airport end and for
transfers; walking-only travel and the home-end walk are handled elsewhere. A transfer to a
different stop costs max(walk, min_transfer); a transfer at the same stop costs min_transfer.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from .flights import Flight, Rules

logger = logging.getLogger(__name__)

DAY_SECONDS = 86400
_NEVER = 1 << 60


@dataclass
class Network:
    """Elementary connections for a service date plus the days before and after it.

    Times are seconds since midnight of the service date (negative for the previous day).
    """

    stop_ids: list[str]
    stop_index: dict[str, int]
    n_trips: int
    trip: np.ndarray
    from_stop: np.ndarray
    to_stop: np.ndarray
    dep: np.ndarray
    arr: np.ndarray
    by_dep: np.ndarray  # connection indices, departure ascending
    by_arr: np.ndarray  # connection indices, arrival descending


def _gtfs_seconds(col: pd.Series) -> pd.Series:
    parts = col.str.split(":", expand=True).astype(int)
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def _stop_times_for_date(engine: Engine, date: str) -> pd.DataFrame:
    query = text(
        """
        SELECT st.trip_id, st.stop_id, st.stop_sequence, st.arrival_time, st.departure_time
        FROM stop_times st
        JOIN trips t ON t.trip_id = st.trip_id
        WHERE t.service_id IN (
            SELECT service_id FROM calendar_dates WHERE date = :date AND exception_type = 1
        )
        """
    )
    with engine.connect() as conn:
        df = pd.DataFrame(
            conn.execute(query, {"date": date}).fetchall(),
            columns=["trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"],
        )
    df["trip_id"] = df["trip_id"].astype(str)
    df["stop_id"] = df["stop_id"].astype(str)
    return df


def build_network(engine: Engine, service_date: str, stop_ids: list[str]) -> Network:
    """Build connections for `service_date` (YYYYMMDD) and the calendar days on either side of it."""
    base = datetime.strptime(service_date, "%Y%m%d")
    stop_index = {sid: i for i, sid in enumerate(stop_ids)}

    frames = []
    for offset in (-1, 0, 1):
        date = (base + timedelta(days=offset)).strftime("%Y%m%d")
        df = _stop_times_for_date(engine, date)
        if df.empty:
            logger.warning("No service found in calendar_dates for %s (offset %d)", date, offset)
            continue
        df = df.sort_values(["trip_id", "stop_sequence"])
        arrival = _gtfs_seconds(df["arrival_time"])
        departure = _gtfs_seconds(df["departure_time"])
        shift = offset * DAY_SECONDS
        nxt = df.groupby("trip_id").shift(-1)
        mask = nxt["stop_id"].notna()
        frames.append(
            pd.DataFrame(
                {
                    "trip": f"{offset}|" + df.loc[mask, "trip_id"],
                    "from_stop": df.loc[mask, "stop_id"],
                    "to_stop": nxt.loc[mask, "stop_id"],
                    "dep": departure[mask] + shift,
                    "arr": _gtfs_seconds(nxt.loc[mask, "arrival_time"]) + shift,
                }
            )
        )
    if not frames:
        raise ValueError(f"No transit service found around {service_date}")

    conns = pd.concat(frames, ignore_index=True)
    conns = conns[conns["from_stop"].isin(stop_index) & conns["to_stop"].isin(stop_index)]
    trip_codes, trip_labels = pd.factorize(conns["trip"])
    dep = conns["dep"].to_numpy(dtype=np.int64)
    arr = conns["arr"].to_numpy(dtype=np.int64)
    return Network(
        stop_ids=stop_ids,
        stop_index=stop_index,
        n_trips=len(trip_labels),
        trip=trip_codes.astype(np.int64),
        from_stop=conns["from_stop"].map(stop_index).to_numpy(dtype=np.int64),
        to_stop=conns["to_stop"].map(stop_index).to_numpy(dtype=np.int64),
        dep=dep,
        arr=arr,
        by_dep=np.argsort(dep, kind="stable"),
        by_arr=np.argsort(-arr, kind="stable"),
    )


def _adjacency(network: Network, transfers: pd.DataFrame, *, reverse: bool) -> dict[int, list[tuple[int, int]]]:
    """Map stop index -> [(other stop index, walk seconds)]; `reverse` keys on the walk's destination."""
    adj: dict[int, list[tuple[int, int]]] = {}
    for row in transfers.itertuples():
        a, b = network.stop_index.get(row.from_stop), network.stop_index.get(row.to_stop)
        if a is None or b is None:
            continue
        key, other = (b, a) if reverse else (a, b)
        adj.setdefault(key, []).append((other, int(row.walk_seconds)))
    return adj


def anchor_seconds(flight: Flight, rules: Rules) -> int:
    """Departures: arrive-by deadline at the airport. Arrivals: time the journey starts at the airport."""
    if flight.direction == "departure":
        return flight.seconds_of_day - rules.arrive_before_departure_minutes * 60
    return flight.seconds_of_day + rules.leave_after_landing_minutes * 60


def seconds_from_airport(
    network: Network, transfers: pd.DataFrame, airport_walk: pd.Series, start: int, rules: Rules
) -> pd.Series:
    """Arrivals: seconds from `start` (at the airport) until the earliest vehicle arrival at each stop."""
    min_transfer = rules.min_transfer_minutes * 60
    horizon = start + rules.max_band_minutes * 60
    adj = _adjacency(network, transfers, reverse=False)

    ready = np.full(len(network.stop_ids), _NEVER, dtype=np.int64)  # earliest boarding time per stop
    arrived = np.full(len(network.stop_ids), _NEVER, dtype=np.int64)
    for stop_id, walk in airport_walk.items():
        idx = network.stop_index.get(stop_id)
        if idx is not None:
            ready[idx] = start + int(walk)
    boarded = np.zeros(network.n_trips, dtype=bool)

    order = network.by_dep
    first = np.searchsorted(network.dep[order], start, side="left")
    for c in order[first:]:
        dep = network.dep[c]
        if dep > horizon:
            break
        trip, u, v, arr = network.trip[c], network.from_stop[c], network.to_stop[c], network.arr[c]
        if not boarded[trip]:
            if ready[u] > dep:
                continue
            boarded[trip] = True
        if arr < arrived[v]:
            arrived[v] = arr
        ready[v] = min(ready[v], arr + min_transfer)
        for w, walk in adj.get(v, ()):
            ready[w] = min(ready[w], arr + max(walk, min_transfer))

    reached = arrived < _NEVER
    result = pd.Series(
        arrived[reached] - start, index=np.array(network.stop_ids)[reached], name="seconds"
    )
    return result[result <= rules.max_band_minutes * 60]


def seconds_to_airport(
    network: Network, transfers: pd.DataFrame, airport_walk: pd.Series, deadline: int, rules: Rules
) -> pd.Series:
    """Departures: seconds from the latest usable departure at each stop until the airport deadline."""
    min_transfer = rules.min_transfer_minutes * 60
    horizon = deadline - rules.max_band_minutes * 60
    adj = _adjacency(network, transfers, reverse=True)

    latest_alight = np.full(len(network.stop_ids), -_NEVER, dtype=np.int64)  # latest time to get off
    departed = np.full(len(network.stop_ids), -_NEVER, dtype=np.int64)
    for stop_id, walk in airport_walk.items():
        idx = network.stop_index.get(stop_id)
        if idx is not None:
            latest_alight[idx] = deadline - int(walk)
    usable = np.zeros(network.n_trips, dtype=bool)

    order = network.by_arr
    first = np.searchsorted(-network.arr[order], -deadline, side="left")
    for c in order[first:]:
        arr = network.arr[c]
        if arr < horizon:
            break
        trip, u, v, dep = network.trip[c], network.from_stop[c], network.to_stop[c], network.dep[c]
        if not usable[trip]:
            if arr > latest_alight[v]:
                continue
            usable[trip] = True
        if dep > departed[u]:
            departed[u] = dep
        latest_alight[u] = max(latest_alight[u], dep - min_transfer)
        for w, walk in adj.get(u, ()):
            latest_alight[w] = max(latest_alight[w], dep - max(walk, min_transfer))

    reached = departed > -_NEVER
    result = pd.Series(
        deadline - departed[reached], index=np.array(network.stop_ids)[reached], name="seconds"
    )
    return result[result <= rules.max_band_minutes * 60]
