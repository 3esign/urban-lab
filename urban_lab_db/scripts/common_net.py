from _paths import DB_DIR, SCRATCH_DIR, rel  # koreni putanja, vidi _paths.py
import hashlib
import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(str(DB_DIR))
RAW_DIR = BASE_DIR / "raw"
CURATED_DIR = BASE_DIR / "curated"
MANIFEST_PATH = BASE_DIR / "manifest.jsonl"

for d in [
    RAW_DIR / "beograd",
    RAW_DIR / "zagreb",
    RAW_DIR / "sarajevo",
    RAW_DIR / "novi_pazar",
    RAW_DIR / "travnik",
    RAW_DIR / "common",
    CURATED_DIR / "boundaries",
    CURATED_DIR / "tables",
]:
    d.mkdir(parents=True, exist_ok=True)


def make_ssl_context():
    ctx = ssl.create_default_context()
    return ctx


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9,sr;q=0.8,hr;q=0.8,bs;q=0.8",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def append_manifest(entry: dict):
    entry.setdefault("checked_at", datetime.now(timezone.utc).isoformat())
    with open(MANIFEST_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def fetch_url(
    url: str,
    dest: Path | None = None,
    city: str = "common",
    layer: str = "misc",
    source_name: str = "",
    timeout: int = 45,
    headers: dict | None = None,
    data: bytes | None = None,
    retries: int = 2,
    save_manifest: bool = True,
) -> dict:
    hdrs = dict(DEFAULT_HEADERS)
    if headers:
        hdrs.update(headers)
    ctx = make_ssl_context()
    t0 = time.time()
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=hdrs)
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
                raw = resp.read()
                status = getattr(resp, "status", 200)
                ctype = resp.headers.get("Content-Type", "")
                final_url = resp.geturl()
                digest = sha256_bytes(raw)
                if dest is not None:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(raw)
                rec = {
                    "ok": True,
                    "city": city,
                    "layer": layer,
                    "source_name": source_name,
                    "url": url,
                    "final_url": final_url,
                    "http_status": status,
                    "content_type": ctype,
                    "bytes": len(raw),
                    "sha256": digest,
                    "local_path": rel(dest) if dest else None,
                    "elapsed_s": round(time.time() - t0, 2),
                }
                if save_manifest:
                    append_manifest(rec)
                rec["_bytes"] = raw
                return rec
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}: {e.reason}"
            if e.code in (400, 401, 403, 404, 410):
                break
            time.sleep(1.5 * (attempt + 1))
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(1.5 * (attempt + 1))

    rec = {
        "ok": False,
        "city": city,
        "layer": layer,
        "source_name": source_name,
        "url": url,
        "http_status": None,
        "error": last_err,
        "local_path": rel(dest) if dest else None,
        "elapsed_s": round(time.time() - t0, 2),
    }
    if save_manifest:
        append_manifest(rec)
    return rec
