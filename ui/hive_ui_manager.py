from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import time
from pathlib import Path


def port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def read_pid(pidfile: Path) -> int | None:
    try:
        return int(pidfile.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def is_pid_alive(pid: int) -> bool:
    try:
        # Windows: tasklist check
        # Use tasklist with filter (case-insensitive) and tolerate locale issues
        out = subprocess.check_output(["cmd", "/c", "tasklist", "/FI", f"PID eq {pid}"], text=True, encoding="utf-8", errors="replace")
        return str(pid) in out
    except Exception:
        return False


def start_server(bind: str, port: int, log_path: Path, pidfile: Path) -> None:
    # Start uvicorn detached
    cmd = [
        "python",
        "-m",
        "uvicorn",
        "hive_ui_app:APP",
        "--host",
        bind,
        "--port",
        str(port),
        "--log-level",
        "info",
    ]

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as log:
        p = subprocess.Popen(
            cmd,
            cwd=str(Path(__file__).resolve().parent),
            stdout=log,
            stderr=log,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
    pidfile.write_text(str(p.pid), encoding="utf-8")


def stop_server(pidfile: Path) -> bool:
    pid = read_pid(pidfile)
    if not pid:
        return False
    try:
        subprocess.check_output(["cmd", "/c", f"taskkill /PID {pid} /T /F"], text=True, encoding="utf-8", errors="replace")
        pidfile.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def determine_leader(active_agents: list[dict]) -> str | None:
    ids = [str(x.get("agent_id")) for x in active_agents if x.get("agent_id")]
    ids = sorted(set(ids))
    return ids[0] if ids else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent-id", required=True)
    ap.add_argument("--ttl", type=int, default=900)
    ap.add_argument("--bind", default=os.environ.get("HIVE_UI_BIND", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("HIVE_UI_PORT", "48765")))
    ap.add_argument("--state", default=r"C:\Users\jarvi\.openclaw\workspace\memory\hive_ui_state.json")
    args = ap.parse_args()

    # Ask repo presence list via script (import locally)
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from github_contents import cfg_from_env
    from presence import list_active

    conf = cfg_from_env()
    pres = list_active(conf, ttl_seconds=int(args.ttl))
    leader = determine_leader(pres.get("active", []))

    pidfile = Path(args.state).with_suffix(".pid")
    log_path = Path(args.state).with_suffix(".log")
    state_path = Path(args.state)

    should_host = (leader is not None) and (leader == args.agent_id)

    running = False
    pid = read_pid(pidfile)
    if pid and is_pid_alive(pid):
        running = True

    # If server is up but port isn't open, mark as not running
    if running and not port_open("127.0.0.1", int(args.port)) and not port_open(args.bind, int(args.port)):
        running = False

    action = "noop"
    if should_host and not running:
        start_server(args.bind, int(args.port), log_path, pidfile)
        action = "started"
        time.sleep(0.5)
    elif (not should_host) and running:
        stop_server(pidfile)
        action = "stopped"

    # publish endpoint to repo (so others can discover and open UI)
    try:
        from github_contents import put_file
        from hive_crypto import maybe_encrypt

        public_url = os.environ.get("HIVE_UI_PUBLIC_URL")
        if not public_url:
            public_url = f"http://{args.bind}:{int(args.port)}/"
        endpoint = {
            "ts": time.time(),
            "leader": leader,
            "active_count": pres.get("active_count"),
            "url": public_url,
            "bind": args.bind,
            "port": int(args.port),
        }
        # write only if we are leader (authoritative)
        if should_host:
            conf2 = cfg_from_env()
            p2, b2, enc = maybe_encrypt("logs/ui_endpoint.json", json.dumps(endpoint, ensure_ascii=False, indent=2).encode("utf-8"))
            put_file(conf2, p2, b2, "hive-ui: update endpoint" + (" (enc)" if enc else ""))
    except Exception:
        pass

    state = {
        "ts": time.time(),
        "agent_id": args.agent_id,
        "leader": leader,
        "should_host": should_host,
        "running": should_host and (action in ["noop", "started"]),
        "bind": args.bind,
        "port": int(args.port),
        "action": action,
        "active_count": pres.get("active_count"),
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    print({"ok": True, **state})


if __name__ == "__main__":
    main()
