import enum
import re

import requests

from tide_api.models import FullStation


def get_station_options() -> list[FullStation]:
    station_req = requests.get(
        "https://api.iwls-sine.azure.cloud-nuage.dfo-mpo.gc.ca/api/v1/stations"
    )
    if station_req.ok:
        station_data = station_req.json()
        station_data = [FullStation.parse_obj(d) for d in station_data]
        station_data = sorted(station_data, key=lambda s: s.name)
        station_data = filter(
            lambda s: any([t.code == "wlp" for t in s.time_series]), station_data
        )
        return list(station_data)
    else:
        raise Exception("Failed to get station options")


STATIONS = get_station_options()

StationName = enum.Enum("StationName", dict([(s.name, s.name) for s in STATIONS]))


def get_station_by_name(station_name: str | re.Pattern) -> FullStation | None:
    for station in STATIONS:
        if re.match(station_name, station.name):
            return station
    return None
