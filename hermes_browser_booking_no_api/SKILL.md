---
name: hermes-browser-booking-no-api
description: Handle manually requested restaurant and coworking reservations using the owner's Mac browser, then synchronize confirmed details to Google Calendar.
---

# Browser booking

Only invoke for a direct user request. For restaurant reservations, use `browser_booking.py` on the Mac with a JSON request after collecting venue, date, exact time and party size. Its supported path is Google Maps/Reserve; prepare with `commit:false`, verify the review, then use `commit:true` for the exact user-authorized booking. `CONFIRMATION_UNKNOWN` requires checking the provider before any retry. Set `HERMES_RESERVATIONS_PATH` inside the owner's private Coffee Work directory. The original installer uses `/opt/data`; use the provided Mac installer instead.

The supplied browser harness does not support coworking providers. For coworking, use the owner's browser with Plow Latch, search availability and complete the specific provider's flow with the user; never claim a booking without its confirmation number or confirmation page. After a confirmed reservation, create a Calendar event through Latch with `mcp__plow__plow_run_command` and `plow-gog calendar create <calendar-id> --summary TITLE --from START --to END`; include the venue, address and reservation reference in the event details when the command supports them, then save its event ID in Coffee Work state. Cancel with the provider first, and only then delete the corresponding Coffee Work-owned Calendar event with `plow-gog calendar delete <calendar-id> EVENT_ID`. Offer an Uber after a confirmed reservation, subject to exact fare approval.
