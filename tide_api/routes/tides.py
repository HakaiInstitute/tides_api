from datetime import datetime

import arrow
from fastapi import APIRouter, Query

from tide_api.consts import ISO8601_START_EXAMPLES, ISO8601_END_EXAMPLES
from tide_api.lib import StationTides
from tide_api.models import (
    TideMeasurement,
)
from tide_api.stations import StationName

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
        openapi_examples=ISO8601_START_EXAMPLES,
    ),
    end_date: datetime = Query(
        ...,
        description="The end date in ISO8601 format",
        openapi_examples=ISO8601_END_EXAMPLES,
    ),
    tz: str = Query("America/Vancouver", description="The timezone to use"),
) -> list[TideMeasurement]:
    station_tides = StationTides.from_name(
        station_name.value,
        start_date=arrow.get(start_date, tz).datetime,
        end_date=arrow.get(end_date, tz).datetime,
    )
    return list(map(TideMeasurement.parse_obj, station_tides.tides))
