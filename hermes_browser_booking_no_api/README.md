# Hermes Browser Booking — no booking API

This version books through the browser instead of a restaurant booking API.

It is designed for the flow shown in the screenshots:

1. Google Maps restaurant page.
2. Click **Reserve a table / Reservar uma mesa**.
3. Google Reserve page opens.
4. Select party size.
5. Select date.
6. Select exact time.
7. Continue.
8. Validate the review panel.
9. Click the final **Reserve** button.
10. Store `CONFIRMED` only after positive confirmation evidence appears.

## Stack

- macOS
- Google Chrome
- `/usr/bin/osascript`
- Python 3 Standard Library
- No Selenium
- No Playwright
- No pip/npm
- No Google booking API

The harness uses Chrome's built-in AppleScript support to execute small DOM queries/clicks in the active tab.

## Safety behavior

Browser automation can break when Google or a provider changes the UI. The harness fails closed:

- no blind second click on the final Reserve button
- no CAPTCHA bypass
- no guessed party/date/time
- no success without confirmation evidence
- no shell interpolation
- no `shell=True`
- UI mismatch stops the transaction
- timeout after final click becomes `CONFIRMATION_UNKNOWN`

## One-time Chrome setup

Run:

```sh
/usr/bin/python3 chrome_probe.py
```

If blocked:

1. In macOS **System Settings > Privacy & Security > Automation**, allow the process running Hermes/Terminal to control Google Chrome.
2. In Chrome, enable **View > Developer > Allow JavaScript from Apple Events**.
3. Keep a dedicated Chrome profile logged into the Google account whose contact details should be used for reservations.
4. Run the probe again.

Do not put Google passwords in Hermes. Login remains inside Chrome.

## Dry run

```json
{
  "start_url": "https://www.google.com/maps/...",
  "date": "2026-09-06",
  "time": "18:30",
  "party_size": 2,
  "commit": false
}
```

This fills the flow and validates the final review without submitting.

## Real booking

```json
{
  "start_url": "https://www.google.com/maps/...",
  "date": "2026-09-06",
  "time": "18:30",
  "party_size": 2,
  "commit": true
}
```

Use `commit=true` only when the user's request clearly identifies the exact restaurant/unit, date, time and party size.

## Outcomes

- `READY_TO_CONFIRM`: review matches, final button not clicked.
- `CONFIRMED`: final click occurred and confirmation evidence appeared.
- `NO_AVAILABILITY`: exact slot not visible; nearby times may be returned.
- `AMBIGUOUS_UI`: DOM did not match the safe flow.
- `AUTH_REQUIRED`: user must finish account/login selection in Chrome.
- `CAPTCHA_REQUIRED`: human verification required; no bypass attempted.
- `CONFIRMATION_UNKNOWN`: final click occurred but confirmation could not be proven. Never retry automatically.

## Persistence

Confirmed reservations are appended to:

`/opt/data/ld/restaurant_reservations.json`

using `fcntl.flock` and atomic replace.

## Why DOM instead of screen coordinates

Hard-coded coordinates break with window size, browser zoom, banners, localization and layout changes.

The harness searches semantic text/roles and supports English, Portuguese and Spanish variants for the core flow.

If Google moves key controls into a cross-origin iframe that Chrome JavaScript cannot access, the harness stops instead of guessing coordinates.

## Install

```sh
chmod +x install_native.sh
./install_native.sh
```

No third-party packages are installed.
