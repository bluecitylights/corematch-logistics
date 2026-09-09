"""
Launches the DuckDB built-in UI server.
start_ui_server() blocks but may return; we restart it automatically.
A separate connection handles control (stop).
"""
import os
import signal
import sys
import threading
import time

import duckdb

DB_PATH = os.environ.get("DB_PATH", "/data/corematch.duckdb")
PORT = int(os.environ.get("UI_PORT", "4213"))

os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)

print(f"[duckdb-ui] Opening {DB_PATH} on port {PORT}", flush=True)

_shutdown_requested = threading.Event()


def _make_con():
    con = duckdb.connect(DB_PATH)
    con.execute(f"SET ui_local_port={PORT}")
    con.execute("INSTALL ui; LOAD ui")
    return con


def _serve():
    while not _shutdown_requested.is_set():
        try:
            con = _make_con()
            con.execute("CALL start_ui_server()")
            con.close()
        except Exception as e:
            msg = str(e).lower()
            if "stop" in msg or "shutdown" in msg:
                break
            print(f"[duckdb-ui] Server exited ({e}), restarting in 2s…", flush=True)
            time.sleep(2)


server_thread = threading.Thread(target=_serve, daemon=True)
server_thread.start()

# Wait for server to bind
time.sleep(2)
print(f"[duckdb-ui] UI ready at http://0.0.0.0:{PORT}", flush=True)


def _shutdown(sig, frame):
    print("[duckdb-ui] Stopping…", flush=True)
    _shutdown_requested.set()
    try:
        ctrl = _make_con()
        ctrl.execute("CALL stop_ui_server()")
        ctrl.close()
    except Exception:
        pass
    sys.exit(0)


signal.signal(signal.SIGTERM, _shutdown)
signal.signal(signal.SIGINT, _shutdown)

while not _shutdown_requested.is_set():
    time.sleep(1)
