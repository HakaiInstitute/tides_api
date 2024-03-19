from datetime import datetime

import arrow
import astral
import astral.sun

from tide_tools.lib import (
    get_station_by_name,
    get_tides_between_dates,
    get_hilo_tides,
    find_tide_windows,
)


def format_time(datetime, tz="America/Vancouver") -> str | None:
    if datetime is None:
        return None
    return arrow.get(datetime).to(tz).isoformat(timespec="seconds")


def hours_time_difference(t2: datetime, t1: datetime) -> str:
    if t1 is None or t2 is None:
        return None
    return round((t2 - t1).seconds / 60 / 60, 2)


def get_data_sheet(
    station_name: str,
    start_date: datetime,
    end_date: datetime,
    tz: str = "America/Vancouver",
    tide_windows: list[float] = None,
):
    if tide_windows is None:
        tide_windows = [1.5, 2.0]
    station = get_station_by_name(station_name)
    tides = get_tides_between_dates(station, start_date, end_date)

    high_tides, low_tides = get_hilo_tides(tides)

    windows_xm = [find_tide_windows(tides, tw) for tw in tide_windows]

    if len(low_tides) and len(high_tides) and high_tides[0][0] < low_tides[0][0]:
        # Missing low tide in first partition, drop other partitions
        windows_xm = [w[1:] for w in windows_xm]

    sheet = []
    for i, lt in enumerate(low_tides):
        date = arrow.get(lt[0]).to(tz).date()

        obs = astral.Observer(station.latitude, station.longitude)
        try:
            sunrise = astral.sun.sunrise(obs, date)
        except ValueError:
            sunrise = None
        try:
            noon = astral.sun.noon(obs, date)
        except ValueError:
            noon = None
        try:
            sunset = astral.sun.sunset(obs, date)
        except ValueError:
            sunset = None

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
                        start=format_time(wvi[i][0], tz),
                        end=format_time(wvi[i][1], tz),
                        hours=hours_time_difference(wvi[i][1], wvi[i][0]),
                    ),
                )
                for wk, wvi in zip(tide_windows, windows_xm)
            ),
        )
        sheet.append(row)

    return sheet, tides


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

    # print(len(high_tides), len(low_tides), len(windows_2m), len(windows_1p5m))
