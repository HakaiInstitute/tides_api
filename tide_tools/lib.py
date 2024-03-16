import re
from datetime import datetime, timedelta

import arrow
import requests
from pydantic import BaseModel
from scipy.interpolate import InterpolatedUnivariateSpline


class TimeSeries(BaseModel):
    id: str
    code: str
    nameEn: str
    nameFr: str
    phenomenonId: str
    owner: str


class Station(BaseModel):
    id: str
    code: str
    officialName: str
    latitude: float
    longitude: float
    type: str
    timeSeries: list[TimeSeries]


class TideMeasurement(BaseModel):
    eventDate: datetime
    value: float
    qcFlagCode: int
    timeSeriesId: str


def get_station_options() -> list[Station]:
    station_req = requests.get(
        "https://api.iwls-sine.azure.cloud-nuage.dfo-mpo.gc.ca/api/v1/stations"
    )
    if station_req.ok:
        station_data = station_req.json()
        return [Station.parse_obj(d) for d in station_data]
    else:
        raise Exception("Failed to get station options")


def get_station_by_name(station_name: str | re.Pattern) -> Station | None:
    stations = get_station_options()
    for station in stations:
        if re.match(station_name, station.officialName):
            return station
    return None


def get_tides_between_dates(
    station: Station, start: datetime, end: datetime, chunk_req_size: int = 30
) -> list[TideMeasurement]:
    if "wlp" not in [ts.code for ts in station.timeSeries]:
        raise ValueError("Station does not have water level data")
    if end <= start:
        raise ValueError("End date must be after start date")

    num_days = (end - start).days + 1

    date_windows = []
    for i in range(0, num_days, chunk_req_size):
        chunk_start = start + timedelta(days=i)
        chunk_end = min(end, chunk_start + timedelta(days=chunk_req_size, minutes=-15))
        start_dt = (
            arrow.get(chunk_start)
            .to("UTC")
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )
        end_dt = (
            arrow.get(chunk_end)
            .to("UTC")
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z")
        )

        date_windows.append((start_dt, end_dt))

    tz = arrow.get(start).tzinfo

    tides = []
    for start_dt, end_dt in date_windows:
        req = requests.get(
            f"https://api.iwls-sine.azure.cloud-nuage.dfo-mpo.gc.ca/api/v1/stations/{station.id}/data?time-series-code=wlp&from={start_dt}&to={end_dt}&resolution=FIFTEEN_MINUTES"
        )
        if not req.ok:
            raise Exception(f"Failed to get tides: {req.text}")
        tides.extend([TideMeasurement.parse_obj(t) for t in req.json()])

    # Convert tz back
    for i, t in enumerate(tides):
        tides[i].eventDate = arrow.get(t.eventDate).to(tz).datetime

    return tides


tide_event = tuple[datetime, float]


def get_hilo_tides(
    tides: list[TideMeasurement],
) -> tuple[list[tide_event], list[tide_event]]:
    """Return a list of high tide events and a list of low tide events."""
    timestamps = [arrow.get(d.eventDate).timestamp() for d in tides]
    heights = [d.value for d in tides]

    f = InterpolatedUnivariateSpline(timestamps, heights, k=4)
    fp = f.derivative()
    rts = fp.roots()

    hilo_heights = [f(rt) for rt in rts]
    hilo_datetimes = [arrow.get(rt).to("UTC").datetime for rt in rts]

    is_low_tide = [
        fp((t - timedelta(minutes=1)).timestamp()) < 0 for t in hilo_datetimes
    ]

    low_tides = [
        (t, h)
        for t, h, is_low in zip(hilo_datetimes, hilo_heights, is_low_tide)
        if is_low
    ]
    high_tides = [
        (t, h)
        for t, h, is_low in zip(hilo_datetimes, hilo_heights, is_low_tide)
        if not is_low
    ]

    return high_tides, low_tides


def split_tides_by_datetimes(
    tides: list[TideMeasurement], datetimes: list[datetime]
) -> list[list[TideMeasurement]]:
    """Split the tide array by the given datetimes."""
    tide_partitions = []
    prev_idx = 0
    for dt in datetimes:
        try:
            idx = next(i for i, t in enumerate(tides) if t.eventDate > dt)
        except StopIteration:
            idx = len(tides)
        if idx == prev_idx:
            continue

        tide_partitions.append(tides[prev_idx:idx])
        prev_idx = idx

    # Add last partition
    tide_partitions.append(tides[prev_idx:])

    return tide_partitions


def find_tide_windows(
    tides: list[TideMeasurement], max_tide_height: float
) -> list[tuple[datetime | None, datetime | None]]:
    high_tides, low_tides = get_hilo_tides(tides)

    # Split the tide array by high tide times
    tide_partitions = split_tides_by_datetimes(tides, [t[0] for t in high_tides])

    windows = []
    for partition in tide_partitions:
        timestamps = [arrow.get(d.eventDate).timestamp() for d in partition]
        heights = [d.value for d in partition]

        if len(timestamps) <= 3:
            windows.append((None, None))
            continue

        f = InterpolatedUnivariateSpline(
            timestamps, [(h - max_tide_height) for h in heights], k=3
        )
        rts = f.roots()
        dts = [arrow.get(rt).datetime for rt in rts]

        is_window_start = [f((t - timedelta(minutes=1)).timestamp()) > 0 for t in dts]

        if len(dts) == 2:
            ws, we = dts
        elif len(dts) == 1 and is_window_start[0]:
            ws, we = dts[0], None
        elif len(dts) == 1 and not is_window_start[0]:
            ws, we = None, dts[0]
        else:
            ws, we = None, None

        windows.append((ws, we))

    return windows
