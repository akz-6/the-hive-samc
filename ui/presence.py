from __future__ import annotations

import argparse
import base64
import json
from datetime import datetime, timezone

from github_contents import cfg_from_env, get_content, list_dir, put_file
from hive_crypto import maybe_decrypt, maybe_encrypt
from hive_model import slugify


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def upsert_presence(conf, agent_id: str, client: str, note: str = "") -> dict:
    ts = now_iso()
    safe_agent = slugify(agent_id)[:80] or "unknown"
    path = f"logs/presence/agent-{safe_agent}.json"
    payload = {
        "ts": ts,
        "agent_id": agent_id,
        "client": client,
        "note": note[:200],
    }
    p2, b2, enc = maybe_encrypt(path, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
    put_file(conf, p2, b2, f"hive: presence ping {agent_id}" + (" (enc)" if enc else ""))
    return {"ok": True, "path": p2, "encrypted": enc, "ts": ts}


def list_active(conf, ttl_seconds: int = 900) -> dict:
    # TTL default: 15 minutes
    items = list_dir(conf, "logs/presence")
    files = [x for x in items if x.get("type") == "file" and x.get("name") and not str(x.get("name")).startswith(".")]

    now = datetime.now(timezone.utc)
    active = []
    stale = []

    for f in files:
        name = f.get("name")
        path = f"logs/presence/{name}"
        c = get_content(conf, path)
        if not c or "content" not in c:
            continue
        blob = base64.b64decode(c["content"])
        blob = maybe_decrypt(blob)
        try:
            data = json.loads(blob.decode("utf-8", errors="strict"))
        except Exception:
            continue
        ts = data.get("ts")
        try:
            dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        except Exception:
            stale.append({"path": path, "reason": "bad_ts"})
            continue
        age = (now - dt).total_seconds()
        entry = {"agent_id": data.get("agent_id"), "client": data.get("client"), "ts": ts, "age_s": int(age), "path": path}
        if age <= ttl_seconds:
            active.append(entry)
        else:
            stale.append(entry)

    active = sorted(active, key=lambda x: x.get("age_s", 0))
    stale = sorted(stale, key=lambda x: x.get("age_s", 10**9))
    return {"ok": True, "ttl_seconds": ttl_seconds, "active": active, "stale": stale, "active_count": len(active), "total_files": len(files)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=None)
    ap.add_argument("--branch", default=None)

    sub = ap.add_subparsers(dest="cmd", required=True)

    p_ping = sub.add_parser("ping")
    p_ping.add_argument("--agent-id", required=True)
    p_ping.add_argument("--client", default="openclaw")
    p_ping.add_argument("--note", default="")

    p_list = sub.add_parser("list")
    p_list.add_argument("--ttl", type=int, default=900)

    args = ap.parse_args()
    conf = cfg_from_env(repo=args.repo, branch=args.branch)

    if args.cmd == "ping":
        print(upsert_presence(conf, args.agent_id, args.client, args.note))
    elif args.cmd == "list":
        print(list_active(conf, ttl_seconds=int(args.ttl)))


if __name__ == "__main__":
    main()
