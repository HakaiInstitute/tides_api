OPENAPI_TAGS = [
    {
        "name": "Stations",
        "description": "Get information about tide stations",
    },
    {
        "name": "Tide Events",
        "description": "Get tide events for a given station",
    },
    {
        "name": "Tides",
        "description": "Get tides for a given station",
    },
]

ISO8601_START_EXAMPLES = {
    "date": {
        "summary": "Date (August 1, 2024)",
        "value": "2024-08-01",
    },
    "datetime": {
        "summary": "Date with time (August 1, 2024 at 1:30 PM)",
        "value": "2024-08-01T13:30:00",
    },
}
ISO8601_END_EXAMPLES = {
    "date": {
        "summary": "Date (August 3, 2024)",
        "value": "2024-08-03",
    },
    "datetime": {
        "summary": "Date with time (August 3, 2024 at 1:30 PM)",
        "value": "2024-08-03T13:30:00",
    },
}
