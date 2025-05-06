from datetime import datetime, timedelta, date, tzinfo

import arrow
import astral
import astral.sun
import dateutil.tz
from scipy.interpolate import InterpolatedUnivariateSpline

from tide_api.models import (
    FullStation,
    FullTideMeasurement,
    TideWindow,
    TideMeasurement,
    TideEvent,
)
from tide_api.utils import chs_api


class StationTides:
    def __init__(self, station: FullStation, start_date: date, end_date: date, tz: str):
        self.tz = dateutil.tz.gettz(tz)
        start_date = arrow.Arrow.fromdate(start_date, self.tz)
        end_date = arrow.Arrow.fromdate(end_date, self.tz)

        if end_date <= start_date:
            raise ValueError("End date must be after start date")

        self.station = station
        self.start_date = start_date
        self.end_date = end_date

        # These are lazy loaded by the properties below
        self._tides = None
        self._high_tides = None
        self._low_tides = None

    @classmethod
    def from_name(cls, station_name: str, *args, **kwargs):
        return cls(FullStation.from_name(station_name), *args, **kwargs)

    @property
    def tides(self) -> list[FullTideMeasurement]:
        if self._tides is None:
            self._tides = self._get_tides()
        return self._tides

    @property
    def timestamps(self) -> list[float]:
        return [arrow.get(d.time).timestamp() for d in self.tides]

    @property
    def heights(self) -> list[float]:
        return [d.height for d in self.tides]

    def get_tide_at_time(self, time: datetime) -> TideMeasurement:
        if time < self.start_date or time > self.end_date:
            raise ValueError("Time is out of range")
            
        # Check if there are enough data points for interpolation
        if len(self.timestamps) < 4:  # Need at least k+1 points for k=3 spline
            # If not enough points, use the closest point's height
            if len(self.timestamps) == 0:
                raise ValueError("No tide data available for interpolation")
                
            # Find closest tide measurement
            closest_idx = min(range(len(self.timestamps)), 
                             key=lambda i: abs(self.timestamps[i] - time.timestamp()))
            height = self.heights[closest_idx]
        else:
            # Use spline interpolation when enough data points are available
            f = InterpolatedUnivariateSpline(self.timestamps, self.heights, k=min(3, len(self.timestamps)-1))
            height = f(time.timestamp())

        return TideMeasurement(time=time, height=height)

    @property
    def high_tides(self) -> list[TideMeasurement]:
        if self._high_tides is None:
            self._high_tides, self._low_tides = self._get_hilo_tides()
        return self._high_tides

    @property
    def low_tides(self) -> list[TideMeasurement]:
        if self._low_tides is None:
            self._high_tides, self._low_tides = self._get_hilo_tides()
        return self._low_tides

    @property
    def _low_tide_partitions(self) -> list[list[FullTideMeasurement]]:
        return split_tides_by_datetimes(self.tides, [t.time for t in self.high_tides])

    def _get_hilo_tides(self) -> tuple[list[TideMeasurement], list[TideMeasurement]]:
        # Need at least k+1 points for k=4 spline
        if len(self.timestamps) < 5:
            # If insufficient data points, return empty lists
            return [], []

        # Determine appropriate k value based on number of data points
        k = min(4, len(self.timestamps) - 1)
        
        f = InterpolatedUnivariateSpline(self.timestamps, self.heights, k=k)
        fp = f.derivative()
        rts = fp.roots()

        hilo_heights = [f(rt) for rt in rts]
        hilo_datetimes = [arrow.get(rt).to(self.tz).datetime for rt in rts]

        is_low_tide = [
            fp((t - timedelta(minutes=15)).timestamp())
            < 0
            < fp((t + timedelta(minutes=15)).timestamp())
            for t in hilo_datetimes
        ]
        is_high_tide = [
            fp((t - timedelta(minutes=15)).timestamp())
            > 0
            > fp((t + timedelta(minutes=15)).timestamp())
            for t in hilo_datetimes
        ]

        low_tides = [
            TideMeasurement(time=t, height=h)  # Changed value to height to match model fields
            for t, h, is_low in zip(hilo_datetimes, hilo_heights, is_low_tide)
            if is_low
        ]
        high_tides = [
            TideMeasurement(time=t, height=h)  # Changed value to height to match model fields
            for t, h, is_high in zip(hilo_datetimes, hilo_heights, is_high_tide)
            if is_high
        ]

        return high_tides, low_tides

    def _get_tides(self, chunk_req_size: int = 30) -> list[FullTideMeasurement]:
        if "wlp" not in [ts.code for ts in self.station.time_series]:
            raise ValueError("Station does not have water level data")

        tides = []
        for chunk_start, chunk_end in arrow.Arrow.interval(
            "day",
            self.start_date.datetime,
            self.end_date.shift(days=-1).datetime,
            interval=chunk_req_size,
        ):
            start_dt = (
                chunk_start.to("UTC")
                .isoformat(timespec="seconds")
                .replace("+00:00", "Z")
            )
            end_dt = (
                chunk_end.to("UTC").isoformat(timespec="seconds").replace("+00:00", "Z")
            )

            req = chs_api.get(
                f"/stations/{self.station.id}/data?time-series-code=wlp&from={start_dt}&to={end_dt}&resolution=FIFTEEN_MINUTES"
            )
            if not req.ok:
                raise Exception(f"Failed to get tides: {req.text}")
            tides.extend([FullTideMeasurement.model_validate(t) for t in req.json()])

        # Convert tz back
        for i, t in enumerate(tides):
            tides[i].time = arrow.get(t.time).to(self.tz).datetime

        return tides

    def detect_tide_windows(self, max_tide_height: float) -> list[TideWindow]:
        windows = []
        for partition in self._low_tide_partitions:
            timestamps = [arrow.get(d.time).timestamp() for d in partition]
            heights = [d.height for d in partition]

            if len(timestamps) <= 3:
                windows.append(TideWindow(start=None, end=None))
                continue

            # Determine appropriate k value based on number of data points
            k = min(3, len(timestamps) - 1)
            
            f = InterpolatedUnivariateSpline(
                timestamps, [(h - max_tide_height) for h in heights], k=k
            )
            rts = f.roots()
            dts = [arrow.get(rt).datetime for rt in rts]

            is_window_start = [
                f((t - timedelta(minutes=1)).timestamp()) > 0 for t in dts
            ]

            ws, we = None, None
            if len(dts) == 2:
                ws = arrow.get(dts[0]).to(self.tz).datetime
                we = arrow.get(dts[1]).to(self.tz).datetime
            elif len(dts) == 1 and is_window_start[0]:
                ws = arrow.get(dts[0]).to(self.tz).datetime
            elif len(dts) == 1 and not is_window_start[0]:
                we = arrow.get(dts[0]).to(self.tz).datetime

            window = TideWindow(start=ws, end=we)
            windows.append(window)

        return windows

    @property
    def _observer(self) -> astral.Observer:
        return astral.Observer(self.station.latitude, self.station.longitude)

    def get_sunrise(self, date_: date) -> datetime | None:
        try:
            return (
                arrow.get(astral.sun.sunrise(self._observer, date_))
                .to(self.tz)
                .datetime
            )
        except ValueError:
            return None

    def get_noon(self, date_: date) -> datetime | None:
        try:
            return (
                arrow.get(astral.sun.noon(self._observer, date_)).to(self.tz).datetime
            )
        except ValueError:
            return None

    def get_sunset(self, date_: date) -> datetime | None:
        try:
            return (
                arrow.get(astral.sun.sunset(self._observer, date_)).to(self.tz).datetime
            )
        except ValueError:
            return None

    def low_tide_events(
        self,
        tz: str,
        tide_windows: list[float] = None,
    ) -> list[TideEvent]:
        if tide_windows is None:
            tide_windows = []
        windows_xm = list(map(self.detect_tide_windows, tide_windows))

        low_tides = self.low_tides
        high_tides = self.high_tides

        if (
            len(low_tides)
            and len(high_tides)
            and high_tides[0].time < low_tides[0].time
        ):
            # Missing low tide in first partition, drop other partitions
            windows_xm = [w[1:] for w in windows_xm]

        events = []
        for i, lt in enumerate(low_tides):
            date_ = arrow.get(lt.time).to(tz).date()
            row = dict(
                low_tide_date=date_,
                low_tide_height_m=round(float(lt.height), 2),
                low_tide_time=format_time(lt.time, tz),
                sunrise=format_time(self.get_sunrise(date_), tz),
                noon=format_time(self.get_noon(date_), tz),
                sunset=format_time(self.get_sunset(date_), tz),
                windows=dict(
                    (
                        f"{wk}m",
                        dict(
                            start=format_time(wvi[i].start, tz),
                            end=format_time(wvi[i].end, tz),
                            hours=wvi[i].hours,
                        ),
                    )
                    for wk, wvi in zip(tide_windows, windows_xm)
                ),
            )
            events.append(TideEvent.parse_obj(row))
        return events


def split_tides_by_datetimes(
    tides: list[FullTideMeasurement], datetimes: list[datetime]
) -> list[list[FullTideMeasurement]]:
    """Split the tide array by the given datetimes."""
    tide_partitions = []
    prev_idx = 0
    for dt in datetimes:
        try:
            idx = next(i for i, t in enumerate(tides) if t.time > dt)
        except StopIteration:
            idx = len(tides)
        if idx == prev_idx:
            continue

        tide_partitions.append(tides[prev_idx:idx])
        prev_idx = idx

    # Add last partition
    tide_partitions.append(tides[prev_idx:])

    return tide_partitions


def format_time(dt: datetime, tz: str | tzinfo) -> str | None:
    if dt is None:
        return None
    return arrow.get(dt).to(tz).isoformat(timespec="seconds")


def expand_windows(sheet: list[TideEvent]) -> list[dict]:
    sheet = [t.dict() for t in sheet]
    for row in sheet:
        for k, v in row["windows"].items():
            row[f"window_start_{k}"] = v["start"]
            row[f"window_end_{k}"] = v["end"]
            row[f"hours_under_{k}"] = v["hours"]
        del row["windows"]
    return sheet


if __name__ == "__main__":
    import polars as pl

    station_tides = StationTides.from_name(
        "Adams Harbour",
        datetime(2024, 6, 1),
        datetime(2024, 6, 5),
        tz="America/Vancouver",
    )
    events = station_tides.low_tide_events(tide_windows=[1.5, 2.0])
    df = pl.DataFrame(expand_windows(events))
    print(df)
