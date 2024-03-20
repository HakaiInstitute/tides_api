from datetime import date

import dateutil.tz

from tide_api.lib import StationTides


def test_StationTides():
    start_date = date(2024, 8, 1)
    end_date = date(2024, 8, 3)
    station_tides = StationTides.from_name(
        "Adams Harbour",
        start_date=start_date,
        end_date=end_date,
        tz="America/Vancouver",
    )

    assert station_tides.tz == dateutil.tz.gettz("America/Vancouver")

    assert station_tides.start_date.tzinfo == dateutil.tz.gettz("America/Vancouver")
    assert station_tides.start_date.date() == start_date
    assert station_tides.end_date.tzinfo == dateutil.tz.gettz("America/Vancouver")
    assert station_tides.end_date.date() == end_date

    tides = station_tides.tides
    for t in tides:
        assert t.time.tzinfo == dateutil.tz.gettz("America/Vancouver")

    low_tides = station_tides.low_tides
    for t in low_tides:
        assert t.time.tzinfo == dateutil.tz.gettz("America/Vancouver")

    high_tides = station_tides.high_tides
    for t in high_tides:
        assert t.time.tzinfo == dateutil.tz.gettz("America/Vancouver")

    sunrise = station_tides.get_sunrise(start_date)
    assert sunrise.tzinfo == dateutil.tz.gettz("America/Vancouver")

    sunset = station_tides.get_sunset(start_date)
    assert sunset.tzinfo == dateutil.tz.gettz("America/Vancouver")

    noon = station_tides.get_noon(start_date)
    assert noon.tzinfo == dateutil.tz.gettz("America/Vancouver")
