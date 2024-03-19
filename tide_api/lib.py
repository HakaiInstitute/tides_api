from datetime import datetime, timedelta

import arrow
import astral
import astral.sun
import requests
from scipy.interpolate import InterpolatedUnivariateSpline

from tide_api.models import FullStation, FullTideMeasurement, TideWindow
from tide_api.stations import get_station_by_name


class StationTides:
    def __init__(self, station: FullStation, start_date: datetime, end_date: datetime):
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
        return cls(get_station_by_name(station_name), *args, **kwargs)

    @property
    def tides(self):
        if self._tides is None:
            self._tides = self._get_tides()
        return self._tides

    @property
    def timestamps(self):
        return [arrow.get(d.time).timestamp() for d in self.tides]

    @property
    def heights(self):
        return [d.value for d in self.tides]

    @property
    def high_tides(self):
        if self._high_tides is None:
            self._high_tides, self._low_tides = self._get_hilo_tides()
        return self._high_tides

    @property
    def low_tides(self):
        if self._low_tides is None:
            self._high_tides, self._low_tides = self._get_hilo_tides()
        return self._low_tides

    @property
    def _low_tide_partitions(self):
        return split_tides_by_datetimes(self.tides, [t[0] for t in self.high_tides])

    def _get_hilo_tides(self):
        f = InterpolatedUnivariateSpline(self.timestamps, self.heights, k=4)
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

    def _get_tides(self, chunk_req_size: int = 30) -> list[FullTideMeasurement]:
        if "wlp" not in [ts.code for ts in self.station.time_series]:
            raise ValueError("Station does not have water level data")

        num_days = (self.end_date - self.start_date).days + 1

        date_windows = []
        for i in range(0, num_days, chunk_req_size):
            chunk_start = self.start_date + timedelta(days=i)
            chunk_end = min(
                self.end_date, chunk_start + timedelta(days=chunk_req_size, minutes=-15)
            )
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

        tz = arrow.get(self.start_date).tzinfo

        tides = []
        for start_dt, end_dt in date_windows:
            req = requests.get(
                f"https://api.iwls-sine.azure.cloud-nuage.dfo-mpo.gc.ca/api/v1/stations/{self.station.id}/data?time-series-code=wlp&from={start_dt}&to={end_dt}&resolution=FIFTEEN_MINUTES"
            )
            if not req.ok:
                raise Exception(f"Failed to get tides: {req.text}")
            tides.extend([FullTideMeasurement.parse_obj(t) for t in req.json()])

        # Convert tz back
        for i, t in enumerate(tides):
            tides[i].time = arrow.get(t.time).to(tz).datetime

        return tides

    def detect_tide_windows(self, max_tide_height: float) -> list[TideWindow]:
        windows = []
        for partition in self._low_tide_partitions:
            timestamps = [arrow.get(d.time).timestamp() for d in partition]
            heights = [d.value for d in partition]

            if len(timestamps) <= 3:
                windows.append((None, None))
                continue

            f = InterpolatedUnivariateSpline(
                timestamps, [(h - max_tide_height) for h in heights], k=3
            )
            rts = f.roots()
            dts = [arrow.get(rt).datetime for rt in rts]

            is_window_start = [
                f((t - timedelta(minutes=1)).timestamp()) > 0 for t in dts
            ]

            if len(dts) == 2:
                ws, we = dts
            elif len(dts) == 1 and is_window_start[0]:
                ws, we = dts[0], None
            elif len(dts) == 1 and not is_window_start[0]:
                ws, we = None, dts[0]
            else:
                ws, we = None, None

            window = TideWindow(start=ws, end=we)
            windows.append(window)

        return windows

    @property
    def _observer(self) -> astral.Observer:
        return astral.Observer(self.station.latitude, self.station.longitude)

    def get_sunrise(self, date: datetime) -> datetime | None:
        try:
            return astral.sun.sunrise(self._observer, date)
        except ValueError:
            return None

    def get_noon(self, date: datetime) -> datetime | None:
        try:
            return astral.sun.noon(self._observer, date)
        except ValueError:
            return None

    def get_sunset(self, date: datetime) -> datetime | None:
        try:
            return astral.sun.sunset(self._observer, date)
        except ValueError:
            return None


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


def format_time(datetime, tz="America/Vancouver") -> str | None:
    if datetime is None:
        return None
    return arrow.get(datetime).to(tz).isoformat(timespec="seconds")


def get_data_sheet(
    station_name: str,
    start_date: datetime,
    end_date: datetime,
    tz: str = "America/Vancouver",
    tide_windows: list[float] = None,
):
    if tide_windows is None:
        tide_windows = []

    station_tides = StationTides.from_name(station_name, start_date, end_date)
    windows_xm = list(map(station_tides.detect_tide_windows, tide_windows))

    if (
        len(station_tides.low_tides)
        and len(station_tides.high_tides)
        and station_tides.high_tides[0][0] < station_tides.low_tides[0][0]
    ):
        # Missing low tide in first partition, drop other partitions
        windows_xm = [w[1:] for w in windows_xm]

    sheet = []
    for i, lt in enumerate(station_tides.low_tides):
        date = arrow.get(lt[0]).to(tz).date()
        sunrise = station_tides.get_sunrise(date)
        noon = station_tides.get_noon(date)
        sunset = station_tides.get_sunset(date)

        row = dict(
            low_tide_date=date,
            low_tide_height_m=round(float(lt[1]), 2),
            low_tide_time=format_time(lt[0], tz),
            sunrise=format_time(sunrise, tz),
            noon=format_time(noon, tz),
            sunset=format_time(sunset, tz),
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
        sheet.append(row)

    return sheet, station_tides.tides


def expand_windows(sheet):
    for row in sheet:
        for k, v in row["windows"].items():
            row[f"window_start_{k}"] = v["start"]
            row[f"window_end_{k}"] = v["end"]
            row[f"hours_under_{k}"] = v["hours"]
        del row["windows"]
    return sheet


if __name__ == "__main__":
    import polars as pl

    sheet, _ = get_data_sheet(
        "Adams Harbour",
        datetime(2024, 6, 1),
        datetime(2024, 6, 5),
        tide_windows=[1.5, 2.0],
    )
    df = pl.DataFrame(expand_windows(sheet))
    print(df)
