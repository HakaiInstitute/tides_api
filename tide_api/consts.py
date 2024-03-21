from timezonefinder import TimezoneFinder

OPENAPI_TAGS = [
    {
        "name": "Stations",
        "description": "Get information about tide stations",
    },
    {
        "name": "Tides",
        "description": "Get tides for a given station",
    },
    {
        "name": "Plots",
        "description": "Interactive plots and maps",
    },
]

ISO8601_START_EXAMPLES = {
    "date": {
        "summary": "Date (August 1, 2024)",
        "value": "2024-08-01",
    },
}
ISO8601_END_EXAMPLES = {
    "date": {
        "summary": "Date (August 3, 2024)",
        "value": "2024-08-03",
    },
}

TF = TimezoneFinder()
