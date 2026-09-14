# Local configuration contract

The source of truth is:

```text
~/Library/Application Support/Hermes/PrepareMyMac/context.json
```

The resolver creates it atomically with mode `0600`. Do not edit it directly while a resolver command is running.

## Mode schema

```json
{
  "schema_version": 2,
  "modes": {
    "demo": {
      "apps": ["Keynote", "Google Chrome", "Notes"],
      "urls": ["https://example.com/demo"],
      "hide_apps": ["Messages", "Mail", "Slack"],
      "layout": "presentable"
    }
  },
  "protected_apps": ["Finder", "Hermes"],
  "usage": {},
  "last_mode": null
}
```

Rules:

- `apps`: visible macOS application names accepted by `/usr/bin/open -a`.
- `urls`: only `https`, `http`, and `file` URLs.
- `hide_apps`: application names to hide, never quit.
- `layout`: `presentable`, `split`, `top`, `corner`, `grid`, or `none`.
- `protected_apps`: never hide these apps during activation.
- built-in modes remain available until a same-name custom mode overrides them.

## Storage

| Data | Local path |
| --- | --- |
| Preferences | `~/Library/Application Support/Hermes/PrepareMyMac/context.json` |
| Context Capsules | `~/Library/Application Support/Hermes/PrepareMyMac/capsules/` |
| Audit log | `~/Library/Application Support/Hermes/PrepareMyMac/audit.ndjson` |
| Runtime state | `~/Library/Application Support/Hermes/PrepareMyMac/run/` |
| Recordings and summaries | `~/Documents/HermesRecordings/` |

All data stays local. There are no OAuth tokens, API keys, cloud folder IDs, or network fallback paths.
