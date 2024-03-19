from fastapi.responses import Response, PlainTextResponse


class PNGResponse(Response):
    media_type = "image/png"


class CSVResponse(PlainTextResponse):
    media_type = "text/csv"
