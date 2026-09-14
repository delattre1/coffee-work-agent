---
name: ld-mac-prepare-native
description: Prepare the owner's Mac for a meeting, record with explicit consent, transcribe on device, summarize with AI and upload the meeting notes to Drive.
---

# Mac preparation and meeting notes

Run these scripts on the owner's Mac through Plow Latch, never in the Linux container. `scripts/mac_executor.py activate meeting --intent TITLE` saves a context capsule, opens configured apps and arranges windows. The calendar orchestrator separately opens a validated HTTPS Zoom, Meet or Teams link. Customize the meeting mode with `scripts/context_resolver.py patch meeting --add-app 'App Name' --add-url https://...` only when the owner asks. Summarize partial failures as partial failures.

Recording is **never** automatic. For each meeting, ask if the owner wants recording and transcription. Only after an explicit yes call `python3 -m coffee_work.cli record start --label TITLE --confirmed-by-user` on the Mac. At meeting end call `python3 -m coffee_work.cli record stop`; the native helper captures system and microphone audio, transcribes locally, and Coffee Work creates an AI summary and uploads transcripts and summary to the central Google Drive folder. Audio stays local unless the owner explicitly asks for `--upload-audio`. If AI or Drive fails, report the local session directory and retry with `~/.coffee-work/bin/coffee-work publish-recording --session PATH`; never claim upload succeeded without Drive IDs. Respect other attendees' recording permissions.
