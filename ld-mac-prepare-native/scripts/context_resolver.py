#!/usr/bin/env python3
"""Resolve and persist Prepare My Mac modes using only the Python stdlib."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from hermes_common import CONTEXT_FILE, atomic_write_json, audit, json_result, read_json

LAYOUTS = {"presentable", "split", "top", "corner", "grid", "none"}

BUILTIN_MODES: dict[str, dict[str, Any]] = {
    "coding": {
        "apps": ["Visual Studio Code", "Terminal"],
        "urls": ["https://github.com"],
        "hide_apps": ["Messages", "Mail"],
        "layout": "split",
    },
    "focus": {
        "apps": ["Visual Studio Code"],
        "urls": [],
        "hide_apps": ["Messages", "Mail", "Slack"],
        "layout": "presentable",
    },
    "meeting": {
        "apps": ["Calendar", "Notes"],
        "urls": [],
        "hide_apps": ["Messages", "Mail"],
        "layout": "presentable",
    },
    "presentation": {
        "apps": ["Keynote", "Finder"],
        "urls": [],
        "hide_apps": ["Messages", "Mail", "Slack"],
        "layout": "presentable",
    },
    "study": {
        "apps": ["Safari", "Notes"],
        "urls": [],
        "hide_apps": ["Messages", "Mail"],
        "layout": "split",
    },
}

DEFAULT_STATE: dict[str, Any] = {
    "schema_version": 2,
    "modes": {},
    "protected_apps": ["Finder", "Hermes"],
    "usage": {},
    "last_mode": None,
}


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = value.strip()
        key = item.casefold()
        if item and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _mode_name(value: str) -> str:
    value = value.strip().lower().replace(" ", "-")
    if not value or len(value) > 48 or not all(c.isalnum() or c == "-" for c in value):
        raise ValueError("Mode names may contain lowercase letters, numbers, and hyphens only.")
    return value


def _apps(values: list[str]) -> list[str]:
    result = _unique(values)
    if any(len(item) > 120 or any(ord(c) < 32 for c in item) for item in result):
        raise ValueError("An application name is invalid.")
    return result


def _urls(values: list[str]) -> list[str]:
    result = _unique(values)
    for value in result:
        parsed = urlparse(value)
        if parsed.scheme not in {"https", "http", "file"}:
            raise ValueError(f"Unsupported URL scheme: {value}")
    return result


class ContextResolver:
    def __init__(self, context_file: Path = CONTEXT_FILE) -> None:
        self.context_file = Path(context_file)
        loaded = read_json(self.context_file, copy.deepcopy(DEFAULT_STATE))
        if not isinstance(loaded, dict):
            raise RuntimeError("Context root must be a JSON object.")
        self.state = copy.deepcopy(DEFAULT_STATE)
        self.state.update(loaded)
        if self.state.get("schema_version") != 2:
            self.state = self._migrate(self.state)
        self.state.setdefault("modes", {})
        self.state.setdefault("usage", {})

    @staticmethod
    def _migrate(old: dict[str, Any]) -> dict[str, Any]:
        migrated = copy.deepcopy(DEFAULT_STATE)
        migrated["modes"] = old.get("modes", {}) if isinstance(old.get("modes"), dict) else {}
        migrated["usage"] = old.get("usage_frequency", old.get("usage", {}))
        if isinstance(old.get("block_list"), list):
            migrated["global_hide_apps"] = _apps(old["block_list"])
        return migrated

    def save(self) -> None:
        atomic_write_json(self.context_file, self.state)

    def resolve_mode(self, name: str) -> dict[str, Any]:
        name = _mode_name(name)
        base = copy.deepcopy(BUILTIN_MODES.get(name, {"apps": [], "urls": [], "hide_apps": [], "layout": "none"}))
        override = self.state["modes"].get(name, {})
        if not isinstance(override, dict):
            raise RuntimeError(f"Mode '{name}' is not a JSON object.")
        base.update(copy.deepcopy(override))
        base["apps"] = _apps(base.get("apps", []))
        base["urls"] = _urls(base.get("urls", []))
        base["hide_apps"] = _apps(self.state.get("global_hide_apps", []) + base.get("hide_apps", []))
        base["layout"] = base.get("layout", "none")
        if base["layout"] not in LAYOUTS:
            raise RuntimeError(f"Mode '{name}' has an invalid layout.")
        return {"name": name, **base}

    def list_modes(self) -> dict[str, dict[str, Any]]:
        names = sorted(set(BUILTIN_MODES) | set(self.state["modes"]))
        return {name: self.resolve_mode(name) for name in names}

    def set_mode(
        self,
        name: str,
        apps: list[str],
        urls: list[str],
        hide_apps: list[str],
        layout: str,
    ) -> dict[str, Any]:
        name = _mode_name(name)
        if layout not in LAYOUTS:
            raise ValueError(f"Layout must be one of: {', '.join(sorted(LAYOUTS))}.")
        self.state["modes"][name] = {
            "apps": _apps(apps),
            "urls": _urls(urls),
            "hide_apps": _apps(hide_apps),
            "layout": layout,
        }
        self.save()
        audit("mode_saved", mode=name)
        return self.resolve_mode(name)

    def patch_mode(
        self,
        name: str,
        add_apps: list[str],
        remove_apps: list[str],
        add_urls: list[str],
        remove_urls: list[str],
        add_hidden: list[str],
        remove_hidden: list[str],
        layout: str | None,
    ) -> dict[str, Any]:
        current = self.resolve_mode(name)

        def changed(existing: list[str], added: list[str], removed: list[str]) -> list[str]:
            remove_keys = {v.casefold() for v in removed}
            return _unique([v for v in existing if v.casefold() not in remove_keys] + added)

        return self.set_mode(
            name,
            changed(current["apps"], _apps(add_apps), _apps(remove_apps)),
            changed(current["urls"], _urls(add_urls), _urls(remove_urls)),
            changed(current["hide_apps"], _apps(add_hidden), _apps(remove_hidden)),
            layout or current["layout"],
        )

    def remove_mode(self, name: str) -> bool:
        name = _mode_name(name)
        removed = self.state["modes"].pop(name, None) is not None
        if removed:
            self.save()
            audit("mode_removed", mode=name)
        return removed

    def mark_activated(self, name: str) -> None:
        name = _mode_name(name)
        entry = self.state["usage"].setdefault(name, {"activations": 0})
        entry["activations"] = int(entry.get("activations", 0)) + 1
        self.state["last_mode"] = name
        self.save()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local Prepare My Mac contexts.")
    parser.add_argument("--context-file", type=Path, default=CONTEXT_FILE)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    show = sub.add_parser("show")
    show.add_argument("mode")
    set_cmd = sub.add_parser("set")
    set_cmd.add_argument("mode")
    for flag in ("app", "url", "hide-app"):
        set_cmd.add_argument(f"--{flag}", action="append", default=[])
    set_cmd.add_argument("--layout", choices=sorted(LAYOUTS), default="none")
    patch = sub.add_parser("patch")
    patch.add_argument("mode")
    for flag in ("add-app", "remove-app", "add-url", "remove-url", "add-hidden", "remove-hidden"):
        patch.add_argument(f"--{flag}", action="append", default=[])
    patch.add_argument("--layout", choices=sorted(LAYOUTS))
    remove = sub.add_parser("remove")
    remove.add_argument("mode")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        resolver = ContextResolver(args.context_file)
        if args.command == "list":
            data = {"modes": resolver.list_modes(), "last_mode": resolver.state["last_mode"]}
        elif args.command == "show":
            data = {"mode": resolver.resolve_mode(args.mode)}
        elif args.command == "set":
            data = {"mode": resolver.set_mode(args.mode, args.app, args.url, args.hide_app, args.layout)}
        elif args.command == "patch":
            data = {"mode": resolver.patch_mode(args.mode, args.add_app, args.remove_app, args.add_url, args.remove_url, args.add_hidden, args.remove_hidden, args.layout)}
        else:
            data = {"removed": resolver.remove_mode(args.mode), "mode": args.mode}
        print(json_result(True, **data))
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(json_result(False, error=str(exc)))
        return 2


if __name__ == "__main__":
    sys.exit(main())
