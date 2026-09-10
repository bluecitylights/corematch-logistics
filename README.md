# CoreMatch-Logistics

A high-performance, local-first dual-resource allocation engine. Given a list of **orders**, each with optional skill and equipment requirements, it finds and atomically assigns the best available **driver** and **vehicle** for every order in a single pass.

## How it works

State is stored in a [DuckDB](https://duckdb.org/) database (file-backed or in-memory). On each run the engine loads drivers, vehicles, and orders into memory and builds [pyroaring](https://github.com/lemire/EWAHBoolArray) `BitMap` indexes — one per active-pool, location, skill, and equipment spec. Matching iterates over orders in sequence:

1. **Driver pool** — start from drivers at the order's destination, intersect with the active-drivers bitmap, then narrow by any required skills (`adr`, `ehbo`).
2. **Vehicle pool** — same approach: location → active → required specs (`liftgate`, `refrigerated`).
3. **Atomic assignment** — both pools must be non-empty. If they are, the lowest-index resource from each is committed to global `assigned_*` bitmaps and cannot be reused. If either pool is empty the order is marked `Unfulfilled` and neither resource is touched.

Bitmap set intersection runs in microseconds, making the engine practical for thousands of resources and orders on commodity hardware.

## Project layout

```
corematch-logistics/
├── engine/               # Matching engine package
│   ├── __init__.py       # Public engine exports
│   └── matching.py       # Matching algorithm and demo entry-point
├── app.py                # FastAPI application wiring and startup
├── db/                   # DuckDB connection, helpers, and schema
│   └── schema.sql        # DuckDB DDL: drivers, vehicles, orders, index_store
├── api/                  # REST API routes
├── ui/                   # HTML/HTMX routes and templates
│   ├── routes.py         # UI route handlers
│   └── templates/        # Jinja2 HTML templates
├── mcp_tools/            # FastMCP server implementation
├── mcp_server.py         # FastMCP compatibility entry point
├── librechat.yaml        # LibreChat MCP server configuration
├── Dockerfile            # Container image
├── docker-compose.yaml   # App service
├── test_engine.py        # pytest test suite (11 tests, 3 acceptance-criteria groups)
├── pyproject.toml        # uv project manifest
└── uv.lock               # Pinned dependency lock
```

## Run with Docker (recommended)

```bash
docker compose up --build
```

LibreChat starts with the CoreMatch MCP server configured through
`librechat.yaml`. You still need to configure an LLM provider/API key for
LibreChat before sending messages. The MCP server calls the app internally at
`http://app:8000`; it does not access DuckDB directly.

LibreChat also requires application secrets. Create a `.env` file in the
repository root before starting the stack:

```powershell
@"
JWT_SECRET=$(-join ((1..64) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) }))
JWT_REFRESH_SECRET=$(-join ((1..64) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) }))
CREDS_KEY=$(-join ((1..64) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) }))
CREDS_IV=$(-join ((1..32) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) }))
"@ | Set-Content .env
```

Alternatively, set these four environment variables in your shell. Do not
commit `.env` or reuse these development values in production.

| Service | URL | Description |
|---|---|---|
| Web UI | [http://localhost:8000](http://localhost:8000) | HTMX dashboard — manage drivers, vehicles, orders, run matching |
| LibreChat | [http://localhost:3080](http://localhost:3080) | Chat UI with the CoreMatch MCP tools configured |
| MCP HTTP | [http://localhost:8001/mcp](http://localhost:8001/mcp) | Streamable HTTP MCP endpoint for LibreChat |

The database is stored in a named Docker volume (`db_data`) so data persists across restarts. Use the **Seed demo data** button on the dashboard to populate it on first run. Use the DuckDB CLI instructions below to inspect this volume directly.

## Inspect the Podman database volume with DuckDB CLI

Install the DuckDB CLI for Windows from the [official DuckDB installation page](https://duckdb.org/install/?platform=windows&environment=cli). Download and extract the Windows CLI, then verify it is available:

```powershell
duckdb --version
```

The Compose file uses the named volume `corematch-logistics_db_data`; it is stored inside the Podman VM rather than in the repository directory. To open the database from that volume, run the DuckDB CLI in a temporary container:

```powershell
podman run --rm -it -v corematch-logistics_db_data:/data docker.io/duckdb/duckdb:latest /duckdb /data/corematch.duckdb
```

Stop the app container first so the database is not locked:

```powershell
podman compose stop app
```

Inside the DuckDB prompt, inspect the schema and data:

```sql
.tables
DESCRIBE drivers;
SELECT * FROM drivers LIMIT 20;
```

## Run locally (development)



- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (`pip install uv` or `winget install astral-sh.uv`)

## Setup

```bash
cd CoreMatch/corematch-logistics

# Create the virtual environment and install all dependencies from uv.lock
uv sync
```

That's it — no separate `pip install` step needed. The lock file pins exact versions of `duckdb`, `pyroaring`, `pandas`, `fastapi`, and `uvicorn`.

## Run the web app (local)

```bash
uv run uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Open [http://localhost:8000](http://localhost:8000). Use the **Seed demo data** button on the dashboard to populate the database on first run.

## Run the FastMCP server

The FastMCP server calls the app's REST API; it does not open the DuckDB file directly. Start the web app first, then run:

```bash
uv run mcp_server.py
```

By default it connects to `http://127.0.0.1:8000`. To use another API URL:

```powershell
$env:COREMATCH_API_URL = "http://127.0.0.1:8000"
uv run mcp_server.py
```

To run the MCP server over HTTP for LibreChat locally:

```powershell
$env:COREMATCH_API_URL = "http://127.0.0.1:8000"
uv run mcp_server.py --transport streamable-http --host 127.0.0.1 --port 8001
```

The MCP tools support CRUD operations for drivers, vehicles, and orders, plus running the matching engine. Deletion deactivates drivers and vehicles; orders are deleted.

For LibreChat, the Compose stack runs the MCP server over Streamable HTTP:

```bash
docker compose up --build
```

Use `http://localhost:3080` for LibreChat. The local stdio entry point remains
available for MCP clients that launch the server as a subprocess:

```bash
uv run mcp_server.py
```

## Inspect the MCP server

Start the Compose stack first, then use the latest MCP Inspector:

```powershell
npx @modelcontextprotocol/inspector@latest
```

Open the Inspector URL shown in the terminal and connect to:

```text
http://localhost:8001/mcp
```

For CLI inspection, specify an MCP method:

```powershell
npx @modelcontextprotocol/inspector@latest --cli `
  http://localhost:8001/mcp `
  --transport streamable-http `
  --method tools/list
```

The `--method` option is required in CLI mode.

## Run the demo

```bash
uv run -m engine.matching
```

Seeds a small dataset (5 drivers, 4 vehicles, 5 orders across Amsterdam / Rotterdam / Utrecht) and prints the assignment results:

```
=== CoreMatch-Logistics Demo Results ===
order_id assigned_driver assigned_vehicle                                  status
 ORD-001         DRV-001          VEH-001                           Fully Matched
 ORD-002         DRV-002          VEH-002                           Fully Matched
 ORD-003         DRV-003          VEH-003                           Fully Matched
 ORD-004             NaN              NaN  Unfulfilled (Missing Driver or Vehicle)
 ORD-005             NaN              NaN  Unfulfilled (Missing Driver or Vehicle)
```

## Run the tests

```bash
uv run pytest test_engine.py -v
```

The suite covers three acceptance criteria:

| Group | What it checks |
|---|---|
| `TestToolingEnforcement` | `uv.lock` exists; all packages importable |
| `TestIdempotency` | Assigned drivers/vehicles cannot be reused across orders |
| `TestAtomicIntegrity` | Both resources must be available; partial matches are never emitted |

Expected output: **11 passed**.

## Using the engine in your own code

```python
import duckdb
from engine import init_schema, run_corematch_logistics

# Create and seed your database
con = duckdb.connect("logistics.duckdb")
init_schema(con)

con.execute("INSERT INTO drivers ...")
con.execute("INSERT INTO vehicles ...")
con.execute("INSERT INTO orders ...")
con.close()

# Run the matcher
results = run_corematch_logistics("logistics.duckdb")
print(results)
```

`run_corematch_logistics` returns a `pandas.DataFrame` with columns `order_id`, `assigned_driver`, `assigned_vehicle`, and `status`.

## Notes

- **DuckDB 1.5 compatibility** — sequences must be declared with `MINVALUE 0` when starting at 0: `CREATE SEQUENCE s START 0 MINVALUE 0`. The provided `db/schema.sql` already handles this.
- Indexes (`index_store` table) are available for persisting serialized bitmaps between runs; the current engine rebuilds them from the relational tables on each invocation.
