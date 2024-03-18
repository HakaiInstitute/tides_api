import enum
import io
import os
from datetime import datetime, date, timedelta
from typing import Optional

import arrow
import dateutil.tz
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import polars as pl
from fastapi import FastAPI, HTTPException
from fastapi.params import Path, Query
from fastapi.responses import RedirectResponse, PlainTextResponse
from pydantic import BaseModel, create_model
from starlette.responses import Response
import polars.selectors as cs
from tide_tools.get_tide_sheet import get_data_sheet, expand_windows
from tide_tools.lib import get_station_options

app = FastAPI(
    title="Tide Window API",
    description="API to get tide windows for a given station between two dates",
    version="0.1.0",
    root_path=os.getenv("ROOT_PATH", ""),
    openapi_tags=[
        {
            "name": "Stations",
            "description": "Get information about stations available in the API",
        },
        {
            "name": "Tides",
            "description": "Get tide windows for a given station between two dates",
        },
    ],
)
stations = list(
    filter(
        lambda s: any([t.code == "wlp" for t in s.timeSeries]),
        sorted(get_station_options(), key=lambda s: s.officialName),
    )
)
station_names = [s.officialName for s in stations]
StationName = enum.Enum("StationName", dict([(s, s) for s in sorted(station_names)]))

iso8601_start_examples = {
    "date": {
        "summary": "Date (August 1, 2024)",
        "value": "2024-08-01",
    },
    "datetime": {
        "summary": "Date with time (August 1, 2024 at 1:30 PM)",
        "value": "2024-08-01T13:30:00",
    },
}

iso8601_end_examples = {
    "date": {
        "summary": "Date (August 3, 2024)",
        "value": "2024-08-03",
    },
    "datetime": {
        "summary": "Date with time (August 3, 2024 at 1:30 PM)",
        "value": "2024-08-03T13:30:00",
    },
}


class StationRead(BaseModel):
    name: str
    latitude: float
    longitude: float


class Window(BaseModel):
    start: Optional[datetime]
    end: Optional[datetime]
    hours: Optional[float]


class TideWindowRead(BaseModel):
    low_tide_date: date
    low_tide_height_m: float
    low_tide_time: datetime
    sunrise: Optional[datetime]
    noon: Optional[datetime]
    sunset: Optional[datetime]
    windows: dict[str, Window] = {}


def make_tide_window_schema(tide_window: list[float]):
    window_fields = []
    for tw in tide_window:
        window_fields.extend(
            [
                (f"window_start_{tw}m".replace(".", "_"), (Optional[datetime], ...)),
                (f"window_end_{tw}m".replace(".", "_"), (Optional[datetime], ...)),
                (f"hours_under_{tw}m".replace(".", "_"), (Optional[float], ...)),
            ]
        )
    window_fields = dict(window_fields)
    return create_model("TideWindowRead", __base__=TideWindowRead, **window_fields)


@app.get("/", include_in_schema=False)
def redirect_to_docs():
    # Redirect to docs
    return RedirectResponse(url=app.root_path + app.docs_url)


@app.get("/stations", tags=["Stations"])
def list_stations() -> list[StationRead]:
    return [
        StationRead(name=s.officialName, latitude=s.latitude, longitude=s.longitude)
        for s in stations
    ]


@app.get("/stations/{station_name}", tags=["Stations"])
def station_info_by_name(station_name: StationName) -> StationRead:
    station = next(s for s in stations if s.officialName == station_name.value)
    station = StationRead(
        name=station.officialName,
        latitude=station.latitude,
        longitude=station.longitude,
    )
    return station


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


@app.get("/tides/{station_name}.png", tags=["Tides"])
def graph_24h_tide_for_station_on_date(
    station_name: StationName = Path(..., description="The name of the station"),
    date: datetime = Query(
        ...,
        description="The start date and time to plot in ISO8601 format",
        openapi_examples=iso8601_start_examples,
        default_factory=lambda: datetime.now().date(),
    ),
    tz: Optional[str] = Query("America/Vancouver", description="The timezone to use"),
    tide_window: list[float] = Query(
        [],
        description="Tide windows of interest, in meters",
    ),
    show_sunrise_sunset: bool = Query(True, description="Show sunrise and sunset times"),
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
    sheet = [TideWindowRead.parse_obj(t) for t in sheet]

    fig = plt.figure(figsize=(width/dpi, height/dpi), dpi=dpi)
    ax1 = fig.subplots()
    ax1.grid(axis="y")

    plt.xticks(rotation=90)
    plt.ylabel("Tide Height (m)")
    plt.xlabel("Time")

    plt.plot(
        [arrow.get(t.eventDate, tz).datetime for t in tides],
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

    return Response(content=png, media_type="image/png")


@app.get("/tides/{station_name}.csv", tags=["Tides"])
def get_tides_for_station_between_dates_as_csv(
    station_name: StationName = Path(..., description="The name of the station"),
    start_date: datetime = Query(
        ...,
        description="The start date in ISO8601 format",
        openapi_examples=iso8601_start_examples,
        default_factory=lambda: datetime.now().date(),
    ),
    end_date: datetime = Query(
        ...,
        description="The end date in ISO8601 format",
        openapi_examples=iso8601_end_examples,
        default_factory=lambda: (datetime.now() + timedelta(weeks=4)).date(),
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

    with io.BytesIO() as f:
        df.write_csv(f)
        csv = f.getvalue()

    return PlainTextResponse(content=csv, media_type="text/csv")


@app.get("/tides/{station_name}", tags=["Tides"])
def get_tides_for_station_between_dates(
    station_name: StationName = Path(..., description="The name of the station"),
    start_date: datetime = Query(
        ...,
        description="The start date in ISO8601 format",
        openapi_examples=iso8601_start_examples,
        default_factory=lambda: datetime.now().date(),
    ),
    end_date: datetime = Query(
        ...,
        description="The end date in ISO8601 format",
        openapi_examples=iso8601_end_examples,
        default_factory=lambda: (datetime.now() + timedelta(weeks=4)).date(),
    ),
    tz: Optional[str] = Query("America/Vancouver", description="The timezone to use"),
    tide_window: list[float] = Query(
        [],
        description="Tide windows to find (in meters)",
    ),
) -> list[TideWindowRead]:
    try:
        sheet, _ = get_tides(station_name, start_date, end_date, tz, tide_window)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    sheet = [TideWindowRead.parse_obj(t) for t in sheet]
    return sheet


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
