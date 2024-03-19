import io
from datetime import datetime, timedelta
from typing import Optional

import arrow
import dateutil.tz
import polars as pl
from fastapi import APIRouter, HTTPException
from fastapi.params import Path, Query
from matplotlib import pyplot as plt, dates as mdates
from polars import selectors as cs

from tide_api.consts import ISO8601_START_EXAMPLES, ISO8601_END_EXAMPLES
from tide_api.lib import get_data_sheet, expand_windows
from tide_api.models import (
    TideEvent,
)
from tide_api.responses import PNGResponse, CSVResponse
from tide_api.stations import StationName

router = APIRouter(
    prefix="/tides/events",
    tags=["Tide Events"],
)


def get_tides(
    station_name: StationName,
    start_date: datetime,
    end_date: datetime,
    tz: Optional[str] = "America/Vancouver",
    tide_window: list[float] = None,
):
    if tide_window is None:
        tide_window = []
    start_date = arrow.get(start_date, tz).datetime
    end_date = arrow.get(end_date, tz).datetime

    if end_date <= start_date:
        raise ValueError("End date must be after start date")

    return get_data_sheet(station_name.value, start_date, end_date, tz, tide_window)


@router.get(
    "/{station_name}.png",
    response_class=PNGResponse,
    responses={
        200: {
            "description": "PNG image of tide events",
            "content": {
                "image/png": {
                    "schema": {"type": "string", "format": "binary"},
                }
            },
        }
    },
)
def graph_24h_tide_for_station_on_date(
    station_name: StationName = Path(..., description="The name of the station"),
    date: datetime = Query(
        ...,
        description="The start date and time to plot in ISO8601 format",
        openapi_examples=ISO8601_START_EXAMPLES,
        default_factory=lambda: arrow.now("America/Vancouver").date(),
    ),
    tz: Optional[str] = Query("America/Vancouver", description="The timezone to use"),
    tide_window: list[float] = Query(
        [],
        description="Tide windows of interest, in meters",
    ),
    show_sunrise_sunset: bool = Query(
        True, description="Show sunrise and sunset times"
    ),
    show_current_time: bool = Query(True, description="Show the current time"),
    width: int = Query(640, description="Width of the plot in pixels"),
    height: int = Query(480, description="Height of the plot in pixels"),
    dpi: int = Query(100, description="DPI of the plot"),
):
    start_date = arrow.get(date, tz).datetime
    end_date = start_date + timedelta(days=1)
    sheet, tides = get_tides(station_name, start_date, end_date, tz, tide_window)
    if isinstance(sheet, HTTPException):
        raise sheet
    sheet = [TideEvent.parse_obj(t) for t in sheet]

    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    ax1 = fig.subplots()
    ax1.grid(axis="y")

    plt.xticks(rotation=90)
    plt.ylabel("Tide Height (m)")
    plt.xlabel("Time")

    plt.plot(
        [arrow.get(t.time, tz).datetime for t in tides],
        [t.value for t in tides],
        c="gray",
    )
    plt.title(f"Tides for {station_name.value} on {start_date.date()}")
    plt.xlim(start_date, end_date)

    x_ticks = []
    for row in sheet:
        d = arrow.get(row.low_tide_time).datetime
        plt.axvline(d, c="r", linestyle="dotted")
        x_ticks.append(d)
        for i, (wk, wv) in enumerate(row.windows.items()):
            c = ["b", "g", "c", "m", "k"][i % 5]
            ws, we = wv.start, wv.end
            if ws:
                d = arrow.get(ws).datetime
                plt.axvline(d, c=c, linestyle="dotted")
                x_ticks.append(d)
            if we:
                d = arrow.get(we).datetime
                plt.axvline(d, c=c, linestyle="dotted")
                x_ticks.append(d)
    if row.sunrise and show_sunrise_sunset:
        d = arrow.get(row.sunrise).datetime
        plt.axvline(d, c="y", linestyle="dashed")
        x_ticks.append(d)
    if row.sunset and show_sunrise_sunset:
        d = arrow.get(row.sunset).datetime
        plt.axvline(d, c="y", linestyle="dashed")
        x_ticks.append(d)
    if show_current_time:
        d = arrow.now(tz).datetime
        if start_date < d < end_date:
            plt.axvline(d, c="k", linestyle="dashed")
            x_ticks.append(d)

    ax1.set_xticks(sorted(list(set(x_ticks))))
    ax1.xaxis.set_major_formatter(
        mdates.DateFormatter("%H:%M", tz=dateutil.tz.gettz(tz))
    )
    plt.tight_layout()

    with io.BytesIO() as buf:
        plt.savefig(buf, format="png")
        buf.seek(0)
        png = buf.getvalue()

    return PNGResponse(content=png)


@router.get(
    "/{station_name}.csv",
    description="Get tide windows for a given station between two dates as a CSV file",
    response_class=CSVResponse,
    responses={
        200: {
            "description": "CSV file of tide windows and events",
            "content": {
                "text/csv": {
                    "schema": {"type": "string"},
                    "example": """low_tide_date,low_tide_height_m,low_tide_time,sunrise,noon,sunset
2024-08-01,0.77,2024-08-01T05:49:42-07:00,2024-08-01T05:56:56-07:00,2024-08-01T13:38:45-07:00,2024-08-01T21:19:27-07:00
2024-08-01,2.14,2024-08-01T17:37:48-07:00,2024-08-01T05:56:56-07:00,2024-08-01T13:38:45-07:00,2024-08-01T21:19:27-07:00
2024-08-02,0.61,2024-08-02T06:40:43-07:00,2024-08-02T05:58:27-07:00,2024-08-02T13:38:41-07:00,2024-08-02T21:17:45-07:00
""",
                },
            },
        },
    },
)
def get_tides_for_station_between_dates_as_csv(
    station_name: StationName = Path(..., description="The name of the station"),
    start_date: datetime = Query(
        ...,
        description="The start date in ISO8601 format",
        openapi_examples=ISO8601_START_EXAMPLES,
        default_factory=lambda: arrow.now("America/Vancouver").date(),
    ),
    end_date: datetime = Query(
        ...,
        description="The end date in ISO8601 format",
        openapi_examples=ISO8601_END_EXAMPLES,
        default_factory=lambda: (
            arrow.now("America/Vancouver") + timedelta(weeks=4)
        ).date(),
    ),
    tz: Optional[str] = Query("America/Vancouver", description="The timezone to use"),
    tide_window: list[float] = Query(
        [],
        description="Tide windows to find (in meters)",
    ),
    excel_date_format: bool = Query(
        False,
        description="Export dates in Excel decimal format instead of ISO8601 strings",
    ),
):
    sheet, _ = get_tides(station_name, start_date, end_date, tz, tide_window)
    if isinstance(sheet, HTTPException):
        raise sheet

    df = pl.DataFrame(expand_windows(sheet))
    if excel_date_format:
        # Convert date time fields
        df = df.with_columns(
            [
                cs.matches("low_tide_time|sunrise|noon|sunset|window_.*")
                .cast(pl.Datetime)
                .dt.timestamp(time_unit="ms")
                .truediv(24 * 60 * 60 * 1000)
                .add(25569)
            ]
        )

    fname_station = station_name.value.lower().replace(" ", "_")
    fname_range = f"{start_date.date()}_to_{end_date.date()}"
    return CSVResponse(
        content=df.to_pandas().to_csv(index=False),
        headers={
            "Content-Disposition": f"attachment; "
            f"filename={fname_station}_tides_{fname_range}.csv"
        },
    )


@router.get("/{station_name}")
def get_tides_for_station_between_dates(
    station_name: StationName = Path(..., description="The name of the station"),
    start_date: datetime = Query(
        ...,
        description="The start date in ISO8601 format",
        openapi_examples=ISO8601_START_EXAMPLES,
        default_factory=lambda: arrow.now("America/Vancouver").date(),
    ),
    end_date: datetime = Query(
        ...,
        description="The end date in ISO8601 format",
        openapi_examples=ISO8601_END_EXAMPLES,
        default_factory=lambda: (
            arrow.now("America/Vancouver") + timedelta(weeks=4)
        ).date(),
    ),
    tz: Optional[str] = Query("America/Vancouver", description="The timezone to use"),
    tide_window: list[float] = Query(
        [],
        description="Tide windows to find (in meters)",
    ),
) -> list[TideEvent]:
    try:
        sheet, _ = get_tides(station_name, start_date, end_date, tz, tide_window)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    sheet = [TideEvent.parse_obj(t) for t in sheet]
    return sheet
