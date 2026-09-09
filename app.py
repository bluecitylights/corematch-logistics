"""FastAPI application wiring and database startup."""

import time

from fastapi import FastAPI

from api import router as api_router
from db import ensure_schema
from ui import router as ui_router


app = FastAPI(title="CoreMatch-Logistics")
app.include_router(api_router)
app.include_router(ui_router)


@app.on_event("startup")
async def startup():
    for attempt in range(5):
        try:
            ensure_schema()
            break
        except Exception as e:
            if attempt == 4:
                raise
            print(f"[app] DB not ready ({e}), retrying in 2s…", flush=True)
            time.sleep(2)
