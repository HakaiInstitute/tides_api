from datetime import date, datetime
from typing import Annotated

import arrow
import plotly.express as px
import polars as pl
from fastapi import APIRouter, Request
from fastapi.params import Path, Query
from fastapi.responses import HTMLResponse

from tide_api.consts import ISO8601_END_EXAMPLES, ISO8601_START_EXAMPLES, TF
from tide_api.lib import StationTides, expand_windows
from tide_api.models import (
    FullStation,
    StationName,
    TideEvent,
    TideMeasurement,
)
from tide_api.responses import CSVResponse

router = APIRouter(
    prefix="/tides",
    tags=["Tides"],
)


@router.get(
    "/plot/{station_name}",
    tags=["Plots"],
    response_class=HTMLResponse,
    operation_id="plot_tides_for_station",
    summary="Plot tide data for a specific station",
)
def plot_tide_data_for_station(
    request: Request,
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
    tide_window: Annotated[
        list[float], Query(description="Tide windows to find (in meters)")
    ] = [],
    show_sunrise: Annotated[
        bool, Query(description="Display sunrise time as yellow line")
    ] = True,
    show_sunset: Annotated[
        bool, Query(description="Display sunset time as yellow line")
    ] = True,
    show_current_time: Annotated[
        bool, Query(description="Annotate current time as red dot.")
    ] = True,
    show_high_tides: Annotated[
        bool, Query(description="Annotate high tide times")
    ] = True,
    show_low_tides: Annotated[
        bool, Query(description="Annotate low tide times")
    ] = True,
    div_only: Annotated[
        bool, Query(description="Return a div instead of full HTML page.")
    ] = False,
):
    """Plot tide data for a specific station for a specified time interval."""
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
        station,
        start_date=start_date.date(),
        end_date=end_date.date(),
        tz=tz,
    )
    windows_xm = [station_tides.detect_tide_windows(w) for w in tide_window]

    fig = px.line(
        x=[t * 1000 for t in station_tides.timestamps],
        y=station_tides.heights,
        title=f"Tides for {station_name.value}",
        labels={"x": "Time", "y": "Height (m)"},
        template="plotly",
    )
    fig.update_layout(xaxis=dict(type="date"))

    if show_low_tides:
        for lt in station_tides.low_tides:
            d = arrow.Arrow.fromdatetime(lt.time)
            fig.add_annotation(
                x=d.timestamp() * 1000,
                y=lt.height,
                text=d.format("HH:mm"),
                align="center",
                showarrow=True,
                arrowhead=2,
                ax=0,
                ay=-25,
            )
    if show_high_tides:
        for ht in station_tides.high_tides:
            d = arrow.Arrow.fromdatetime(ht.time)
            fig.add_annotation(
                x=d.timestamp() * 1000,
                y=ht.height,
                text=d.format("HH:mm"),
                align="center",
                showarrow=True,
                arrowhead=2,
                ax=0,
                ay=25,
            )

    for win in windows_xm:
        for w in win:
            if w.start:
                d = arrow.Arrow.fromdatetime(w.start)
                fig.add_vline(
                    x=d.timestamp() * 1000,
                    line_dash="dot",
                    line_color="blue",
                    annotation_text="start",
                    annotation_position="bottom right",
                    annotation_hovertext=d.format("HH:mm"),
                )
            if w.end:
                d = arrow.Arrow.fromdatetime(w.end)
                fig.add_vline(
                    x=d.timestamp() * 1000,
                    line_dash="dot",
                    line_color="blue",
                    annotation_text="end",
                    annotation_position="bottom right",
                    annotation_hovertext=d.format("HH:mm"),
                )

    for day in arrow.Arrow.range(
        "day", start_date.datetime, end_date.shift(days=-1).datetime, tz=tz
    ):
        if show_sunrise and (sunrise := station_tides.get_sunrise(day.date())):
            d = arrow.Arrow.fromdatetime(sunrise)
            fig.add_vline(
                x=d.timestamp() * 1000,
                line_dash="dash",
                line_color="yellow",
                annotation_text="sunrise",
                annotation_hovertext=d.format("HH:mm"),
                annotation_bgcolor="yellow",
            )
        if show_sunset and (sunset := station_tides.get_sunset(day.date())):
            d = arrow.Arrow.fromdatetime(sunset)
            fig.add_vline(
                x=d.timestamp() * 1000,
                line_dash="dash",
                line_color="yellow",
                annotation_text="sunset",
                annotation_hovertext=d.format("HH:mm"),
                annotation_bgcolor="yellow",
            )
    if show_current_time:
        d = arrow.now(tz)
        if start_date < d < end_date:
            height = station_tides.get_tide_at_time(d.datetime).height

            # Add point marker
            fig.add_scatter(
                x=[d.timestamp() * 1000],
                y=[height],
                mode="markers",
                marker=dict(color="red", size=10),
                name="Current Time",
                hoverinfo="text",
                hoverinfosrc="x",
                hovertext=f"Current: {height:.2f}m",
                showlegend=False,
            )

    fig.update_layout(title_x=0.5, xaxis_title=None)
    return fig.to_html(include_plotlyjs="cdn", full_html=(not div_only))


@router.get(
    "/events/{station_name}.csv",
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
    operation_id="tides_events_for_station_as_csv",
    summary="Get tide events for a specific station as CSV",
)
def tides_events_for_station_as_csv(
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
    tide_window: Annotated[
        list[float], Query(description="Tide windows to find (in meters)")
    ] = None,
):
    """Get a list of tide events for a specific station in a specific time window as comma-separated values (CSV)."""
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
        station,
        start_date=start_date.date(),
        end_date=end_date.date(),
        tz=tz,
    )

    sheet = station_tides.low_tide_events(tz=tz, tide_windows=tide_window)
    df = pl.DataFrame(expand_windows(sheet))
    df = df.with_columns([pl.col(pl.Datetime).dt.replace_time_zone(tz)])

    filename = (
        f"{station_name.value.lower().replace(' ', '_')}"
        f"_tides_"
        f"{start_date.date()}_to_{end_date.date()}.csv"
    )

    return CSVResponse(
        content=df.to_pandas().to_csv(index=False),
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get(
    "/events/{station_name}",
    operation_id="tides_events_for_station_as_json",
    summary="Get tide events for a specific station",
)
def tides_events_for_station_as_json(
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
    tide_window: Annotated[
        list[float], Query(description="Tide windows to find (in meters)")
    ] = None,
) -> list[TideEvent]:
    """Get a list of tide events for a specific station in a specific time window."""
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
        station,
        start_date=start_date.date(),
        end_date=end_date.date(),
        tz=tz,
    )

    return station_tides.low_tide_events(tz=tz, tide_windows=tide_window)


@router.get(
    "/at/{station_name}",
    operation_id="tide_at_time_for_station_as_json",
    summary="Get tide height at a specific time for a given station",
)
def tide_at_time_for_station_as_json(
    station_name: Annotated[StationName, Path(description="The name of the station")],
    date_time: Annotated[
        datetime,
        Query(
            description="The date and time for the tide query in ISO8601 format (e.g., 2024-08-01T12:30:00)"
        ),
    ],
    tz: Annotated[
        str | None,
        Query(
            description="The timezone to use. If not provided, it will be inferred from the station's coordinates."
        ),
    ] = None,
) -> TideMeasurement:
    """Get the tide height at a specific time for a given station."""
    station = FullStation.from_name(station_name.value)
    tz = (
        TF.timezone_at(lat=station.latitude, lng=station.longitude)
        if tz is None
        else tz
    )

    # Convert datetime to Arrow object with timezone
    # If the input datetime is timezone-naive, assume it's in the station's timezone
    if date_time.tzinfo is None:
        query_time = arrow.get(date_time).replace(tzinfo=tz)
    else:
        query_time = arrow.get(date_time).to(tz)

    # Create StationTides object with a day range around the query time
    # This ensures we have enough data to interpolate
    start_date = query_time.shift(days=-1).date()
    end_date = query_time.shift(days=1).date()

    station_tides = StationTides(
        station, start_date=start_date, end_date=end_date, tz=tz
    )

    # Get interpolated tide height at the specific time
    tide_at_time = station_tides.get_tide_at_time(query_time.datetime)

    return tide_at_time


@router.get(
    "/{station_name}",
    operation_id="tides_for_station",
    summary="Get tide data for a specific station",
)
def tides_for_station_as_json(
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
