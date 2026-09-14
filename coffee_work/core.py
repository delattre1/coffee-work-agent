"""Deterministic event triage and pending approval state."""
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

LINK = re.compile(r'https://[^\s<>"\']+', re.I)
ALLOWED = ("meet.google.com", "zoom.us", "teams.microsoft.com", "teams.live.com")


def meeting_link(event):
    links = [event.get("hangoutLink", "")] + LINK.findall(event.get("description", ""))
    for link in links:
        parsed = urlparse(link.rstrip(".,;)"))
        host = (parsed.hostname or "").lower()
        if parsed.scheme == "https" and any(host == domain or host.endswith("." + domain) for domain in ALLOWED):
            return link.rstrip(".,;)")
    return None


def event_time(event):
    raw = event.get("start", {}).get("dateTime")
    return datetime.fromisoformat(raw.replace("Z", "+00:00")) if raw else None


def classify(event):
    kind = event.get("extendedProperties", {}).get("private", {}).get("coffee_work_type")
    if kind in ("restaurant", "coworking"):
        return kind
    if event.get("attendees") or event.get("hangoutLink") or meeting_link(event):
        return "meeting"
    return "other"


def proposals(events, now, state, mode="manual", meeting_minutes=15, ride_minutes=60):
    actions = []
    for event in events:
        if event.get("status") == "cancelled" or event.get("visibility") in ("private", "confidential"):
            continue
        start = event_time(event)
        if not start or start.tzinfo is None:
            continue
        mins = (start - now).total_seconds() / 60
        kind = classify(event)
        key = event.get("id", "") + ":" + start.isoformat()
        if not key.strip(":"):
            continue
        if kind == "meeting" and 0 <= mins <= meeting_minutes:
            if key + ":prep" not in state or state[key + ":prep"].get("status") == "prepared_notification_pending":
                actions.append({"key": key + ":prep", "action": "prepare", "event": event, "automatic": mode == "automatic"})
            if key + ":record" not in state:
                actions.append({"key": key + ":record", "action": "offer_recording", "event": event, "automatic": False})
        if kind in ("restaurant", "coworking") and 0 <= mins <= ride_minutes and key + ":ride" not in state:
            actions.append({"key": key + ":ride", "action": "offer_ride", "event": event, "automatic": False})
    return actions


def prepare(event, mac_script, contexts=None, dry_run=False):
    link = meeting_link(event)
    name = event.get("summary", "Meeting")[:100]
    context_text = " ".join([name] + [x.get("email", "") for x in event.get("attendees", [])]).lower()
    contexts = contexts or {}
    mode = "meeting"
    for keyword, saved_mode in contexts.items():
        if keyword.lower() in context_text and keyword.strip():
            mode = saved_mode
            break
    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", mode):
        raise ValueError("Invalid configured meeting mode")
    args = ["python3", str(mac_script), "activate", mode, "--intent", name]
    if dry_run:
        args.append("--dry-run")
    result = subprocess.run(args, capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Mac preparation failed")
    output = json.loads(result.stdout)
    if not output.get("ok") or output.get("failures"):
        raise RuntimeError("Mac preparation incomplete: " + result.stdout[:500])
    if link and not dry_run:
        subprocess.run(["open", link], check=True, timeout=15)
    return {"prepared": True, "mode": mode, "join_link_opened": bool(link), "result": output}


def load_state(path):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return {}


def save_state(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temp.chmod(0o600)
    temp.replace(path)
