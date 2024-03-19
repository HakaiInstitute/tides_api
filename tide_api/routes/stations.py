from fastapi import APIRouter
from fastapi.params import Query
from fastapi.responses import HTMLResponse

import plotly.graph_objects as go

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
    
    name,latitude,longitude = [],[],[]
    for station in stations:
        name.append(station.officialName)
        latitude.append(station.latitude)
        longitude.append(station.longitude)

    fig = go.Figure(go.Scattermapbox(
            lat=latitude,
            lon=longitude,
            mode='markers',
            marker=go.scattermapbox.Marker(
                size=9
            ),
            text=name,
            name="CHS Tide Stations"
        )
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
