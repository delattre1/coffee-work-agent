#!/usr/bin/env python3
"""Small shared primitives for ld-mac-prepare (stdlib only)."""

from __future__ import annotations

import datetime as dt
import fcntl
import json
import os
import tempfile
from pathlib import Path
from typing import Any

STATE_ROOT = Path(
    os.environ.get(
        "HERMES_MAC_PREPARE_HOME",
        "~/Library/Application Support/Hermes/PrepareMyMac",
    )
).expanduser()
CONTEXT_FILE = STATE_ROOT / "context.json"
AUDIT_FILE = STATE_ROOT / "audit.ndjson"
CAPSULES_DIR = STATE_ROOT / "capsules"
RECORDINGS_DIR = Path(
    os.environ.get("HERMES_RECORDINGS_DIR", "~/Documents/HermesRecordings")
).expanduser()
RUN_DIR = STATE_ROOT / "run"
BIN_DIR = STATE_ROOT / "bin"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def ensure_private_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        path.chmod(0o700)
    except OSError:
        pass


def atomic_write_json(path: Path, value: Any) -> None:
    """Write JSON atomically, fsync it, and keep it owner-readable only."""
    ensure_private_dir(path.parent)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def read_json(path: Path, default: Any) -> Any:
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Invalid local state at {path}: {exc}") from exc


def audit(event: str, **payload: Any) -> None:
    """Append one compact NDJSON record without allowing concurrent interleaving."""
    ensure_private_dir(AUDIT_FILE.parent)
    record = {"ts": utc_now(), "skill": "ld-mac-prepare", "event": event, **payload}
    with AUDIT_FILE.open("a", encoding="utf-8") as handle:
        os.chmod(AUDIT_FILE, 0o600)
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        handle.flush()
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def clean_label(value: str, fallback: str = "session") -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in value.strip())
    cleaned = "-".join(filter(None, cleaned.split("-")))[:80]
    return cleaned or fallback


def json_result(ok: bool, **payload: Any) -> str:
    return json.dumps({"ok": ok, **payload}, ensure_ascii=False, separators=(",", ":"))
