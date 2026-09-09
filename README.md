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
├── schema.sql        # DuckDB DDL: sequences, drivers, vehicles, orders, index_store
├── engine.py         # Matching engine + demo entry-point (_seed_demo / __main__)
├── test_engine.py    # pytest test suite (11 tests, 3 acceptance-criteria groups)
├── pyproject.toml    # uv project manifest
└── uv.lock           # Pinned dependency lock
```

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (`pip install uv` or `winget install astral-sh.uv`)

## Setup

```bash
cd CoreMatch/corematch-logistics

# Create the virtual environment and install all dependencies from uv.lock
uv sync
```

That's it — no separate `pip install` step needed. The lock file pins exact versions of `duckdb`, `pyroaring`, and `pandas`.

## Run the demo

```bash
uv run engine.py
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

- **DuckDB 1.5 compatibility** — sequences must be declared with `MINVALUE 0` when starting at 0: `CREATE SEQUENCE s START 0 MINVALUE 0`. The provided `schema.sql` already handles this.
- Indexes (`index_store` table) are available for persisting serialized bitmaps between runs; the current engine rebuilds them from the relational tables on each invocation.
