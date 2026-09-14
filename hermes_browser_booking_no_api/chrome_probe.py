#!/usr/bin/env python3
'''One-time Chrome automation capability probe.'''
import json
import subprocess

script = r'''
tell application "Google Chrome"
    activate
    if not (exists front window) then make new window
    set URL of active tab of front window to "https://www.google.com/"
    delay 2
    return execute active tab of front window javascript "JSON.stringify({title:document.title,url:location.href,ready:document.readyState})"
end tell
'''

p = subprocess.run(
    ["/usr/bin/osascript", "-e", script],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    check=False,
    shell=False,
)
if p.returncode != 0:
    print(json.dumps({
        "ok": False,
        "error": (p.stderr or p.stdout).strip(),
        "help": [
            "Allow the agent/Terminal to control Google Chrome in macOS System Settings > Privacy & Security > Automation.",
            "In Chrome, enable View > Developer > Allow JavaScript from Apple Events.",
            "Run this probe again."
        ]
    }, ensure_ascii=False, indent=2))
    raise SystemExit(2)

try:
    data = json.loads(p.stdout.strip())
except Exception:
    data = {"raw": p.stdout.strip()}
print(json.dumps(
    {"ok": True, "chrome": data},
    ensure_ascii=False,
    indent=2
))
