from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class StationBase(BaseModel):
    name: str = Field(..., validation_alias="officialName")


class Station(StationBase):
    latitude: float
    longitude: float


class StationWithoutCoords(StationBase):
    pass


class FullStation(Station):
    id: str
    code: str
    type: str
    time_series: list["TimeSeries"] = Field(..., validation_alias="timeSeries")


class TideWindow(BaseModel):
    start: Optional[datetime]
    end: Optional[datetime]

    @computed_field
    @property
    def hours(self) -> float | None:
        if self.start is None or self.end is None:
            return None
        return round((self.end - self.start).seconds / 60 / 60, 2)


class TideEvent(BaseModel):
    low_tide_date: date
    low_tide_height_m: float
    low_tide_time: datetime
    sunrise: Optional[datetime]
    noon: Optional[datetime]
    sunset: Optional[datetime]
    windows: dict[str, TideWindow] = {}

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
                    }
                ]
            ]
        }
    }


class TimeSeries(BaseModel):
    id: str
    code: str
    name_en: str = Field(..., validation_alias="nameEn")
    name_fr: str = Field(..., validation_alias="nameFr")
    phenomenon_id: str = Field(..., validation_alias="phenomenonId")
    owner: str


class TideMeasurementBase(BaseModel):
    time: datetime = Field(..., validation_alias="eventDate")
    value: float


class TideMeasurement(TideMeasurementBase):
    pass


class FullTideMeasurement(TideMeasurementBase):
    qc_flag_code: int = Field(..., validation_alias="qcFlagCode")
    time_series_id: str = Field(..., validation_alias="timeSeriesId")
