#!/usr/bin/env python3
"""Fast, conservative macOS context transitions and Context Capsules."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from context_resolver import ContextResolver, LAYOUTS
from hermes_common import CAPSULES_DIR, atomic_write_json, audit, clean_label, json_result, read_json, utc_now

OSASCRIPT = "/usr/bin/osascript"
OPEN = "/usr/bin/open"


class NativeError(RuntimeError):
    pass


def _require_macos(dry_run: bool = False) -> None:
    if not dry_run and platform.system() != "Darwin":
        raise NativeError("This command requires macOS. Use --dry-run for validation elsewhere.")


def _run(command: list[str], *, timeout: float = 12, dry_run: bool = False) -> str:
    if dry_run:
        return ""
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise NativeError(f"Native command failed: {exc}") from exc
    if result.returncode:
        detail = result.stderr.strip() or f"exit {result.returncode}"
        raise NativeError(detail)
    return result.stdout.strip()


def _applescript(source: str, *args: str, dry_run: bool = False) -> str:
    return _run([OSASCRIPT, "-e", source, "--", *args], dry_run=dry_run)


def _jxa(source: str, dry_run: bool = False) -> Any:
    output = _run([OSASCRIPT, "-l", "JavaScript", "-e", source], dry_run=dry_run)
    if dry_run or not output:
        return []
    try:
        return json.loads(output)
    except json.JSONDecodeError as exc:
        raise NativeError("macOS returned malformed window data.") from exc


def check_prerequisites(dry_run: bool = False) -> dict[str, Any]:
    _require_macos(dry_run)
    checks = {"macos": platform.system() == "Darwin" or dry_run, "automation": False, "accessibility": False}
    if dry_run:
        checks.update({"automation": True, "accessibility": True})
    else:
        try:
            _applescript('tell application "System Events" to get name of first application process')
            checks.update({"automation": True, "accessibility": True})
        except NativeError:
            pass
    checks["ok"] = all(checks.values())
    checks["help"] = (
        "Enable Automation and Accessibility for the Hermes host in "
        "System Settings > Privacy & Security."
        if not checks["ok"] else None
    )
    return checks


WINDOW_SNAPSHOT_JXA = r'''
const se = Application("System Events");
const result = {frontmost_app: null, apps: [], windows: []};
const processes = se.applicationProcesses.whose({backgroundOnly: false})();
for (const p of processes) {
  let name = "";
  try { name = p.name(); } catch (_) { continue; }
  result.apps.push(name);
  try { if (p.frontmost()) result.frontmost_app = name; } catch (_) {}
  try {
    const windows = p.windows();
    for (let i = 0; i < windows.length; i++) {
      const w = windows[i];
      const pos = w.position(); const size = w.size();
      result.windows.push({app:name, index:i + 1, title:String(w.name() || ""), bounds:[pos[0],pos[1],size[0],size[1]]});
    }
  } catch (_) {}
}
JSON.stringify(result);
'''

SCREENS_JXA = r'''
ObjC.import("AppKit");
const raw = $.NSScreen.screens.js;
let maxY = 0;
for (const screen of raw) { const f = screen.visibleFrame; maxY = Math.max(maxY, f.origin.y + f.size.height); }
const result = raw.map((screen, index) => {
  const f = screen.visibleFrame;
  return {index:index, x:Math.round(f.origin.x), y:Math.round(maxY-(f.origin.y+f.size.height)), width:Math.round(f.size.width), height:Math.round(f.size.height)};
});
JSON.stringify(result);
'''

CHROME_TABS_JXA = r'''
const se = Application("System Events");
const running = se.applicationProcesses.name().includes("Google Chrome");
const result = [];
if (running) {
  const chrome = Application("Google Chrome");
  const windows = chrome.windows();
  for (let wi = 0; wi < windows.length; wi++) {
    const tabs = windows[wi].tabs();
    for (let ti = 0; ti < tabs.length; ti++) {
      try { result.push({window:wi + 1, tab:ti + 1, title:String(tabs[ti].title()), url:String(tabs[ti].url())}); } catch (_) {}
    }
  }
}
JSON.stringify(result);
'''


def capture_capsule(intent: str = "", label: str = "", dry_run: bool = False) -> dict[str, Any]:
    _require_macos(dry_run)
    if dry_run:
        state: dict[str, Any] = {"frontmost_app": "Demo App", "apps": ["Demo App"], "windows": []}
        screens = [{"index": 0, "x": 0, "y": 0, "width": 1440, "height": 900}]
        tabs: list[dict[str, Any]] = []
    else:
        state = _jxa(WINDOW_SNAPSHOT_JXA)
        screens = _jxa(SCREENS_JXA)
        try:
            tabs = _jxa(CHROME_TABS_JXA)
        except NativeError:
            tabs = []
    timestamp = utc_now()
    capsule = {
        "schema_version": 1,
        "created_at": timestamp,
        "intent": intent.strip(),
        "frontmost_app": state.get("frontmost_app"),
        "apps": state.get("apps", []),
        "windows": state.get("windows", []),
        "chrome_tabs": tabs,
        "screens": screens,
    }
    filename = f"{timestamp.replace(':', '').replace('-', '')[:15]}-{clean_label(label or intent, 'context')}.json"
    path = CAPSULES_DIR / filename
    if not dry_run:
        atomic_write_json(path, capsule)
        audit("capsule_created", path=str(path), intent=capsule["intent"], app_count=len(capsule["apps"]))
    return {"capsule": capsule, "path": str(path), "dry_run": dry_run}


def _hide_app(app: str, dry_run: bool = False) -> None:
    source = '''on run argv
set appName to item 1 of argv
tell application "System Events"
  if exists application process appName then set visible of application process appName to false
end tell
end run'''
    _applescript(source, app, dry_run=dry_run)


def _notify(title: str, message: str, dry_run: bool = False) -> None:
    source = '''on run argv
display notification (item 2 of argv) with title (item 1 of argv)
end run'''
    _applescript(source, title, message, dry_run=dry_run)


def _launch_app(app: str, dry_run: bool = False) -> None:
    _run([OPEN, "-a", app], dry_run=dry_run)


def _open_url(url: str, dry_run: bool = False) -> None:
    _run([OPEN, "-a", "Google Chrome", url], dry_run=dry_run)


def _set_window(app: str, index: int, bounds: list[int], dry_run: bool = False) -> None:
    source = '''on run argv
set appName to item 1 of argv
set windowIndex to (item 2 of argv) as integer
set px to (item 3 of argv) as integer
set py to (item 4 of argv) as integer
set pw to (item 5 of argv) as integer
set ph to (item 6 of argv) as integer
tell application "System Events"
  tell application process appName
    if (count of windows) >= windowIndex then
      set position of window windowIndex to {px, py}
      set size of window windowIndex to {pw, ph}
    end if
  end tell
end tell
end run'''
    _applescript(source, app, str(index), *(str(v) for v in bounds), dry_run=dry_run)


def _layout_bounds(preset: str, screen: dict[str, int], count: int) -> list[list[int]]:
    x, y, width, height = screen["x"], screen["y"], screen["width"], screen["height"]
    gap = 8
    if count <= 0:
        return []
    if preset == "corner":
        cell_height = max(220, (height // 2) // count)
        return [
            [x + width // 2, y + i * cell_height, width // 2 - gap, cell_height - gap]
            for i in range(count)
        ]
    if preset == "top":
        cell_width = width // count
        return [
            [x + i * cell_width, y, cell_width - gap, max(300, int(height * 0.62))]
            for i in range(count)
        ]
    if preset == "split":
        left = [x, y, width // 2 - gap, height]
        right = [x + width // 2 + gap, y, width // 2 - gap, height]
        if count <= 2:
            return [left, right][:count]
        return _layout_bounds("grid", screen, count)
    if preset == "grid":
        cells = [
            [x, y, width // 2 - gap, height // 2 - gap],
            [x + width // 2 + gap, y, width // 2 - gap, height // 2 - gap],
            [x, y + height // 2 + gap, width // 2 - gap, height // 2 - gap],
            [x + width // 2 + gap, y + height // 2 + gap, width // 2 - gap, height // 2 - gap],
        ]
        return [cells[i % 4] for i in range(count)]
    # presentable: hero window + a clean support column.
    hero_width = int(width * 0.68)
    return [[x, y, hero_width - gap, height]] + [
        [x + hero_width + gap, y + (i - 1) * (height // max(1, count - 1)), width - hero_width - gap, height // max(1, count - 1) - gap]
        for i in range(1, count)
    ]


def apply_layout(apps: list[str], preset: str, dry_run: bool = False) -> dict[str, Any]:
    if preset not in LAYOUTS:
        raise ValueError(f"Unknown layout: {preset}")
    if preset == "none" or not apps:
        return {"preset": preset, "placed": []}
    screens = ([{"index": 0, "x": 0, "y": 0, "width": 1440, "height": 900}] if dry_run else _jxa(SCREENS_JXA))
    if not screens:
        raise NativeError("No display was detected.")
    placed: list[dict[str, Any]] = []
    if preset == "presentable" and len(screens) > 1:
        # Main content fills display 1; supporting apps form a grid on display 2.
        primary, secondary = screens[0], screens[1]
        assignments = [(apps[0], [primary["x"], primary["y"], primary["width"], primary["height"]])]
        support_bounds = _layout_bounds("grid", secondary, len(apps) - 1)
        assignments += list(zip(apps[1:], support_bounds))
    else:
        assignments = list(zip(apps, _layout_bounds(preset, screens[0], len(apps))))
    for app, bounds in assignments:
        try:
            _set_window(app, 1, bounds, dry_run)
            placed.append({"app": app, "bounds": bounds})
        except NativeError as exc:
            placed.append({"app": app, "error": str(exc)})
    audit("layout_applied", preset=preset, displays=len(screens), apps=apps) if not dry_run else None
    return {"preset": preset, "displays": len(screens), "placed": placed}


def activate_mode(mode_name: str, intent: str = "", capsule: bool = True, dry_run: bool = False) -> dict[str, Any]:
    _require_macos(dry_run)
    checks = check_prerequisites(dry_run)
    if not checks["ok"]:
        raise NativeError(checks["help"] or "macOS permissions are incomplete.")
    resolver = ContextResolver()
    mode = resolver.resolve_mode(mode_name)
    previous = capture_capsule(intent, f"before-{mode_name}", dry_run) if capsule else None
    protected = {name.casefold() for name in resolver.state.get("protected_apps", [])}
    hidden: list[str] = []
    for app in mode["hide_apps"]:
        if app.casefold() in protected or app.casefold() in {a.casefold() for a in mode["apps"]}:
            continue
        try:
            _hide_app(app, dry_run)
            hidden.append(app)
        except NativeError:
            continue
    opened: list[str] = []
    failures: list[dict[str, str]] = []
    for app in mode["apps"]:
        try:
            _launch_app(app, dry_run)
            opened.append(app)
        except NativeError as exc:
            failures.append({"app": app, "error": str(exc)})
    for url in mode["urls"]:
        try:
            _open_url(url, dry_run)
        except NativeError as exc:
            failures.append({"url": url, "error": str(exc)})
    if not dry_run:
        time.sleep(0.8)
    layout = apply_layout(opened, mode["layout"], dry_run)
    if not dry_run:
        resolver.mark_activated(mode_name)
        audit("mode_activated", mode=mode_name, opened=opened, hidden=hidden, failures=failures)
        try:
            _notify("Hermes", f"{mode_name.title()} is ready. Your previous workspace is saved.")
        except NativeError:
            pass
    return {"mode": mode_name, "opened": opened, "urls": mode["urls"], "hidden": hidden, "layout": layout, "capsule_path": previous["path"] if previous else None, "failures": failures, "dry_run": dry_run}


def resume_capsule(path: Path, hide_current: bool = False, dry_run: bool = False) -> dict[str, Any]:
    _require_macos(dry_run)
    capsule = read_json(path, None)
    if not isinstance(capsule, dict) or capsule.get("schema_version") != 1:
        raise ValueError("Invalid Context Capsule.")
    restored_apps: list[str] = []
    for app in capsule.get("apps", []):
        try:
            _launch_app(app, dry_run)
            restored_apps.append(app)
        except NativeError:
            continue
    for tab in capsule.get("chrome_tabs", []):
        url = str(tab.get("url", ""))
        if url.startswith(("https://", "http://", "file://")):
            _open_url(url, dry_run)
    if not dry_run:
        time.sleep(0.8)
    for window in capsule.get("windows", []):
        try:
            bounds = [int(value) for value in window["bounds"]]
            _set_window(str(window["app"]), int(window.get("index", 1)), bounds, dry_run)
        except (KeyError, ValueError, TypeError, NativeError):
            continue
    if hide_current:
        previous = {str(app).casefold() for app in capsule.get("apps", [])}
        current = [] if dry_run else _jxa(WINDOW_SNAPSHOT_JXA).get("apps", [])
        for app in current:
            if app.casefold() not in previous and app not in {"Finder", "Hermes"}:
                try:
                    _hide_app(app, dry_run)
                except NativeError:
                    pass
    if not dry_run:
        audit("capsule_resumed", path=str(path), intent=capsule.get("intent", ""))
        try:
            detail = str(capsule.get("intent", "")).strip()
            _notify("Hermes", f"Back to your previous context. {detail}".strip())
        except NativeError:
            pass
    return {"restored_apps": restored_apps, "intent": capsule.get("intent", ""), "frontmost_app": capsule.get("frontmost_app"), "dry_run": dry_run}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare and restore native macOS contexts.")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--dry-run", action="store_true")
    snapshot = sub.add_parser("snapshot")
    snapshot.add_argument("--intent", default="")
    snapshot.add_argument("--label", default="")
    snapshot.add_argument("--dry-run", action="store_true")
    activate = sub.add_parser("activate")
    activate.add_argument("mode")
    activate.add_argument("--intent", default="")
    activate.add_argument("--no-capsule", action="store_true")
    activate.add_argument("--dry-run", action="store_true")
    layout = sub.add_parser("layout")
    layout.add_argument("preset", choices=sorted(LAYOUTS - {"none"}))
    layout.add_argument("--app", action="append", required=True)
    layout.add_argument("--dry-run", action="store_true")
    resume = sub.add_parser("resume")
    resume.add_argument("capsule", type=Path)
    resume.add_argument("--hide-current", action="store_true")
    resume.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "check":
            result = check_prerequisites(args.dry_run)
        elif args.command == "snapshot":
            result = capture_capsule(args.intent, args.label, args.dry_run)
        elif args.command == "activate":
            result = activate_mode(args.mode, args.intent, not args.no_capsule, args.dry_run)
        elif args.command == "layout":
            result = apply_layout(args.app, args.preset, args.dry_run)
        else:
            result = resume_capsule(args.capsule, args.hide_current, args.dry_run)
        print(json_result(bool(result.pop("ok", True)), **result))
        return 0
    except (NativeError, ValueError, RuntimeError, OSError) as exc:
        print(json_result(False, error=str(exc)))
        return 2


if __name__ == "__main__":
    sys.exit(main())
