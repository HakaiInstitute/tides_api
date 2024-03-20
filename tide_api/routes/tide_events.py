import io
from datetime import datetime, date
from typing import Any, Annotated

import arrow
import dateutil.tz
import plotly.express as px
import polars as pl
from fastapi import APIRouter
from fastapi.params import Path, Query
from fastapi.responses import HTMLResponse
from matplotlib import pyplot as plt, dates as mdates

from tide_api.consts import ISO8601_START_EXAMPLES, ISO8601_END_EXAMPLES, TF
from tide_api.lib import expand_windows, StationTides
from tide_api.models import (
    TideEvent,
    StationName,
    FullStation,
)
from tide_api.responses import PNGResponse, CSVResponse

router = APIRouter(
    prefix="/tides/events",
    tags=["Tide Events"],
)


def parse_tz_date(dt: Any, tz: str) -> datetime:
    return arrow.get(dt, tz).datetime


@router.get("/{station_name}/plot", response_class=HTMLResponse)
def interactive_tide_graph(
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
    end_date = start_date.shift(days=1) if end_date is None else arrow.get(end_date, tz)

    station_tides = StationTides(
        station,
        start_date=start_date.date(),
        end_date=end_date.date(),
        tz=tz,
    )
    windows_xm = [station_tides.detect_tide_windows(w) for w in tide_window]

    df = pl.DataFrame(
        station_tides.tides, schema_overrides={"time": pl.Datetime(time_zone=tz)}
    )
    fig = px.line(
        df,
        x="time",
        y="height",
        title=f"Tides for {station_name.value}",
        labels={"time": "Time", "height": "Height (m)"},
        template="plotly",
    )
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
        height = station_tides.get_tide_at_time(d.datetime).height
        if start_date < d < end_date:
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
def generate_tide_graph_image(
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
    ] = False,
    show_sunset: Annotated[
        bool, Query(description="Display sunset time as yellow line")
    ] = False,
    show_current_time: Annotated[
        bool, Query(description="Display current time as black dashed line")
    ] = True,
    show_high_tides: Annotated[
        bool, Query(description="Display high tides as red dashed line")
    ] = True,
    show_low_tides: Annotated[
        bool, Query(description="Display low tides as green dashed line")
    ] = True,
    width: Annotated[int, Query(description="Width of the plot in pixels")] = 640,
    height: Annotated[int, Query(description="Height of the plot in pixels")] = 480,
    dpi: Annotated[int, Query(description="DPI of the plot")] = 100,
):
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
    end_date = start_date.shift(days=1) if end_date is None else arrow.get(end_date, tz)

    station_tides = StationTides(
        station,
        start_date=start_date.date(),
        end_date=end_date.date(),
        tz=tz,
    )
    windows_xm = [station_tides.detect_tide_windows(w) for w in tide_window]

    df = pl.DataFrame(station_tides.tides, schema_overrides={"time": pl.Datetime})

    fig = plt.figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    ax1 = fig.subplots()
    ax1.grid(axis="y")

    plt.xticks(rotation=90)
    plt.ylabel("Tide Height (m)")
    plt.xlabel("Time")

    plt.plot(
        df["time"].to_numpy(),
        df["height"].to_numpy(),
    )
    plt.title(f"Tides for {station.name}")
    plt.xlim(start_date, end_date)

    x_ticks = []
    if show_low_tides:
        for lt in station_tides.low_tides:
            d = arrow.get(lt.time).to(tz).datetime
            x_ticks.append(d)
            plt.axvline(d, linestyle="dashed", c="red")
    if show_high_tides:
        for ht in station_tides.high_tides:
            d = arrow.get(ht.time).to(tz).datetime
            x_ticks.append(d)
            plt.axvline(d, linestyle="dashed", c="green")

    for win in windows_xm:
        for w in win:
            if w.start:
                d = arrow.get(w.start).to(tz).datetime
                x_ticks.append(d)
                plt.axvline(d, linestyle="dotted", c="blue")
            if w.end:
                d = arrow.get(w.end).to(tz).datetime
                x_ticks.append(d)
                plt.axvline(d, linestyle="dotted", c="blue")

    for day in arrow.Arrow.range(
        "day", start_date.datetime, end_date.shift(days=-1).datetime, tz=tz
    ):
        if show_sunrise and (sunrise := station_tides.get_sunrise(day)):
            d = arrow.get(sunrise).to(tz).datetime
            x_ticks.append(d)
            plt.axvline(d, linestyle="dashed", c="yellow")
        if show_sunset and (sunset := station_tides.get_sunset(day)):
            d = arrow.get(sunset).to(tz).datetime
            x_ticks.append(d)
            plt.axvline(d, linestyle="dashed", c="yellow")
    if show_current_time:
        d = arrow.now(tz).datetime
        if start_date < d < end_date:
            x_ticks.append(d)
            plt.axvline(d, linestyle="dashed", c="black")

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
    tz: Annotated[
        str | None,
        Query(
            description="The timezone to use. If not provided, it will be inferred from the station's coordinates."
        ),
    ] = None,
    tide_window: Annotated[
        list[float], Query(description="Tide windows to find (in meters)")
    ] = [],
):
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
    end_date = start_date.shift(days=1) if end_date is None else arrow.get(end_date, tz)

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
        f'{station_name.value.lower().replace(" ", "_")}'
        f"_tides_"
        f"{start_date.date()}_to_{end_date.date()}.csv"
    )

    return CSVResponse(
        content=df.to_pandas().to_csv(index=False),
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/{station_name}")
def get_tides_for_station_between_dates(
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
    tz: Annotated[
        str | None,
        Query(
            description="The timezone to use. If not provided, it will be inferred from the station's coordinates."
        ),
    ] = None,
    tide_window: Annotated[
        list[float], Query(description="Tide windows to find (in meters)")
    ] = [],
) -> list[TideEvent]:
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
    end_date = start_date.shift(days=1) if end_date is None else arrow.get(end_date, tz)

    station_tides = StationTides(
        station,
        start_date=start_date.date(),
        end_date=end_date.date(),
        tz=tz,
    )

    return station_tides.low_tide_events(tz=tz, tide_windows=tide_window)
