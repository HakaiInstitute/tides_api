import enum
import io
import os
from datetime import datetime, date
from typing import Optional

import arrow
import polars as pl
from fastapi import FastAPI, HTTPException
from fastapi.params import Path, Query
from fastapi.responses import RedirectResponse, PlainTextResponse
from pydantic import BaseModel

from tide_tools.get_tide_sheet import get_data_sheet
from tide_tools.lib import get_station_options, get_station_by_name

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

station_names = list(
    map(
        lambda s: s.officialName,
        filter(
            lambda s: any([t.code == "wlp" for t in s.timeSeries]),
            get_station_options(),
        ),
    )
)
StationName = enum.Enum("StationName", dict([(s, s) for s in sorted(station_names)]))


class StationRead(BaseModel):
    name: str
    latitude: float
    longitude: float


class TideWindowRead(BaseModel):
    low_tide_date: date
    low_tide_height_m: float
    low_tide_time: datetime
    sunrise: Optional[datetime]
    noon: Optional[datetime]
    sunset: Optional[datetime]
    window_start_2m: Optional[datetime]
    window_start_1p5m: Optional[datetime]
    window_end_1p5m: Optional[datetime]
    window_end_2m: Optional[datetime]
    hours_under_1p5m: Optional[float]
    hours_under_2m: Optional[float]


@app.get("/", include_in_schema=False)
def redirect_to_docs():
    # Redirect to docs
    return RedirectResponse(url=app.root_path + app.docs_url)


@app.get("/stations", tags=["Stations"])
def list_stations() -> list[StationRead]:
    stations = get_station_options()
    stations = filter(lambda s: any(t.code == "wlp" for t in s.timeSeries), stations)
    stations = [
        StationRead(name=s.officialName, latitude=s.latitude, longitude=s.longitude)
        for s in stations
    ]
    return stations


@app.get("/stations/{station_name}", tags=["Stations"])
def station_info_by_name(station_name: StationName) -> StationRead:
    station = get_station_by_name(station_name.value)
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
        tz: Optional[str] = Query("America/Vancouver"),
):
    start_date = arrow.get(start_date).datetime
    end_date = arrow.get(end_date).datetime

    try:
        arrow.get(tzinfo=tz)
    except arrow.parser.ParserError:
        return HTTPException(status_code=400, detail="Invalid timezone")

    if start_date > end_date:
        return HTTPException(
            status_code=400, detail="start_date must be before end_date"
        )

    return get_data_sheet(station_name.value, start_date, end_date, tz)


@app.get("/tides/{station_name}.csv", tags=["Tides"])
def get_tides_for_station_between_dates_as_csv(
        station_name: StationName = Path(..., description="The name of the station"),
        start_date: datetime = Query(..., description="The start date in ISO8601 format"),
        end_date: datetime = Query(..., description="The end date in ISO8601 format"),
        tz: Optional[str] = Query("America/Vancouver", description="The timezone to use"),
        excel_date_format: bool = Query(
            False, description="Convert to Excel date format instead of ISO8601"
        ),
):
    sheet = get_tides(station_name, start_date, end_date, tz)
    if isinstance(sheet, HTTPException):
        raise sheet

    df = pl.DataFrame(sheet)
    if excel_date_format:
        df = df.with_columns(
            [
                pl.col("low_tide_time")
                .cast(pl.Datetime).dt.timestamp(time_unit="ms")
                .truediv(24 * 60 * 60 * 1000).add(25569),
                pl.col("sunrise")
                .cast(pl.Datetime).dt.timestamp(time_unit="ms")
                .truediv(24 * 60 * 60 * 1000).add(25569),
                pl.col("noon")
                .cast(pl.Datetime).dt.timestamp(time_unit="ms")
                .truediv(24 * 60 * 60 * 1000).add(25569),
                pl.col("sunset")
                .cast(pl.Datetime).dt.timestamp(time_unit="ms")
                .truediv(24 * 60 * 60 * 1000).add(25569),
                pl.col("window_start_2m")
                .cast(pl.Datetime).dt.timestamp(time_unit="ms")
                .truediv(24 * 60 * 60 * 1000).add(25569),
                pl.col("window_start_1.5m")
                .cast(pl.Datetime).dt.timestamp(time_unit="ms")
                .truediv(24 * 60 * 60 * 1000).add(25569),
                pl.col("window_end_1.5m")
                .cast(pl.Datetime).dt.timestamp(time_unit="ms")
                .truediv(24 * 60 * 60 * 1000).add(25569),
                pl.col("window_end_2m")
                .cast(pl.Datetime).dt.timestamp(time_unit="ms")
                .truediv(24 * 60 * 60 * 1000).add(25569),
            ]
        )

    with io.BytesIO() as f:
        df.write_csv(f)
        csv = f.getvalue()

    return PlainTextResponse(content=csv, media_type="text/csv")


@app.get("/tides/{station_name}", tags=["Tides"])
def get_tides_for_station_between_dates(
        station_name: StationName = Path(..., description="The name of the station"),
        start_date: datetime = Query(..., description="The start date in ISO8601 format",
                                     examples=["2021-08-01", "2021-08-01T12:30:00"]),
        end_date: datetime = Query(..., description="The end date in ISO8601 format"),
        tz: Optional[str] = Query("America/Vancouver", description="The timezone to use"),
) -> list[TideWindowRead]:
    tides = get_tides(station_name, start_date, end_date, tz)
    if isinstance(tides, HTTPException):
        raise tides
    tides = [TideWindowRead.parse_obj(t) for t in tides]
    return tides


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
