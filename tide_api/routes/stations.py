from typing import Annotated

import plotly.express as px
import polars as pl
from fastapi import APIRouter
from fastapi.params import Query
from fastapi.responses import HTMLResponse

from tide_api.models import STATIONS, Station, StationName, StationWithoutCoords

router = APIRouter(
    prefix="/stations",
    tags=["Stations"],
)


@router.get("")
def list_stations(
    include_coords: Annotated[
        bool, Query(description="Include station coordinates in the response")
    ] = True,
) -> list[Station] | list[StationWithoutCoords]:
    cls = Station if include_coords else StationWithoutCoords
    return list(map(cls.parse_obj, STATIONS))


@router.get("/map", tags=["Plots"], response_class=HTMLResponse)
def stations_map(
    div_only: Annotated[
        bool, Query(description="Return a div instead of full HTML page.")
    ] = False,
):
    df = pl.DataFrame(list_stations()).to_pandas()
    fig = px.scatter_mapbox(
        df,
        lat="latitude",
        lon="longitude",
        hover_name="name",
        center=dict(lat=53.7267, lon=-127.6476),
        zoom=1,
    )
    fig.update_layout(mapbox_style="open-street-map", margin=dict(r=0, l=0, b=0, t=0))
    config = {"scrollZoom": True, "displayModeBar": True}
    return fig.to_html(include_plotlyjs="cdn", full_html=(not div_only), config=config)


@router.get("/{station_name}")
def station_info_by_name(
    station_name: StationName,
    include_coords: bool = Query(
        True, description="Include station coordinates in the response"
    ),
) -> Station | StationWithoutCoords:
    station = next(s for s in STATIONS if s.name == station_name.value)
    if include_coords:
        return Station.parse_obj(station)
    else:
        return StationWithoutCoords.parse_obj(station)
