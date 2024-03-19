import enum
from datetime import datetime, date
from typing import Optional

import arrow
from pydantic import BaseModel
from starlette.responses import Response, PlainTextResponse

from tide_tools.lib import get_station_options


class StationBase(BaseModel):
    name: str


class StationRead(StationBase):
    latitude: float
    longitude: float


class StationReadWithoutCoords(StationBase):
    pass


class Window(BaseModel):
    start: Optional[datetime]
    end: Optional[datetime]
    hours: Optional[float]


class TideWindowRead(BaseModel):
    low_tide_date: date
    low_tide_height_m: float
    low_tide_time: datetime
    sunrise: Optional[datetime]
    noon: Optional[datetime]
    sunset: Optional[datetime]
    windows: dict[str, Window] = {}

    model_config = {
        "json_schema_extra": {
            "examples": [
                [
                    {
                        "low_tide_date": "2024-08-01",
                        "low_tide_height_m": 0.8,
                        "low_tide_time": "2024-08-01T09:28:30-07:00",
                        "sunrise": "2024-08-01T02:13:11-07:00",
                        "noon": "2024-08-01T09:29:37-07:00",
                        "sunset": "2024-08-01T16:45:16-07:00",
                        "windows": {
                            "1.5m": {
                                "start": "2024-08-01T07:18:37-07:00",
                                "end": "2024-08-01T11:53:32-07:00",
                                "hours": 4.58,
                            },
                            "2.0m": {
                                "start": "2024-08-01T06:31:51-07:00",
                                "end": "2024-08-01T12:44:54-07:00",
                                "hours": 6.22,
                            },
                        },
                    },
                    {
                        "low_tide_date": "2024-08-01",
                        "low_tide_height_m": 0.45,
                        "low_tide_time": "2024-08-01T22:20:00-07:00",
                        "sunrise": "2024-08-01T02:13:11-07:00",
                        "noon": "2024-08-01T09:29:37-07:00",
                        "sunset": "2024-08-01T16:45:16-07:00",
                        "windows": {
                            "1.5m": {
                                "start": "2024-08-01T19:46:04-07:00",
                                "end": "2024-08-02T01:18:51-07:00",
                                "hours": 5.55,
                            },
                            "2.0m": {
                                "start": "2024-08-01T19:09:23-07:00",
                                "end": "2024-08-02T02:09:45-07:00",
                                "hours": 7.01,
                            },
                        },
                    },
                ]
            ]
        }
    }


class TideRead(BaseModel):
    time: datetime
    value: float

    @classmethod
    def from_chs_obj(cls, obj):
        return cls(time=arrow.get(obj.eventDate).datetime, value=obj.value)


class PNGResponse(Response):
    media_type = "image/png"


class CSVResponse(PlainTextResponse):
    media_type = "text/csv"


stations = list(
    filter(
        lambda s: any([t.code == "wlp" for t in s.timeSeries]),
        sorted(get_station_options(), key=lambda s: s.officialName),
    )
)
station_names = [s.officialName for s in stations]
StationName = enum.Enum("StationName", dict([(s, s) for s in sorted(station_names)]))


iso8601_start_examples = {
    "date": {
        "summary": "Date (August 1, 2024)",
        "value": "2024-08-01",
    },
    "datetime": {
        "summary": "Date with time (August 1, 2024 at 1:30 PM)",
        "value": "2024-08-01T13:30:00",
    },
}
iso8601_end_examples = {
    "date": {
        "summary": "Date (August 3, 2024)",
        "value": "2024-08-03",
    },
    "datetime": {
        "summary": "Date with time (August 3, 2024 at 1:30 PM)",
        "value": "2024-08-03T13:30:00",
    },
}
