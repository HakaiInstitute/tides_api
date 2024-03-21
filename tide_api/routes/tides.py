from datetime import date
from typing import Annotated

import arrow
from fastapi import APIRouter
from fastapi.params import Path, Query

from tide_api.consts import ISO8601_START_EXAMPLES, ISO8601_END_EXAMPLES, TF
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
def tides_as_json(
    station_name: Annotated[StationName, Path(description="The name of the station")],
    start_date: Annotated[
        date | None,
        Query(
            description="The start date in ISO8601 format",
            openapi_examples=ISO8601_START_EXAMPLES,
        ),
    ] = None,
    end_date: Annotated[
        date | None,
        Query(
            description="The end date in ISO8601 format",
            openapi_examples=ISO8601_END_EXAMPLES,
        ),
    ] = None,
    num_days: Annotated[
        int | None,
        Query(
            description="Number of days to display. Cannot be used with end_date.", gt=0
        ),
    ] = None,
    tz: Annotated[
        str | None,
        Query(
            description="The timezone to use. If not provided, it will be inferred from the station's coordinates."
        ),
    ] = None,
) -> list[TideMeasurement]:
    station = FullStation.from_name(station_name.value)
    tz = (
        TF.timezone_at(lat=station.latitude, lng=station.longitude)
        if tz is None
        else tz
    )

    start_date = (
        arrow.now(tz).replace(hour=0, minute=0, second=0)
        if start_date is None
        else arrow.get(start_date, tz)
    )
    if end_date and num_days:
        raise ValueError("Cannot use both end_date and num_days")
    elif end_date:
        end_date = arrow.get(end_date, tz)
    else:
        end_date = start_date.shift(days=(num_days if num_days is not None else 1))

    station_tides = StationTides(
        station, start_date=start_date.date(), end_date=end_date.date(), tz=tz
    )
    return station_tides.tides
