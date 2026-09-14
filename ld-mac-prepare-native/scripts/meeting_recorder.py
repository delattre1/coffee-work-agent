#!/usr/bin/env python3
"""Local Calendar awareness, explicit-consent recording, and on-device notes."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from hermes_common import BIN_DIR, RECORDINGS_DIR, RUN_DIR, atomic_write_json, audit, clean_label, ensure_private_dir, json_result, read_json, utc_now

SCRIPT_DIR = Path(__file__).resolve().parent
BUILD_SCRIPT = SCRIPT_DIR / "build_native_helpers.sh"
NATIVE_BINARY = BIN_DIR / "hermes-native-meeting"
RECORDING_STATE = RUN_DIR / "meeting-recording.json"
CALENDAR_STATE = RUN_DIR / "calendar-seen.json"
OSASCRIPT = "/usr/bin/osascript"


class MeetingError(RuntimeError):
    pass


def _notify(message: str) -> None:
    source = '''on run argv
display notification (item 1 of argv) with title "Hermes"
end run'''
    try:
        subprocess.run([OSASCRIPT, "-e", source, "--", message], capture_output=True, timeout=8, check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass


CALENDAR_SCRIPT = r'''
on scrub(rawText)
  set cleanText to rawText as text
  set AppleScript's text item delimiters to {tab, return, linefeed}
  set parts to text items of cleanText
  set AppleScript's text item delimiters to " "
  set cleanText to parts as text
  set AppleScript's text item delimiters to ""
  return cleanText
end scrub

on run argv
  set horizonMinutes to (item 1 of argv) as integer
  set nowDate to current date
  set endDate to nowDate + (horizonMinutes * minutes)
  set rows to {}
  tell application "Calendar"
    repeat with cal in calendars
      try
        set matches to (every event of cal whose start date is greater than or equal to nowDate and start date is less than or equal to endDate)
        repeat with ev in matches
          set secondsAway to ((start date of ev) - nowDate) as integer
          set rowText to (my scrub(summary of ev)) & tab & (secondsAway as text) & tab & (my scrub(uid of ev))
          set end of rows to rowText
        end repeat
      end try
    end repeat
  end tell
  set AppleScript's text item delimiters to linefeed
  return rows as text
end run
'''


def _require_macos() -> None:
    if platform.system() != "Darwin":
        raise MeetingError("This command requires macOS.")


def upcoming_events(minutes: int = 30, dry_run: bool = False) -> list[dict[str, Any]]:
    if minutes < 1 or minutes > 1440:
        raise ValueError("Calendar horizon must be between 1 and 1440 minutes.")
    if dry_run:
        return [{"id": "demo-event", "title": "Product Review", "starts_in_minutes": 9.0}]
    _require_macos()
    try:
        result = subprocess.run(
            [OSASCRIPT, "-e", CALENDAR_SCRIPT, "--", str(minutes)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MeetingError(f"Calendar query failed: {exc}") from exc
    if result.returncode:
        raise MeetingError(result.stderr.strip() or "Calendar permission was denied.")
    events: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) != 3:
            continue
        try:
            starts_in = max(0.0, int(fields[1]) / 60)
        except ValueError:
            continue
        events.append({"id": fields[2], "title": fields[0] or "Meeting", "starts_in_minutes": round(starts_in, 1)})
    return sorted(events, key=lambda item: item["starts_in_minutes"])


def calendar_suggestions(minutes: int = 10, dry_run: bool = False) -> list[dict[str, Any]]:
    seen = read_json(CALENDAR_STATE, {"ids": []})
    seen_ids = set(seen.get("ids", [])) if isinstance(seen, dict) else set()
    suggestions: list[dict[str, Any]] = []
    for event in upcoming_events(minutes + 1, dry_run):
        if event["id"] in seen_ids:
            continue
        suggestions.append({
            **event,
            "message": f"{event['title']} starts in {max(1, round(event['starts_in_minutes']))} min. Want me to prepare your Mac?",
            "requires_confirmation": True,
        })
        seen_ids.add(event["id"])
    if suggestions and not dry_run:
        ensure_private_dir(CALENDAR_STATE.parent)
        atomic_write_json(CALENDAR_STATE, {"ids": sorted(seen_ids)[-200:], "updated_at": utc_now()})
        audit("calendar_suggestion", events=[item["id"] for item in suggestions])
    return suggestions


def watch_calendar(interval: int = 60, minutes: int = 10, once: bool = False, dry_run: bool = False) -> None:
    if interval < 15:
        raise ValueError("Polling interval must be at least 15 seconds.")
    while True:
        print(json_result(True, suggestions=calendar_suggestions(minutes, dry_run)), flush=True)
        if once or dry_run:
            return
        time.sleep(interval)


def _build_native_binary() -> None:
    _require_macos()
    source = SCRIPT_DIR / "native_meeting.swift"
    if NATIVE_BINARY.exists() and NATIVE_BINARY.stat().st_mtime >= source.stat().st_mtime:
        return
    ensure_private_dir(BIN_DIR)
    result = subprocess.run([str(BUILD_SCRIPT), str(NATIVE_BINARY)], capture_output=True, text=True, timeout=180, check=False)
    if result.returncode:
        raise MeetingError(result.stderr.strip() or "Native helper build failed. Install Apple Command Line Tools.")


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def recording_status() -> dict[str, Any]:
    state = read_json(RECORDING_STATE, None)
    if not isinstance(state, dict):
        return {"recording": False}
    pid = int(state.get("pid", -1))
    alive = pid > 0 and _process_alive(pid)
    return {"recording": alive, **state}


def start_recording(label: str, confirmed_by_user: bool, dry_run: bool = False) -> dict[str, Any]:
    if not confirmed_by_user:
        raise MeetingError("Recording requires explicit user confirmation in the current conversation.")
    current = recording_status()
    if current.get("recording"):
        raise MeetingError("A recording is already in progress.")
    safe_label = clean_label(label or "meeting")
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    session_dir = RECORDINGS_DIR / f"{stamp}-{safe_label}"
    if dry_run:
        return {"recording": True, "session_dir": str(session_dir), "dry_run": True}
    _build_native_binary()
    ensure_private_dir(session_dir)
    ensure_private_dir(RUN_DIR)
    log_path = session_dir / "capture.log"
    with log_path.open("ab") as log_handle:
        process = subprocess.Popen(
            [str(NATIVE_BINARY), "record", "--output-dir", str(session_dir)],
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    time.sleep(0.7)
    if process.poll() is not None:
        detail = log_path.read_text(errors="replace")[-1000:]
        raise MeetingError(f"Native recording could not start. {detail}".strip())
    state = {"pid": process.pid, "label": safe_label, "session_dir": str(session_dir), "started_at": utc_now()}
    atomic_write_json(RECORDING_STATE, state)
    audit("recording_started", session_dir=str(session_dir), consent="explicit")
    _notify("Recording started. Audio stays on this Mac.")
    return {"recording": True, **state}


def _wait_for_exit(pid: int, timeout: float = 20) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _process_alive(pid):
            return
        time.sleep(0.2)
    os.kill(pid, signal.SIGTERM)
    raise MeetingError("Recorder did not stop cleanly; it was terminated. Audio files may still be recoverable.")


def _transcribe(audio: Path, output: Path, locale: str) -> str:
    result = subprocess.run(
        [str(NATIVE_BINARY), "transcribe", "--input", str(audio), "--output", str(output), "--locale", locale],
        capture_output=True,
        text=True,
        timeout=3600,
        check=False,
    )
    if result.returncode:
        raise MeetingError(result.stderr.strip() or f"On-device transcription failed for {audio.name}.")
    return output.read_text(encoding="utf-8").strip()


def _summary_markdown(label: str, transcript: str, started_at: str) -> str:
    lines = [line.strip() for line in transcript.replace("?", ".").replace("!", ".").split(".") if line.strip()]
    action_words = ("need to", "will ", "should ", "action item", "todo", "follow up")
    decision_words = ("decided", "agreed", "decision", "we'll use", "we will use")
    actions = [line for line in lines if any(word in line.casefold() for word in action_words)][:8]
    decisions = [line for line in lines if any(word in line.casefold() for word in decision_words)][:8]
    overview = ". ".join(lines[:3]) + ("." if lines else "No transcript was available.")

    def bullets(items: list[str], empty: str) -> str:
        return "\n".join(f"- {item}." for item in items) if items else f"- {empty}"

    return f"""# Meeting Memory — {label}

Recorded locally: {started_at}

## Overview

{overview}

## Decisions

{bullets(decisions, 'No explicit decisions detected.')}

## Action items

{bullets(actions, 'No explicit action items detected.')}

## Transcript

{transcript or '[On-device transcription unavailable. Audio remains saved locally.]'}
"""


def stop_recording(locale: str = "en-US", transcribe: bool = True, dry_run: bool = False) -> dict[str, Any]:
    raw_state = read_json(RECORDING_STATE, None)
    if not isinstance(raw_state, dict):
        raise MeetingError("No active recording was found.")
    state = {"recording": _process_alive(int(raw_state.get("pid", -1))), **raw_state}
    session_dir = Path(state["session_dir"])
    if dry_run:
        return {"recording": False, "session_dir": str(session_dir), "dry_run": True}
    pid = int(state["pid"])
    if state["recording"]:
        os.kill(pid, signal.SIGINT)
        _wait_for_exit(pid)
    RECORDING_STATE.unlink(missing_ok=True)
    audio_files = [path for path in (session_dir / "microphone.m4a", session_dir / "system.m4a") if path.exists()]
    transcript_parts: list[str] = []
    errors: list[str] = []
    if transcribe:
        _build_native_binary()
        for audio in audio_files:
            output = session_dir / f"{audio.stem}-transcript.txt"
            try:
                text = _transcribe(audio, output, locale)
                if text:
                    transcript_parts.append(f"[{audio.stem}]\n{text}")
            except MeetingError as exc:
                errors.append(str(exc))
    transcript = "\n\n".join(transcript_parts)
    summary = _summary_markdown(str(state.get("label", "meeting")), transcript, str(state.get("started_at", "")))
    summary_path = session_dir / "summary.md"
    summary_path.write_text(summary, encoding="utf-8")
    os.chmod(summary_path, 0o600)
    audit("recording_stopped", session_dir=str(session_dir), audio=[p.name for p in audio_files], transcription_errors=errors)
    _notify("Recording stopped. Meeting memory was saved locally.")
    return {"recording": False, "session_dir": str(session_dir), "audio": [str(p) for p in audio_files], "summary": str(summary_path), "transcription_errors": errors, "local_only": True}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Native local meeting memory for Prepare My Mac.")
    sub = parser.add_subparsers(dest="command", required=True)
    calendar = sub.add_parser("calendar")
    calendar.add_argument("--minutes", type=int, default=10)
    calendar.add_argument("--dry-run", action="store_true")
    watch = sub.add_parser("watch")
    watch.add_argument("--minutes", type=int, default=10)
    watch.add_argument("--interval", type=int, default=60)
    watch.add_argument("--once", action="store_true")
    watch.add_argument("--dry-run", action="store_true")
    start = sub.add_parser("start")
    start.add_argument("--label", default="meeting")
    start.add_argument("--confirmed-by-user", action="store_true")
    start.add_argument("--dry-run", action="store_true")
    stop = sub.add_parser("stop")
    stop.add_argument("--locale", default="en-US")
    stop.add_argument("--no-transcribe", action="store_true")
    stop.add_argument("--dry-run", action="store_true")
    sub.add_parser("status")
    sub.add_parser("build")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "calendar":
            result = {"events": upcoming_events(args.minutes, args.dry_run)}
        elif args.command == "watch":
            watch_calendar(args.interval, args.minutes, args.once, args.dry_run)
            return 0
        elif args.command == "start":
            result = start_recording(args.label, args.confirmed_by_user, args.dry_run)
        elif args.command == "stop":
            result = stop_recording(args.locale, not args.no_transcribe, args.dry_run)
        elif args.command == "status":
            result = recording_status()
        else:
            _build_native_binary()
            result = {"binary": str(NATIVE_BINARY), "built": True}
        print(json_result(True, **result))
        return 0
    except (MeetingError, ValueError, RuntimeError, OSError) as exc:
        print(json_result(False, error=str(exc)))
        return 2


if __name__ == "__main__":
    sys.exit(main())
