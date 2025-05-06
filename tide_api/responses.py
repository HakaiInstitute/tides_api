from fastapi.responses import PlainTextResponse, Response


class PNGResponse(Response):
    media_type = "image/png"


class CSVResponse(PlainTextResponse):
    media_type = "text/csv"
