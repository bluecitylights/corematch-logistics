"""
Launches the DuckDB built-in UI server.
Port is controlled via the ui_local_port setting (default 4213).
start_ui_server() blocks the connection it runs on, so it gets its own
thread + connection. A separate connection is used for stop/status.
"""
import os
import signal
import sys
import threading
import time

import duckdb

DB_PATH = os.environ.get("DB_PATH", "/data/corematch.duckdb")
PORT = int(os.environ.get("UI_PORT", "4213"))

print(f"[duckdb-ui] Opening {DB_PATH}", flush=True)

# Ensure data dir exists
os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)

# Connection dedicated to running the blocking UI server
server_con = duckdb.connect(DB_PATH)
server_con.execute(f"SET ui_local_port={PORT}")
server_con.execute("INSTALL ui; LOAD ui")

stop_event = threading.Event()


def _serve():
    try:
        server_con.execute("CALL start_ui_server()")
    except Exception as e:
        if "stop" not in str(e).lower():
            print(f"[duckdb-ui] Server exited: {e}", flush=True)
    finally:
        stop_event.set()


server_thread = threading.Thread(target=_serve, daemon=True)
server_thread.start()

# Wait briefly for the server to bind, then report
time.sleep(1.5)
print(f"[duckdb-ui] UI ready at http://0.0.0.0:{PORT}", flush=True)


def _shutdown(sig, frame):
    print("[duckdb-ui] Stopping…", flush=True)
    try:
        # Open a fresh connection to send the stop command
        ctrl = duckdb.connect(DB_PATH)
        ctrl.execute("LOAD ui; CALL stop_ui_server()")
        ctrl.close()
    except Exception:
        pass
    sys.exit(0)


signal.signal(signal.SIGTERM, _shutdown)
signal.signal(signal.SIGINT, _shutdown)

while not stop_event.is_set():
    time.sleep(1)
