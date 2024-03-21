import os

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from tide_api.consts import OPENAPI_TAGS
from tide_api.routes import stations_router
from tide_api.routes import tides_router

app = FastAPI(
    title="Tides API",
    version="0.1.0alpha",
    description="API to get tide data for CHS stations.   \n"
    "*Warning: This tool is in development. "
    "Results may not be accurate and URLs may change. Use at your own risk.*",
    root_path=os.getenv("ROOT_PATH", ""),
    openapi_tags=OPENAPI_TAGS,
    contact={"name": "Hakai API Support", "email": "api.support@hakai.org"},
)


@app.get("/", include_in_schema=False)
def redirect_to_docs():
    # Redirect to docs
    return RedirectResponse(url=app.docs_url)


app.include_router(tides_router)
app.include_router(stations_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
