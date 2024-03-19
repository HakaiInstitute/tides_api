from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel


class StationRead(BaseModel):
    name: str
    latitude: float
    longitude: float


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
                    {
                        "low_tide_date": "2024-08-02",
                        "low_tide_height_m": 0.79,
                        "low_tide_time": "2024-08-02T10:28:25-07:00",
                        "sunrise": "2024-08-02T02:14:16-07:00",
                        "noon": "2024-08-02T09:29:33-07:00",
                        "sunset": "2024-08-02T16:44:02-07:00",
                        "windows": {
                            "1.5m": {
                                "start": "2024-08-02T08:16:50-07:00",
                                "end": "2024-08-02T12:53:23-07:00",
                                "hours": 4.61,
                            },
                            "2.0m": {
                                "start": "2024-08-02T07:31:10-07:00",
                                "end": "2024-08-02T13:43:07-07:00",
                                "hours": 6.2,
                            },
                        },
                    },
                    {
                        "low_tide_date": "2024-08-02",
                        "low_tide_height_m": 0.4,
                        "low_tide_time": "2024-08-02T23:16:54-07:00",
                        "sunrise": "2024-08-02T02:14:16-07:00",
                        "noon": "2024-08-02T09:29:33-07:00",
                        "sunset": "2024-08-02T16:44:02-07:00",
                        "windows": {
                            "1.5m": {
                                "start": "2024-08-02T20:40:40-07:00",
                                "end": None,
                                "hours": None,
                            },
                            "2.0m": {
                                "start": "2024-08-02T20:05:13-07:00",
                                "end": None,
                                "hours": None,
                            },
                        },
                    },
                ]
            ]
        }
    }
