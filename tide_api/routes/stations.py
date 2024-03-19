import plotly.express as px
import polars as pl
from fastapi import APIRouter
from fastapi.params import Query
from fastapi.responses import HTMLResponse

from tide_api.models import Station, StationWithoutCoords
from tide_api.stations import STATIONS, StationName

router = APIRouter(
    prefix="/stations",
    tags=["Stations"],
)


@router.get("")
def list_stations(
    include_coords: bool = Query(
        True, description="Include station coordinates in the response"
    )
) -> list[Station] | list[StationWithoutCoords]:
    cls = Station if include_coords else StationWithoutCoords
    return list(map(cls.parse_obj, STATIONS))


@router.get("/map", response_class=HTMLResponse)
def show_map():
    df = pl.DataFrame(list_stations()).to_pandas()
    fig = px.scatter_mapbox(
        df,
        lat="latitude",
        lon="longitude",
        hover_name="name",
        zoom=1,
    )
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin=dict(r=0, l=0, b=0, t=0))
    return fig.to_html(include_plotlyjs="cdn")


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
