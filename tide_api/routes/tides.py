from datetime import date

import arrow
from fastapi import APIRouter, Query
from timezonefinder import timezonefinder

from tide_api.consts import ISO8601_START_EXAMPLES, ISO8601_END_EXAMPLES
from tide_api.lib import StationTides
from tide_api.models import (
    TideMeasurement,
    StationName,
    FullStation,
)

router = APIRouter(
    prefix="/tides",
    tags=["Tides"],
)


@router.get("/{station_name}")
def get_tides_for_station(
    station_name: StationName,
    start_date: date = Query(
        None,
        description="The start date in ISO8601 format",
        openapi_examples=ISO8601_START_EXAMPLES,
    ),
    end_date: date = Query(
        None,
        description="The end date in ISO8601 format",
        openapi_examples=ISO8601_END_EXAMPLES,
    ),
    tz: str = Query(
        None,
        description="The timezone to use. If not provided, it will be inferred from the station's coordinates.",
    ),
) -> list[TideMeasurement]:
    station = FullStation.from_name(station_name.value)
    tz = (
        timezonefinder.TimezoneFinder().timezone_at(
            lat=station.latitude, lng=station.longitude
        )
        if tz is None
        else tz
    )

    start_date = (
        arrow.now(tz).replace(hour=0, minute=0, second=0)
        if start_date is None
        else arrow.get(start_date, tz)
    )
    end_date = start_date.shift(days=1) if end_date is None else arrow.get(end_date, tz)

    station_tides = StationTides(
        station, start_date=start_date.datetime, end_date=end_date.datetime
    )
    return station_tides.tides
