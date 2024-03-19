from fastapi import APIRouter
from fastapi.params import Query
from fastapi.responses import HTMLResponse

import pandas as pd
import plotly.express as px

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

@router.get("/map")
def show_map()  -> HTMLResponse:
    df = pd.DataFrame([s.dict() for s in stations])
    fig = px.scatter_mapbox(
        df,
        lat="latitude",
        lon="longitude",
        hover_name="officialName",
        hover_data=["tides"],
        zoom=2,
    )
    fig.update_layout(mapbox_style="open-street-map")
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    return HTMLResponse(fig.to_html(include_plotlyjs="cdn"))

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
