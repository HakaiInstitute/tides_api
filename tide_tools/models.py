from datetime import datetime

from pydantic import BaseModel


class TimeSeries(BaseModel):
    id: str
    code: str
    nameEn: str
    nameFr: str
    phenomenonId: str
    owner: str


class Station(BaseModel):
    id: str
    code: str
    officialName: str
    latitude: float
    longitude: float
    type: str
    timeSeries: list[TimeSeries]


class TideMeasurement(BaseModel):
    eventDate: datetime
    value: float
    qcFlagCode: int
    timeSeriesId: str
