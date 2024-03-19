import os

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from tide_api.routes import stations_router
from tide_api.routes import tide_events_router
from tide_api.routes import tides_router

app = FastAPI(
    title="Tide Window API",
    version="0.1.0alpha",
    description="API to get tide windows for a given station between two dates.   \n"
    "*Warning: This tool is in development. "
    "Results may not be accurate and URLs may change. Use at your own risk.*",
    root_path=os.getenv("ROOT_PATH", ""),
    openapi_tags=[
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
    ],
    contact={"name": "Hakai API Support", "email": "api.support@hakai.org"},
)


@app.get("/", include_in_schema=False)
def redirect_to_docs():
    # Redirect to docs
    return RedirectResponse(url=app.root_path + app.docs_url)


app.include_router(stations_router)
app.include_router(tide_events_router)
app.include_router(tides_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
