import pandas as pd
import plotly.express as px
from fastapi import APIRouter
from fastapi.params import Query
from fastapi.responses import HTMLResponse

from tide_api.models import StationRead, StationReadWithoutCoords, stations, StationName

router = APIRouter(
    prefix="/stations",
    tags=["Stations"],
)


@router.get("/")
def list_stations(
    include_coords: bool = Query(
        True, description="Include station coordinates in the response"
    )
) -> list[StationRead] | list[StationReadWithoutCoords]:
    cls = StationRead if include_coords else StationReadWithoutCoords
    return [
        cls(name=s.officialName, latitude=s.latitude, longitude=s.longitude)
        for s in stations
    ]


@router.get("/map", response_class=HTMLResponse)
def show_map():
    df = pd.DataFrame([s.model_dump() for s in list_stations()])
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
    include_coords=Query(
        True, description="Include station coordinates in the response"
    ),
) -> StationRead | StationReadWithoutCoords:
    station = next(s for s in stations if s.officialName == station_name.value)
    if include_coords:
        station = StationRead(
            name=station.officialName,
            latitude=station.latitude,
            longitude=station.longitude,
        )
    else:
        station = StationReadWithoutCoords(name=station.officialName)
    return station
