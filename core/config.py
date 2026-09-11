import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("COREMATCH_DB_PATH", str(BASE_DIR / "corematch.duckdb"))
SCHEMA_PATH = BASE_DIR / "db" / "schema.sql"

