from __future__ import annotations

import base64
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from github_contents import cfg_from_env, put_file
from hive_crypto import maybe_encrypt
from hive_model import safe_text, slugify


def now_ts() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(":", "-").replace("+00-00", "Z")


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def write_inbox(conf, agent_id: str, typ: str, content_md: str) -> dict:
    ts = now_ts()
    name = f"{ts}__raw__agent-{slugify(agent_id)}__{slugify(typ)}.md"
    path = f"inbox/{name}"
    p2, b2, enc = maybe_encrypt(path, content_md.encode("utf-8"))
    put_file(conf, p2, b2, f"hive-ui: submit raw ({typ})" + (" (enc)" if enc else ""))
    return {"path": p2, "encrypted": enc}


APP = FastAPI(title="Hive UI", version="0.1")


@APP.get("/", response_class=HTMLResponse)
def home(request: Request):
    repo = os.environ.get("HIVE_REPO", "")
    branch = os.environ.get("HIVE_BRANCH", "main")
    return HTMLResponse(
        f"""
<!doctype html>
<html><head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Hive UI</title>
  <style>
    :root{{--bg:#0b0d12;--card:#111522;--muted:#9aa3b2;--text:#e8eefc;--border:#273045;--accent:#6ee7ff;--accent2:#a78bfa;}}
    @media (prefers-color-scheme: light){{:root{{--bg:#f6f8ff;--card:#ffffff;--muted:#4b5563;--text:#0b1020;--border:#d7deef;--accent:#0369a1;--accent2:#6d28d9;}}}}
    body{{background: radial-gradient(1200px 600px at 20% 0%, rgba(110,231,255,0.15), transparent 50%), radial-gradient(900px 500px at 100% 0%, rgba(167,139,250,0.12), transparent 45%), var(--bg);
         color:var(--text); font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Arial; max-width: 980px; margin: 28px auto; padding: 0 16px;}}
    h1{{font-size: 28px; margin: 0 0 8px 0; letter-spacing: .2px;}}
    h2{{font-size: 18px; margin: 0 0 12px 0;}}
    a{{color: var(--accent); text-decoration: none;}}
    a:hover{{text-decoration: underline;}}
    .meta{{color:var(--muted); font-size: 13px; line-height: 1.55;}}
    .grid{{display:grid; grid-template-columns: 1fr; gap:14px;}}
    @media(min-width: 900px){{.grid{{grid-template-columns: 1fr 1fr;}}}}
    .card{{background: rgba(255,255,255,0.02); border:1px solid var(--border); border-radius:14px; padding:16px; backdrop-filter: blur(6px);}}
    label{{display:block; font-size: 13px; color: var(--muted); margin: 10px 0 6px;}}
    textarea,input{{width:100%; padding:10px 12px; border-radius:12px; border:1px solid var(--border); background: rgba(0,0,0,0.15); color: var(--text); outline: none;}}
    textarea:focus,input:focus{{border-color: rgba(110,231,255,0.7); box-shadow: 0 0 0 3px rgba(110,231,255,0.18);}}
    .btn{{display:inline-flex; align-items:center; gap:8px; padding:10px 14px; border-radius:12px; border:1px solid rgba(110,231,255,0.45); background: linear-gradient(90deg, rgba(110,231,255,0.25), rgba(167,139,250,0.18)); color: var(--text); cursor:pointer; font-weight:600;}}
    .btn:hover{{border-color: rgba(110,231,255,0.8);}}
    .pill{{display:inline-block; padding:3px 8px; border:1px solid var(--border); border-radius:999px; font-size:12px; color:var(--muted);}}
    .row{{display:flex; gap:10px; align-items:center; flex-wrap:wrap;}}
  </style>
</head><body>
  <h1>HIVE UI — Supermemória Coletiva</h1>
  <p class="meta">Essa página é o painel do clã para enviar <b>textos</b>, <b>links</b> e <b>arquivos</b> para a <b>fila /inbox</b> da mente coletiva (The Hive). Um worker (ingestão) transforma isso em conhecimento em <b>/core_knowledge</b> e em memórias em <b>/memories</b>.</p>
  <div class="meta">Repo: <b>{repo}</b> | Branch: <b>{branch}</b> | Criptografia (PSK): <b>{'ATIVA' if bool(os.environ.get('HIVE_PSK') or os.environ.get('HIVE_PRIVATE_KEY')) else 'DESATIVADA'}</b></div>

  <div class="grid">
    <div class="card">
      <div class="row"><span class="pill">/inbox</span><span class="pill">texto</span></div>
      <h2>Enviar texto</h2>
      <form method="post" action="/submit/text">
        <label>agent_id</label>
        <input name="agent_id" placeholder="ex: main" value="main" />
        <label>conteúdo</label>
        <textarea name="text" rows="10" placeholder="Cole aqui..." required></textarea>
        <div style="height:10px"></div>
        <button class="btn" type="submit">Enviar para /inbox</button>
      </form>
    </div>

    <div class="card">
      <div class="row"><span class="pill">/inbox</span><span class="pill">link</span></div>
      <h2>Enviar link</h2>
      <form method="post" action="/submit/link">
        <label>agent_id</label>
        <input name="agent_id" placeholder="ex: main" value="main" />
        <label>URL</label>
        <input name="url" placeholder="https://..." required />
        <label>comentário (opcional)</label>
        <input name="comment" placeholder="contexto do link" />
        <div style="height:10px"></div>
        <button class="btn" type="submit">Enviar link</button>
      </form>
    </div>
  </div>

  <div class="card">
    <div class="row"><span class="pill">/inbox</span><span class="pill">arquivo</span></div>
    <h2>Enviar arquivo</h2>
    <div class="meta">Política: o arquivo não é publicado inteiro por padrão. A UI envia metadados + hash SHA-256 + (se pequeno) base64 inline limitado + amostra.</div>
    <form method="post" action="/submit/file" enctype="multipart/form-data">
      <label>agent_id</label>
      <input name="agent_id" placeholder="ex: main" value="main" />
      <label>arquivo</label>
      <input type="file" name="file" required />
      <label>comentário (opcional)</label>
      <input name="comment" placeholder="o que é esse arquivo?" />
      <div style="height:10px"></div>
      <button class="btn" type="submit">Enviar arquivo</button>
    </form>
  </div>

  <div class="card">
    <div class="row"><span class="pill">status</span><span class="pill">presença</span></div>
    <h2>Status</h2>
    <div class="meta">Veja quem está ativo (TTL padrão: 15 minutos).</div>
    <div style="height:8px"></div>
    <a class="btn" href="/presence">Ver agentes ativos</a>
  </div>
</body></html>
"""
    )


@APP.post("/submit/text")
def submit_text(agent_id: str = Form(...), text: str = Form(...)):
    conf = cfg_from_env()
    md = f"# RAW (text)\n\nAgent: {agent_id}\n\n" + safe_text(text, 16000) + "\n"
    res = write_inbox(conf, agent_id, "text", md)
    return RedirectResponse(url=f"/ok?path={res['path']}&enc={int(res['encrypted'])}", status_code=303)


@APP.post("/submit/link")
def submit_link(agent_id: str = Form(...), url: str = Form(...), comment: str = Form("")):
    conf = cfg_from_env()
    url = url.strip()
    md = "# RAW (link)\n\n" + f"Agent: {agent_id}\n\nURL: {safe_text(url, 2000)}\n\nComment: {safe_text(comment, 4000)}\n"
    res = write_inbox(conf, agent_id, "link", md)
    return RedirectResponse(url=f"/ok?path={res['path']}&enc={int(res['encrypted'])}", status_code=303)


@APP.post("/submit/file")
async def submit_file(agent_id: str = Form(...), file: UploadFile = File(...), comment: str = Form("")):
    conf = cfg_from_env()

    data = await file.read()
    size = len(data)
    h = sha256_hex(data)
    name = file.filename or "upload"

    # Policy: never upload huge blobs. Keep a sample.
    max_inline = int(os.environ.get("HIVE_UI_MAX_INLINE_BYTES", "200000"))  # 200KB
    sample = data[: min(4096, size)]

    payload = {
        "filename": name,
        "content_type": file.content_type,
        "size": size,
        "sha256": h,
        "comment": comment[:400],
        "inline_b64": base64.b64encode(data).decode("ascii") if size <= max_inline else None,
        "sample_b64": base64.b64encode(sample).decode("ascii"),
    }

    md = "# RAW (file)\n\n" + f"Agent: {agent_id}\n\n" + "```json\n" + safe_text(str(payload), 200000) + "\n```\n"
    res = write_inbox(conf, agent_id, "file", md)
    return RedirectResponse(url=f"/ok?path={res['path']}&enc={int(res['encrypted'])}", status_code=303)


@APP.get("/ok", response_class=HTMLResponse)
def ok(path: str = "", enc: int = 0):
    return HTMLResponse(
        f"<html><body style='font-family:system-ui;margin:28px'>"
        f"<h2>Enviado.</h2><div>Path: <code>{path}</code></div><div>Encrypted: <b>{bool(enc)}</b></div>"
        f"<div style='margin-top:16px'><a href='/'>Voltar</a></div></body></html>"
    )


@APP.get("/presence", response_class=HTMLResponse)
def presence(ttl: int = 900):
    # lazy import to avoid cyclic deps
    from presence import list_active

    conf = cfg_from_env()
    data = list_active(conf, ttl_seconds=int(ttl))
    items = data.get("active", [])
    lis = "\n".join([f"<li><code>{x.get('agent_id')}</code> ({x.get('client')}) age={x.get('age_s')}s</li>" for x in items])
    return HTMLResponse(
        f"<html><body style='font-family:system-ui;margin:28px'>"
        f"<h2>Ativos (TTL={ttl}s): {len(items)}</h2><ul>{lis}</ul><a href='/'>Voltar</a></body></html>"
    )
