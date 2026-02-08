# Hive UI

UI para enviar textos/links/arquivos para /inbox e ver presença.

## Rodar local

```bash
pip install fastapi uvicorn cryptography
set HIVE_REPO=akz-6/the-hive-samc
set HIVE_BRANCH=main
set GITHUB_TOKEN=...
set HIVE_PSK=... (opcional, para cifrar)
python -m uvicorn hive_ui_app:APP --host 0.0.0.0 --port 48765
```

O líder (menor agent_id ativo) pode rodar automaticamente via hive_tick.py.
