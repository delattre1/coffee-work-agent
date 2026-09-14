#!/usr/bin/env python3
"""Ten-minute Coffee Work watcher running inside the Plow Hermes container."""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(HERE))
from latch_calendar import RelayError, calendar_argv, json_array, run_command  # noqa: E402

HOME = Path("/var/lib/hermes/coffee-work")
CONFIG = HOME / "config.json"
STATE = HOME / "state.json"
LINK = re.compile(r"https://[^\s<>\"']+", re.I)
URI = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:\S+")
MARKERS = re.compile(r"<<<(?:END_)?EXTERNAL_UNTRUSTED_CONTENT[^>]*>>>")
ALLOWED = ("meet.google.com", "zoom.us", "teams.microsoft.com", "teams.live.com")


def clean(value):
    """Keep invite text data from becoming a second instruction channel."""
    return " ".join(URI.sub("", MARKERS.sub("", str(value or ""))).split())


def load(path, default):
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else default
    except (OSError, ValueError):
        return default


def event_start(event):
    raw = (event.get("start") or {}).get("dateTime")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def meeting_link(event):
    links = [event.get("hangoutLink", "")] + LINK.findall(event.get("description", ""))
    for link in links:
        link = link.rstrip(".,;)")
        host = (urllib.parse.urlparse(link).hostname or "").lower()
        if link.startswith("https://") and any(host == x or host.endswith("." + x) for x in ALLOWED):
            return link
    return None


def kind(event):
    value = ((event.get("extendedProperties") or {}).get("private") or {}).get("coffee_work_type")
    if value in ("restaurant", "coworking"):
        return value
    if event.get("attendees") or event.get("hangoutLink") or meeting_link(event):
        return "meeting"
    return "other"


def post_chat(text):
    base = os.environ.get("PLOW_API_BASE", "").rstrip("/")
    token = os.environ.get("PLOW_AGENT_TOKEN", "")
    channel = os.environ.get("PLOW_HOME_CHANNEL", "")
    if not base or not token or not channel:
        raise RelayError("Plow Chat is not configured for the calendar watcher")
    url = base + "/v1/chats/" + urllib.parse.quote(channel, safe="") + "/messages"
    request = urllib.request.Request(url, data=json.dumps({"body": text}).encode(),
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if not 200 <= response.status < 300:
                raise RelayError("Plow Chat returned HTTP " + str(response.status))
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        raise RelayError("Plow Chat request failed") from exc


def save_state(state):
    HOME.mkdir(mode=0o700, parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(STATE)


def prepare_mac(config, event):
    project = str(config.get("mac_project_dir", "")).strip()
    if not project:
        return False
    title = clean(event.get("summary") or "Meeting")[:100]
    mode = "meeting"
    for keyword, value in (config.get("meeting_contexts") or {}).items():
        if str(keyword).lower() in title.lower():
            mode = str(value)
            break
    script = project.rstrip("/") + "/ld-mac-prepare-native/scripts/mac_executor.py"
    run_command(["python3", script, "activate", mode, "--intent", title])
    link = meeting_link(event)
    if link:
        run_command(["open", link])
    return True


def main():
    config = load(CONFIG, {"mode": "manual", "calendar_id": "primary"})
    state = load(STATE, {})
    now = datetime.now(timezone.utc)
    events = json_array(run_command(calendar_argv(config, days=1)))
    changed = False
    results = []
    for event in events:
        if event.get("status") == "cancelled" or event.get("visibility") in ("private", "confidential"):
            continue
        start = event_start(event)
        if not start or start.tzinfo is None:
            continue
        minutes = (start - now).total_seconds() / 60
        event_kind = kind(event)
        key = str(event.get("id", "")) + ":" + start.isoformat()
        if not key.strip(":"):
            continue
        title = clean(event.get("summary") or "Upcoming event")[:100]
        stamp = start.isoformat()
        if event_kind == "meeting" and 0 <= minutes <= 15 and key + ":prep" not in state:
            automatic = config.get("mode") == "automatic"
            prepared = False
            if automatic:
                try:
                    prepared = prepare_mac(config, event)
                except Exception as exc:
                    results.append({"action": "prepare", "status": "failed", "error": str(exc)})
            message = f"Your Mac is ready for {title} at {stamp}." if prepared else f"Upcoming meeting: {title} at {stamp}. Should I prepare your Mac? Reply yes or no."
            post_chat(message)
            state[key + ":prep"] = {"status": "completed" if prepared else "offered", "at": now.isoformat()}
            save_state(state)
            changed = True
        if event_kind == "meeting" and 0 <= minutes <= 15 and key + ":record" not in state:
            post_chat(f"Would you like me to record and transcribe {title} at {stamp}? Reply yes or no. Recording starts only after your explicit consent.")
            state[key + ":record"] = {"status": "offered", "at": now.isoformat()}
            save_state(state)
            changed = True
        if event_kind in ("restaurant", "coworking") and 0 <= minutes <= 60 and key + ":ride" not in state:
            location = clean(event.get("location") or "location unknown")[:160]
            post_chat(f"You have {title} at {stamp}, {location}. Would you like me to arrange an Uber? Reply yes or no; I will show the fare before ordering.")
            state[key + ":ride"] = {"status": "offered", "at": now.isoformat()}
            save_state(state)
            changed = True
    if changed:
        save_state(state)
    print(json.dumps({"ok": True, "events": len(events), "results": results}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        raise SystemExit(2)
