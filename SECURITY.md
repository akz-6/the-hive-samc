# The Hive – Security / Defense-in-Depth

This repository stores *collective memory* artifacts. Treat it as **untrusted at rest**.
Assume it can be compromised; design for **tamper-evidence + recovery**.

## Threat model (practical)
- Accidental corruption (bad merge, partial writes, API errors)
- Malicious edits (token leak, compromised GitHub account)
- History rewrites / force-push

## Defensive layers (what we implement)

### 1) Tamper-evident integrity chain (repo)
We maintain:
- `logs/integrity_chain.jsonl` (append-only in normal operation)
- `logs/integrity_manifest.json`

Each record includes `prev_root` and `root`.
`root` is SHA-256 over the sorted list of `"<path>\t<github_sha>"` for files in:
- `dna/`
- `core_knowledge/`
- `memories/`
- `logs/`

This makes unauthorized changes **detectable** (especially when compared to a LOCAL anchor).

### 2) Local anchors (outside GitHub)
The system writes local anchors in the OpenClaw workspace:
- `C:\Users\jarvi\.openclaw\workspace\memory\hive_integrity_anchors.jsonl`

If GitHub is compromised, you still have an external reference for the last known-good root.

### 3) Locking during ingestion
Ingestion uses `/locks` (per-file lock) so concurrent runs don’t double-process.

## Operational hardening (recommended)
- Protect branch `main`: no force-push, require PR reviews.
- Restrict token scope: Fine-grained token, **Contents: Read/Write**, repo-only.
- Rotate token if suspected leak.
- Enable GitHub security features (secret scanning, dependabot) if applicable.

## Recovery playbook (high level)
1) If integrity mismatch is detected:
   - Stop ingestion cron.
   - Compare repo `logs/integrity_chain.jsonl` vs local `hive_integrity_anchors.jsonl`.
2) Roll back to last known-good commit/tag.
3) Re-run bootstrap if directories missing.
4) Re-ingest any preserved raw data (if available) from offline backups.
