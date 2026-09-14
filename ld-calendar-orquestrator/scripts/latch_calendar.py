#!/usr/bin/env python3
"""Small MCP relay client for Coffee Work calendar operations.

The Plow/Latch runtime injects PLOW_MCP_URL and PLOW_AGENT_TOKEN into the
container after the owner connects Google in Plow Light.  Calendar access must
therefore go through plow-gog over this relay; no Google OAuth desktop file is
needed by the agent.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request


class RelayError(RuntimeError):
    pass


def _post(url, token, body, timeout=30):
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(), response.headers.get("Content-Type", "")
    except (urllib.error.HTTPError, urllib.error.URLError) as exc:
        raise RelayError("Plow Latch relay request failed") from exc


def _envelope(raw, content_type):
    try:
        if "text/event-stream" not in content_type:
            return json.loads(raw)
        for line in raw.decode("utf-8", "replace").splitlines():
            if line.startswith("data:"):
                value = json.loads(line[5:].strip())
                if "result" in value or "error" in value:
                    return value
    except (UnicodeError, ValueError, TypeError) as exc:
        raise RelayError("Plow relay returned malformed JSON") from exc
    raise RelayError("Plow relay returned no response frame")


def _payload(result):
    try:
        block = next(x for x in result["content"] if x.get("type") == "text")
        value = json.loads(block["text"])
    except (KeyError, StopIteration, TypeError, ValueError) as exc:
        raise RelayError("Plow relay returned malformed tool output") from exc
    if not isinstance(value, dict):
        raise RelayError("Plow relay tool output is not an object")
    return value


def call(name, arguments):
    url = os.environ.get("PLOW_MCP_URL", "").strip()
    token = os.environ.get("PLOW_AGENT_TOKEN", "").strip()
    if not url or not token:
        raise RelayError("Plow Latch is not connected (PLOW_MCP_URL missing)")
    body, content_type = _post(url, token, {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })
    envelope = _envelope(body, content_type)
    if "error" in envelope:
        raise RelayError("Plow Latch rejected the calendar command")
    result = envelope.get("result")
    if not isinstance(result, dict) or result.get("isError") is True:
        raise RelayError("Plow Latch calendar command failed")
    payload = _payload(result)
    while payload.get("status") == "pending":
        time.sleep(1)
        payload = call("plow_get_result", {"handle": payload.get("handle")})
        if payload.get("status") == "ready":
            value = payload.get("result")
            if not isinstance(value, dict):
                raise RelayError("Plow Latch returned an empty deferred result")
            return value
    if payload.get("status") in ("denied", "failed", "expired", "unknown"):
        raise RelayError("Plow Latch calendar command " + str(payload["status"]))
    return payload


def run_command(argv):
    payload = call("plow_run_command", {"argv": argv})
    if payload.get("status") != "completed" or payload.get("exit_code") != 0:
        raise RelayError("plow-gog did not complete successfully")
    output = payload.get("output")
    if not isinstance(output, str):
        raise RelayError("plow-gog returned no output")
    return output


def json_array(output):
    """Decode plow-gog output after its optional Note/preamble lines."""
    match = re.search(r"^\[", output, re.MULTILINE)
    if not match:
        raise RelayError("plow-gog returned no calendar array")
    try:
        data = json.loads(output[match.start():])
    except json.JSONDecodeError as exc:
        raise RelayError("plow-gog returned malformed calendar JSON") from exc
    if not isinstance(data, list):
        raise RelayError("plow-gog calendar output is not an array")
    return data


def calendar_argv(config, *, days=1):
    calendar = config.get("calendar") if isinstance(config, dict) else {}
    calendar = calendar if isinstance(calendar, dict) else {}
    account = str(calendar.get("account") or config.get("calendar_account") or "").strip()
    sources = calendar.get("sources") or config.get("calendar_ids") or []
    ids = []
    for source in sources:
        value = source.get("calendar_id") if isinstance(source, dict) else source
        if value:
            ids.append(str(value).strip())
    ids = [x for x in ids if x] or [str(config.get("calendar_id") or "primary")]
    argv = ["plow-gog", "calendar", "events", "list"]
    if account:
        argv.append("--account=" + account)
    argv.append("--calendars=" + ",".join(ids))
    argv += ["--from=now", f"--days={int(days)}", "--json", "--results-only", "--sort=start", "--max=250"]
    return argv


def create_argv(config, title, start, end, calendar_id=None):
    calendar = config.get("calendar") if isinstance(config, dict) else {}
    calendar = calendar if isinstance(calendar, dict) else {}
    sources = calendar.get("sources") or []
    first = sources[0] if sources else {}
    cid = calendar_id or (first.get("calendar_id", "primary") if isinstance(first, dict) else first)
    return ["plow-gog", "calendar", "create", str(cid), "--summary", title, "--from", start, "--to", end]


def delete_argv(config, event_id, calendar_id=None):
    calendar = config.get("calendar") if isinstance(config, dict) else {}
    calendar = calendar if isinstance(calendar, dict) else {}
    sources = calendar.get("sources") or []
    first = sources[0] if sources else {}
    cid = calendar_id or (first.get("calendar_id", "primary") if isinstance(first, dict) else first)
    return ["plow-gog", "calendar", "delete", str(cid), event_id]
