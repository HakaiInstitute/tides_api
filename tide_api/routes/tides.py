from datetime import datetime

import arrow
from fastapi import APIRouter, Query

from tide_api.models import (
    StationName,
    iso8601_start_examples,
    iso8601_end_examples,
    TideRead,
)
from tide_tools.lib import get_tides_between_dates, get_station_by_name

router = APIRouter(
    prefix="/tides",
    tags=["Tides"],
)


@router.get("/{station_name}")
def get_tides_for_station(
    station_name: StationName,
    start_date: datetime = Query(
        ...,
        description="The start date in ISO8601 format",
        openapi_examples=iso8601_start_examples,
    ),
    end_date: datetime = Query(
        ...,
        description="The end date in ISO8601 format",
        openapi_examples=iso8601_end_examples,
    ),
    tz: str = Query("America/Vancouver", description="The timezone to use"),
) -> list[TideRead]:
    start_date = arrow.get(start_date, tz).datetime
    end_date = arrow.get(end_date, tz).datetime
    station = get_station_by_name(station_name.value)
    tides = get_tides_between_dates(station, start_date, end_date)
    return list(map(TideRead.from_chs_obj, tides))
