"""FastAPI application wiring and database startup."""

import time

from fastapi import FastAPI

from features import api_router
from core.database import init_schema as ensure_schema # assuming we moved ensure_schema
from ui import router as ui_router


app = FastAPI(title="CoreMatch-Logistics")
app.include_router(api_router)
app.include_router(ui_router)


@app.on_event("startup")
async def startup():
    for attempt in range(5):
        try:
            from core.database import get_db
            with get_db() as con:
                ensure_schema(con)
            break
        except Exception as e:
            if attempt == 4:
                raise
            print(f"[app] DB not ready ({e}), retrying in 2s…", flush=True)
            time.sleep(2)


@app.on_event("shutdown")
async def shutdown():
    from core.database import close_master_connection
    close_master_connection()

