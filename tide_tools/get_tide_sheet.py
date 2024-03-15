from datetime import datetime

import arrow
import polars as pl
import astral, astral.sun
from matplotlib import pyplot as plt

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
    plot: bool = False,
):
    station = get_station_by_name(station_name)
    tides = get_tides_between_dates(station, start_date, end_date)

    high_tides, low_tides = get_hilo_tides(tides)

    windows_2m = find_tide_windows(tides, 2)
    windows_1p5m = find_tide_windows(tides, 1.5)

    if len(low_tides) != len(windows_2m) and len(low_tides) and len(high_tides):
        if high_tides[0][0] < low_tides[0][0]:
            # Missing low tide in first partition, drop other partitions
            windows_2m = windows_2m[1:]
            windows_1p5m = windows_1p5m[1:]

    sheet = []
    for lt, w2, w1p5 in zip(low_tides, windows_2m, windows_1p5m):
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

        sheet.append(
            {
                "low_tide_date": date,
                "low_tide_height_m": round(float(lt[1]), 2),
                "low_tide_time": format_time(lt[0], tz),
                "sunrise": format_time(sunrise, tz),
                "noon": format_time(noon, tz),
                "sunset": format_time(sunset, tz),
                "window_start_2m": format_time(w2[0], tz),
                "window_start_1.5m": format_time(w1p5[0], tz),
                "window_end_1.5m": format_time(w1p5[1], tz),
                "window_end_2m": format_time(w2[1], tz),
                "hours_under_1.5m": hours_time_difference(w1p5[1], w1p5[0]),
                "hours_under_2m": hours_time_difference(w2[1], w2[0]),
            }
        )

    if plot:
        fig = plt.figure()
        ax1 = fig.subplots()
        ax1.grid(axis="y")
        # tilt x labels
        plt.xticks(rotation=30)

        plt.plot([t.eventDate for t in tides], [t.value for t in tides], c="gray")
        # ax1.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: ts2time(x)))
        for lt in low_tides:
            plt.axvline(lt[0], c="r", linestyle="dotted")

        # plt.axhline(2, c='b', linestyle='dotted')
        for ws, we in windows_2m:
            if ws:
                plt.axvline(ws, c="b", linestyle="dotted")
            if we:
                plt.axvline(we, c="b", linestyle="dotted")

        # plt.axhline(1.5, c='g', linestyle='dotted')
        for ws, we in windows_1p5m:
            if ws:
                plt.axvline(ws, c="g", linestyle="dotted")
            if we:
                plt.axvline(we, c="g", linestyle="dotted")

        plt.show()

    return sheet


if __name__ == "__main__":
    sheet = get_data_sheet(
        "Adams Harbour", datetime(2024, 6, 1), datetime(2024, 6, 5), plot=True
    )
    df = pl.DataFrame(sheet)
    print(df)

    # print(len(high_tides), len(low_tides), len(windows_2m), len(windows_1p5m))
